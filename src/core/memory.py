"""三层会话记忆模块 + LLM 摘要压缩"""
from collections import deque
from typing import List, Dict, Any, Optional
from src.core.llm_client import get_client, Message


class SessionMemory:
    """
    三层记忆架构：

    Layer 1 - 短期记忆: 最近 N 轮对话（deque, maxlen=10）
    Layer 2 - 中期主题: 当前会话的关键主题追踪
    Layer 3 - 长期画像: 用户简历摘要（持久化，不随对话变化）

    压缩策略：超过 COMPRESSION_THRESHOLD (48K) tokens → LLM 压缩至 ≤500字
    """

    def __init__(self, max_turns: int = 10, max_tokens: int = 4000,
                 compression_threshold: int = 48000, summary_max_chars: int = 500):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold
        self.summary_max_chars = summary_max_chars

        # Layer 1: 短期对话
        self.short_term: deque = deque(maxlen=max_turns)

        # Layer 2: 中期主题
        self.session_topics: List[str] = []

        # Layer 3: 长期画像（简历摘要缓存）
        self.long_term_profile: str = ""

        # 压缩缓存
        self._compressed_summary: str = ""
        self._total_turns: int = 0

        self.client = get_client()

    def set_profile(self, profile_text: str) -> None:
        """设置长期画像"""
        self.long_term_profile = profile_text

    def add_turn(self, question: str, answer: str, importance: float = 0.5) -> None:
        """添加一轮对话"""
        self.short_term.append({
            "question": question,
            "answer": answer,
            "importance": importance,
        })
        self._total_turns += 1

        # 提取主题关键词
        self._update_topics(question)

        # 检查是否需要压缩
        if self._estimate_tokens() > self.compression_threshold:
            self._trigger_compression()

    def get_context(self, max_tokens: int = None) -> str:
        """获取当前会话上下文"""
        max_tokens = max_tokens or self.max_tokens
        context_parts = []

        # 长期画像（始终包含）
        if self.long_term_profile:
            context_parts.append(f"## 候选人画像\n{self.long_term_profile}")

        # 压缩摘要（如果有）
        if self._compressed_summary:
            context_parts.append(f"## 对话历史摘要\n{self._compressed_summary}")

        # 近期对话
        if self.short_term:
            recent = []
            for turn in self.short_term:
                recent.append(f"Q: {turn['question']}\nA: {turn['answer'][:500]}")
            context_parts.append("## 近期对话\n" + "\n\n".join(recent))

        # 主题追踪
        if self.session_topics:
            context_parts.append(f"## 讨论主题\n{', '.join(self.session_topics[-5:])}")

        return "\n\n".join(context_parts)

    def get_recent_history(self, n: int = 5) -> List[Dict[str, str]]:
        """获取最近 N 轮对话"""
        return list(self.short_term)[-n:]

    def clear(self) -> None:
        """清除会话（保留长期画像）"""
        self.short_term.clear()
        self.session_topics = []
        self._compressed_summary = ""
        self._total_turns = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "short_term_turns": len(self.short_term),
            "total_turns": self._total_turns,
            "topics": self.session_topics[-10:],
            "has_compression": bool(self._compressed_summary),
            "estimated_tokens": self._estimate_tokens(),
        }

    # ===== 私有方法 =====

    def _update_topics(self, question: str) -> None:
        """从问题中提取主题关键词"""
        # 简单关键词提取
        import re
        # 提取技术名词、项目名等
        keywords = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+|[A-Z]{2,}', question)
        keywords += re.findall(r'(?:LangGraph|FastAPI|Python|RAG|Agent|Transformer|ChromaDB)', question, re.IGNORECASE)

        for kw in set(keywords):
            if kw not in self.session_topics:
                self.session_topics.append(kw)

    def _estimate_tokens(self) -> int:
        """估算当前记忆占用的 token 数（中文按字符数×2，英文按字符数÷4）"""
        total_chars = 0
        for turn in self.short_term:
            total_chars += len(turn["question"]) + len(turn["answer"])
        total_chars += len(self.long_term_profile)
        total_chars += len(self._compressed_summary)
        # 中英文混合估算：约 1.5 字符/token
        return int(total_chars / 1.5)

    def _trigger_compression(self) -> None:
        """触发 LLM 摘要压缩"""
        if len(self.short_term) < 3:
            return

        # 构建压缩请求
        turns_text = "\n".join([
            f"Q{turn['question']}\nA: {turn['answer'][:300]}"
            for i, turn in enumerate(self.short_term)
        ])

        prompt = f"""请将以下面试对话历史压缩为不超过{self.summary_max_chars}字的摘要。

保留以下信息：
1. 讨论过的主要话题和技术领域
2. 候选人展示的关键优势和能力
3. 面试中暴露的潜在弱点或盲区
4. 重要的上下文信息（用于后续追问）

## 对话历史
{turns_text}

请输出摘要（不超过{self.summary_max_chars}字）："""

        try:
            # 同步压缩（阻塞）
            import asyncio
            loop = asyncio.new_event_loop()
            messages = [Message(role="user", content=prompt)]
            result = loop.run_until_complete(
                self.client.chat_sync(messages, temperature=0.3, max_tokens=300)
            )
            loop.close()

            if len(result) > self.summary_max_chars:
                result = result[:self.summary_max_chars] + "..."

            # 合并旧摘要和新摘要
            if self._compressed_summary:
                self._compressed_summary = f"{self._compressed_summary}\n{result}"
            else:
                self._compressed_summary = result

            # 清除已压缩的短期记忆
            self.short_term.clear()

        except Exception:
            pass  # 压缩失败不影响主流程

    async def compress_async(self) -> str:
        """异步 LLM 摘要压缩"""
        if len(self.short_term) < 3:
            return ""

        turns_text = "\n".join([
            f"Q: {turn['question']}\nA: {turn['answer'][:300]}"
            for turn in self.short_term
        ])

        prompt = f"""请将以下面试对话历史压缩为不超过{self.summary_max_chars}字的摘要。
保留关键话题、优势展示和重要上下文。

## 对话历史
{turns_text}"""

        messages = [Message(role="user", content=prompt)]
        result = await self.client.chat_sync(messages, temperature=0.3, max_tokens=300)

        if len(result) > self.summary_max_chars:
            result = result[:self.summary_max_chars] + "..."

        if self._compressed_summary:
            self._compressed_summary = f"{self._compressed_summary}\n{result}"
        else:
            self._compressed_summary = result

        self.short_term.clear()
        return result
