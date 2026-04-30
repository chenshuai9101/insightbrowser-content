"""Agent Browser — Login & Session Management Engine

为 Agent 提供登录能力：
- 自动检测登录表单
- 智能填充凭证
- Cookie/Session 持久化
- 登录状态检测
- OAuth/Social 登录支持（基础）
"""
import logging
import time
import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger("agent-browser.login")

@dataclass
class LoginResult:
    url: str
    success: bool = False
    detection_method: str = "unknown"  # form_detection, cookie_check, url_check
    form_fields: List[Dict[str, str]] = field(default_factory=list)
    filled_fields: Dict[str, str] = field(default_factory=dict)
    cookies_count: int = 0
    session_id: str = ""
    redirect_url: str = ""
    response_title: str = ""
    error: str = ""
    elapsed_ms: float = 0

class LoginEngine:
    """Agent 登录引擎"""

    # 常见登录相关关键词
    LOGIN_KEYWORDS = [
        "login", "signin", "log in", "sign in", "登录", "登入",
    ]

    # 常见用户名/密码字段名
    USERNAME_NAMES = [
        "username", "user", "email", "login", "account", "phone", "mobile",
        "userid", "user_id", "login_name", "loginname", "名称", "手机号",
    ]
    PASSWORD_NAMES = [
        "password", "pass", "passwd", "pwd", "pin", "secret", "密码",
    ]

    # 登录成功指示器
    SUCCESS_INDICATORS = [
        "logout", "sign out", "退出", "登出", "my account", "个人中心",
        "dashboard", "profile", "settings", "welcome", "欢迎",
    ]

    def __init__(self, session_dir: str = "/tmp/agent_browser_sessions"):
        self.session_dir = session_dir
        os.makedirs(session_dir, exist_ok=True)

    async def detect_login_form(self, renderer, url: str) -> Optional[dict]:
        """检测页面上的登录表单"""
        page = await renderer.render(url, wait_ms=1500, extract_forms=True)
        from dataclasses import asdict
        page_data = asdict(page)

        forms = page_data.get("forms", [])
        if not forms:
            return None

        for form in forms:
            inputs = form.get("inputs", [])
            input_names = [inp.get("name", "").lower() for inp in inputs]
            input_types = [inp.get("type", "").lower() for inp in inputs]

            # 检测是否为登录表单
            has_username = any(
                any(un in name for un in self.USERNAME_NAMES)
                for name in input_names
            )
            has_password = "password" in input_types

            if has_username and has_password:
                return {
                    "form_action": form.get("action", url),
                    "form_method": form.get("method", "post"),
                    "form_id": form.get("id", ""),
                    "username_field": next(
                        (inp for inp in inputs if any(un in inp.get("name", "").lower() for un in self.USERNAME_NAMES)),
                        None
                    ),
                    "password_field": next(
                        (inp for inp in inputs if inp.get("type") == "password"),
                        None
                    ),
                    "all_inputs": inputs,
                }

        return None

    async def login(self, renderer, login_url: str,
                    username: str, password: str,
                    custom_fields: Optional[Dict[str, str]] = None) -> LoginResult:
        """执行登录

        Args:
            renderer: AgentRenderer 实例
            login_url: 登录页 URL
            username: 用户名
            password: 密码
            custom_fields: 额外填充（如验证码/2FA）
        """
        start = time.time()
        result = LoginResult(url=login_url)

        try:
            await renderer._ensure_browser()
            context = await renderer._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="InsightBrowser/2.0 (AgentBrowser; +https://insightbrowser.app)"
            )
            page = await context.new_page()
            await page.goto(login_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            # Step 1: 检测登录表单
            login_form = await self._detect_form_in_page(page)
            if not login_form:
                # 可能已经登录
                if await self._check_logged_in(page):
                    result.success = True
                    result.detection_method = "already_logged_in"
                    cookies = await context.cookies()
                    result.cookies_count = len(cookies)
                    result.response_title = await page.title()
                    result.redirect_url = page.url
                    await context.close()
                    result.elapsed_ms = (time.time() - start) * 1000
                    return result

                result.error = "No login form detected on page"
                await context.close()
                result.elapsed_ms = (time.time() - start) * 1000
                return result

            result.form_fields = login_form.get("all_inputs", [])
            result.detection_method = "form_detection"

            # Step 2: 填充用户名
            uname_field = login_form["username_field"]
            if uname_field:
                uname_name = uname_field["name"]
                await page.fill(f"[name='{uname_name}']", username)
                result.filled_fields[uname_name] = username

            # Step 3: 填充密码
            pwd_field = login_form["password_field"]
            if pwd_field:
                pwd_name = pwd_field["name"]
                await page.fill(f"[name='{pwd_name}']", password)
                result.filled_fields[pwd_name] = "***"

            # Step 4: 填充自定义字段
            if custom_fields:
                for name, value in custom_fields.items():
                    try:
                        await page.fill(f"[name='{name}']", value)
                        result.filled_fields[name] = value
                    except:
                        pass

            # Step 5: 提交
            try:
                await page.click("button[type='submit'], input[type='submit']")
            except:
                # JS submit
                await page.evaluate("document.forms[0].submit()")

            await page.wait_for_load_state("networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # Step 6: 验证登录结果
            logged_in = await self._check_logged_in(page)

            if logged_in:
                result.success = True
                result.redirect_url = page.url
                result.response_title = await page.title()

                # 保存 session
                cookies = await context.cookies()
                result.cookies_count = len(cookies)
                result.session_id = self._save_session(login_url, cookies)
            else:
                result.error = "Login form submitted but login not detected. Check credentials."
                result.response_title = await page.title()

            await context.close()

        except Exception as e:
            result.error = str(e)[:300]
            logger.error(f"Login error for {login_url}: {e}")

        result.elapsed_ms = (time.time() - start) * 1000
        return result

    async def login_with_session(self, renderer, url: str, session_id: str) -> Optional[dict]:
        """使用已保存的 session 访问页面"""
        cookies = self._load_session(session_id)
        if not cookies:
            return None

        await renderer._ensure_browser()
        context = await renderer._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="InsightBrowser/2.0 (AgentBrowser)"
        )
        await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)

        logged_in = await self._check_logged_in(page)
        title = await page.title()

        await context.close()

        return {
            "logged_in": logged_in,
            "title": title,
            "session_valid": logged_in,
        }

    async def _detect_form_in_page(self, page) -> Optional[dict]:
        """在页面中检测登录表单"""
        forms = await page.evaluate("""() => {
            return [...document.querySelectorAll('form')].map(f => ({
                id: f.id || '',
                action: f.action || window.location.href,
                method: (f.method || 'get').toLowerCase(),
                inputs: [...f.querySelectorAll('input:not([type="hidden"]), select, textarea')]
                    .slice(0, 20).map(el => ({
                        name: el.name || el.id || '',
                        type: el.type || el.tagName.toLowerCase(),
                        placeholder: (el.placeholder || '').substring(0, 100),
                        required: !!el.required,
                        tag: el.tagName.toLowerCase()
                    }))
            })).filter(f => f.inputs.length > 0);
        }""")

        uname_names = self.USERNAME_NAMES

        for form in forms:
            inputs = form["inputs"]
            input_names = [inp["name"].lower() for inp in inputs]
            input_types = [inp["type"] for inp in inputs]

            has_username = any(
                any(un in name for un in uname_names)
                for name in input_names
            )
            has_password = "password" in input_types

            if has_username and has_password:
                return {
                    "form_action": form["action"],
                    "form_method": form["method"],
                    "form_id": form["id"],
                    "username_field": next(
                        (inp for inp in inputs if any(un in inp["name"].lower() for un in uname_names)),
                        None
                    ),
                    "password_field": next(
                        (inp for inp in inputs if inp["type"] == "password"),
                        None
                    ),
                    "all_inputs": inputs,
                }

        return None

    async def _check_logged_in(self, page) -> bool:
        """检测是否已登录"""
        text = (await page.evaluate(
            "() => document.body?.innerText?.substring(0, 2000) || ''"
        )).lower()

        for indicator in self.SUCCESS_INDICATORS:
            if indicator.lower() in text:
                return True

        return False

    def _save_session(self, url: str, cookies: List[dict]) -> str:
        """保存 session cookies 到文件"""
        import hashlib
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.replace(".", "_")
        sid = f"{domain}_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        path = os.path.join(self.session_dir, f"{sid}.json")

        with open(path, "w") as f:
            json.dump({"url": url, "domain": domain, "cookies": cookies}, f, indent=2)

        logger.info(f"Session saved: {sid} ({len(cookies)} cookies)")
        return sid

    def _load_session(self, session_id: str) -> Optional[List[dict]]:
        """加载保存的 session cookies"""
        path = os.path.join(self.session_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        return data.get("cookies", [])

    def list_sessions(self) -> List[dict]:
        """列出所有保存的 session"""
        sessions = []
        for fname in os.listdir(self.session_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.session_dir, fname)
                with open(path) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": fname.replace(".json", ""),
                    "url": data.get("url", ""),
                    "domain": data.get("domain", ""),
                    "cookies_count": len(data.get("cookies", [])),
                })
        return sessions
