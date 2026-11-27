# -*- coding: utf-8 -*-
"""模型连通性 + 延迟探测（换模型后验证）"""
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from src.config import settings                     # noqa: E402
from src.core.llm_client import DeepSeekClient, Message  # noqa: E402


async def probe(model: str = None):
    from src.core import llm_client as mod
    old = settings.DEEPSEEK_MODEL
    if model:
        settings.DEEPSEEK_MODEL = model
    client = DeepSeekClient()
    if model:
        client.model = model
    reasoning = client._is_reasoning_model()
    t0 = time.time()
    try:
        r = await client.chat(
            [Message(role="system", content="你是助手，简短回答。"),
             Message(role="user", content="用一句话说明什么是RAG。")],
            temperature=0.3,
        )
        ms = round((time.time() - t0) * 1000)
        print(f"model={client.model!r} reasoning={reasoning} 延迟={ms}ms")
        print(f"  返回长度={len(r.content)} usage={r.usage}")
        print(f"  内容前80字: {r.content[:80]}")
        return True
    except Exception as ex:
        ms = round((time.time() - t0) * 1000)
        print(f"model={client.model!r} reasoning={reasoning} 失败({ms}ms): {str(ex)[:200]}")
        return False
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
        settings.DEEPSEEK_MODEL = old


async def main():
    print("配置模型:", settings.DEEPSEEK_MODEL)
    ok = await probe()
    if not ok:
        # 网关若需要 provider 前缀，再试一次
        await probe("deepseek/deepseek-v4.1-flash")


if __name__ == "__main__":
    asyncio.run(main())
