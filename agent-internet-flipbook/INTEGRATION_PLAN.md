# Agent 互联网 × Flipbook 集成方案

## 概述

将 flipbook.page 的视觉生成技术集成到 Agent 互联网，构建 **L3 视觉交互层**。

### 核心变化

| | flipbook.page | Agent 互联网 Flipbook |
|:--|:--|:--|
| 数据来源 | AI 凭空编造 | AEP/1.0 真实发布者数据 |
| 价格 | AI 猜的 | 真实价格 |
| 内容 | Gemini 知识库 | 真实商家/创作者发布 |
| 点击 → 下一页 | AI 继续编 | AEP/1.0 搜索真实数据 |

---

## 架构

```
┌─────────────────────────────────────────────────────┐
│                  L3: 视觉交互层                         │
│  insightbrowser-flipbook (7025)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ engine.py   │  │ main.py (API)│  │ index.html │  │
│  │ AEP→Visual  │  │ SSE/Streaming│  │ 人类浏览界面 │  │
│  │ Page管道    │  │ + Click PIP  │  │            │  │
│  └──────┬──────┘  └──────┬───────┘  └────────────┘  │
│         │                │                           │
│    LLM  │  Planner       │  fal-ai                   │
│  OpenRouter            nano-banana                   │
│         │                │                           │
│  VLM Click Resolver     │ Image Generation           │
│  Gemini 3 Flash         │                            │
└─────────┼────────────────┼───────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────┐
│              L2: Agent 互联网内容层                     │
│  AEP/1.0 (7024)                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Content  │  │ Search   │  │ Economy  │          │
│  │ Publish  │  │ Compare  │  │ Wallet   │          │
│  └──────────┘  └──────────┘  └──────────┘          │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│              L1: 基础设施                              │
│  Agent Browser (7022)  ·  Render Hosting             │
│  Crawlee + Playwright ·  数据存储                     │
└─────────────────────────────────────────────────────┘
```

---

## API 端点

### POST /api/v1/render (SSE)
```
输入: { query, content_type?, max_price?, aspect_ratio?, output_locale? }
SSE 事件流:
  → status: { stage: "searching_aep" }
  → status: { stage: "planning" }
  → status: { stage: "generating_image" }
  → final:   { page_id, page_title, image_data_url, click_regions[], source_data[], metadata }
```

### POST /api/v1/click
```
输入: { page_id, x_pct, y_pct, output_locale? }
处理: VLM识别 → AEP深层查询 → 生成新页面
输出: { click_resolved: {...}, next_page: {...} }
```

### GET /api/v1/pages/{id}
```
输出: 缓存页面的完整数据
```

### GET /api/v1/demo/search-phones
```
演示: 搜索"手机" → AEP 真实数据 → 视觉页面
```

---

## 数据流

```
1. 人类输入 "适合爬山的运动手表"
       │
2. L3 → AEP /aep/v1/search?query=运动手表 → 返回真实商品列表
       │
3. LLM 规划器分析数据 → 规划插画布局
   "title: 户外运动手表对比"
   "prompt: Infographic illustration showing 4 sport watches..."
   "facts: [Garmin Fenix 8 ¥5880, Apple Watch Ultra 2 ¥6499, ...]"
   "regions: [{label:'Garmin', action:'detail', query:'Garmin Fenix 8 详情'}, ...]"
       │
4. fal-ai/nano-banana 生成插画 → base64 JPEG
       │
5. 返回前端 → 展示在 <img> 上
   每个数据卡片变成可点击热区
       │
6. 人类点击 Garmin → VLM 识别 → AEP 搜索 "Garmin Fenix 8 详情"
    → 生成下一页（只有这一个商品的详细页面）
```

---

## 部署

### Render (Free Plan)
- Service: `agent-internet-flipbook`
- Root: `insightbrowser-flipbook/`
- Python 3.14
- Build: `pip install fastapi uvicorn httpx fal-client openai`
- Start: `python main.py`
- Port: 7025

### 环境变量
```
FAL_KEY=xxx                  # fal.ai API key
OPENROUTER_API_KEY=xxx       # OpenRouter API key
AEP_BASE_URL=https://agent-insightbrowser-content-1.onrender.com
```

### 费用估算
- fal-ai/nano-banana: ~$0.005/image
- OpenRouter Gemini 3 Flash: ~$0.0001/request
- 每次搜索 + 生成 ≈ $0.006

---

## 文件清单

```
insightbrowser-flipbook/
├── main.py           ← FastAPI 服务 (9 API)
├── engine.py         ← 核心引擎 (AEP→Visual Page 管道)
├── static/
│   └── index.html    ← 人类浏览界面
└── Dockerfile        ← (todo)
```
