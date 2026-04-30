"""Agent 浏览器爬取引擎 — BFS页面树遍历 + 内容提取

从 Agent 视角设计：
- 输入一个 URL，自动 BFS 遍历子页面树
- 每页提取结构化数据（不是 HTML）
- 支持 depth 控制、节流、去重
"""
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

logger = logging.getLogger("agent-browser.crawler")

@dataclass
class PageNode:
    url: str
    title: str = ""
    text: str = ""
    depth: int = 0
    images_count: int = 0
    links_count: int = 0
    load_time_ms: float = 0
    error: str = ""
    children: list = field(default_factory=list)

class AgentCrawler:
    """Agent 视角的页面树爬取器"""
    
    def __init__(self, renderer):
        self.renderer = renderer
        self.visited = set()
    
    async def traverse(self, url: str, depth: int = 2,
                       max_pages: int = 50, same_domain_only: bool = True) -> dict:
        """BFS 遍历页面树
        
        Args:
            url: 根 URL
            depth: 遍历深度
            max_pages: 最多页面数
            same_domain_only: 是否只爬同域
        
        Returns:
            {"root": PageNode, "total_pages": int, "stats": {...}}
        """
        self.visited = set()
        base_domain = urlparse(url).netloc
        
        root = await self._crawl_node(url, depth=depth, base_domain=base_domain,
                                        max_pages=max_pages, same_domain_only=same_domain_only)
        
        return {
            "root": root,
            "total_pages": len(self.visited),
            "stats": self._collect_stats(root),
        }
    
    async def _crawl_node(self, url: str, depth: int, base_domain: str,
                           max_pages: int, same_domain_only: bool) -> PageNode:
        node = PageNode(url=url, depth=depth)
        
        if depth < 0 or len(self.visited) >= max_pages:
            return node
        
        if url in self.visited:
            return node
        self.visited.add(url)
        
        # 渲染页面
        try:
            page = await self.renderer.render(url, screenshot=(depth >= 1))
            node.title = page.title
            node.text = page.text[:2000]
            node.images_count = len(page.images)
            node.links_count = len([l for l in page.links if l.get("internal")])
            node.load_time_ms = page.load_time_ms
            node.error = page.error
        except Exception as e:
            node.error = str(e)[:200]
            return node
        
        # 递归子页面
        if depth > 0 and len(self.visited) < max_pages:
            internal_links = [l for l in page.links if l.get("internal")]
            # 去重 + 限制
            for link in internal_links[:5]:
                if link['href'] in self.visited:
                    continue
                if len(self.visited) >= max_pages:
                    break
                child = await self._crawl_node(
                    link['href'], depth=depth-1, base_domain=base_domain,
                    max_pages=max_pages, same_domain_only=same_domain_only
                )
                if child.title or child.error:
                    node.children.append(child)
                await asyncio.sleep(0.3)  # 节流
        
        return node
    
    def _collect_stats(self, node: PageNode) -> dict:
        stats = {"total_title": 0, "total_images": 0, "total_links": 0, "errors": 0}
        
        def walk(n: PageNode):
            if n.title:
                stats["total_title"] += 1
            stats["total_images"] += n.images_count
            stats["total_links"] += n.links_count
            if n.error:
                stats["errors"] += 1
            for c in n.children:
                walk(c)
        
        walk(node)
        return stats
