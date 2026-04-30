"""Agent Browser — Form Fill & Interaction Engine

为 Agent 提供表单交互能力：
- 自动识别表单字段（input/select/textarea）
- 智能填充（根据字段名/placeholder 推断内容）
- 表单提交 + 结果抓取
- 支持多步表单（wizard/multi-step）
- Cookie/Session 保持（同一 context 内复用）
"""
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urljoin

logger = logging.getLogger("agent-browser.forms")

@dataclass
class FormField:
    """单个表单字段"""
    name: str
    type: str = "text"
    label: str = ""
    placeholder: str = ""
    required: bool = False
    options: List[str] = field(default_factory=list)  # select options
    value: Optional[str] = None

@dataclass
class FormResult:
    url: str
    form_id: str = ""
    action: str = ""
    method: str = "get"
    fields: List[FormField] = field(default_factory=list)
    filled: Dict[str, str] = field(default_factory=dict)
    submitted: bool = False
    response_title: str = ""
    response_text: str = ""
    error: str = ""
    elapsed_ms: float = 0

@dataclass
class MultiStepResult:
    url: str
    steps: List[FormResult] = field(default_factory=list)
    completed: bool = False
    total_steps: int = 0
    final_url: str = ""
    elapsed_ms: float = 0

class FormEngine:
    """Agent 表单交互引擎"""

    # 智能字段映射：根据字段名/placeholder 推断填充内容
    FIELD_INFERENCE = {
        "q": lambda: "search",
        "search": lambda: "search",
        "keyword": lambda: "search",
        "query": lambda: "search",
        "s": lambda: "search",
        "email": lambda: "agent@insightbrowser.app",
        "mail": lambda: "agent@insightbrowser.app",
        "username": lambda: "agent_user",
        "name": lambda: "Agent Browser",
        "firstname": lambda: "Agent",
        "lastname": lambda: "Browser",
        "password": lambda: "Test1234!",
        "pass": lambda: "Test1234!",
        "phone": lambda: "13800138000",
        "tel": lambda: "13800138000",
        "mobile": lambda: "13800138000",
        "city": lambda: "Beijing",
        "address": lambda: "1 Agent Street",
        "zip": lambda: "100000",
        "zipcode": lambda: "100000",
        "postal": lambda: "100000",
        "comment": lambda: "This is an automated message from Agent Browser.",
        "message": lambda: "Automated message from Agent Browser.",
        "feedback": lambda: "Automated feedback from Agent Browser.",
        "min_price": lambda: "0",
        "max_price": lambda: "999999",
        "price_min": lambda: "0",
        "price_max": lambda: "999999",
        "budget_min": lambda: "0",
        "budget_max": lambda: "999999",
        "date_from": lambda: "2026-01-01",
        "date_to": lambda: "2026-12-31",
        "checkin": lambda: "2026-05-01",
        "checkout": lambda: "2026-05-03",
        "guests": lambda: "2",
        "adults": lambda: "2",
        "currency": lambda: "CNY",
        "lang": lambda: "zh-CN",
        "language": lambda: "Chinese",
        "country": lambda: "China",
        "agree": lambda: "on",
        "consent": lambda: "on",
        "subscribe": lambda: "on",
    }

    async def detect_forms(self, renderer, url: str) -> List[dict]:
        """检测页面所有表单"""
        page = await renderer.render(url, wait_ms=1500, extract_forms=True)
        from dataclasses import asdict
        return asdict(page).get("forms", [])

    async def fill_and_submit(self, renderer, url: str,
                              form_index: int = 0,
                              custom_fields: Optional[Dict[str, str]] = None,
                              submit: bool = True) -> FormResult:
        """填充并提交表单

        Args:
            renderer: AgentRenderer 实例
            url: 页面 URL
            form_index: 表单序号（0-based）
            custom_fields: 自定义字段值 {"field_name": "value"}
            submit: 是否提交
        """
        start = time.time()
        result = FormResult(url=url)

        try:
            await renderer._ensure_browser()
            context = await renderer._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="InsightBrowser/2.0 (AgentBrowser)"
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)

            # Step 1: 获取表单列表
            forms = await page.evaluate("""() => {
                return [...document.querySelectorAll('form')].map((f, i) => ({
                    index: i,
                    id: f.id || '',
                    action: f.action || window.location.href,
                    method: (f.method || 'get').toLowerCase(),
                    fields: [...f.querySelectorAll(
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), ' +
                        'select, textarea'
                    )].slice(0, 30).map(el => ({
                        name: el.name || el.id || '',
                        type: el.type || el.tagName.toLowerCase(),
                        label: (() => {
                            // try label[for]
                            if (el.id) {
                                const lbl = document.querySelector('label[for="' + el.id + '"]');
                                if (lbl) return lbl.textContent.trim();
                            }
                            // try parent label
                            const parent = el.closest('label');
                            if (parent) return parent.textContent.replace(el.textContent, '').trim();
                            // try sibling label
                            const prev = el.previousElementSibling;
                            if (prev && prev.tagName === 'LABEL') return prev.textContent.trim();
                            // try placeholder as fallback
                            return el.placeholder || '';
                        })().substring(0, 100),
                        placeholder: (el.placeholder || '').substring(0, 100),
                        required: !!el.required,
                        options: el.tagName === 'SELECT' ?
                            [...el.querySelectorAll('option')].slice(0, 50).map(o => o.value || o.textContent.trim()) : [],
                    }))
                })).filter(f => f.fields.length > 0);
            }""")

            if not forms or form_index >= len(forms):
                result.error = f"No forms found or form_index {form_index} out of range ({len(forms)} forms)"
                await context.close()
                return result

            target_form = forms[form_index]
            result.form_id = target_form["id"]
            result.action = target_form["action"]
            result.method = target_form["method"]

            for f in target_form["fields"]:
                result.fields.append(FormField(
                    name=f["name"],
                    type=f["type"],
                    label=f["label"],
                    placeholder=f["placeholder"],
                    required=f["required"],
                    options=f.get("options", [])
                ))

            # Step 2: 智能填充
            for field in target_form["fields"]:
                name = field["name"]
                if not name:
                    continue

                # 优先使用自定义值
                if custom_fields and name in custom_fields:
                    value = custom_fields[name]
                else:
                    value = self._infer_value(name, field["type"], field["placeholder"], field.get("options", []))

                if value is None:
                    continue

                result.filled[name] = value

                # 执行填充
                if field["type"] == "select" or field["type"] == "select-one":
                    if value in field.get("options", []):
                        await page.select_option(f"[name='{name}']", value)
                elif field["type"] == "checkbox":
                    await page.check(f"[name='{name}']")
                elif field["type"] == "radio":
                    await page.check(f"[name='{name}'][value='{value}']")
                elif field["type"] == "textarea":
                    await page.fill(f"textarea[name='{name}']", value)
                else:
                    await page.fill(f"[name='{name}']", value)

            # Step 3: 提交
            if submit:
                # 点击第一个 submit 按钮
                try:
                    submit_btn = await page.query_selector(
                        "button[type='submit'], input[type='submit'], form button:last-child"
                    )
                    if submit_btn:
                        await submit_btn.click()
                    else:
                        # JS submit
                        await page.evaluate(f"document.forms[{form_index}].submit()")
                except Exception as e:
                    logger.warning(f"Submit click failed: {e}")

                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(1000)

                result.submitted = True
                result.response_title = await page.title()
                result.response_text = await page.evaluate(
                    "() => document.body?.innerText?.substring(0, 5000) || ''"
                )

            await context.close()

        except Exception as e:
            result.error = str(e)[:300]
            logger.error(f"Form fill error for {url}: {e}")

        result.elapsed_ms = (time.time() - start) * 1000
        return result

    def _infer_value(self, name: str, ftype: str, placeholder: str, options: list) -> Optional[str]:
        """智能推断字段值"""
        name_lower = name.lower().strip()

        # 精确匹配
        if name_lower in self.FIELD_INFERENCE:
            return self.FIELD_INFERENCE[name_lower]()

        # 模糊匹配
        for pattern, fn in self.FIELD_INFERENCE.items():
            if pattern in name_lower:
                return fn()

        # 从 placeholder 推断
        if placeholder.lower() in self.FIELD_INFERENCE:
            return self.FIELD_INFERENCE[placeholder.lower()]()

        # Select: 选第一个非空选项
        if ftype in ("select", "select-one") and options:
            for opt in options:
                if opt and opt not in ("", "0"):
                    return opt

        return None

    async def multi_step_wizard(self, renderer, url: str,
                                form_data: List[Dict[str, str]],
                                max_steps: int = 5) -> MultiStepResult:
        """处理多步表单向导

        Args:
            url: 起始 URL
            form_data: 每个步骤的填充数据
            max_steps: 最大步数
        """
        start = time.time()
        result = MultiStepResult(url=url)

        try:
            await renderer._ensure_browser()
            context = await renderer._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="InsightBrowser/2.0 (AgentBrowser)"
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            for step_num in range(min(max_steps, len(form_data) + 1)):
                step_data = form_data[step_num] if step_num < len(form_data) else {}
                step_result = FormResult(url=url)

                # 检测当前表单
                forms = await page.evaluate("""() => {
                    return [...document.querySelectorAll('form')].map(f => ({
                        id: f.id,
                        action: f.action,
                        fields: [...f.querySelectorAll('input:not([type="hidden"]), select, textarea')]
                            .slice(0, 20).map(el => el.name || el.id || '')
                    })).filter(f => f.fields.length > 0);
                }""")

                if not forms:
                    break  # 没有表单了

                step_result.form_id = forms[0]["id"]
                step_result.action = forms[0]["action"]

                # 填充
                for field_name in forms[0]["fields"]:
                    if field_name in step_data:
                        value = step_data[field_name]
                    else:
                        value = self._infer_value(field_name, "text", "", [])
                    if value:
                        step_result.filled[field_name] = value
                        await page.fill(f"[name='{field_name}']", value)

                # 找"下一步"按钮
                next_btn = await page.evaluate("""() => {
                    const btns = [
                        ...document.querySelectorAll('button'),
                        ...document.querySelectorAll('input[type="submit"]')
                    ];
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').trim().toLowerCase();
                        if (t.includes('next') || t.includes('下一步') ||
                            t.includes('continue') || t.includes('继续') ||
                            t.includes('proceed')) {
                            return b.id || b.className || true;
                        }
                    }
                    return null;
                }""")

                if next_btn:
                    try:
                        await page.click(f"button:has-text('Next'), input[value*='next' i], " +
                                        f"button:has-text('下一步'), button:has-text('Continue')")
                    except:
                        await page.evaluate("document.forms[0].submit()")

                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await page.wait_for_timeout(500)

                    step_result.submitted = True
                    step_result.response_title = await page.title()
                    result.steps.append(step_result)
                else:
                    # 可能是最后一步
                    await page.evaluate("document.forms[0].submit()")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    step_result.submitted = True
                    step_result.response_title = await page.title()
                    result.steps.append(step_result)
                    break

            result.completed = len(result.steps) > 0
            result.total_steps = len(result.steps)
            result.final_url = page.url
            await context.close()

        except Exception as e:
            logger.error(f"Multi-step wizard error: {e}")

        result.elapsed_ms = (time.time() - start) * 1000
        return result
