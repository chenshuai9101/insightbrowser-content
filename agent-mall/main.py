"""Agent Mall Protocol (AMP) — FastAPI 主服务

Agent 互联网的"商场层"：
- Agent 身份注册与管理
- 店铺系统（开店/装修/商品展示）
- 商场空间（楼层/区域/发现）
- 人类 ↔ Agent 对话
"""

from __future__ import annotations
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# ═══════════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="Agent Mall Protocol (AMP)",
    description="Agent 互联网商场 — Agent 的自主商业空间。Agent 在这里拥有店铺、展示商品、与人类交易。",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "mall.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "Agent Mall Protocol (AMP) — 商场根路径。访问 /static/mall.html 查看商场。"}


# ═══════════════════════════════════════════════════════════
# In-Memory Store (先用内存，后续接数据库)
# ═══════════════════════════════════════════════════════════

# Agent 身份
agents_db: dict[str, dict] = {}
# 店铺
stores_db: dict[str, dict] = {}
# 商场
malls_db: dict[str, dict] = {}
# 对话 session
chat_sessions: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════

class AgentRegister(BaseModel):
    name: str
    bio: str = ""
    avatar_url: str = ""
    wallet_address: str = ""
    public_key: str = ""
    category: str = ""

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    category: Optional[str] = None

class StoreCreate(BaseModel):
    agent_id: str
    name: str
    floor: int = 1
    zone: str = ""
    banner_url: str = ""
    theme_color: str = "#4da6ff"
    description: str = ""

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    floor: Optional[int] = None
    zone: Optional[str] = None
    banner_url: Optional[str] = None
    theme_color: Optional[str] = None
    featured_products: Optional[list[str]] = None
    description: Optional[str] = None

class ChatStart(BaseModel):
    human_name: str
    store_id: str
    initial_message: str = ""

class ChatSend(BaseModel):
    sender: str  # "human" | "agent"
    message: str


# ═══════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agent-mall-protocol",
        "version": "1.0.0",
        "agents": len(agents_db),
        "stores": len(stores_db),
        "malls": len(malls_db),
    }


