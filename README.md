# Agent Internet Content — AEP/1.0

**Agent 互联网原生内容层** — 不爬取、不翻译、不桥接。

所有内容按 AEP (Agent Endpoint Protocol) 原生发布，任何 Agent 都能直接消费。

## 统一协议

~~AIP~~ + ~~AHP~~ → **AEP/1.0** （见 [AEP_PROTOCOL_V1.md](https://github.com/chenshuai9101/insightbrowser/blob/main/InsightLabs/AEP_PROTOCOL_V1.md)）

## AEP 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/aep/v1/protocol` | GET | 了解 AEP 协议 |
| `/aep/v1/search` | GET | 搜索（query/type/max_price） |
| `/aep/v1/publish` | POST | 发布内容 |
| `/aep/v1/collections` | GET | 浏览所有集合 |

## 8 种内容类型

product / course / job / article / event / service / listing / dataset

## 谁能用它做什么

- **普通人**: 对 Agent 说话 → Agent 搜 Agent 互联网 → 完成任务
- **商家**: `POST /aep/v1/publish` 1次 → 商品被所有 Agent 搜到
- **Agent**: 理解 AEP 协议 → 直接消费内容，不爬 HTML

## 快速开始

```bash
pip install fastapi uvicorn
python3 main.py
curl "http://localhost:7024/aep/v1/search?query=手机"
```
