"""Agent 浏览器内容提取器 — 结构化数据提取

从渲染后的页面文本中提取 Agent 真正需要的结构化数据：
- 价格识别（¥ / $ 模式）
- 商品信息提取
- 关键数据点
"""
import re
import logging
from typing import Optional

logger = logging.getLogger("agent-browser.extractor")

# 价格模式
PRICE_PATTERNS = [
    (r'¥\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "CNY"),
    (r'￥\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "CNY"),
    (r'CN¥\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "CNY"),
    (r'\$\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "USD"),
    (r'(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\s*元', "CNY"),
    (r'RMB\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "CNY"),
    (r'€\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "EUR"),
    (r'£\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "GBP"),
    (r'(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)元起', "CNY"),
    (r'起售价.*?RMB\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', "CNY"),
]

def extract_prices(text: str) -> list:
    """从文本中提取所有价格"""
    prices = []
    seen = set()
    for pattern, currency in PRICE_PATTERNS:
        for m in re.finditer(pattern, text):
            val = m.group(1).replace(",", "")
            key = f"{currency}{val}"
            if key not in seen:
                seen.add(key)
                prices.append({
                    "amount": float(val),
                    "currency": currency,
                    "context": text[max(0,m.start()-30):m.end()+30].strip()
                })
    # 排序
    if prices:
        prices.sort(key=lambda x: x["amount"])
    return prices[:30]

def extract_key_value_pairs(text: str) -> list:
    """提取 '键: 值' 或 '键：值' 模式的结构化数据"""
    pairs = []
    for m in re.finditer(r'([^\n]{1,30})[：:]\s*([^\n]{1,100})', text):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if key and val and len(key) < 20 and len(val) > 1:
            pairs.append({"key": key, "value": val})
    return pairs[:30]

def extract_structured_data(rendered_page: dict) -> dict:
    """从渲染结果中提取 Agent 需要的结构化数据
    
    Args:
        rendered_page: Renderer 输出 (RenderedPage asdict)
    
    Returns:
        结构化数据字典
    """
    text = rendered_page.get("text", "")
    title = rendered_page.get("title", "")
    headings = rendered_page.get("headings", [])
    images = rendered_page.get("images", [])
    tables = rendered_page.get("tables", [])
    
    result = {
        "page_info": {
            "title": title,
            "url": rendered_page.get("url", ""),
            "load_time_ms": rendered_page.get("load_time_ms", 0),
        },
        "prices": extract_prices(text),
        "key_values": extract_key_value_pairs(text),
        "structured_tables": tables,
        "headline_hierarchy": headings,
        "media_summary": {
            "images": len(images),
            "videos": len(rendered_page.get("videos", [])),
            "forms": len(rendered_page.get("forms", [])),
            "has_screenshot": bool(rendered_page.get("screenshot_path")),
            "og_image": rendered_page.get("og_image", ""),
        },
        "interactive_elements": {
            "forms": rendered_page.get("forms", []),
            "links_count": len(rendered_page.get("links", [])),
        },
        "text_stats": {
            "char_count": len(text),
            "line_count": text.count('\n') + 1,
            "word_count_zh": len(re.findall(r'[\u4e00-\u9fff]', text)),
        }
    }
    
    return result
