from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import bazi, palmistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时可以初始化数据库连接池、Redis 连接等
    # 1.0 版本保持无状态，仅预留
    yield
    # 关闭时清理资源


app = FastAPI(
    title="Metaphysics Fortune API",
    description="八字算命与看手相 Web App 后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许前端跨域访问，生产环境应限制为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bazi.router, prefix="/api/v1", tags=["八字算命"])
app.include_router(palmistry.router, prefix="/api/v1", tags=["看手相"])


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
