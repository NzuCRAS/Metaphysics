from typing import AsyncIterator, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.services.llm_client import LLMClient


class OpenAIProvider(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        kwargs = {"api_key": api_key, "model": model}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = ChatOpenAI(**kwargs)

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
        return {"provider": "openai", "model": self.model}
