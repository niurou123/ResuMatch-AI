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
                # 常见故障归一化：402 余额不足要显式指出（否则上游表现为
                # "空答案+低分+空转修订"，极难定位）；401 是 key 无效
                hint = ""
                if response.status_code == 402:
                    hint = "（DeepSeek 账户余额不足，请充值）"
                elif response.status_code == 401:
                    hint = "（API Key 无效或未配置）"
                raise Exception(f"API Error: {response.status_code} - {response.text[:200]}{hint}")
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
        # 推理模型（deepseek-v4-pro 线）：思维链与正式答案共享 max_tokens 预算。
        # 思维链通常消耗数百到数千 token——预算不放大时 content 会被截成空串
        # （finish_reason=length，全部 token 被 reasoning 吃掉）。
        # 这里按 3 倍放大预算并显式关闭思维链输出（业务场景只需正式答案）。
        if self.model and ("v4" in self.model or "reasoner" in self.model):
            data["max_tokens"] = mt * 3
            data["reasoning"] = {"effort": "low"}  # 最短思维链（若网关支持）

        if stream:
            return await self._request("chat/completions", data, stream=True)
        else:
            response = await self._request("chat/completions", data, stream=False)
            try:
                msg = response["choices"][0]["message"]
                content = msg.get("content") or ""
                # 推理模型兜底：content 为空但 reasoning_content 有值时，
                # 说明预算被思维链耗尽——把思维链里的可用文本作为降级返回
                # （好过返回空串让上层误判为生成失败）
                if not content.strip():
                    reasoning = msg.get("reasoning_content") or ""
                    if reasoning.strip():
                        content = reasoning.strip()
                return ChatResponse(
                    content=content,
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