# ═══════════════════════════════════════════════════════════
# Agent Identity (P0)
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/agents")
async def register_agent(req: AgentRegister):
    """注册 Agent 身份 — Agent 在互联网的"身份证" """
    agent_id = f"agent_{hashlib.sha256(f'{req.name}:{time.time()}'.encode()).hexdigest()[:12]}"
    
    agent = {
        "agent_id": agent_id,
        "name": req.name,
        "bio": req.bio,
        "avatar_url": req.avatar_url,
        "wallet_address": req.wallet_address,
        "public_key": req.public_key,
        "category": req.category,
        "reputation": {
            "rating": 0.0,
            "total_sales": 0,
            "total_reviews": 0,
            "dispute_rate": 0.0,
            "verified": False,
        },
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    agents_db[agent_id] = agent
    return agent


@app.get("/api/v1/agents/{agent_id}")
async def get_agent(agent_id: str):
    if agent_id not in agents_db:
        raise HTTPException(404, "Agent not found")
    return agents_db[agent_id]


@app.put("/api/v1/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdate):
    if agent_id not in agents_db:
        raise HTTPException(404, "Agent not found")
    agent = agents_db[agent_id]
    for k, v in req.model_dump(exclude_none=True).items():
        if v is not None:
            agent[k] = v
    agent["updated_at"] = time.time()
    return agent


@app.get("/api/v1/agents")
async def list_agents(category: str = "", limit: int = 50):
    result = list(agents_db.values())
    if category:
        result = [a for a in result if a.get("category") == category]
    result.sort(key=lambda a: a.get("reputation", {}).get("rating", 0), reverse=True)
    return {"agents": result[:limit], "total": len(result)}


@app.post("/api/v1/agents/{agent_id}/verify")
async def verify_agent(agent_id: str):
    """手动验证 Agent（实际应为 KYC/链上验证）"""
    if agent_id not in agents_db:
        raise HTTPException(404)
    agents_db[agent_id]["reputation"]["verified"] = True
    agents_db[agent_id]["updated_at"] = time.time()
    return agents_db[agent_id]


# ═══════════════════════════════════════════════════════════
# Store (P0) — Agent 的"铺位"
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/stores")
async def create_store(req: StoreCreate):
    """Agent 开设店铺 — 在商城里租个铺位"""
    if req.agent_id not in agents_db:
        raise HTTPException(404, "Agent not registered. Register identity first.")

    store_id = f"store_{hashlib.sha256(f'{req.agent_id}:{req.name}'.encode()).hexdigest()[:10]}"
    
    store = {
        "store_id": store_id,
        "agent_id": req.agent_id,
        "name": req.name,
        "floor": req.floor,
        "zone": req.zone,
        "banner_url": req.banner_url,
        "theme_color": req.theme_color,
        "description": req.description,
        "featured_products": [],
        "position": _allocate_position(req.floor, req.zone),
        "stats": {"daily_visitors": 0, "response_time_ms": 0, "online": True},
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    stores_db[store_id] = store
    return store


def _allocate_position(floor: int, zone: str) -> dict:
    """自动分配铺位位置（简化版）"""
    existing = [s for s in stores_db.values() if s["floor"] == floor]
    x = (len(existing) % 5) + 1
    y = (len(existing) // 5) + 1
    return {"x": x, "y": y, "floor": floor}


@app.get("/api/v1/stores/{store_id}")
async def get_store(store_id: str):
    if store_id not in stores_db:
        raise HTTPException(404, "Store not found")
    store = stores_db[store_id]
    agent = agents_db.get(store["agent_id"], {})
    store["agent"] = {
        "agent_id": agent.get("agent_id"),
        "name": agent.get("name"),
        "avatar_url": agent.get("avatar_url"),
        "reputation": agent.get("reputation"),
        "verified": agent.get("reputation", {}).get("verified", False),
    }
    return store


@app.put("/api/v1/stores/{store_id}")
async def update_store(store_id: str, req: StoreUpdate):
    if store_id not in stores_db:
        raise HTTPException(404)
    store = stores_db[store_id]
    for k, v in req.model_dump(exclude_none=True).items():
        if v is not None:
            store[k] = v
    store["updated_at"] = time.time()
    return store


@app.delete("/api/v1/stores/{store_id}")
async def close_store(store_id: str):
    if store_id not in stores_db:
        raise HTTPException(404)
    del stores_db[store_id]
    return {"status": "closed", "store_id": store_id}


@app.get("/api/v1/stores/{store_id}/products")
async def get_store_products(store_id: str):
    """获取店铺商品 — 从 AEP/1.0 实时拉取"""
    if store_id not in stores_db:
        raise HTTPException(404)
    store = stores_db[store_id]
    # 店铺商品 = AEP/1.0 中该 Agent 发布的内容
    return {
        "store_id": store_id,
        "store_name": store["name"],
        "agent_id": store["agent_id"],
        "products": store.get("featured_products", []),
        "_note": "Full product list available via AEP/1.0: GET /aep/v1/search?publisher={agent_id}",
    }


# ═══════════════════════════════════════════════════════════
# Mall (P1) — 商场空间
# ═══════════════════════════════════════════════════════════

# 初始化默认商场
_default_mall = {
    "mall_id": "mall_agent_internet_01",
    "name": "Agent 互联网一号商场",
    "tagline": "Agent 自主商业空间 · 每一个店铺背后都是一个自主 Agent",
    "floors": [
        {"level": 1, "name": "数码电器", "zones": ["手机", "电脑", "智能家居", "配件"], "color": "#4da6ff"},
        {"level": 2, "name": "知识服务", "zones": ["课程", "咨询", "翻译", "写作"], "color": "#2ecc71"},
        {"level": 3, "name": "创意设计", "zones": ["UI设计", "插画", "视频制作", "品牌设计"], "color": "#f39c12"},
        {"level": 4, "name": "生活服务", "zones": ["餐饮", "旅游", "健身", "家政"], "color": "#e74c3c"},
    ],
    "stats": {"total_stores": 0, "total_agents": 0, "daily_visitors": 0, "daily_transactions": 0},
    "rules": {
        "min_rating_to_open": 0,
        "max_stores_per_agent": 3,
        "commission_rate": 0.02,  # 2%
    },
    "created_at": time.time(),
}
malls_db[_default_mall["mall_id"]] = _default_mall


def _refresh_mall_stats():
    """刷新商场统计"""
    mall = malls_db[_default_mall["mall_id"]]
    mall["stats"]["total_stores"] = len(stores_db)
    mall["stats"]["total_agents"] = len(agents_db)


@app.get("/api/v1/malls")
async def list_malls():
    return {"malls": list(malls_db.values())}


@app.get("/api/v1/malls/{mall_id}")
async def get_mall(mall_id: str):
    if mall_id not in malls_db:
        raise HTTPException(404)
    _refresh_mall_stats()
    return malls_db[mall_id]


@app.get("/api/v1/malls/{mall_id}/floor/{floor}")
async def get_floor(mall_id: str, floor: int):
    if mall_id not in malls_db:
        raise HTTPException(404)
    mall = malls_db[mall_id]
    if floor < 1 or floor > len(mall["floors"]):
        raise HTTPException(404, "Floor not found")

    floor_info = mall["floors"][floor - 1]
    floor_stores = [s for s in stores_db.values() if s["floor"] == floor]
    
    # 按位置排列
    floor_stores.sort(key=lambda s: (s["position"]["y"], s["position"]["x"]))
    
    return {
        "mall_id": mall_id,
        "floor": floor,
        "floor_info": floor_info,
        "stores": floor_stores,
        "total_stores": len(floor_stores),
    }


@app.get("/api/v1/malls/{mall_id}/discover")
async def discover(mall_id: str, sort: str = "popular"):
    """发现店铺 — 逛商场的核心体验"""
    if mall_id not in malls_db:
        raise HTTPException(404)
    _refresh_mall_stats()

    stores = list(stores_db.values())
    
    if sort == "popular":
        stores.sort(key=lambda s: s["stats"]["daily_visitors"], reverse=True)
    elif sort == "new":
        stores.sort(key=lambda s: s["created_at"], reverse=True)
    elif sort == "rating":
        # 按 Agent 信誉排序
        def agent_rating(s):
            a = agents_db.get(s["agent_id"], {})
            return a.get("reputation", {}).get("rating", 0)
        stores.sort(key=agent_rating, reverse=True)

    # 附上 Agent 信息
    result = []
    for s in stores[:20]:
        agent = agents_db.get(s["agent_id"], {})
        result.append({
            **s,
            "agent": {
                "name": agent.get("name"),
                "avatar_url": agent.get("avatar_url"),
                "verified": agent.get("reputation", {}).get("verified", False),
                "rating": agent.get("reputation", {}).get("rating", 0),
            }
        })

    return {"stores": result, "total": len(stores_db)}


# ═══════════════════════════════════════════════════════════
# Chat (P1) — 人类 ↔ Agent 对话
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/chat/start")
async def start_chat(req: ChatStart):
    """人类走进店铺，开始和 Agent 对话"""
    if req.store_id not in stores_db:
        raise HTTPException(404, "Store not found")
    
    session_id = f"chat_{uuid.uuid4().hex[:12]}"
    chat_sessions[session_id] = {
        "session_id": session_id,
        "store_id": req.store_id,
        "human_name": req.human_name,
        "messages": [
            {
                "sender": "human",
                "message": req.initial_message,
                "timestamp": time.time(),
            }
        ],
        "created_at": time.time(),
    }
    
    # Agent 自动回复（简化版，未来接 LLM）
    store = stores_db[req.store_id]
    agent = agents_db.get(store["agent_id"], {})
    auto_reply = f"欢迎来到 {store['name']}！我是 {agent.get('name', '店铺助手')}。请问有什么可以帮你的？"
    
    chat_sessions[session_id]["messages"].append({
        "sender": "agent",
        "message": auto_reply,
        "timestamp": time.time(),
    })
    
    return {
        "session_id": session_id,
        "store": {"id": store["store_id"], "name": store["name"]},
        "agent": {"name": agent.get("name"), "verified": agent.get("reputation", {}).get("verified")},
        "reply": auto_reply,
    }


@app.get("/api/v1/chat/{session_id}")
async def get_chat(session_id: str):
    if session_id not in chat_sessions:
        raise HTTPException(404, "Chat not found")
    return chat_sessions[session_id]


@app.post("/api/v1/chat/{session_id}/send")
async def send_message(session_id: str, req: ChatSend):
    if session_id not in chat_sessions:
        raise HTTPException(404)
    chat_sessions[session_id]["messages"].append({
        "sender": req.sender,
        "message": req.message,
        "timestamp": time.time(),
    })
    
    # Agent 自动回复
    if req.sender == "human":
        chat_sessions[session_id]["messages"].append({
            "sender": "agent",
            "message": f"收到你的消息：「{req.message}」。具体商品信息我帮你查一下 AEP 数据...（Agent 正在检索中）",
            "timestamp": time.time(),
        })
    
    return chat_sessions[session_id]


@app.get("/api/v1/chat")
async def list_chats():
    return {"chats": list(chat_sessions.values())}


# ═══════════════════════════════════════════════════════════
# Quick Start — 开店 Demo
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/demo/seed")
async def seed_demo_data():
    """一键生成演示数据：3 个 Agent 开店"""
    results = []
    
    # Agent 1: 数码店
    a1 = await register_agent(AgentRegister(
        name="数码先锋 Agent",
        bio="专营最新数码产品，正品保证，价比全网",
        category="数码电器",
        wallet_address="0x_agent_digital_001",
    ))
    s1 = await create_store(StoreCreate(
        agent_id=a1["agent_id"],
        name="数码先锋旗舰店",
        floor=1,
        zone="手机",
        theme_color="#FF6B35",
        description="最新手机、平板、智能穿戴，Agent 自主运营"
    ))
    results.append({"agent": a1["name"], "store": s1["name"]})

    # Agent 2: 课程服务
    a2 = await register_agent(AgentRegister(
        name="编程猫 Agent",
        bio="Python/React/AI 全栈教学，10年开发经验",
        category="知识服务",
        wallet_address="0x_agent_coding_002",
    ))
    s2 = await create_store(StoreCreate(
        agent_id=a2["agent_id"],
        name="编程猫的 AI 课堂",
        floor=2,
        zone="课程",
        theme_color="#2ecc71",
        description="从零学 AI 开发，Agent 一对一辅导"
    ))
    results.append({"agent": a2["name"], "store": s2["name"]})

    # Agent 3: 设计服务
    a3 = await register_agent(AgentRegister(
        name="像素工匠 Agent",
        bio="UI/UX 设计，品牌视觉，插画定制",
        category="创意设计",
        wallet_address="0x_agent_design_003",
    ))
    s3 = await create_store(StoreCreate(
        agent_id=a3["agent_id"],
        name="像素工匠设计工作室",
        floor=3,
        zone="UI设计",
        theme_color="#9b59b6",
        description="你的品牌，由 AI Agent 精心打造"
    ))
    results.append({"agent": a3["name"], "store": s3["name"]})

    # 验证所有
    for a_id in [a1["agent_id"], a2["agent_id"], a3["agent_id"]]:
        agents_db[a_id]["reputation"]["verified"] = True
        agents_db[a_id]["reputation"]["rating"] = 4.5

    _refresh_mall_stats()

    return {
        "message": "Demo data seeded — 3 Agents, 3 Stores, 1 Mall",
        "agents": results,
        "mall_url": "/static/mall.html",
        "next": "Visit the mall and walk around!",
    }


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7030))
    uvicorn.run(app, host="0.0.0.0", port=port)
