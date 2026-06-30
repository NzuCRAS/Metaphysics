from typing import AsyncIterator, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.services.llm_client import LLMClient


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
        kwargs = {"api_key": api_key, "model": model}
        if base_url:
            kwargs["base_url"] = base_url
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        self._client = ChatOpenAI(**kwargs)
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

    async def complete(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        lc_messages = self._to_lc_messages(messages)
        response = await self._client.ainvoke(lc_messages, **kwargs)
        self._last_usage = self._extract_usage(response)
        # 若底层未返回 usage（部分私有化模型），按生成文本长度保守估算 output tokens，
        # 避免成本统计低估导致日预算被突破。
        if (
            self._last_usage
            and self._last_usage.get("output_tokens") is None
            and isinstance(response.content, str)
            and response.content
        ):
            self._last_usage["output_tokens"] = self._estimate_text_tokens(response.content)
        return response.content

    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[str]:
        lc_messages = self._to_lc_messages(messages)
        self._last_usage = None
        total_input = 0
        total_output = 0
        async for chunk in self._client.astream(lc_messages, **kwargs):
            if chunk.content:
                yield chunk.content
            # 流式通常没有完整 usage；有则累计
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                um = chunk.usage_metadata
                total_input = um.get("input_tokens") or total_input
                total_output = um.get("output_tokens") or total_output
        if total_input or total_output:
            self._last_usage = {"input_tokens": total_input, "output_tokens": total_output}

    @property
    def metadata(self) -> Dict[str, Any]:
        data = {"provider": "openai", "model": self.model}
        if self._last_usage:
            data["usage"] = self._last_usage
        return data
