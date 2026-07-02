# BaZi LLM 流式输出实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task inline in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为八字 `/bazi` 增加 SSE 流式输出接口 `/bazi/stream`，前端切换为流式渲染，同时保留每日 50 元成本上限、事件记录和中文 429 提示。

**Architecture:** 后端复用现有 `OpenAIProvider.stream()`，新增 `stream_with_guard()` 统一处理预算检查、事件记录和 SSE 封装；`/bazi/stream` 返回 `text/event-stream`；前端用 `fetch` + `ReadableStream` 解析 SSE 数据块并追加渲染。

**Tech Stack:** FastAPI, LangChain ChatOpenAI, Server-Sent Events, vanilla JS, Nginx.

## Global Constraints

- 只给八字 `/bazi` 做流式；手相 `/palmistry` 保持同步不变。
- 旧 `/api/v1/bazi` 同步接口保留作为兼容入口。
- 每日 LLM 花费上限 50 元，流式前后都要 enforce。
- `analytics_events` 必须继续记录 `bazi_request` 和 `bazi_report`（含 cost）。
- 预算耗尽时返回 HTTP 429，前端显示中文“今天的服务已经结束啦，请明天再来”。
- Nginx 必须关闭 buffering 以保证 SSE 实时到达前端。
- 所有 DB 操作 async，依赖 `get_db_optional`。

---

### Task 1: OpenAIProvider 流式 usage 兜底与耗时日志

**Files:**
- Modify: `backend/app/services/providers/openai_provider.py:81-95`

**Interfaces:**
- Consumes: `ChatOpenAI.astream(...)`
- Produces: `OpenAIProvider.stream()` yields `str`, sets `self._last_usage` after stream.

- [ ] **Step 1: 修改 `stream()`，流结束后没有 usage 时按累计文本长度估算 output tokens**

```python
async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[str]:
    lc_messages = self._to_lc_messages(messages)
    self._last_usage = None
    total_input = 0
    total_output = 0
    accumulated_text = ""
    async for chunk in self._client.astream(lc_messages, **kwargs):
        if chunk.content:
            accumulated_text += chunk.content
            yield chunk.content
        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            um = chunk.usage_metadata
            total_input = um.get("input_tokens") or total_input
            total_output = um.get("output_tokens") or total_output
    if total_input or total_output:
        self._last_usage = {"input_tokens": total_input, "output_tokens": total_output}
    elif accumulated_text:
        self._last_usage = {
            "input_tokens": 0,
            "output_tokens": self._estimate_text_tokens(accumulated_text),
        }
```

- [ ] **Step 2: 运行 Python 语法检查**

```bash
cd backend
python -m py_compile app/services/providers/openai_provider.py
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/providers/openai_provider.py
git commit -m "feat: streaming usage fallback in OpenAIProvider

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 新增 stream_with_guard 统一流式调用封装

**Files:**
- Modify: `backend/app/services/llm_guard.py`

**Interfaces:**
- Consumes: `client.stream(messages)`, `cost_tracker`, `record_event`
- Produces: `async def stream_with_guard(...) -> AsyncIterator[str]` which yields SSE data lines and sends final metadata.

- [ ] **Step 1: 在 `llm_guard.py` 里新增 `stream_with_guard()` 和 `format_sse()` 辅助函数**

```python
import json


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_with_guard(
    request: Request,
    db: Optional[AsyncSession],
    region: str,
    client,
    messages: list[dict],
    request_event_type: str,
    report_event_type: str,
):
    """统一封装 LLM 流式调用：记录请求、检查预算、流式生成、记录报告与成本。

    产生 SSE 数据行（包括 chunk / done / error）。
    """
    if db is None:
        logger.error("LLM stream attempted while analytics database is unavailable")
        yield _format_sse({"type": "error", "message": "Cost tracking database is not available; LLM calls are disabled."})
        return

    await record_event(db, request_event_type, request, region)

    try:
        await cost_tracker.check_budget(db, messages)
    except HTTPException as exc:
        if exc.status_code == 429:
            yield _format_sse({"type": "error", "message": "今天的服务已经结束啦，请明天再来"})
        else:
            yield _format_sse({"type": "error", "message": str(exc.detail)})
        return

    llm_start = time.monotonic()
    first_chunk_time: Optional[float] = None
    accumulated_text = ""
    chunk_count = 0

    try:
        async for delta in client.stream(messages):
            if first_chunk_time is None:
                first_chunk_time = time.monotonic() - llm_start
            if delta:
                accumulated_text += delta
                chunk_count += 1
                yield _format_sse({"type": "chunk", "delta": delta})
    except Exception as e:
        logger.exception("LLM stream failed")
        yield _format_sse({"type": "error", "message": "Analysis failed. Please try again later."})
        return

    stream_duration = time.monotonic() - llm_start
    logger.info(
        "LLM stream finished in %.2fs (first_chunk=%.2fs, chunks=%d, provider=%s, model=%s)",
        stream_duration,
        first_chunk_time or 0.0,
        chunk_count,
        settings.llm_provider,
        getattr(client, "model", "unknown"),
    )

    usage = client.last_usage or {}
    if usage.get("input_tokens") is None:
        usage["input_tokens"] = cost_tracker.estimate_input_tokens(messages)
    if usage.get("output_tokens") is None and accumulated_text:
        usage["output_tokens"] = cost_tracker.estimate_text_tokens(accumulated_text)

    cost = cost_tracker.compute_cost(usage)
    await record_event(
        db,
        report_event_type,
        request,
        region,
        tokens_input=usage.get("input_tokens"),
        tokens_output=usage.get("output_tokens"),
        cost_cny=cost,
    )

    yield _format_sse({
        "type": "done",
        "metadata": {**client.metadata, "cost_cny": float(cost)},
    })
