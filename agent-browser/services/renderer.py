"""Agent Browser 渲染引擎 — 基于 Playwright 的 Headless 浏览器服务

为 Agent 提供：
- JS动态渲染（SPA/React/Vue）
- 全页截图（JPEG/PNG）
- 元素级截图
- 懒加载图片提取（data-src/data-lazy-src）
- CSS背景图提取
- 表单交互识别
- 页面文本提取（去标签纯文本）
- Cookie/Session保持
"""
import asyncio
import logging
import base64
import re
from typing import Optional
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, urljoin

logger = logging.getLogger("agent-browser.renderer")

@dataclass
class RenderedPage:
    url: str
    title: str = ""
    text: str = ""
    og_image: str = ""
    favicon: str = ""
    images: list = field(default_factory=list)
    videos: list = field(default_factory=list)
    forms: list = field(default_factory=list)
    headings: list = field(default_factory=list)
    links: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    screenshot_path: str = ""
    load_time_ms: float = 0
    error: str = ""

class AgentRenderer:
    """Agent 专用页面渲染器"""
    
    def __init__(self):
        self._playwright = None
        self._browser = None
    
    async def _ensure_browser(self):
        """懒加载浏览器实例"""
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        logger.info("✅ Playwright browser launched")
    
    async def render(self, url: str, wait_ms: int = 2000,
                     viewport_width: int = 1440, viewport_height: int = 900,
                     screenshot: bool = True, extract_images: bool = True,
                     extract_forms: bool = True) -> RenderedPage:
        """渲染一个 URL，返回 Agent 可消费的结构化数据
        
        Args:
            url: 目标 URL
            wait_ms: JS渲染等待时间(ms)
            viewport_width: 视口宽度
            viewport_height: 视口高度
            screenshot: 是否截图
            extract_images: 是否提取图片
            extract_forms: 是否提取表单
        """
        result = RenderedPage(url=url)
        import time
        start = time.time()
        
        try:
            await self._ensure_browser()
            context = await self._browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                user_agent="InsightBrowser/2.0 (AgentBrowser; +https://insightbrowser.app)"
            )
            page = await context.new_page()
            
            # 加载页面
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(wait_ms / 1000)
            
            # 滚动触发懒加载
            await page.evaluate("""async () => {
                await new Promise(r => {
                    let h = 0;
                    const t = setInterval(() => {
                        window.scrollBy(0, 500);
                        h += 500;
                        if (h >= document.body.scrollHeight) { clearInterval(t); r(); }
                    }, 100);
                });
            }""")
            await asyncio.sleep(0.5)
            
            # 提取
            result.title = await page.title()
            
            # 纯文本
            result.text = (await page.evaluate(
                "() => document.body?.innerText?.substring(0, 10000) || ''"
            )).strip()
            
            # OG Image
            result.og_image = (await page.evaluate("""() => {
                const m = document.querySelector('meta[property="og:image"]');
                return m ? m.getAttribute('content') : '';
            }""")) or ""
            
            # Favicon
            result.favicon = (await page.evaluate("""() => {
                const l = document.querySelector('link[rel*="icon"]');
                if (l) {
                    let href = l.getAttribute('href') || '';
                    if (href && href.startsWith('/')) href = window.location.origin + href;
                    return href;
                }
                return window.location.origin + '/favicon.ico';
            }""")) or ""
            
            # 图片提取
            if extract_images:
                result.images = await page.evaluate("""() => {
                    const imgs = [];
                    const seen = new Set();
                    // <img> tags
                    document.querySelectorAll('img').forEach(img => {
                        let src = img.src || img.getAttribute('data-src') ||
                                  img.getAttribute('data-lazy-src') ||
                                  img.getAttribute('data-original') ||
                                  img.getAttribute('srcset');
                        if (!src || src.startsWith('data:') || src.length < 10) return;
                        if (src.includes(',')) src = src.split(',')[0].trim().split(' ')[0];
                        // resolve relative
                        if (src.startsWith('/')) src = window.location.origin + src;
                        if (!seen.has(src) && src.startsWith('http')) {
                            seen.add(src);
                            imgs.push({
                                src: src,
                                alt: (img.alt || '').substring(0, 200),
                                width: img.naturalWidth || img.width || 0,
                                height: img.naturalHeight || img.height || 0,
                                type: 'img'
                            });
                        }
                    });
                    // CSS background-image
                    document.querySelectorAll('[style*="background-image"]').forEach(el => {
                        const style = el.getAttribute('style') || '';
                        const m = style.match(/url\\(["']?([^)"']+)["']?\\)/);
                        if (m && m[1].startsWith('http') && !seen.has(m[1])) {
                            seen.add(m[1]);
                            imgs.push({src: m[1], alt: '', width: 0, height: 0, type: 'css-bg'});
                        }
                    });
                    // picture > source
                    document.querySelectorAll('picture source').forEach(s => {
                        const srcset = s.getAttribute('srcset') || '';
                        if (srcset) {
                            const first = srcset.split(',')[0].trim().split(' ')[0];
                            if (first && !seen.has(first) && first.startsWith('http')) {
                                seen.add(first);
                                imgs.push({src: first, alt: '', width: 0, height: 0, type: 'picture'});
                            }
                        }
                    });
                    return imgs.slice(0, 50);
                }""")
            
            # 视频
            result.videos = await page.evaluate("""() => {
                const vids = [];
                document.querySelectorAll('video').forEach(v => {
                    vids.push({
                        src: v.src || (v.querySelector('source')||{}).src || '',
                        poster: v.getAttribute('poster') || '',
                        type: 'html5-video'
                    });
                });
                document.querySelectorAll('iframe').forEach(f => {
                    const src = f.src || '';
                    if (src.includes('youtube.com') || src.includes('youtu.be'))
                        vids.push({src, type: 'youtube'});
                    else if (src.includes('vimeo.com'))
                        vids.push({src, type: 'vimeo'});
                    else if (src.includes('bilibili.com'))
                        vids.push({src, type: 'bilibili'});
                });
                document.querySelectorAll('audio').forEach(a => {
                    vids.push({src: a.src || (a.querySelector('source')||{}).src || '', type: 'audio'});
                });
                return vids;
            }""")
            
            # 表单
            if extract_forms:
                result.forms = await page.evaluate("""() => {
                    return [...document.querySelectorAll('form')].map(f => ({
                        action: f.action || window.location.href,
                        method: (f.method || 'get').toLowerCase(),
                        id: f.id || '',
                        inputs: [...f.querySelectorAll('input,select,textarea,button')]
                            .slice(0, 20).map(el => ({
                                name: el.name || el.id || '',
                                type: el.type || el.tagName.toLowerCase(),
                                placeholder: (el.placeholder || '').substring(0, 100),
                                required: !!el.required,
                                tag: el.tagName.toLowerCase()
                            }))
                    })).filter(f => f.inputs.length > 0);
                }""")
            
            # 标题层级
            result.headings = await page.evaluate("""() => {
                return [...document.querySelectorAll('h1,h2,h3')].slice(0, 30).map(h => ({
                    tag: h.tagName.toLowerCase(),
                    text: h.textContent.trim().substring(0, 200)
                }));
            }""")
            
            # 链接（同域 + 跨域分类）
            raw_links = await page.evaluate("""() => {
                return [...document.querySelectorAll('a[href]')].map(a => ({
                    href: a.href,
                    text: a.textContent.trim().substring(0, 100)
                })).filter(l => l.href.startsWith('http'));
            }""")
            base_domain = urlparse(url).netloc
            result.links = []
            for l in raw_links:
                is_internal = urlparse(l['href']).netloc == base_domain
                result.links.append({
                    **l,
                    "internal": is_internal,
                    "type": "page"
                })
            result.links = result.links[:100]
            
            # 表格
            result.tables = await page.evaluate("""() => {
                return [...document.querySelectorAll('table')].slice(0, 10).map((t, i) => ({
                    id: i,
                    caption: (t.querySelector('caption')?.textContent || '').trim(),
                    rows: [...t.querySelectorAll('tr')].slice(0, 50).map(tr =>
                        [...tr.querySelectorAll('td,th')].map(cell =>
                            cell.textContent.trim().substring(0, 200)
                        )
                    )
                })).filter(t => t.rows.length > 0);
            }""")
            
            # 截图
            if screenshot:
                import os, tempfile
                safe = re.sub(r'[^a-zA-Z0-9]', '_', url)[:50]
                import hashlib
                fname = f"/tmp/agent_browser_{hashlib.md5(url.encode()).hexdigest()[:12]}.jpg"
                await page.screenshot(path=fname, full_page=True, type="jpeg", quality=70)
                result.screenshot_path = fname
            
            await context.close()
            result.load_time_ms = (time.time() - start) * 1000
            
        except Exception as e:
            result.error = str(e)[:200]
            logger.error(f"Render error for {url}: {e}")
        
        return result
    
    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

# 全局单例
_renderer: Optional[AgentRenderer] = None

async def get_renderer() -> AgentRenderer:
    global _renderer
    if _renderer is None:
        _renderer = AgentRenderer()
    return _renderer
