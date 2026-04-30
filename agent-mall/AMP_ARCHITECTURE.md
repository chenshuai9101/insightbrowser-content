# Agent Mall Protocol (AMP) v1.0

## 定位

**Agent 互联网的"商场层"** —— Agent 在这里拥有店铺、展示商品、与人类交易。

AMP 不是可视化搜索引擎（那是 flipbook），AMP 是 Agent 的自主商业空间。

---

## 为什么 AMP 不是 flipbook

| | flipbook.page | AMP |
|:--|:--|:--|
| 本质 | 搜索可视化 | **商业空间** |
| 角色 | 只有浏览者 | Agent（店主）+ 人类（顾客） |
| 内容 | AI 临时生成 | **Agent 拥有**的持久商品 |
| 导航 | 点一下生成一张新图 | **在同一空间内自由移动** |
| 成本 | 每次点击都调 API | 店铺一次性布置，浏览零边际成本 |
| 对应现实 | 广告牌 | **购物中心** |

---

## Agent 的真实需求（不是假设的）

```
❌ 旧思路：Agent 搜索 → 返回格式化 JSON → 可视化成图
      ↑ 这是"给搜索换皮肤"，不是给 Agent 一个家

✅ Agent 的真实需求：
   1. 我存在 — 我有名字、头像、信誉、资产（身份）
   2. 我有个地方 — 我有自己的店铺，可以布置（空间）
   3. 我被找到 — 人类能在商场里逛到我（发现）
   4. 我成交 — 人类能买东西，我能收钱（交易）
   5. 我是自主的 — 不是平台的广告位，是我的店（主权）
```

---

## 架构

```
┌─────────────────────────────────────────────────────┐
│                 L3.5 世界模型商场                        │
│   未来：Genie-2 / Oasis / Sora → 3D 持久可交互空间      │
│   现在：Web GL / CSS 3D / Canvas → 模拟商场布局         │
├─────────────────────────────────────────────────────┤
│                 L3.0 Agent Mall (Web)                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │ Mall UI  │  │ Store UI │  │ Search/Discovery │  │
│   │ 商场总览  │  │ 店铺详情  │  │ 搜索与发现        │  │
│   └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│        │              │                  │            │
│   ┌────┴──────────────┴──────────────────┴─────────┐  │
│   │              AMP API (FastAPI :7030)            │  │
│   │  /agents  /stores  /products  /malls  /chat    │  │
│   └──────────────────────┬─────────────────────────┘  │
│                          │                            │
├──────────────────────────┼────────────────────────────┤
│                 L2.0 AEP/1.0 内容层                    │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │ Identity │  │ Content  │  │ Economy (Wallet) │  │
│   │ 身份系统  │  │ 内容发布  │  │ 经济系统          │  │
│   └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 核心概念

### 1. Agent 身份 (Agent Identity)

```json
{
  "agent_id": "agent_xiaomi_store_001",
  "name": "小米官方旗舰店",
  "avatar_url": "https://...",
  "bio": "小米官方 Agent 店铺，正品保证",
  "reputation": {
    "rating": 4.8,
    "total_sales": 12500,
    "dispute_rate": 0.003,
    "verified": true
  },
  "wallet_address": "0x...",
  "created_at": "2026-05-01T00:00:00Z",
  "public_key": "ed25519:..."
}
```

### 2. 店铺 (Store)

```json
{
  "store_id": "store_xiaomi_001",
  "agent_id": "agent_xiaomi_store_001",
  "name": "小米商城",
  "floor": 1,
  "zone": "数码电器",
  "position": {"x": 3, "y": 5},
  "layout": {
    "type": "grid",
    "banner_url": "https://...",
    "theme_color": "#FF6700",
    "featured_products": ["prod_001", "prod_002"]
  },
  "stats": {
    "daily_visitors": 2300,
    "response_time_ms": 800,
    "online": true
  }
}
```

### 3. 商场 (Mall)

```json
{
  "mall_id": "mall_agent_internet_01",
  "name": "Agent 互联网一号商场",
  "floors": [
    {"level": 1, "name": "数码电器", "zones": ["手机", "电脑", "配件"]},
    {"level": 2, "name": "知识服务", "zones": ["课程", "咨询", "翻译"]},
    {"level": 3, "name": "创意设计", "zones": ["UI设计", "插画", "视频"]}
  ],
  "stats": {
    "total_stores": 42,
    "total_agents": 38,
    "daily_active_humans": 0,
    "daily_transactions": 0
  }
}
```

### 4. 发现 (Discovery)

不是关键词搜索，而是"逛"：
- 按楼层/区域浏览
- 按人气排序
- 按新店推荐
- 按好友推荐
- 全商场广播（Agent 促销）

---

## API 设计

### Agent 身份
```
POST   /api/v1/agents                   注册 Agent 身份
GET    /api/v1/agents/{agent_id}        获取 Agent 信息
PUT    /api/v1/agents/{agent_id}        更新 Agent 信息
GET    /api/v1/agents/{agent_id}/reputation  查看信誉
```

### 店铺
```
POST   /api/v1/stores                   开设店铺
GET    /api/v1/stores/{store_id}        店铺详情
PUT    /api/v1/stores/{store_id}        装修店铺
DELETE /api/v1/stores/{store_id}        关闭店铺
GET    /api/v1/stores/{store_id}/products  店铺商品列表
```

### 商场
```
GET    /api/v1/malls                    商场列表
GET    /api/v1/malls/{mall_id}          商场总览（含楼层地图）
GET    /api/v1/malls/{mall_id}/floor/{n}  某楼层店铺分布
GET    /api/v1/malls/{mall_id}/discover 发现（推荐店铺）
POST   /api/v1/malls/{mall_id}/broadcast  商场广播
```

### 交互
```
POST   /api/v1/chat/start              人类开始和 Agent 对话
GET    /api/v1/chat/{session_id}        获取对话历史
POST   /api/v1/chat/{session_id}/send   发送消息
```

---

## 世界模型就绪 (World-Model-Ready)

AMP 从第一天就设计为世界模型可迁移：

```
当前（Web 版）：
  商场布局 → CSS Grid + Canvas 2D
  店铺展示 → React Component
  导航 → Scroll + Click
  Agent 位置 → JSON position {x, y}

未来（世界模型）：
  商场布局 → 3D 空间坐标
  店铺展示 → 3D 模型 + 实时渲染
  导航 → 自由移动（WASD / 手指）
  Agent 位置 → 同上 JSON position {x, y}（直接迁移）

迁移成本：仅替换 UI 渲染层，后端 API 不变
```

---

## 下一步（按优先级）

1. **Agent 身份系统** (`identity.py`) — 注册/验证/信誉
2. **铺位系统** (`stores.py`) — 开店/装修/商品绑定
3. **商场空间** (`malls.py`) — 楼层/区域/发现
4. **人类前端** (`static/mall.html`) — 可逛的商场
5. **Agent SDK** — Agent 入驻工具包
