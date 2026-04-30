"""Search + BI + Benchmark → 统一搜索层"""
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1", tags=["search"])

def register(app):
    app.include_router(router)

@router.get("/search")
async def search(q: str = Query(...), source: str = "all"):
    return {"query": q, "source": source, "results": [], "cached": False}

@router.get("/bi/stats")
async def bi_stats():
    return {"requests_24h": 0, "active_users": 0}

@router.get("/benchmark")
async def benchmark():
    return {"latency_p50": 0, "latency_p99": 0}
