"""FastAPI 主应用入口"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.setrecursionlimit(10000)  # ChromaDB + Pydantic 复杂嵌套需要更高限制

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.config import settings, ensure_directories
from src.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 正在启动 ResuMatch AI...")
    ensure_directories()

    # 预热嵌入模型 + 精排模型（冷启动 10-20s，预热后首次请求秒回）
    try:
        import time
        t0 = time.time()
        from src.rag.embedder import get_embedder
        get_embedder().model  # 触发模型加载
        try:
            from src.rag.reranker import get_reranker
            get_reranker().model
        except Exception as e:
            print(f"[WARN] reranker 预热失败: {e}")
        print(f"✅ 模型预热完成 ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"[WARN] 模型预热失败（首次请求可能较慢）: {e}")

    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} 已就绪")
    yield
    print("👋 应用正在关闭...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于多Agent协作的AI面试助手 - 蒸馏简历，智能回答",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
    )
