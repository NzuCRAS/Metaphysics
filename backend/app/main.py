from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.db import init_db
from app.routers import bazi, palmistry, analytics


def _configure_logging():
    """确保应用日志级别与配置一致，否则 uvicorn 默认只打印 WARNING。"""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    # 启动时初始化数据库表
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title="Metaphysics Fortune API",
    description="BaZi fortune-telling Web App backend API",
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

app.include_router(bazi.router, prefix="/api/v1", tags=["BaZi"])
app.include_router(palmistry.router, prefix="/api/v1", tags=["Palmistry"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
