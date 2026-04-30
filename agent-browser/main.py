"""Agent Browser (7022) — 为 Agent 设计的专用浏览器服务

设计理念：Agent 不需要"看"网页，需要"消费"结构化数据。

核心 API：
  POST /open       → 打开 URL，返回完整结构化数据
  POST /traverse   → BFS 页面树遍历
  POST /screenshot → 截图
  POST /extract    → 提取结构化数据（价格/键值对/表单）
  POST /compare    → diff 页面变更
  POST /capture    → 多媒体资源抓取
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-browser")

app = FastAPI(
    title="Agent Browser",
    description="为 Agent 设计的专用浏览器 — 结构化数据提取 + 页面树遍历 + 多媒体抓取",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from routes.browser import router
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agent-browser", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7022)
