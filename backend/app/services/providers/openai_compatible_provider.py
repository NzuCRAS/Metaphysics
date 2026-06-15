from typing import List, Dict, Any

from app.services.providers.openai_provider import OpenAIProvider
from app.services.llm_client import LLMClient


class OpenAICompatibleProvider(OpenAIProvider):
    """兼容 OpenAI API 格式的国产模型或私有化模型（如通义千问、文心一言、DeepSeek、vLLM 等）。

    本质上复用 OpenAIProvider，但要求传入 base_url。
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        super().__init__(api_key=api_key, model=model, base_url=base_url)

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"provider": "openai_compatible", "model": self.model, "base_url": self.base_url}


def create_llm_client(settings) -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
    elif provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
