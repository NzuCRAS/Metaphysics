from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Union, Optional


class LLMClient(ABC):
    """可插拔 LLM Client 抽象基类。

    统一消息格式：
    {
        "role": "system" | "human" | "ai",
        "content": str | list[dict]
    }

    其中 content 为 list 时支持多模态，参考 OpenAI 格式：
    [
        {"type": "text", "text": "..."},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
    """

    @abstractmethod
    async def complete(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """非流式调用，返回完整文本。"""
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[str]:
        """流式调用，返回文本片段迭代器。"""
        pass

    @property
    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """返回当前 Provider 的元数据，用于接口响应。"""
        pass

    @property
    def last_usage(self) -> Optional[Dict[str, Any]]:
        """返回最近一次 complete/stream 调用的 token 使用统计（若可用）。"""
        return getattr(self, "_last_usage", None)

    def _normalize_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Union[str, List[Dict[str, Any]]]]]:
        """将统一格式转换为 LangChain 可接受的 message 列表。"""
        role_map = {"human": "user", "ai": "assistant", "system": "system"}
        normalized = []
        for msg in messages:
            role = role_map.get(msg.get("role", "human"), "user")
            content = msg.get("content", "")
            normalized.append({"role": role, "content": content})
        return normalized
