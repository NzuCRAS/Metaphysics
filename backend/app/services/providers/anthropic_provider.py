from typing import AsyncIterator, List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.services.llm_client import LLMClient


class AnthropicProvider(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self._client = ChatAnthropic(api_key=api_key, model=model)

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
        return response.content

    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[str]:
        lc_messages = self._to_lc_messages(messages)
        async for chunk in self._client.astream(lc_messages, **kwargs):
            if chunk.content:
                yield chunk.content

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"provider": "anthropic", "model": self.model}
