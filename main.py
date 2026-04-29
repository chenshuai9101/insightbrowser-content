"""Agent 互联网内容层 (7024)

这是 Agent 互联网的"内容" — 不依赖现有互联网，原生发布的 Agent 内容。

端口: 7024
协议: AEP/1.0 (Agent Endpoint Protocol)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-internet-content")

app = FastAPI(
    title="Agent Internet Content",
    description="Agent 互联网原生内容层 — 发布、搜索、消费，不需要 HTML",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from routes.content import router
app.include_router(router)

@app.get("/health")
async def health():
    from services.aep import store
    return {
        "status": "healthy",
        "service": "agent-internet-content",
        "protocol": "AEP/1.0",
        "collections": len(store.collections),
        "total_items": sum(len(c.get("items",[])) for c in store.collections.values()),
    }

if __name__ == "__main__":
    logger.info("🌐 Agent 互联网内容层启动 (7024)")
    logger.info("   这是 Agent 互联网的'网页'——但不是 HTML，是 AEP 协议")
    uvicorn.run(app, host="0.0.0.0", port=7024)
