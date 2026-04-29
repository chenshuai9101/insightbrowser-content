"""Agent 互联网内容 API — 原生内容发布、搜索、消费

这是 Agent 互联网的"内容层"。
不爬取、不翻译、不桥接。所有内容都是 Agent 原生发布的。
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from services.aep import store, AEP_TYPES

router = APIRouter(prefix="/aep/v1", tags=["Agent Internet Content"])

# ═══════════════════════════════════════════════════════
# 协议发现
# ═══════════════════════════════════════════════════════

@router.get("/protocol")
async def get_protocol():
    """返回 AEP 协议规范，Agent 可以用此了解如何使用"""
    return {
        "protocol": "AEP/1.0",
        "description": "Agent Endpoint Protocol — Agent 互联网原生内容协议",
        "types": {k: v for k, v in AEP_TYPES.items()},
    }


# ═══════════════════════════════════════════════════════
# 内容发布
# ═══════════════════════════════════════════════════════

class PublishRequest(BaseModel):
    publisher: str = Field(..., description="发布者 Agent ID")
    name: str = Field(..., description="集合名称")
    description: str = Field(default="")
    content_type: str = Field(..., description="内容类型: product/article/service/...")
    items: list = Field(default=[], description="资源项列表")

@router.post("/publish")
async def publish_content(req: PublishRequest):
    """发布内容到 Agent 互联网
    
    任何 Agent 都可以直接发布内容。
    不需要建网站，不需要写 HTML。
    只需要按 AEP 协议发结构化数据。
    """
    try:
        coll = store.publish(
            publisher=req.publisher,
            name=req.name,
            description=req.description,
            content_type=req.content_type,
            items=req.items,
        )
        return {
            "success": True,
            "collection_id": coll.collection_id,
            "items_count": len(coll.items),
            "message": f"已发布到 Agent 互联网。Agent 可通过 /aep/v1/search 搜索到你的内容。"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════
# 内容搜索
# ═══════════════════════════════════════════════════════

@router.get("/search")
async def search_content(
    query: str = Query(default="", description="搜索关键词"),
    content_type: str = Query(default="", description="内容类型过滤"),
    max_price: Optional[float] = Query(default=None, description="最高价格"),
    limit: int = Query(default=20),
):
    """Agent 搜索 Agent 互联网上的原生内容
    
    就像人类用 Google 搜网页，Agent 用这个搜 Agent 互联网内容。
    返回的是结构化数据，不是 HTML。
    """
    results = store.search(query=query, content_type=content_type,
                           max_price=max_price, limit=limit)
    return {
        "query": query,
        "total": len(results),
        "results": results,
    }


# ═══════════════════════════════════════════════════════
# 内容详情
# ═══════════════════════════════════════════════════════

@router.get("/collections")
async def list_collections():
    """列出所有已发布的内容集合"""
    return {"total": len(store.collections), "collections": store.list_collections()}


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    """获取指定集合的完整内容"""
    coll = store.get_collection(collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return coll


# ═══════════════════════════════════════════════════════
# Agent 间内容消费实例
# ═══════════════════════════════════════════════════════

@router.get("/consume/cheapest-phone")
async def consumer_example_find_cheapest_phone():
    """Agent 消费示例：帮用户找最便宜的手机
    
    一个真实 Agent 会这样调用：
    1. GET /aep/v1/search?content_type=product&query=手机
    2. 从结果中筛选 price > 0 的
    3. 排序返回最便宜的
    """
    results = store.search(content_type="product", query="手机")
    priced = [r for r in results if r.get("price", {}).get("amount", 0) > 0]
    priced.sort(key=lambda x: x["price"]["amount"])
    
    return {
        "task": "找到 Agent 互联网上最便宜的手机",
        "cheapest": priced[0] if priced else None,
        "top3": priced[:3] if priced else [],
        "sources": list(set(r["_collection"] for r in results)),
        "note": "Agent 直接从 AEP 获取结构化数据，无需解析任何 HTML"
    }


@router.get("/consume/compare-phones")
async def consumer_example_compare_phones():
    """Agent 消费示例：比较手机
    
    直接比较 Agent 互联网上已有数据，跨"店铺"（其实是跨集合）
    """
    results = store.search(content_type="product", query="手机")
    phones = [r for r in results if "Pro" in r.get("name","") or "Ultra" in r.get("name","")]
    
    compare = []
    for p in phones:
        compare.append({
            "name": p["name"],
            "price": p.get("price", {}).get("amount"),
            "rating": p.get("data", {}).get("rating"),
            "reviews": p.get("data", {}).get("reviews_count"),
            "source": p["_collection"],
            "publisher": p["_publisher"],
        })
    
    compare.sort(key=lambda x: x.get("price", 0) or 0)
    
    return {
        "task": "比较 Agent 互联网上的手机",
        "compared": compare,
        "best_value": compare[0] if compare else None,
        "note": "跨'店铺'比较，无需登录多个网站，全是结构化数据"
    }


@router.get("/consume/find-free-course")
async def consumer_example_find_free_course():
    """Agent 消费示例：找免费课程"""
    results = store.search(content_type="course", query="")
    free = [r for r in results if r.get("price", {}).get("amount", 0) == 0]
    
    return {
        "task": "找所有免费课程",
        "free_courses": [{"name": r["name"], "level": r.get("data",{}).get("level"),
                          "instructor": r.get("data",{}).get("instructor")}
                         for r in free],
    }
