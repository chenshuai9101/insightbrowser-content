"""Agent Browser — Session Pool + Login Engine (Crawlee 1.6.3 驱动)

基于 Crawlee SessionPool：
- 自动 Cookie/Session 管理
- 智能登录表单检测 + 提交
- 有 legacy fallback
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("agent-browser.sessions")

@dataclass
class LoginResult:
    url: str
    success: bool = False
    session_id: str = ""
    cookies_count: int = 0
    error: str = ""
    elapsed_ms: float = 0

class SessionPoolEngine:
    """Crawlee SessionPool 封装"""

    async def login(self, login_url: str, username: str, password: str) -> LoginResult:
        import time
        start = time.time()
        result = LoginResult(url=login_url)

        try:
            from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
            from crawlee.sessions import SessionPool

            pool = SessionPool(max_pool_size=1)
            session = await pool.get_session()
            login_done = False
            cookies_count = 0

            crawler = PlaywrightCrawler(
                max_requests_per_crawl=1,
                headless=True,
                session_pool=pool,
            )

            @crawler.request_handler
            async def handler(context: PlaywrightCrawlingContext) -> None:
                nonlocal login_done, cookies_count
                page = context.page
                await page.goto(login_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1500)

                # 检测用户名 + 密码字段
                username_sel = await page.evaluate("""() => {
                    const keywords = ['username','user','email','login','account','phone','mobile'];
                    for (const el of document.querySelectorAll('input:not([type="hidden"])')) {
                        const n = (el.name || el.id || '').toLowerCase();
                        if (keywords.some(k => n.includes(k))) return el.name || el.id;
                    }
                    return '';
                }""")
                pwd_el = await page.query_selector("input[type='password']")

                if username_sel and pwd_el:
                    await page.fill(f"[name='{username_sel}']", username)
                    pwd_name = await pwd_el.get_attribute("name") or ""
                    await page.fill(f"[name='{pwd_name}']", password)
                    try:
                        await page.click("button[type='submit'], input[type='submit']")
                    except:
                        await page.evaluate("document.forms[0].submit()")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    login_done = True
                    cookies = await context.page.context.cookies()
                    cookies_count = len(cookies)

            await crawler.run([login_url])
            await crawler.close()

            if login_done:
                result.success = True
                result.session_id = session.id if session else ""
                result.cookies_count = cookies_count
            else:
                result.error = "No login form detected"

        except Exception as e:
            # Fallback to legacy
            try:
                from services.login import LoginEngine
                from services.renderer import get_renderer
                renderer = await get_renderer()
                engine = LoginEngine()
                legacy_result = await engine.login(renderer, login_url, username, password)
                result.success = legacy_result.success
                result.session_id = legacy_result.session_id
                result.cookies_count = legacy_result.cookies_count
            except Exception as e2:
                result.error = f"Crawlee: {str(e)[:100]} | Legacy: {str(e2)[:100]}"

        result.elapsed_ms = (time.time() - start) * 1000
        return result
