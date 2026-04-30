"""Agent Browser — Pagination Engine (Crawlee 驱动)

基于 Crawlee 1.6.3 的 enqueue_links + PlaywrightCrawler：
- 自动检测"下一页"链接并入队
- 支持 URL pattern 翻页
- 同域限制 + 最大页面数
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("agent-browser.pagination")

@dataclass
class PaginationResult:
    url: str
    total_pages: int = 0
    pages: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pagination_type: str = "crawlee_enqueue_links"
    elapsed_ms: float = 0

class PaginationEngine:
    """基于 Crawlee 的翻页引擎"""

    async def paginate(self, url: str, max_pages: int = 10) -> PaginationResult:
        """使用 Crawlee PlaywrightCrawler 自动翻页"""
        import time
        start = time.time()
        result = PaginationResult(url=url)
        pages_data = []

        try:
            from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
            from crawlee import EnqueueStrategy

            crawler = PlaywrightCrawler(
                max_requests_per_crawl=max_pages,
                headless=True,
                request_handler_timeout_secs=30,
            )

            @crawler.request_handler
            async def handler(context: PlaywrightCrawlingContext) -> None:
                title = await context.page.title()
                text = await context.page.evaluate(
                    "() => document.body?.innerText?.substring(0, 10000) || ''"
                )
                pages_data.append({
                    "page": len(pages_data) + 1,
                    "url": context.request.loaded_url or context.request.url,
                    "title": title,
                    "text": text,
                })

                # Crawlee 自动发现并 enqueue "下一页" 链接
                await context.enqueue_links(
                    strategy=EnqueueStrategy.SAME_DOMAIN,
                    label="NEXT_PAGE",
                )

            await crawler.run([url])
            await crawler.close()

        except Exception as e:
            result.errors.append(f"Crawlee pagination failed: {str(e)[:300]}")
            logger.error(f"Crawlee pagination error: {e}")

            # Fallback: 用 legacy 版本
            try:
                from services.pagination_legacy import PaginationEngine as LegacyEngine
                from services.renderer import get_renderer
                renderer = await get_renderer()
                engine = LegacyEngine()
                from dataclasses import asdict
                page = await renderer.render(url=url)
                legacy_result = await engine.paginate(renderer, url, asdict(page), max_pages)
                pages_data = [
                    {"page": p["page"], "url": p["data"].get("url", url),
                     "title": p["data"].get("title", ""),
                     "text": p["data"].get("text", "")}
                    for p in legacy_result.pages
                ]
                result.pagination_type = "legacy_fallback"
            except Exception as e2:
                result.errors.append(f"Legacy fallback also failed: {str(e2)[:200]}")

        result.pages = pages_data
        result.total_pages = len(pages_data)
        result.elapsed_ms = (time.time() - start) * 1000
        return result
