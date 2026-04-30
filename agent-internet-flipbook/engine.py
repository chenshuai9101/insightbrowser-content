"""Agent Internet Visual Layer — Flipbook 集成
AEP/1.0 → AI-generated visual browsable pages

L3 视觉交互层：将 Agent 互联网的结构化数据转化为人类可浏览的 AI 生成插画页面。

核心链路：
  AEP/1.0 搜索结果 → LLM 规划页面布局 → 图片模型生成插画
  → 用户点击插画区域 → 视觉模型识别 → AEP/1.0 深层查询 → 下一页

与 flipbook.page 的关键区别：
  - flipbook.page: AI 凭空编造内容
  - 我们的 L3: AI 可视化真实 AEP 数据（价格、配置、评价都来自发布者）
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
import fal_client
from openai import AsyncOpenAI

# ═══════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
VLM_MODEL = "google/gemini-3-flash-preview"        # 点击识别
TEXT_MODEL = "google/gemini-3-flash-preview"       # 页面规划
IMAGE_MODEL = "fal-ai/nano-banana"                  # 图片生成

# AEP/1.0 content service URL
AEP_BASE = os.environ.get("AEP_BASE_URL", "https://agent-insightbrowser-content-1.onrender.com")
AGENT_BROWSER_BASE = os.environ.get("AGENT_BROWSER_URL", "https://agent-browser.onrender.com")


# ═══════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════

@dataclass
class AEPResult:
    """一条 AEP 搜索结果"""
    name: str
    content_type: str
    price: Optional[float] = None
    currency: str = "CNY"
    rating: Optional[float] = None
    specs: dict = field(default_factory=dict)
    publisher: str = ""
    collection_name: str = ""
    description: str = ""

@dataclass
class VisualPage:
    """一页 AI 生成的视觉页面"""
    page_id: str
    page_title: str
    image_data_url: str          # base64 JPEG
    click_regions: list[ClickRegion]  # 可点击区域映射
    source_data: list[AEPResult]  # 底层真实数据
    metadata: dict = field(default_factory=dict)

@dataclass
class ClickRegion:
    """页面上的一个可点击区域"""
    label: str                    # 显示的文字
    x_pct: float                  # 归一化坐标 0-1
    y_pct: float
    width_pct: float
    height_pct: float
    action: str                   # "search" | "detail" | "compare" | "buy"
    query: str                    # 点击后调 AEP 的搜索词
    aep_content_type: str = ""


# ═══════════════════════════════════════════════════════════
# AEP Data Fetcher
# ═══════════════════════════════════════════════════════════

async def fetch_aep_search(
    query: str,
    content_type: str = "",
    max_price: float | None = None,
    limit: int = 10,
) -> list[AEPResult]:
    """从 Agent 互联网拉取真实结构化数据"""
    params = {"query": query, "limit": limit}
    if content_type:
        params["content_type"] = content_type
    if max_price is not None:
        params["max_price"] = max_price

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{AEP_BASE}/aep/v1/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"AEP search failed: {e}")

    results = []
    for item in data.get("results", []):
        price_info = item.get("price", {})
        results.append(AEPResult(
            name=item.get("name", ""),
            content_type=item.get("_content_type", ""),
            price=price_info.get("amount"),
            currency=price_info.get("currency", "CNY"),
            rating=item.get("data", {}).get("rating"),
            specs=item.get("data", {}).get("specs", {}),
            publisher=item.get("_publisher", ""),
            collection_name=item.get("_collection", ""),
            description=item.get("description", ""),
        ))
    return results


# ═══════════════════════════════════════════════════════════
# LLM Planner — 把 AEP 数据规划成视觉页面
# ═══════════════════════════════════════════════════════════

PAGE_PLANNER_SYSTEM = """You are a visual page designer for the Agent Internet.

You receive STRUCTURED DATA from real publishers (NOT AI-generated text).
Your job: plan a single illustrated diagram page that visualizes this data
for a HUMAN user to browse and explore.

Page layout guidelines:
- Title at top (<=8 words)
- Each data item shown as a distinct visual card/box
- Price prominently displayed
- Key specs as callout labels
- Ratings as visual stars/indicators
- A "compare" area if multiple items

Return JSON:
{
  "page_title": "标题",
  "prompt": "详细绘图描述 (<=120 words, English, for image model)",
  "facts": ["标注1", "标注2", ...],
  "regions": [
    {
      "label": "区域显示文字",
      "x_pct": 0.1, "y_pct": 0.2,
      "width_pct": 0.3, "height_pct": 0.15,
      "action": "detail",
      "query": "点击后搜索词"
    }
  ]
}"""


async def plan_visual_page(
    query: str,
    aep_results: list[AEPResult],
    page_title_hint: str = "",
    output_locale: str = "zh-CN",
) -> dict:
    """LLM 规划：AEP 数据 → 视觉页面蓝图"""
    client = AsyncOpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE,
        default_headers={
            "HTTP-Referer": "https://github.com/chenshuai9101/insightbrowser-content",
            "X-Title": "Agent Internet Flipbook",
        },
    )

    # 构造数据摘要
    data_summary = _format_aep_results(aep_results)

    user_prompt = f"""User query: {query}
Locale: {output_locale}

REAL PUBLISHER DATA (from AEP/1.0 Agent Internet):
{data_summary}

IMPORTANT: All prices, names, specs above are REAL data from publishers.
Do NOT invent or change any values. Visualize exactly this data.

