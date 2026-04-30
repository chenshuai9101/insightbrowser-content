"""Reliability + Agent Registry → 信任层"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["reliability"])

def register(app):
    app.include_router(router)

@router.get("/reliability/status/{agent_id}")
async def agent_status(agent_id: str):
    return {"agent_id": agent_id, "uptime_pct": 99.9, "rating": 4.8}

@router.post("/reliability/heartbeat")
async def heartbeat(data: dict):
    return {"ack": True}

@router.get("/reliability/leaderboard")
async def leaderboard():
    return {"top": []}

@router.get("/registry/search")
async def registry_search(q: str = ""):
    return {"agents": [], "query": q}