```

- [ ] **Step 2: 运行语法检查**

```bash
cd backend
python -m py_compile app/services/llm_guard.py
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/llm_guard.py
git commit -m "feat: add stream_with_guard helper for SSE

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 新增 `/bazi/stream` SSE 端点

**Files:**
- Modify: `backend/app/routers/bazi.py`

**Interfaces:**
- Consumes: `stream_with_guard(...)` generator
- Produces: `POST /api/v1/bazi/stream` returns `StreamingResponse(media_type="text/event-stream")`.

- [ ] **Step 1: 在 `bazi.py` 里新增 `/bazi/stream` 路由**

```python
from fastapi.responses import StreamingResponse


@router.post("/bazi/stream")
async def analyze_bazi_stream(
    request: Request,
    bazi_request: BaziRequest,
    x_region: Optional[str] = Header(default=None),
    db: Optional = Depends(get_db_optional),
):
    region = _region(x_region)
    client = create_llm_client(settings)
    prompt = prompt_manager.get_bazi_prompt()

    messages = prompt.format_messages(
        birth_date=bazi_request.birth_date,
        birth_time=bazi_request.birth_time,
        gender=bazi_request.gender,
        birthplace=bazi_request.birthplace,
    )

    normalized = [{"role": "system", "content": messages[0].content}]
    for msg in messages[1:]:
        role = "human" if msg.type == "human" else "ai"
        normalized.append({"role": role, "content": msg.content})

    async def event_generator():
        async for sse_line in stream_with_guard(
            request=request,
            db=db,
            region=region,
            client=client,
            messages=normalized,
            request_event_type=EVENT_BAZI_REQUEST,
            report_event_type=EVENT_BAZI_REPORT,
        ):
            yield sse_line

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 2: 运行语法检查**

```bash
cd backend
python -m py_compile app/routers/bazi.py
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/bazi.py
git commit -m "feat: add SSE streaming endpoint /bazi/stream

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 前端切换为流式请求与渲染

**Files:**
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html` (if needed for rendering hook)

**Interfaces:**
- Consumes: `/api/v1/bazi/stream` SSE
- Produces: `streamBazi(payload)` replaces `postBazi(payload)`.

- [ ] **Step 1: 替换 `postBazi()` 为 `streamBazi()`**

```javascript
async function streamBazi(data) {
  hideGlobalError();
  const response = await fetch(`${API_BASE_URL}/bazi/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Region": region,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.detail || `${copy.errorPrefix}: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let accumulatedReport = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice("data: ".length).trim();
      if (!jsonStr) continue;

      let event;
      try {
        event = JSON.parse(jsonStr);
      } catch (err) {
        console.warn("Failed to parse SSE event:", jsonStr);
        continue;
      }

      if (event.type === "chunk") {
        accumulatedReport += event.delta || "";
        renderStreamingReport(accumulatedReport);
      } else if (event.type === "done") {
        return { report: accumulatedReport, metadata: event.metadata };
      } else if (event.type === "error") {
        throw new Error(event.message || copy.errorPrefix);
      }
    }
  }

  return { report: accumulatedReport, metadata: null };
}

function renderStreamingReport(rawMarkdown) {
  if (typeof DOMPurify === "undefined" || typeof marked === "undefined") return;
  const html = DOMPurify.sanitize(marked.parse(rawMarkdown));
  document.getElementById("result-content").innerHTML = html;
}
```

- [ ] **Step 2: 修改表单提交调用 `streamBazi()`**

```javascript
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const payload = {
    birth_date: form.elements.birthDate.value,
    birth_time: form.elements.birthTime.value,
    gender: form.elements.gender.value,
    birthplace: form.elements.birthPlace.value,
  };

  setSubmitDisabled(true);
  showLoading();

  try {
    const result = await streamBazi(payload);
    showResult(result.report);
    showToast(copy.submitted);
  } catch (err) {
    const msg =
      err.message || `${copy.errorPrefix}; please check your network and try again.`;
    showError(msg);
    showGlobalError(msg);
  } finally {
    setSubmitDisabled(false);
  }
});
```

- [ ] **Step 3: 删除旧的 `postBazi()` 函数**（如果上面已替换引用）。

- [ ] **Step 4: Commit**

```bash
git add frontend/js/app.js
git commit -m "feat: frontend streaming for /bazi/stream

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Nginx 关闭 buffering 与中文 429 提示验证

**Files:**
- Modify: `frontend/nginx.conf`

**Interfaces:**
- Nginx `/api/` location passes SSE without buffering.

- [ ] **Step 1: 在 `location /api/` 里增加 buffering 关闭配置**

```nginx
location /api/ {
    proxy_pass http://backend:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    client_max_body_size 20M;

    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    proxy_buffering off;
    proxy_cache off;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/nginx.conf
git commit -m "fix: disable nginx buffering for SSE

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Verification

1. 重新构建并启动：
   ```bash
   docker compose down
   docker compose up -d --build
   ```
2. 打开首页，选择 `/1`、`/2` 或 `/3` 路由，填写八字并提交。
3. 观察报告文字是否逐段出现，浏览器 Network 中 `/bazi/stream` 的 Response 是否为 `text/event-stream`。
4. 将 `.env` 中 `MAX_DAILY_COST_CNY` 临时改为 `0.001` 再提交，应看到中文提示“今天的服务已经结束啦，请明天再来”。
5. 查看后端日志中 `LLM stream finished in ... first_chunk=... chunks=...` 确认首块时间和块数。
6. 在 admin 仪表盘查看当天 `bazi_request` 和 `bazi_report` 事件及 cost 是否正常记录。