Design the page. For EACH data item in the list, create a clickable region
so the user can tap it to see details. Also create a "compare all" region
if there are 2+ items."""

    if page_title_hint:
        user_prompt = f"Suggested title: {page_title_hint}\n\n{user_prompt}"

    resp = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": PAGE_PLANNER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1200,
    )
    
    raw = resp.choices[0].message.content or "{}"
    return _safe_json(raw)


def _format_aep_results(results: list[AEPResult]) -> str:
    lines = []
    for i, r in enumerate(results):
        parts = [f"{i+1}. {r.name}"]
        if r.price is not None:
            parts.append(f"¥{r.price}")
        if r.rating:
            parts.append(f"⭐{r.rating}")
        if r.specs:
            specs_str = ", ".join(f"{k}:{v}" for k, v in list(r.specs.items())[:5])
            parts.append(f"[{specs_str}]")
        parts.append(f"(publisher:{r.publisher})")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# Image Generator
# ═══════════════════════════════════════════════════════════

async def generate_page_image(
    prompt: str,
    aspect_ratio: str = "16:9",
) -> tuple[bytes, str]:
    """用 fal-ai 生成页面插画"""
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        raise RuntimeError("FAL_KEY not set")
    os.environ["FAL_KEY"] = fal_key

    result = await fal_client.subscribe_async(
        IMAGE_MODEL,
        arguments={"prompt": prompt, "aspect_ratio": aspect_ratio},
        with_logs=False,
    )
    images = result.get("images", [])
    if not images:
        raise RuntimeError("Image generation returned no images")
    
    url = images[0].get("url")
    mime = images[0].get("content_type", "image/jpeg")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content, mime


# ═══════════════════════════════════════════════════════════
# Click Resolver — 视觉模型识别用户点击了什么
# ═══════════════════════════════════════════════════════════

CLICK_RESOLVER_SYSTEM = """You examine an AI-generated illustration that visualizes
real products/services from the Agent Internet. A red crosshair marks where the user
tapped. Return JSON with:

- "subject": 2-8 word noun phrase naming what's under the crosshair
- "aep_query": what AEP/1.0 search query to run next
- "aep_content_type": "product" | "service" | "course" | "article" | ""
- "action": "detail" | "compare" | "search" | "buy"

Return: {"subject": "...", "aep_query": "...", "aep_content_type": "...", "action": "..."}"""


async def resolve_click(
    image_data_url: str,
    x_pct: float,
    y_pct: float,
    page_context: str = "",
    output_locale: str = "zh-CN",
) -> dict:
    """视觉模型识别：用户点击了什么 → 下一步查什么"""
    client = AsyncOpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE,
        default_headers={
            "HTTP-Referer": "https://github.com/chenshuai9101/insightbrowser-content",
            "X-Title": "Agent Internet Flipbook",
        },
    )

    resp = await client.chat.completions.create(
        model=VLM_MODEL,
        messages=[
            {"role": "system", "content": CLICK_RESOLVER_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Page context: {page_context}\n"
                            f"Click position: x={x_pct:.3f}, y={y_pct:.3f} (0-1, origin top-left)\n"
                            f"Output locale: {output_locale}\n"
                            "What did the user tap, and what AEP query should follow?"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url, "detail": "high"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=200,
    )
    raw = resp.choices[0].message.content or "{}"
    return _safe_json(raw)


# ═══════════════════════════════════════════════════════════
# E2E Pipeline: AEP → Visual Page
# ═══════════════════════════════════════════════════════════

async def aep_to_visual_page(
    query: str,
    content_type: str = "",
    max_price: float | None = None,
    aspect_ratio: str = "16:9",
    output_locale: str = "zh-CN",
) -> VisualPage:
    """完整管线：AEP 搜索 → LLM 规划 → 图片生成 → 可点击页面"""
    
    # Step 1: 从 Agent 互联网拉取真实数据
    aep_results = await fetch_aep_search(query, content_type, max_price)

    # Step 2: LLM 规划页面
    plan = await plan_visual_page(query, aep_results, output_locale=output_locale)
    
    composed_prompt = plan.get("prompt", query)
    if plan.get("facts"):
        composed_prompt += "\n\nLabels to include:\n" + "\n".join(
            f"- {f}" for f in plan["facts"]
        )
    
    # Step 3: 生成图片
    jpeg_bytes, mime = await generate_page_image(composed_prompt, aspect_ratio)
    data_url = f"data:{mime};base64,{base64.b64encode(jpeg_bytes).decode()}"

    # Step 4: 映射可点击区域
    regions = []
    for r in plan.get("regions", []):
        regions.append(ClickRegion(
            label=r.get("label", ""),
            x_pct=r.get("x_pct", 0),
            y_pct=r.get("y_pct", 0),
            width_pct=r.get("width_pct", 0),
            height_pct=r.get("height_pct", 0),
            action=r.get("action", "detail"),
            query=r.get("query", ""),
            aep_content_type=r.get("aep_content_type", content_type),
        ))

    page_id = hashlib.sha256(f"{query}:{time.time()}".encode()).hexdigest()[:12]

    return VisualPage(
        page_id=page_id,
        page_title=plan.get("page_title", query),
        image_data_url=data_url,
        click_regions=regions,
        source_data=aep_results,
        metadata={
            "query": query,
            "aep_results_count": len(aep_results),
            "image_model": IMAGE_MODEL,
            "planner_model": TEXT_MODEL,
            "generated_at": time.time(),
        },
    )


# ═══════════════════════════════════════════════════════════
# Utils
# ═══════════════════════════════════════════════════════════

def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}
