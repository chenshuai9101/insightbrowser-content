"""Agent Internet Flipbook — L3 Visual Layer API

将 Agent 互联网的结构化数据渲染成人类可浏览的 AI 生成插画页面。

API:
  POST /api/v1/render           → AEP 搜索 + 生成视觉页面
  POST /api/v1/click            → 点击页面区域 → 解析 + AEP 深层查询 + 新页面
  GET  /api/v1/pages/{id}       → 获取已缓存页面
  GET  /api/v1/status           → 服务状态
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn
import logging

from engine import (
    aep_to_visual_page,
    resolve_click,
    fetch_aep_search,
    VisualPage,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flipbook")

app = FastAPI(
    title="Agent Internet Flipbook",
    description="AEP/1.0 → AI Visual Pages. Human-browsable Agent Internet.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 页面缓存
_page_cache: dict[str, VisualPage] = {}


# ═══════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════

class RenderRequest(BaseModel):
    """生成视觉页面请求 — 和 flipbook.page 的接口一致"""
    query: str = Field(..., description="搜索关键词，如 '适合爬山的运动手表'")
    content_type: str = Field(default="", description="AEP 内容类型过滤")
    max_price: Optional[float] = Field(default=None, description="最高价格")
    aspect_ratio: str = Field(default="16:9")
    output_locale: str = Field(default="zh-CN")
    mode: str = Field(default="query", description="'query' | 'tap'")
    # tap mode 参数
    image: Optional[str] = Field(default=None, description="当前页面 base64")
    click_x: Optional[float] = Field(default=None, description="点击 x_pct")
    click_y: Optional[float] = Field(default=None, description="点击 y_pct")
    parent_page_id: Optional[str] = Field(default=None)


class ClickRequest(BaseModel):
    """点击页面区域 → 下一页面"""
    page_id: str = Field(..., description="当前页面 ID")
    x_pct: float = Field(..., ge=0, le=1)
    y_pct: float = Field(..., ge=0, le=1)
    output_locale: str = Field(default="zh-CN")


# ═══════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agent-internet-flipbook",
        "version": "1.0.0",
        "cached_pages": len(_page_cache),
        "aep_backend": os.environ.get("AEP_BASE_URL", "https://agent-insightbrowser-content-1.onrender.com"),
    }


@app.get("/api/v1/status")
async def status():
    """环境检测 — Check 哪些 API Key 配了"""
    import os
    checks = {
        "fal_key": "ok" if os.environ.get("FAL_KEY") else "missing",
        "openrouter_key": "ok" if os.environ.get("OPENROUTER_API_KEY") else "missing",
        "aep_backend": os.environ.get("AEP_BASE_URL", "default"),
    }
    return {"status": "ok", "checks": checks}


# ═══════════════════════════════════════════════════════════
# Render — AEP 搜索 → 视觉页面
# ═══════════════════════════════════════════════════════════

async def _event_stream(body: RenderRequest):
    """SSE 流式生成页面"""
    try:
        # Step 1: AEP 搜索
        yield _sse({"type": "status", "stage": "searching_aep", "query": body.query})

        if body.mode == "tap" and body.image and body.click_x is not None:
            # 点击模式：先解析点击 → 再做 AEP 查询
            yield _sse({"type": "status", "stage": "resolving_click"})
            resolution = await resolve_click(
                image_data_url=body.image,
                x_pct=body.click_x,
                y_pct=body.click_y,
                page_context=f"Previous query: {body.query}",
                output_locale=body.output_locale,
            )
            aep_query = resolution.get("aep_query", body.query)
            yield _sse({"type": "click_resolved", "resolution": resolution})
        else:
            aep_query = body.query

        # Step 2: 生成视觉页面
        yield _sse({"type": "status", "stage": "planning"})
        page = await aep_to_visual_page(
            query=aep_query,
            content_type=body.content_type,
            max_price=body.max_price,
            aspect_ratio=body.aspect_ratio,
            output_locale=body.output_locale,
        )

        # 缓存
        _page_cache[page.page_id] = page

        # Step 3: 返回
        yield _sse({
            "type": "final",
            "page_id": page.page_id,
            "page_title": page.page_title,
            "image_data_url": page.image_data_url,
            "click_regions": [
                {
                    "label": r.label,
                    "x_pct": r.x_pct,
                    "y_pct": r.y_pct,
                    "width_pct": r.width_pct,
                    "height_pct": r.height_pct,
                    "action": r.action,
                    "query": r.query,
                }
                for r in page.click_regions
            ],
            "source_data": [
                {
                    "name": d.name,
                    "price": d.price,
                    "currency": d.currency,
                    "rating": d.rating,
                    "publisher": d.publisher,
                }
                for d in page.source_data
            ],
            "metadata": page.metadata,
        })

    except Exception as e:
        import traceback
        logger.error(f"SSE error: {traceback.format_exc()}")
        yield _sse({"type": "error", "message": str(e)})


def _sse(data: dict) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@app.post("/api/v1/render")
async def render_page(req: RenderRequest):
    """生成视觉页面 (SSE 流式)
    
    和 flipbook.page 的 /sse/generate 接口兼容，
    但数据来自 AEP/1.0 而非 AI 凭空生成。
    """
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════
# Click → Next Page
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/click")
async def click_and_next(req: ClickRequest):
    """点击页面区域 → 识别 → AEP 查询 → 生成下一页"""
    page = _page_cache.get(req.page_id)
    if not page:
        # 页面不在缓存中，只做点击识别
        raise HTTPException(status_code=404, detail="Page not found in cache")

    # 1. 视觉模型识别点击
    resolution = await resolve_click(
        image_data_url=page.image_data_url,
        x_pct=req.x_pct,
        y_pct=req.y_pct,
        page_context=page.page_title,
        output_locale=req.output_locale,
    )

    aep_query = resolution.get("aep_query", page.metadata.get("query", ""))
    content_type = resolution.get("aep_content_type", "")

    # 2. 生成下一页
    next_page = await aep_to_visual_page(
        query=aep_query,
        content_type=content_type,
        output_locale=req.output_locale,
    )

    _page_cache[next_page.page_id] = next_page

    return {
        "click_resolved": resolution,
        "next_page": {
            "page_id": next_page.page_id,
            "page_title": next_page.page_title,
            "image_data_url": next_page.image_data_url,
            "click_regions": [
                {
                    "label": r.label,
                    "x_pct": r.x_pct, "y_pct": r.y_pct,
                    "width_pct": r.width_pct, "height_pct": r.height_pct,
                    "action": r.action, "query": r.query,
                }
                for r in next_page.click_regions
            ],
            "source_data": [
                {"name": d.name, "price": d.price, "rating": d.rating}
                for d in next_page.source_data
            ],
        },
    }


# ═══════════════════════════════════════════════════════════
# Cached Pages
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/pages/{page_id}")
async def get_page(page_id: str):
    """获取已缓存的页面"""
    page = _page_cache.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {
        "page_id": page.page_id,
        "page_title": page.page_title,
        "image_data_url": page.image_data_url,
        "source_data": [
            {"name": d.name, "price": d.price, "rating": d.rating}
            for d in page.source_data
        ],
        "metadata": page.metadata,
    }


@app.get("/api/v1/pages/{page_id}/regions")
async def get_page_regions(page_id: str):
    """获取页面的可点击区域"""
    page = _page_cache.get(page_id)
    if not page:
        raise HTTPException(status_code=404)
    return {
        "page_id": page_id,
        "regions": [
            {
                "label": r.label,
                "x_pct": r.x_pct, "y_pct": r.y_pct,
                "width_pct": r.width_pct, "height_pct": r.height_pct,
                "action": r.action, "query": r.query,
            }
            for r in page.click_regions
        ],
    }


# ═══════════════════════════════════════════════════════════
# Demo — E2E 演示
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/demo/search-phones")
async def demo_search_phones():
    """演示：搜索手机 → 视觉页面
    
    这是完整 E2E 链路的最小示例。
    先拉 AEP 真实数据，再生成可点击插画。
    """
    page = await aep_to_visual_page(
        query="手机",
        content_type="product",
        output_locale="zh-CN",
    )
    _page_cache[page.page_id] = page

    return {
        "page_id": page.page_id,
        "page_title": page.page_title,
        "image_data_url": page.image_data_url[:100] + "...",  # 截断展示
        "click_regions_count": len(page.click_regions),
        "click_regions": [
            {"label": r.label, "action": r.action, "query": r.query}
            for r in page.click_regions
        ],
        "source_data": [
            {"name": d.name, "price": f"¥{d.price}", "rating": d.rating}
            for d in page.source_data
        ],
        "_note": "这些价格、名称来自 AEP/1.0 真实发布者数据，非 AI 编造",
    }


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7025))
    uvicorn.run(app, host="0.0.0.0", port=port)
