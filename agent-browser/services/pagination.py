"""Agent Browser — Pagination Engine

为 Agent 提供翻页能力：
- 自动检测"下一页"按钮/链接
- 多页遍历，逐页提取结构化数据
- 支持 URL pattern 翻页（?page=N）
- 支持 Infinite scroll 触发
"""
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("agent-browser.pagination")

@dataclass
class PaginationResult:
    url: str
    total_pages: int = 0
    pages: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    next_selector: str = ""
    pagination_type: str = "unknown"  # link, button, url_pattern, infinite_scroll
    elapsed_ms: float = 0

class PaginationEngine:
    """Agent 分页引擎"""

    async def paginate(self, renderer, url: str, base_result: dict,
                       max_pages: int = 10, same_domain: bool = True) -> PaginationResult:
        """对 URL 执行分页遍历

        Args:
            renderer: AgentRenderer 实例
            url: 起始 URL
            base_result: 第一页的结构化数据
            max_pages: 最大翻页数
            same_domain: 是否限同域
        """
        start = time.time()
        result = PaginationResult(url=url)
        result.pages.append({"page": 1, "data": base_result})

        base_domain = urlparse(url).netloc

        # Step 1: 检测翻页方式
        next_info = await self._detect_next(renderer, url, base_result)
        result.next_selector = next_info.get("selector", "")
        result.pagination_type = next_info.get("type", "unknown")

        if not next_info["has_next"]:
            result.total_pages = 1
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        # Step 2: 逐页遍历
        current_url = url
        for page_num in range(2, max_pages + 1):
            try:
                next_url = await self._get_next_url(
                    renderer, current_url, next_info, page_num, base_domain
                )
                if not next_url:
                    break
                if not same_domain and urlparse(next_url).netloc != base_domain:
                    break

                page = await renderer.render(next_url, wait_ms=1500)
                from dataclasses import asdict
                page_data = asdict(page)

                from services.extractor import extract_structured_data
                page_data["structured"] = extract_structured_data(page_data)

                result.pages.append({"page": page_num, "data": page_data})
                current_url = next_url

                # 每翻一页重新检测下一页（有些网站翻页结构会变）
                next_info = await self._detect_next(renderer, current_url, page_data)

            except Exception as e:
                result.errors.append(f"Page {page_num}: {str(e)[:200]}")
                break

        result.total_pages = len(result.pages)
        result.elapsed_ms = (time.time() - start) * 1000
        logger.info(f"Pagination done: {result.pagination_type}, {result.total_pages} pages, {result.elapsed_ms:.0f}ms")
        return result

    async def _detect_next(self, renderer, url: str, page_data: dict) -> dict:
        """检测页面翻页方式"""
        page = await renderer.render(url, wait_ms=1000)

        # 1. 按 className/text 找"下一页"按钮
        next_btn = await page.page.evaluate("""() => {
            const candidates = [
                ...document.querySelectorAll('a'),
                ...document.querySelectorAll('button'),
                ...document.querySelectorAll('[class*="pagination"] a'),
                ...document.querySelectorAll('[class*="pagination"] button'),
                ...document.querySelectorAll('[class*="page"] a'),
                ...document.querySelectorAll('[class*="page"] button'),
                ...document.querySelectorAll('[rel="next"]'),
                ...document.querySelectorAll('[aria-label*="next"],[aria-label*="Next"]'),
                ...document.querySelectorAll('[aria-label*="下一页"]'),
            ];
            for (const el of candidates) {
                if (!el) continue;
                const text = (el.textContent || '').trim().toLowerCase();
                const cls = (el.className || '').toLowerCase();
                const rel = (el.getAttribute('rel') || '').toLowerCase();
                if (text === 'next' || text === '下一页' || text === '>' ||
                    text === '›' || text === '»' || text === 'next page' ||
                    text === '下一頁' || text === '次へ' ||
                    cls.includes('next') || cls.includes('pagination-next') ||
                    cls.includes('page-next') || rel === 'next') {
                    return {
                        selector: (el.href) ? 'a[href]' : 'button',
                        href: el.href || '',
                        text: text,
                        type: el.href ? 'link' : 'button'
                    };
                }
            }
            return null;
        }""")

        if next_btn:
            return {
                "has_next": True,
                "type": next_btn["type"],
                "selector": next_btn["selector"],
                "href_template": next_btn["href"],
                "next_text": next_btn["text"]
            }

        # 2. 检测 URL pattern (?page=N / &page=N / /page/N)
        import re
        url_pattern_match = re.search(r'[?&]page=(\d+)', url)
        if url_pattern_match:
            import urllib.parse
            parsed = list(urllib.parse.urlparse(url))
            return {
                "has_next": True,
                "type": "url_pattern",
                "pattern_type": "query_param",
                "base_url": url,
                "param_name": "page",
                "current_page": int(url_pattern_match.group(1))
            }

        # 3. 检测分页列表（<ul class="pagination">）
        has_pagination_list = await page.page.evaluate("""() => {
            const ul = document.querySelector(
                'ul[class*="pagination"], ul.pager, div.pagination, nav.pagination'
            );
            if (!ul) return false;
            const links = ul.querySelectorAll('a[href]');
            for (const a of links) {
                const text = a.textContent.trim();
                const href = a.href;
                if (/\\d+/.test(text) && href !== window.location.href) {
                    return true;
                }
            }
            return false;
        }""")

        if has_pagination_list:
            return {
                "has_next": True,
                "type": "pagination_list",
                "selector": "ul[class*='pagination'] a"
            }

        return {"has_next": False, "type": "unknown"}

    async def _get_next_url(self, renderer, current_url: str,
                            next_info: dict, page_num: int, base_domain: str) -> Optional[str]:
        """获取下一页 URL"""
        ptype = next_info["type"]

        if ptype == "link":
            page = await renderer.render(current_url, wait_ms=800)
            next_href = await page.page.evaluate("""() => {
                const candidates = [
                    ...document.querySelectorAll('a'),
                    ...document.querySelectorAll('[rel="next"]'),
                    ...document.querySelectorAll('[aria-label*="next"]'),
                    ...document.querySelectorAll('[aria-label*="下一页"]'),
                ];
                for (const el of candidates) {
                    const text = (el.textContent || '').trim().toLowerCase();
                    const cls = (el.className || '').toLowerCase();
                    const rel = (el.getAttribute('rel') || '').toLowerCase();
                    if (text === 'next' || text === '下一页' || text === '>' ||
                        text === '›' || text === '»' || cls.includes('next') ||
                        cls.includes('pagination-next') || rel === 'next') {
                        return el.href || '';
                    }
                }
                return '';
            }""")
            if next_href and next_href != current_url:
                return urljoin(current_url, next_href)

        elif ptype == "url_pattern":
            import re, urllib.parse
            parsed = list(urllib.parse.urlparse(current_url))
            query = urllib.parse.parse_qs(parsed[4])
            if next_info.get("param_name"):
                query[next_info["param_name"]] = [str(page_num)]
            else:
                # try common params
                for p in ["page", "p", "pg"]:
                    if p in query:
                        query[p] = [str(page_num)]
                        break
            parsed[4] = urllib.parse.urlencode(query, doseq=True)
            return urllib.parse.urlunparse(parsed)

        elif ptype in ("pagination_list", "button"):
            page = await renderer.render(current_url, wait_ms=800)
            next_href = await page.page.evaluate(f"""(pageNum) => {{
                const containers = document.querySelectorAll(
                    'ul[class*="pagination"], ul.pager, div.pagination, nav.pagination,' +
                    '[class*="pagination"]'
                );
                for (const c of containers) {{
                    const links = c.querySelectorAll('a[href]');
                    for (const a of links) {{
                        if (a.textContent.trim() === String(pageNum)) {{
                            return a.href;
                        }}
                    }}
                }}
                // fallback: find any pagination link with page number
                const allLinks = document.querySelectorAll('a[href*="page="], a[href*="p="], a[href*="pg="]');
                for (const a of allLinks) {{
                    const url = new URL(a.href);
                    if (url.searchParams.get('page') === String(pageNum) ||
                        url.searchParams.get('p') === String(pageNum) ||
                        url.searchParams.get('pg') === String(pageNum)) {{
                        return a.href;
                    }}
                }}
                return '';
            }}""")
            if next_href and next_href != current_url:
                return urljoin(current_url, next_href)

        return None
