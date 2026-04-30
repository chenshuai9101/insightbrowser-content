"""Agent Internet Core — 精简单体微服务
P1 架构精简: 23→10 服务
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="Agent Internet Core",
    description="AEP/1.0 API Gateway + L1基础设施",
    version="3.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 注册路由
from app.routes import content, search, auth_queue, reliability, economy
content.register(app)
search.register(app)
auth_queue.register(app)
reliability.register(app)
economy.register(app)

@app.get("/health")
async def health():
    return {"status":"healthy","service":"agent-internet-core","version":"3.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7000)
