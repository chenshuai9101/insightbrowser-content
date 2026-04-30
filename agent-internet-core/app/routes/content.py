"""AEP/1.0 Content + Publish"""
from fastapi import APIRouter, Query
from typing import Optional
import uuid, time

router = APIRouter(prefix="/aep/v1", tags=["content"])
_collections = {}
_items = {}

def register(app):
    app.include_router(router)

# 复制 content 服务的核心逻辑
COLLECTIONS = {
    "af330c3d": {"name":"手机商店","content_type":"product"},
    "bf441d4e": {"name":"在线课程平台","content_type":"course"},
    "cf552e5f": {"name":"科技招聘平台","content_type":"job"},
    "df663f6g": {"name":"技术博客","content_type":"article"},
    "ef774g7h": {"name":"演出票务","content_type":"event"},
}
PRODUCTS = [
    {"name":"iPhone 17 Pro 256GB","price":{"amount":8999,"currency":"CNY"},"type":"product","collection":"手机商店","item_id":"af330c3d-0","availability":"in_stock","data":{"specs":{"chip":"A19 Pro","screen":"6.3英寸","storage":"256GB"},"rating":4.8,"reviews_count":2340},"actions":["order","compare","subscribe"]},
    {"name":"华为 Mate 80 Pro 512GB","price":{"amount":7999,"currency":"CNY"},"type":"product","collection":"手机商店","item_id":"af330c3d-1","availability":"in_stock","data":{"specs":{"chip":"麒麟9100","screen":"6.8英寸","storage":"512GB"},"rating":4.7,"reviews_count":1890},"actions":["order","compare","subscribe"]},
    {"name":"小米 16 Ultra 512GB","price":{"amount":6499,"currency":"CNY"},"type":"product","collection":"手机商店","item_id":"af330c3d-2","availability":"limited","data":{"specs":{"chip":"骁龙8 Gen4","screen":"6.7英寸","storage":"512GB"},"rating":4.6,"reviews_count":1560},"actions":["order","compare","subscribe"]},
    {"name":"iPhone 17e 128GB","price":{"amount":4499,"currency":"CNY"},"type":"product","collection":"手机商店","item_id":"af330c3d-3","availability":"in_stock","data":{"specs":{"chip":"A19","screen":"6.1英寸","storage":"128GB"},"rating":4.5,"reviews_count":3200},"actions":["order","compare","subscribe"]},
    {"name":"Phone Case iPhone 17 Pro","price":{"amount":399,"currency":"CNY"},"type":"product","collection":"手机商店","item_id":"af330c3d-4","availability":"in_stock","data":{"specs":{"material":"硅胶","colors":["黑","蓝","粉"]},"rating":4.4,"reviews_count":8900},"actions":["order","compare","subscribe"]},
]

@router.get("/protocol")
async def get_protocol():
    return {
        "protocol":"AEP/1.0",
        "description":"Agent Endpoint Protocol",
        "types":{
            "product":{"description":"商品","data_fields":["specs","images","variants","reviews_count","rating"],"actions":["order","compare","subscribe"]},
            "article":{"description":"文章/博客","data_fields":["body","author","published_at","tags"],"actions":["read","comment","share"]},
            "service":{"description":"服务","data_fields":["provider","region","specs","availability"],"actions":["order","subscribe"]},
            "job":{"description":"职位","data_fields":["company","salary","location","requirements"],"actions":["apply","save"]},
            "course":{"description":"课程","data_fields":["instructor","duration","level","syllabus"],"actions":["enroll","preview"]},
            "event":{"description":"活动/票务","data_fields":["venue","datetime","capacity","agenda"],"actions":["register","remind"]},
            "dataset":{"description":"数据集","data_fields":["format","size","source","license"],"actions":["download","preview"]},
            "listing":{"description":"分类信息","data_fields":["category","location","condition","contact"],"actions":["contact","save"]},
        }
    }

@router.get("/search")
async def search_aep(query: str = Query(...), type: Optional[str] = None, max_price: Optional[float] = None):
    results = [p for p in PRODUCTS if query in (p.get("name","") + p.get("collection",""))]
    if type:
        results = [r for r in results if r["type"]==type]
    if max_price:
        results = [r for r in results if r["price"]["amount"] <= max_price]
    return {"query":query,"total":len(results),"results":results}

@router.post("/publish")
async def publish(data: dict):
    cid = uuid.uuid4().hex[:8]
    info = {
        "content_type": data.get("content_type","article"),
        "name": data.get("name",""),
        "description": data.get("description",""),
        "publisher": data.get("publisher","anonymous"),
        "collection": data.get("collection","default"),
        "collection_id": cid,
        "price": data.get("price"),
        "actions": data.get("actions",[]),
        "published_at": time.time(),
    }
    _collections[cid] = info
    return {"success":True,"collection_id":cid,"message":"已发布到 Agent 互联网"}

@router.get("/collections")
async def list_collections():
    all_c = list({**COLLECTIONS, **_collections}.values())
    return {"total":len(all_c),"collections":[{"name":c.get("collection",c.get("name","?")),"content_type":c.get("content_type",c.get("type","unknown"))} for c in all_c]}
