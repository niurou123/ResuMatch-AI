"""自我介绍生成器 - 30s/1min/3min 三个版本"""
from typing import Dict, Any
from src.core.llm_client import get_client, Message
from src.core.prompts import build_self_intro_prompt


class SelfIntroGenerator:
    """自我介绍生成器"""

    def __init__(self):
        self.client = get_client()

    async def generate(
        self, profile: Dict[str, Any],
        target_position: str = "技术岗位",
        target_company: str = "",
    ) -> Dict[str, str]:
        """
        生成三个版本的自我介绍

        Returns:
            {"30s": "...", "1min": "...", "3min": "..."}
        """
        import asyncio

        length_configs = [
            ("30s", "约30秒，突出核心亮点，一句话概括优势"),
            ("1min", "约1分钟，包含技能+代表性项目+关键成果"),
            ("3min", "约3分钟，完整介绍教育背景+项目经历+技术栈+职业目标"),
        ]

        async def gen_one(length: str, style_hint: str) -> tuple:
            system, user = build_self_intro_prompt(profile, target_position, length)
            # 添加风格提示
            user += f"\n\n风格提示: {style_hint}"
            if target_company:
                user += f"\n目标公司: {target_company}"

            messages = [
                Message(role="system", content=system),
                Message(role="user", content=user),
            ]
            result = await self.client.chat_sync(messages, temperature=0.7)
            return length, result

        tasks = [gen_one(l, h) for l, h in length_configs]
        results = await asyncio.gather(*tasks)

        return {length: content for length, content in results}

    async def generate_single(
        self, profile: Dict[str, Any], length: str = "1min",
        target_position: str = "", style: str = "professional"
    ) -> str:
        """生成单个版本的自我介绍"""
        system, user = build_self_intro_prompt(profile, target_position, length)

        style_hints = {
            "professional": "语言专业正式，适合技术面试",
            "casual": "语言轻松自然，适合非正式场合",
            "passionate": "语言充满热情，突出对技术的热爱",
            "concise": "极其精炼，每句话都有信息量",
        }

        user += f"\n\n风格要求: {style_hints.get(style, style_hints['professional'])}"

        messages = [
            Message(role="system", content=system),
            Message(role="user", content=user),
        ]
        return await self.client.chat_sync(messages, temperature=0.7)
