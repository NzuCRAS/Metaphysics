import re


# 常见模型声明 / 免责声明模式
DISCLAIMER_PATTERNS = [
    # DeepSeek
    r"以上\s*(?:内容|回答|分析|文本)?\s*由\s*DeepSeek\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    r"以下\s*(?:内容|回答|分析|文本)?\s*由\s*DeepSeek\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    r"本\s*(?:内容|回答|分析|文本)?\s*由\s*DeepSeek\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    # 通用 AI 声明
    r"以上\s*(?:内容|回答|分析|文本)?\s*由\s*AI\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    r"以下\s*(?:内容|回答|分析|文本)?\s*由\s*AI\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    r"本\s*(?:内容|回答|分析|文本)?\s*由\s*AI\s*(?:模型)?\s*(?:生成|提供)[^\n]*",
    r"以上\s*(?:内容|回答|分析|文本)?\s*由\s*(?:人工智能|大模型|语言模型)[^\n]*",
    r"以下\s*(?:内容|回答|分析|文本)?\s*由\s*(?:人工智能|大模型|语言模型)[^\n]*",
    r"本\s*(?:内容|回答|分析|文本)?\s*由\s*(?:人工智能|大模型|语言模型)[^\n]*",
    # 英文
    r"^\s*The\s+above\s+content\s+was\s+generated\s+by\s+[^\n]*(?:AI|DeepSeek|model)[^\n]*",
    r"^\s*The\s+following\s+content\s+was\s+generated\s+by\s+[^\n]*(?:AI|DeepSeek|model)[^\n]*",
    r"^\s*This\s+content\s+was\s+generated\s+by\s+[^\n]*(?:AI|DeepSeek|model)[^\n]*",
    r"^\s*Generated\s+by\s+[^\n]*(?:AI|DeepSeek|model)[^\n]*",
]


def clean_report(text: str) -> str:
    """清理报告中常见的模型声明和 AI 生成提示。"""
    if not text:
        return text

    cleaned = text
    for pattern in DISCLAIMER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # 移除因删除声明产生的多余空行（最多保留两个换行）
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()
