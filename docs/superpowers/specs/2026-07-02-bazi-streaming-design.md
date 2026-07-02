# BaZi LLM 流式输出设计

## 目标

将八字（BaZi）命理报告的 LLM 调用从同步返回改为流式输出（SSE），降低用户等待焦虑；同时保留每日 50 元成本上限、事件记录和前端英文界面。预算耗尽时前端提示中文：“今天的服务已经结束啦，请明天再来”。

## 范围

- 仅覆盖 `POST /api/v1/bazi` 对应的八字服务。
- 手相 `/palmistry` 保持现有同步接口不变。
- 旧同步接口 `/api/v1/bazi` 保留作为兼容/测试入口。

## 方案

采用 **SSE（Server-Sent Events）**：新增 `POST /api/v1/bazi/stream`，返回 `text/event-stream`；前端使用 `fetch` + `ReadableStream` 手动解析 SSE 数据块并渲染。

## 架构

```
Frontend (app.js)
  |
  | POST /api/v1/bazi/stream  (body: BaziRequest, header: X-Region)
  v
Nginx (proxy_buffering off)
  |
  v
backend/app/routers/bazi.py  -> analyze_bazi_stream()
  |
  v
backend/app/services/llm_guard.py  -> stream_with_guard()
  |
  v
backend/app/services/providers/openai_provider.py  -> stream()
  |
  v
DeepSeek (stream=true)
```

## 数据流

1. 用户提交表单，前端调用 `fetch('/api/v1/bazi/stream', {method:'POST', ...})`。
2. 后端校验请求、构造 prompt，调用 `stream_with_guard()`。
3. `stream_with_guard()`：
   - 记录 `bazi_request` 分析事件。
   - 调用 `cost_tracker.check_budget()`，若会超支则抛 HTTP 429。
   - 调用 `client.stream(messages)`，开始异步流式生成。
   - 将每个内容块以 SSE 事件推送给前端：
     ```
     data: {"type":"chunk","delta":"..."}\n\n
     ```
   - 流结束后根据 usage 或累计文本长度估算 tokens，计算 cost，记录 `bazi_report`。
   - 发送结束事件：
     ```
     data: {"type":"done","metadata":{"provider":"...","model":"...","usage":{...}},"cost_cny":0.0012}\n\n
     ```
4. 前端收到 `chunk` 时追加文本到结果区；收到 `done` 时启用“复制报告”。

## SSE 事件格式

| type  | 字段      | 含义                     |
|-------|-----------|--------------------------|
| chunk | delta     | 新增的文本片段           |
| done  | metadata  | provider/model/usage     |
| done  | cost_cny  | 本次调用实际花费（CNY）  |
| error | message   | 错误信息                 |

## 接口

### 新增

- `POST /api/v1/bazi/stream`
  - Request: 与 `/bazi` 相同（JSON + `X-Region` header）
  - Response: `text/event-stream`

### 保留

- `POST /api/v1/bazi`（同步，作为兼容入口）

## 成本与预算

- 流式调用前仍按最坏情况（prompt tokens × 安全系数 + `max_tokens`）检查预算。
- 流式调用后若底层未返回 usage，则按累计文本长度保守估算 output tokens，再计算 cost 入库。
- 当天额度耗尽时返回 HTTP 429，前端显示“今天的服务已经结束啦，请明天再来”。

## 前端渲染

- 流式过程中：追加原始 Markdown 文本到 `#result-content`（可按需做轻量 Markdown 解析）。
- 流式结束后：使用 `marked.parse()` + `DOMPurify.sanitize()` 渲染最终报告。
- 流式过程中禁用提交按钮，结束后恢复。

## Nginx 配置

在 `location /api/` 中增加：

```nginx
proxy_buffering off;
proxy_cache off;
```

确保 SSE 数据块不被 Nginx 缓冲。

## 错误处理

- 预算耗尽：调用前直接返回 HTTP 429。
- LLM 超时/失败：流中发送 `{"type":"error","message":"..."}` 后关闭连接。
- 连接意外中断：前端在未收到 `done` 时提示输出被中断。

## 性能观测

在 `stream_with_guard()` 中增加日志：

- `time_to_first_chunk`：到第一个内容块的耗时
- `stream_duration`：整个流的总耗时
- `chunks`：收到的内容块数量

用于判断是 DeepSeek 响应慢，还是前端/网络层缓冲导致。

## 改动文件

- `backend/app/services/llm_guard.py` — 新增 `stream_with_guard`
- `backend/app/routers/bazi.py` — 新增 `/bazi/stream`
- `backend/app/services/providers/openai_provider.py` — 完善流式 usage 兜底
- `frontend/js/app.js` — 新增 `streamBazi` 并替换表单提交
- `frontend/nginx.conf` — 关闭 buffering

## 验收标准

1. 提交八字表单后，报告文字逐字/逐段出现，而非等待完整响应。
2. 浏览器 Network 中 `/bazi/stream` 返回 `text/event-stream`。
3. 预算耗尽时返回 429，前端显示“今天的服务已经结束啦，请明天再来”。
4. `analytics_events` 仍正确记录 `bazi_request` 和 `bazi_report` 及 cost。
5. 后端日志输出 `LLM stream` 首块时间和总耗时。
