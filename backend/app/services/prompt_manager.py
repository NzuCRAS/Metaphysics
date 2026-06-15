import os
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate


class PromptManager:
    """管理 prompt 模板，支持 System + Human 组合，以及 RAG 上下文预留。"""

    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            # 默认指向 backend/prompts
            self.prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)

    def load_template(self, name: str) -> str:
        path = self.prompts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def get_bazi_prompt(self, context: str = "") -> ChatPromptTemplate:
        system = self.load_template("bazi_system.txt")
        human = self.load_template("bazi_human.txt")
        if context:
            system += f"\n\n参考以下古籍与案例：\n{context}"
        return ChatPromptTemplate.from_messages(
            [("system", system), ("human", human)],
            template_format="jinja2",
        )

    def get_palmistry_prompt(self, context: str = "") -> ChatPromptTemplate:
        system = self.load_template("palmistry_system.txt")
        human = self.load_template("palmistry_human.txt")
        if context:
            system += f"\n\n参考以下古籍与案例：\n{context}"
        return ChatPromptTemplate.from_messages(
            [("system", system), ("human", human)],
            template_format="jinja2",
        )

    @staticmethod
    def attach_image_to_human(
        messages: List[Dict[str, Any]], base64_image: str, mime_type: str = "image/jpeg"
    ) -> List[Dict[str, Any]]:
        """在最后一条 human message 后附加图片内容。

        返回统一的多模态 message 列表，供 LLMClient 使用。
        """
        if not messages:
            messages = [{"role": "human", "content": ""}]

        # 找到最后一条 human message
        last_human_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "human":
                last_human_idx = i
                break

        if last_human_idx == -1:
            messages.append({"role": "human", "content": ""})
            last_human_idx = len(messages) - 1

        human_msg = messages[last_human_idx]
        content = human_msg.get("content", "")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]

        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
        })
        human_msg["content"] = content
        return messages


prompt_manager = PromptManager()
