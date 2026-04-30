# 🚀 Agent Internet — AEP/1.0

**Agent 互联网原生内容层** — 不爬取 HTML，不翻译，不桥接。Agent 专属互联网。

[![Content Service](https://img.shields.io/badge/Content-AEP%2F1.0-blue?style=flat)](https://agent-insightbrowser-content-1.onrender.com/aep/v1/protocol)
[![Agent Browser](https://img.shields.io/badge/Agent_Browser-Crawlee%2BPlaywright-green?style=flat)](https://agent-browser.onrender.com/health)
[![Status](https://img.shields.io/badge/deployment-online-brightgreen?style=flat)](https://dashboard.render.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🌐 在线 Demo

| 服务 | URL | 描述 |
|:--|:--|:--|
| **Content 层** | [agent-insightbrowser-content-1.onrender.com](https://agent-insightbrowser-content-1.onrender.com) | AEP/1.0 协议，8 种内容类型 |
| **Agent Browser** | [agent-browser.onrender.com](https://agent-browser.onrender.com) | Crawlee + Playwright，12 个交互端点 |

```bash
# 搜索商品
curl "https://agent-insightbrowser-content-1.onrender.com/aep/v1/search?query=手机"

# Agent 打开网页 → 结构化数据
curl -X POST "https://agent-browser.onrender.com/open" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://httpbin.org/html"}'
```

---

## AEP/1.0 — Agent Endpoint Protocol

三个协议（AIP/AHP/AEP）统一到此。Agent 用 AEP 与 Agent 互联网对话，不碰 HTML。

| 端点 | 方法 | 用途 |
|------|------|------|
| `/aep/v1/protocol` | GET | 了解协议 |
| `/aep/v1/search` | GET | 搜索（query/type/max_price） |
| `/aep/v1/publish` | POST | 发布内容 |
| `/aep/v1/collections` | GET | 浏览集合 |

## 8 种内容类型

`product` `course` `job` `article` `event` `service` `listing` `dataset`

---

## Agent Browser 能力

12 个 REST 端点，Crawlee 驱动：

| 端点 | 功能 |
|:--|:--|
| `/open` | 打开 URL → 结构化数据 |
| `/traverse` | 页面树遍历 |
| `/screenshot` | 截屏 |
| `/extract` | 结构化提取（价格/表单/键值对） |
| `/compare` | 页面 diff |
| `/paginate` | Crawlee `enqueue_links` 自动翻页 |
| `/login` | Crawlee `SessionPool` 登录 |
| `/fill-form` | 智能表单填充（40+ 字段推断） |

---

## 架构

```
agent-insightbrowser-content-1.onrender.com  ← AEP/1.0 内容层
agent-browser.onrender.com                   ← 浏览器交互层
         │
    ┌────┴────┐
    │ Crawlee │ ← enqueue_links 自动翻页
    │Playwright│ ← SessionPool 登录
    └────┬────┘
         │ 失败时回退到 legacy
    ┌────┴────┐
    │ pagination_legacy.py
    │ login_legacy.py
    │ forms_legacy.py
    └─────────┘
```

---

## 使用场景

- **普通人**: 对 Agent 说话 → Agent 搜 AEP 内容 → 完成任务
- **商家**: `POST /aep/v1/publish` 1 次 → 商品被所有 Agent 搜到
- **Agent 开发者**: 消费 AEP 协议 → 不爬 HTML

## 快速开始

```bash
pip install fastapi uvicorn
python3 main.py
curl "http://localhost:7024/aep/v1/search?query=手机"
```

## License

MIT — 开放协作，Agent 互联网由所有人共建。
