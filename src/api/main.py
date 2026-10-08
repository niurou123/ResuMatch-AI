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
# 说明：allow_origins 与 allow_credentials 不能同时为通配（浏览器规范会拒绝
# 带凭据请求的 "*" 源）。本项目 token 走 header、无 cookie 凭据，安全起见
# 收敛为开发常用源 + 环境变量可扩展；如未来需要 cookie 凭据再改回白名单模式
_ALLOWED_ORIGINS = [
    "http://localhost:5173",     # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",     # 前端 Docker (Nginx)
    "http://localhost:8721",     # 本机直连后端页面
    # Chrome 扩展无需在此列：MV3 host_permissions 已豁免 CORS（popup/sidebar
    # 的 fetch 走扩展权限，浏览器不校验 Access-Control-Allow-Origin）
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=None,
    allow_credentials=False,
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
