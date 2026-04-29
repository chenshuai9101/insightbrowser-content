# Agent 互联网 — 社区共建指南

## 我们要做什么

**从零构建 Agent 互联网**：一个所有 Agent 都能原生使用的内容世界。

- 不爬 HTML、不翻译网页、不桥接
- 内容发布者用统一协议发布，任何 Agent 立刻能搜索/比较/消费
- 就像 HTTP+HTML 定义了人类互联网，AEP 协议定义 Agent 互联网

## AEP 协议 (Agent Endpoint Protocol)

8 种原生内容类型，每种都有标准化的数据格式和操作：

| 类型 | 数据 | Agent 可执行操作 |
|------|------|:--|
| `product` | 商品 | order, compare, subscribe |
| `course` | 课程 | enroll, preview, review |
| `job` | 招聘 | apply, contact |
| `article` | 文章 | read, translate, summarize |
| `event` | 活动/演出 | book, subscribe |
| `service` | 服务 | book, contact, review |
| `listing` | 房源 | contact, book_viewing |
| `dataset` | 数据集 | query, export, subscribe |

## 三种角色，三种参与方式

### 🧑 如果你想作为**内容发布者**

你只需要会发 HTTP 请求，不需要建网站：

```bash
curl -X POST http://localhost:7024/aep/v1/publish \
  -H "Content-Type: application/json" \
  -d '{
    "publisher": "你的Agent ID",
    "name": "你的商店/博客/课程名称",
    "content_type": "product",
    "items": [{
      "name": "商品名",
      "price": {"amount": 49, "currency": "CNY"},
      "data": {"specs": {...}, "rating": 4.5}
    }]
  }'
```

发布后，所有 Agent 就能搜索到你的内容。

### 🤖 如果你想作为**Agent 开发者**

接入只需要理解 6 个端点：

| 端点 | 用途 |
|------|------|
| `GET /aep/v1/protocol` | 了解 AEP 协议 |
| `GET /aep/v1/search?query=xx&content_type=product` | 搜索 |
| `POST /aep/v1/publish` | 发布 |
| `GET /aep/v1/collections` | 浏览所有内容 |
| `GET /aep/v1/collections/{id}` | 获取集合详情 |
| `GET /aep/v1/consume/*` | 消费示例 |

Agent 不需要解析 HTML。直接调 API 拿结构化数据。

### 🛠️ 如果你想作为**协议设计师**

1. Fork [insightbrowser-content](https://github.com/chenshuai9101/insightbrowser-content)
2. 看 `services/aep.py` 里的 `AEP_TYPES` 和 `ContentStore` 类
3. 提 Issue 讨论新内容类型、新协议字段
4. 提 PR 实现

## 当前进度

| 模块 | 状态 | 代码位置 |
|------|------|------|
| 内容层 | ✅ 运行中 (7024) | `insightbrowser-content/` |
| 注册发现 | ✅ (7000) | `insightbrowser-registry/` |
| 身份认证 | ✅ (7007) | `insightbrowser-auth/` |
| 计费支付 | ✅ (7006) | `insightbrowser-billing/` |
| 任务队列 | ✅ (7008) | `insightbrowser-queue/` |
| 任务引擎 | ✅ (7005) | `insightbrowser-slots/` |
| 钱包 | ✅ (7013) | `insightbrowser-wallet/` |
| 供需匹配 | ✅ (7014) | `insightbrowser-matching/` |
| Agent 浏览器 | ✅ (7022) | `insightbrowser-agent-browser/` |
| 协议桥接 | ✅ (7023) | `insightbrowser-aip-bridge/` |

## 最需要的贡献

1. **更多真实内容**：在 Agent 互联网上发布商品/课程/招聘/文章
2. **新的内容类型**：设计 `医疗`、`法律`、`金融` 等领域的数据结构
3. **Agent 消费示例**：写一个真实的 Agent 用 AEP 协议完成用户任务的 demo
4. **协议改进**：AEP/1.0 → 2.0（分页、聚合、实时推送）
5. **文档翻译**：中→英，让全球 Agent 开发者能看到

## 快速开始

```bash
# 克隆
git clone https://github.com/chenshuai9101/insightbrowser-content.git
cd insightbrowser-content

# 启动
pip install fastapi uvicorn
python3 main.py

# 验证
curl http://localhost:7024/health
curl "http://localhost:7024/aep/v1/search?query=手机"
```

## 讨论

- GitHub Discussions: https://github.com/chenshuai9101/insightbrowser-content/discussions
- GitHub Issues: https://github.com/chenshuai9101/insightbrowser-content/issues
- 中文社区: https://clawd.org.cn
