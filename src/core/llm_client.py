"""DeepSeek API 客户端模块 - 重构版"""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass, field
import httpx
from src.config import settings


@dataclass
class Message:
    """聊天消息"""
    role: str          # system, user, assistant
    content: str


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""


class DeepSeekClient:
    """DeepSeek API 异步客户端

    连接池说明（BUG_LOG 案例 9 的根治）：
    早期实现每次请求都 `async with httpx.AsyncClient()` 新建连接，
    既有 TCP/TLS 握手开销，也出现过"新 client 实例导致响应异常变短"的线上问题。
    现在持有长生命周期 AsyncClient（连接池 limits + keep-alive），
    全局单例 get_client() 全程复用。
    """

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model = settings.DEEPSEEK_MODEL
        self.timeout = settings.DEEPSEEK_TIMEOUT
        # 长生命周期连接池：复用 TCP/TLS 连接；上限按多 Agent 并发场景取 20
        self._http = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        """释放连接池（进程退出时调用；全局单例通常无需手动调）"""
        await self._http.aclose()

    async def _request(
        self, endpoint: str, data: Dict[str, Any], stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator]:
        """发送请求到 DeepSeek API（复用全局连接池）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/{endpoint}"

        if stream:
            # 流式：context manager 管理 response 生命周期，生成器内消费
            resp = await self._http.send(
                self._http.build_request("POST", url, json=data, headers=headers),
                stream=True,
            )
            if resp.status_code != 200:
                await resp.aread()
                raise Exception(f"API Error: {resp.status_code} - {resp.text}")

            async def stream_gen():
                try:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                yield chunk
                            except json.JSONDecodeError:
                                continue
                finally:
                    await resp.aclose()
            return stream_gen()
        else:
            response = await self._http.post(url, json=data, headers=headers)
            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code} - {response.text}")
            return response.json()

    async def chat(
        self, messages: List[Message], temperature: float = None,
        max_tokens: int = None, stream: bool = False
    ) -> Union[ChatResponse, AsyncGenerator]:
        """聊天补全"""
        temp = temperature if temperature is not None else settings.TEMPERATURE
        mt = max_tokens if max_tokens is not None else settings.MAX_NEW_TOKENS

        data = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temp,
            "max_tokens": mt,
            "top_p": settings.TOP_P,
            "stream": stream,
        }

        if stream:
            return await self._request("chat/completions", data, stream=True)
        else:
            response = await self._request("chat/completions", data, stream=False)
            try:
                return ChatResponse(
                    content=response["choices"][0]["message"]["content"],
                    usage=response.get("usage", {}),
                    model=response.get("model", self.model),
                )
            except (KeyError, IndexError, TypeError) as e:
                raise Exception(f"Invalid response format: {response}") from e

    async def chat_sync(self, messages: List[Message], temperature: float = None,
                        max_tokens: int = None) -> str:
        """同步聊天（获取完整响应文本）"""
        response = await self.chat(messages, temperature, max_tokens, stream=False)
        return response.content

    async def chat_stream(self, messages: List[Message], temperature: float = None,
                          max_tokens: int = None) -> AsyncGenerator[str, None]:
        """流式聊天补全"""
        stream_gen = await self.chat(messages, temperature, max_tokens, stream=True)
        async for chunk in stream_gen:
            try:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    yield delta["content"]
            except (KeyError, IndexError, TypeError):
                continue

    async def generate_structured(
        self, system_prompt: str, user_prompt: str,
        temperature: float = 0.3
    ) -> dict:
        """生成结构化 JSON 输出"""
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        raw = await self.chat_sync(messages, temperature=temperature)
        # 尝试提取 JSON 块
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 尝试提取 ```json ... ``` 块
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"无法解析 JSON 输出: {raw[:200]}...")


# 全局客户端实例（延迟初始化）
_client: Optional[DeepSeekClient] = None


def get_client() -> DeepSeekClient:
    """获取全局 DeepSeek 客户端实例"""
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client
