"""Agent 浏览器 API 路由

POST /open            - 打开 URL，返回结构化页面数据
POST /traverse        - BFS 遍历页面树
POST /screenshot      - 截图
POST /extract         - 提取结构化数据
POST /compare         - diff 两个页面版本
POST /capture         - 抓取多媒体资源
POST /paginate        - 翻页遍历（多页数据提取）
POST /fill-form       - 识别并填充表单
POST /multi-step      - 多步表单向导
POST /login           - 自动登录 + Session 保持
GET  /sessions        - 列出已保存的 Session
POST /login-check     - 检测页面是否需要登录
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import logging
import json

from services.renderer import get_renderer
from services.crawler import AgentCrawler
from services.extractor import extract_structured_data
from services.pagination import PaginationEngine, PaginationResult
from services.forms import FormEngine, FormResult, MultiStepResult
from services.login import LoginEngine, LoginResult

logger = logging.getLogger("agent-browser.routes")
router = APIRouter(prefix="/api/v1/agent-browser", tags=["Agent Browser"])

# ─── Request Models ───

class OpenRequest(BaseModel):
    url: str = Field(..., description="目标 URL")
    wait_ms: int = Field(default=2000, description="JS渲染等待时间(ms)")
    viewport_width: int = Field(default=1440)
    viewport_height: int = Field(default=900)
    screenshot: bool = Field(default=True, description="是否截图")
    extract_images: bool = Field(default=True, description="是否提取图片")
    extract_forms: bool = Field(default=True, description="是否提取表单")

class TraverseRequest(BaseModel):
    url: str = Field(..., description="根 URL")
    depth: int = Field(default=2, ge=0, le=4, description="遍历深度")
    max_pages: int = Field(default=50, ge=1, le=200, description="最多页面数")
    same_domain_only: bool = Field(default=True)

class CompareRequest(BaseModel):
    url: str = Field(...)
    previous_snapshot: Optional[dict] = Field(default=None, description="上次的页面快照")

class CaptureRequest(BaseModel):
    url: str = Field(...)
    capture_type: str = Field(default="all", description="all | images | videos | screenshots")


# ─── Routes ───

@router.post("/open")
async def open_page(req: OpenRequest):
    """打开 URL 并返回 Agent 可消费的结构化页面数据
    
    返回：
    - page: 页面元数据（标题、文本、OG图、Favicon）
    - images: 图片列表（含懒加载的data-src、CSS背景图）
    - videos: 视频/音频列表
    - forms: 表单元素（Agent 可据此交互）
    - links: 链接列表（同域/跨域分类）
    - tables: HTML 表格数据
    - screenshot_path: 截图文件路径
    - structured: 提取的结构化数据（价格、键值对等）
    """
    renderer = await get_renderer()
    page = await renderer.render(
        url=req.url,
        wait_ms=req.wait_ms,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
        screenshot=req.screenshot,
        extract_images=req.extract_images,
        extract_forms=req.extract_forms,
    )
    
    from dataclasses import asdict
    result = asdict(page)
    
    # 结构化提取
    result["structured"] = extract_structured_data(result)
    
    return {
        "success": not bool(page.error),
        "url": req.url,
        "error": page.error,
        "data": result,
    }


@router.post("/traverse")
async def traverse_pages(req: TraverseRequest):
    """BFS 遍历页面树
    
    Agent 视角：输入根URL，自动递归子页面，返回完整站点地图
    
    返回：
    - root: 根节点（含子节点树）
    - total_pages: 总页面数
    - stats: 统计（标题数、图片数、链接数、错误数）
    """
    renderer = await get_renderer()
    crawler = AgentCrawler(renderer)
    result = await crawler.traverse(
        url=req.url,
        depth=req.depth,
        max_pages=req.max_pages,
        same_domain_only=req.same_domain_only,
    )
    
    return {
        "success": True,
        "url": req.url,
        "total_pages": result["total_pages"],
        "stats": result["stats"],
        "root_title": result["root"].title,
        "root_children_count": len(result["root"].children),
    }


@router.post("/screenshot")
async def take_screenshot(url: str = Query(...), full_page: bool = True):
    """对指定 URL 截图并返回路径"""
    renderer = await get_renderer()
    page = await renderer.render(url, screenshot=True)
    
    return {
        "success": not bool(page.error),
        "url": url,
        "screenshot_path": page.screenshot_path,
        "title": page.title,
        "load_time_ms": page.load_time_ms,
    }


@router.post("/extract")
async def extract_structured(req: OpenRequest):
    """提取页面的结构化数据（价格、键值对、表格、表单等）"""
    renderer = await get_renderer()
    page = await renderer.render(
        url=req.url, wait_ms=req.wait_ms,
        screenshot=False, extract_images=True, extract_forms=True,
    )
    
    from dataclasses import asdict
    result = extract_structured_data(asdict(page))
    
    return {
        "success": not bool(page.error),
        "url": req.url,
        "title": page.title,
        "structured": result,
    }


@router.post("/compare")
async def compare_pages(req: CompareRequest):
    """对比当前页面与之前的快照，检测变更
    
    Agent 监控场景：定期重访同一 URL，发现变化
    """
    renderer = await get_renderer()
    page = await renderer.render(req.url, screenshot=False)
    
    from dataclasses import asdict
    current = asdict(page)
    
    changes = {
        "title_changed": False,
        "text_similarity": 1.0,
        "new_images": 0,
        "new_links": 0,
        "removed_links": 0,
    }
    
    if req.previous_snapshot:
        prev = req.previous_snapshot
        changes["title_changed"] = prev.get("title") != current.get("title")
        
        # 简单文本相似度（Jaccard）
        prev_words = set((prev.get("text", "") or "").split())
        curr_words = set((current.get("text", "") or "").split())
        if prev_words or curr_words:
            intersection = prev_words & curr_words
            union = prev_words | curr_words
            changes["text_similarity"] = len(intersection) / max(len(union), 1)
        
        prev_imgs = len(prev.get("images") or [])
        curr_imgs = len(current.get("images") or [])
        changes["new_images"] = max(0, curr_imgs - prev_imgs)
        
        prev_links = set(l.get("href","") for l in (prev.get("links") or []))
        curr_links = set(l.get("href","") for l in (current.get("links") or []))
        changes["new_links"] = len(curr_links - prev_links)
        changes["removed_links"] = len(prev_links - curr_links)
    
    return {
        "success": True,
        "url": req.url,
        "current_title": page.title,
        "changes": changes,
        "has_changes": changes["title_changed"] or changes["text_similarity"] < 0.95 or changes["new_images"] > 0 or changes["new_links"] > 0,
    }


# ─── Pagination ───

@router.post("/paginate")
async def paginate_pages(req: OpenRequest, max_pages: int = 10):
    """自动翻页遍历 — Agent 视角的分页提取
    
    自动检测"下一页"按钮，逐页提取结构化数据。
    支持：链接翻页、URL参数翻页（?page=N）、分页列表。
    """
    renderer = await get_renderer()
    engine = PaginationEngine()
    
    # 先渲染第一页
    page = await renderer.render(url=req.url, wait_ms=req.wait_ms,
        screenshot=False, extract_images=True, extract_forms=True)
    from dataclasses import asdict
    page_data = asdict(page)
    page_data["structured"] = extract_structured_data(page_data)
    
    result = await engine.paginate(renderer, req.url, page_data, max_pages=max_pages)
    
    return {
        "success": True,
        "url": req.url,
        "total_pages": result.total_pages,
        "pagination_type": result.pagination_type,
        "next_selector": result.next_selector,
        "errors": result.errors,
        "elapsed_ms": result.elapsed_ms,
        "pages": [
            {"page": p["page"], "title": p["data"].get("title", ""),
             "text_length": len(p["data"].get("text", "")),
             "structured": p["data"].get("structured", {})}
            for p in result.pages
        ],
    }


# ─── Form Fill ───

class FormFillRequest(BaseModel):
    url: str = Field(..., description="目标 URL")
    form_index: int = Field(default=0, description="表单序号")
    custom_fields: Optional[Dict[str, str]] = Field(default=None, description="自定义填充值")
    submit: bool = Field(default=True, description="是否提交")
    wait_ms: int = Field(default=1500)

class MultiStepRequest(BaseModel):
    url: str = Field(..., description="表单向导起始 URL")
    steps_data: List[Dict[str, str]] = Field(default=[], description="每步的填充数据")
    max_steps: int = Field(default=5)

@router.post("/fill-form")
async def fill_form(req: FormFillRequest):
    """智能识别并填充表单
    
    Agent 视角：给一个 URL，自动检测表单，根据字段名智能填充，可选提交。
    支持：text/select/checkbox/radio/textarea。
    """
    renderer = await get_renderer()
    engine = FormEngine()
    result = await engine.fill_and_submit(
        renderer, req.url, req.form_index, req.custom_fields, req.submit
    )
    return {
        "success": not bool(result.error),
        "url": req.url,
        "form_id": result.form_id,
        "action": result.action,
        "method": result.method,
        "fields_detected": len(result.fields),
        "fields_filled": result.filled,
        "submitted": result.submitted,
        "response_title": result.response_title,
        "response_text": result.response_text[:500] if result.response_text else "",
        "error": result.error,
        "elapsed_ms": result.elapsed_ms,
    }

@router.post("/multi-step")
async def multi_step_form(req: MultiStepRequest):
    """多步表单向导 — 自动填充多页表单
    
    Agent 视角：注册向导、购物结账等多步流程。
    """
    renderer = await get_renderer()
    engine = FormEngine()
    result = await engine.multi_step_wizard(
        renderer, req.url, req.steps_data, req.max_steps
    )
    return {
        "success": result.completed,
        "url": req.url,
        "total_steps": result.total_steps,
        "completed": result.completed,
        "final_url": result.final_url,
        "elapsed_ms": result.elapsed_ms,
    }


# ─── Login / Session ───

class LoginRequest(BaseModel):
    login_url: str = Field(..., description="登录页 URL")
    username: str = Field(..., description="用户名/邮箱")
    password: str = Field(..., description="密码")
    custom_fields: Optional[Dict[str, str]] = Field(default=None, description="额外字段（验证码等）")

class LoginCheckRequest(BaseModel):
    url: str = Field(..., description="检测页面 URL")

@router.post("/login")
async def login_to_site(req: LoginRequest):
    """自动登录 + Session 持久化
    
    Agent 视角：给定登录页 URL + 凭证，自动检测登录表单、填充、提交，
    保存 Cookie 为 Session 供后续请求使用。
    """
    renderer = await get_renderer()
    engine = LoginEngine()
    result = await engine.login(
        renderer, req.login_url, req.username, req.password, req.custom_fields
    )
    return {
        "success": result.success,
        "login_url": req.login_url,
        "detection_method": result.detection_method,
        "filled_fields": {k: ("***" if "password" in k.lower() else v) for k, v in result.filled_fields.items()},
        "cookies_count": result.cookies_count,
        "session_id": result.session_id,
        "redirect_url": result.redirect_url,
        "response_title": result.response_title,
        "error": result.error,
        "elapsed_ms": result.elapsed_ms,
    }

@router.get("/sessions")
async def list_sessions():
    """列出所有已保存的 Session"""
    engine = LoginEngine()
    sessions = engine.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}

@router.post("/login-check")
async def check_login_needed(req: LoginCheckRequest):
    """检测页面是否需要登录"""
    renderer = await get_renderer()
    engine = LoginEngine()
    login_form = await engine.detect_login_form(renderer, req.url)
    return {
        "url": req.url,
        "login_required": login_form is not None,
        "login_form_detected": login_form is not None,
        "username_field": login_form.get("username_field", {}).get("name") if login_form else None,
        "form_action": login_form.get("form_action") if login_form else None,
    }


@router.post("/capture")
async def capture_media(req: CaptureRequest):
    """抓取页面的多媒体资源（图片、视频、截图）"""
    renderer = await get_renderer()
    page = await renderer.render(req.url, screenshot=True, extract_images=True)
    
    from dataclasses import asdict
    data = asdict(page)
    
    return {
        "success": not bool(page.error),
        "url": req.url,
        "title": page.title,
        "images": data.get("images", [])[:20],
        "videos": data.get("videos", []),
        "screenshot": data.get("screenshot_path", ""),
        "og_image": data.get("og_image", ""),
        "favicon": data.get("favicon", ""),
    }
