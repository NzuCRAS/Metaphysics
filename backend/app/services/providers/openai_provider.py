from typing import AsyncIterator, List, Dict, Any
import logging
import openai
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "",
        max_tokens: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        # LangChain 客户端（非流式 / 兼容层）
        lc_kwargs = {"api_key": api_key, "model": model}
        if base_url:
            lc_kwargs["base_url"] = base_url
        if max_tokens:
            lc_kwargs["max_tokens"] = max_tokens
        if timeout is not None:
            lc_kwargs["timeout"] = timeout
        if max_retries is not None:
            lc_kwargs["max_retries"] = max_retries
        self._client = ChatOpenAI(**lc_kwargs)

        # 原生 OpenAI 客户端（流式，避免 LangChain 中间层缓冲）
        raw_kwargs = {"api_key": api_key}
        if base_url:
            raw_kwargs["base_url"] = base_url
        if timeout is not None:
            raw_kwargs["timeout"] = timeout
        if max_retries is not None:
            raw_kwargs["max_retries"] = max_retries
        self._raw_client = openai.AsyncOpenAI(**raw_kwargs)

        self._last_usage: Dict[str, Any] | None = None

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        """离线环境下对 token 数量的保守兜底估算（1 token ≈ 2 chars）。"""
        return max(1, int(len(text) / 2))

    @staticmethod
    def _extract_usage(response) -> Dict[str, Any]:
        usage: Dict[str, Any] = {}
        # LangChain AIMessage.usage_metadata
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage["input_tokens"] = um.get("input_tokens")
            usage["output_tokens"] = um.get("output_tokens")
            usage["total_tokens"] = um.get("total_tokens")
        # OpenAI/DeepSeek raw token_usage in response_metadata
        raw = (response.response_metadata or {}).get("token_usage") if hasattr(response, "response_metadata") else None
        if isinstance(raw, dict):
            usage.setdefault("input_tokens", raw.get("prompt_tokens"))
            usage.setdefault("output_tokens", raw.get("completion_tokens"))
            usage.setdefault("total_tokens", raw.get("total_tokens"))
        return {k: v for k, v in usage.items() if v is not None}

    def _to_lc_messages(self, messages: List[Dict[str, Any]]):
        role_map = {"human": HumanMessage, "ai": AIMessage, "system": SystemMessage}
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "human")
            content = msg.get("content", "")
            cls = role_map.get(role, HumanMessage)
            lc_messages.append(cls(content=content))
        return lc_messages

    @staticmethod
    def _is_deepseek_v4(model: str) -> bool:
        return "deepseek-v4" in model.lower()

    @staticmethod
    def _thinking_disabled_body(model: str) -> Dict[str, Any] | None:
        """DeepSeek V4 系列默认开启 thinking，需要显式关闭才能直接拿到正式结果。"""
        if OpenAIProvider._is_deepseek_v4(model):
            return {"thinking": {"type": "disabled"}}
        return None

    async def complete(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """使用原生 OpenAI 客户端完成非流式调用，避免 LangChain 对 extra_body 的过滤。"""
        api_messages = self._normalize_messages(messages)
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
        }
        if self.max_tokens:
            request_kwargs["max_tokens"] = self.max_tokens
        thinking_body = self._thinking_disabled_body(self.model)
        if thinking_body:
            request_kwargs["extra_body"] = thinking_body

        response = await self._raw_client.chat.completions.create(**request_kwargs, **kwargs)
        self._last_usage = {
            "input_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
        }
        message = response.choices[0].message if response.choices else None
        content = getattr(message, "content", None) or ""
        return content

    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[str]:
        """使用原生 OpenAI 客户端做真正的逐 token 流式输出。

        直接调用底层 chat.completions.create(stream=True)，避免 LangChain 中间层
        可能存在的缓冲或 chunk 合并，保证模型开始生成后立刻推送到前端。
        """
        self._last_usage = None
        api_messages = self._normalize_messages(messages)
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
        }
        if self.max_tokens:
            request_kwargs["max_tokens"] = self.max_tokens

        # DeepSeek V4 系列默认开启 thinking，需要显式关闭才能直接拿到正式结果
        thinking_body = self._thinking_disabled_body(self.model)
        if thinking_body:
            request_kwargs["extra_body"] = thinking_body

        # DeepSeek / OpenAI 支持通过 stream_options.include_usage 在最后一个 chunk 返回 usage
        is_deepseek = "deepseek" in self.model.lower() or "deepseek" in (self.base_url or "").lower()
        if is_deepseek:
            request_kwargs["stream_options"] = {"include_usage": True}

        accumulated_text = ""
        accumulated_reasoning = ""
        chunk_index = 0
        response = await self._raw_client.chat.completions.create(**request_kwargs, **kwargs)
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            delta = choice.delta if choice else None
            finish_reason = choice.finish_reason if choice else None

            content = getattr(delta, "content", None) or ""
            reasoning = getattr(delta, "reasoning_content", None) or ""

            if chunk_index < 5 or content or reasoning:
                logger.info(
                    "Raw chunk #%d: content_len=%d reasoning_len=%d finish_reason=%s",
                    chunk_index,
                    len(content),
                    len(reasoning),
                    finish_reason,
                )

            if reasoning:
                accumulated_reasoning += reasoning
            if content:
                accumulated_text += content
                yield content

            # 部分流式接口在最后一个 chunk 的 usage 字段返回 token 统计
            if chunk.usage:
                self._last_usage = {
                    "input_tokens": chunk.usage.prompt_tokens,
                    "output_tokens": chunk.usage.completion_tokens,
                }
            chunk_index += 1

        logger.info(
            "Stream summary: content_len=%d reasoning_len=%d total_chunks=%d",
            len(accumulated_text),
            len(accumulated_reasoning),
            chunk_index,
        )

        if not self._last_usage and accumulated_text:
            self._last_usage = {
                "input_tokens": 0,
                "output_tokens": self._estimate_text_tokens(accumulated_text),
            }

    @property
    def metadata(self) -> Dict[str, Any]:
        data = {"provider": "openai", "model": self.model}
        if self._last_usage:
            data["usage"] = self._last_usage
        return data
