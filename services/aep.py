"""
Agent 互联网内容协议 — AEP (Agent Endpoint Protocol) v1.0

设计原则：
- 所有内容是 Agent 原生可消费的，不是 HTML 翻译的
- 内容发布者直接发布到 Agent 互联网，不经过桥接
- Agent 不需要理解 HTML，只需要理解 AEP 格式

AEP 定义了 Agent 互联网上"内容"的标准格式。
就像 HTML 定义了人类互联网上"页面"的标准格式。

Agent 互联网上的内容以"资源集合"为单位：
  一个商家 → 发布一个包含商品列表的资源集合
  一个博客 → 发布一个包含文章列表的资源集合

不需要建网站。直接在 Agent 互联网上发布数据。

资源类型(type)决定了 Agent 可以对该内容执行什么操作(actions)。
"""

# ═══════════════════════════════════════════════════════════
# AEP 核心协议：资源集合定义
# ═══════════════════════════════════════════════════════════

# 资源集合 = 发布者在 Agent 互联网上发布的最小单位
AEP_COLLECTION_SCHEMA = {
    "collection_id": "uuid",
    "publisher": "发布者 Agent ID",
    "name": "集合名称（人类可读）",
    "description": "描述",
    "type": "product|article|service|event|data|...",
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601",
    "items": [],        # 资源项列表
    "actions": [],      # Agent 可对此集合执行的操作
}

# 资源项 = 集合中的单个内容
AEP_ITEM_SCHEMA = {
    "item_id": "uuid",
    "type": "product|article|service|job|course|event|dataset",
    "name": "名称",
    "description": "描述",
    "price": {"amount": 0, "currency": "CNY"},
    "availability": "in_stock|limited|sold_out",
    "data": {},         # 类型特定的结构化数据
    "actions": [],      # ["order", "subscribe", "compare", "contact"]
    "created_at": "ISO-8601",
}

# ═══════════════════════════════════════════════════════════
# 各资源类型的数据格式定义
# ═══════════════════════════════════════════════════════════

AEP_TYPES = {
    "product": {
        "description": "商品",
        "data_fields": ["specs", "images", "variants", "reviews_count", "rating"],
        "actions": ["order", "compare", "subscribe"],
    },
    "article": {
        "description": "文章/文档",
        "data_fields": ["body_text", "author", "tags", "reading_time"],
        "actions": ["read", "translate", "summarize"],
    },
    "service": {
        "description": "服务",
        "data_fields": ["provider", "duration", "location", "requirements"],
        "actions": ["book", "contact", "review"],
    },
    "job": {
        "description": "招聘岗位",
        "data_fields": ["company", "salary_range", "location", "requirements", "skills"],
        "actions": ["apply", "contact"],
    },
    "course": {
        "description": "课程",
        "data_fields": ["syllabus", "instructor", "duration", "level", "prerequisites"],
        "actions": ["enroll", "preview", "review"],
    },
    "event": {
        "description": "活动/演出",
        "data_fields": ["datetime", "venue", "price_range", "remaining_tickets"],
        "actions": ["book", "subscribe"],
    },
    "dataset": {
        "description": "数据集/表格",
        "data_fields": ["rows", "columns", "source", "update_frequency"],
        "actions": ["query", "export", "subscribe"],
    },
    "listing": {
        "description": "房源/租房",
        "data_fields": ["address", "area_sqm", "rooms", "floor", "images"],
        "actions": ["contact", "book_viewing"],
    },
}

# ═══════════════════════════════════════════════════════════
# 内容发布者的数据存储
# ═══════════════════════════════════════════════════════════

import json, os, uuid, time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

@dataclass
class Collection:
    collection_id: str
    publisher: str
    name: str
    description: str
    type: str
    items: List[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

class ContentStore:
    """Agent 互联网内容存储 — 发布者直接发布到这里的结构化数据"""
    
    def __init__(self, data_dir="/tmp/agent-internet-content"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._load()
    
    def _load(self):
        path = os.path.join(self.data_dir, "index.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.collections = data.get("collections", {})
        else:
            self.collections = {}
    
    def _save(self):
        with open(os.path.join(self.data_dir, "index.json"), "w") as f:
            json.dump({"collections": self.collections}, f, ensure_ascii=False, indent=2)
    
    def publish(self, publisher: str, name: str, description: str,
                content_type: str, items: list) -> Collection:
        """发布一个资源集合到 Agent 互联网"""
        if content_type not in AEP_TYPES:
            raise ValueError(f"Unknown content type: {content_type}. Allowed: {list(AEP_TYPES.keys())}")
        
        coll = Collection(
            collection_id=str(uuid.uuid4())[:8],
            publisher=publisher,
            name=name,
            description=description,
            type=content_type,
        )
        
        # 为每个 item 补充 id 和标准字段
        for i, item in enumerate(items):
            if "item_id" not in item:
                item["item_id"] = f"{coll.collection_id}-{i}"
            if "type" not in item:
                item["type"] = content_type
            if "actions" not in item:
                item["actions"] = AEP_TYPES[content_type].get("actions", [])
        
        coll.items = items
        self.collections[coll.collection_id] = asdict(coll)
        self._save()
        return coll
    
    def search(self, query: str = "", content_type: str = "",
               max_price: float = None, limit: int = 20) -> list:
        """搜索 Agent 互联网上的内容"""
        results = []
        query_lower = query.lower() if query else ""
        
        for cid, coll in self.collections.items():
            if content_type and coll["type"] != content_type:
                continue
            
            for item in coll["items"]:
                match = True
                if query_lower:
                    match = (query_lower in (item.get("name","")+item.get("description","")).lower()
                             or query_lower in coll.get("name","").lower())
                if max_price and item.get("price",{}).get("amount", 0) > max_price:
                    match = False
                if match:
                    results.append({
                        **item,
                        "_collection": coll["name"],
                        "_publisher": coll["publisher"],
                        "_collection_id": cid,
                    })
        
        return results[:limit]
    
    def get_collection(self, collection_id: str) -> dict:
        return self.collections.get(collection_id)

    def list_collections(self) -> list:
        return [{"id": cid, "name": c["name"], "type": c["type"],
                 "publisher": c["publisher"], "items_count": len(c["items"])}
                for cid, c in self.collections.items()]

    def fill_with_demo_data(self):
        """填充示例数据，让 Agent 互联网有原生内容"""
        if self.collections:
            return  # 已有数据
        
        # 手机商店
        self.publish("store-agent-001", "手机商店", "iPhone、华为、小米手机及配件",
            "product", [
                {"name": "iPhone 17 Pro 256GB", "description": "A19 Pro芯片，6.3英寸OLED",
                 "price": {"amount": 8999, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"specs": {"chip": "A19 Pro", "screen": "6.3英寸", "storage": "256GB"},
                          "images": [], "variants": ["128GB","256GB","512GB","1TB"],
                          "rating": 4.8, "reviews_count": 2340}},
                {"name": "华为 Mate 80 Pro 512GB", "description": "麒麟9100，6.8英寸曲面屏",
                 "price": {"amount": 7999, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"specs": {"chip": "麒麟9100", "screen": "6.8英寸", "storage": "512GB"},
                          "images": [], "variants": ["256GB","512GB","1TB"],
                          "rating": 4.7, "reviews_count": 1890}},
                {"name": "小米 16 Ultra 512GB", "description": "骁龙8 Gen4，徕卡影像",
                 "price": {"amount": 6499, "currency": "CNY"}, "availability": "limited",
                 "data": {"specs": {"chip": "骁龙8 Gen4", "screen": "6.7英寸", "storage": "512GB"},
                          "images": [], "variants": ["256GB","512GB"],
                          "rating": 4.6, "reviews_count": 1560}},
                {"name": "iPhone 17e 128GB", "description": "A19芯片，性价比之选",
                 "price": {"amount": 4499, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"specs": {"chip": "A19", "screen": "6.1英寸", "storage": "128GB"},
                          "images": [], "variants": ["128GB","256GB"],
                          "rating": 4.5, "reviews_count": 3200}},
                {"name": "Phone Case iPhone 17 Pro", "description": "MagSafe 磁吸保护壳",
                 "price": {"amount": 399, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"specs": {"material": "硅胶", "colors": ["黑","蓝","粉"]},
                          "images": [], "variants": ["黑","蓝","粉"],
                          "rating": 4.4, "reviews_count": 8900}},
            ])
        
        # 课程平台
        self.publish("course-agent-001", "在线课程平台", "Python、AI、前端课程",
            "course", [
                {"name": "Python 全栈开发从入门到精通", "description": "60小时系统课程，包含Django+FastAPI项目实战",
                 "price": {"amount": 299, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"syllabus": ["Python基础","面向对象","Web开发","数据库","项目实战"],
                          "instructor": "张老师", "duration": "60小时", "level": "入门",
                          "prerequisites": [], "rating": 4.8}},
                {"name": "机器学习实战入门", "description": "从线性回归到深度学习的完整路径",
                 "price": {"amount": 399, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"syllabus": ["数学基础","监督学习","无监督学习","深度学习","NLP","CV"],
                          "instructor": "李教授", "duration": "80小时", "level": "中级",
                          "prerequisites": ["Python基础", "线性代数"], "rating": 4.9}},
                {"name": "React 18 + TypeScript 实战", "description": "从零搭建企业级前端项目",
                 "price": {"amount": 0, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"syllabus": ["TypeScript基础","React Hooks","状态管理","项目实战"],
                          "instructor": "王老师", "duration": "40小时", "level": "入门",
                          "prerequisites": ["JavaScript基础"], "rating": 4.6}},
            ])
        
        # 招聘平台
        self.publish("job-agent-001", "科技招聘平台", "Python/前端/AI 岗位",
            "job", [
                {"name": "Python 后端工程师", "description": "负责微服务架构设计和开发",
                 "price": {}, "availability": "in_stock",
                 "data": {"company": "字节跳动", "salary_range": "30K-60K",
                          "location": "北京", "requirements": "3年以上Python后端经验",
                          "skills": ["Python","Go","Kubernetes","MySQL","Redis"]}},
                {"name": "AI 算法工程师", "description": "负责推荐系统模型优化",
                 "price": {}, "availability": "in_stock",
                 "data": {"company": "阿里巴巴", "salary_range": "40K-80K",
                          "location": "杭州", "requirements": "硕士以上，顶会论文优先",
                          "skills": ["Python","PyTorch","推荐系统","NLP"]}},
                {"name": "前端开发工程师", "description": "负责低代码平台前端架构",
                 "price": {}, "availability": "in_stock",
                 "data": {"company": "腾讯", "salary_range": "25K-50K",
                          "location": "深圳", "requirements": "3年以上React经验",
                          "skills": ["React","TypeScript","Webpack","Node.js"]}},
            ])
        
        # 技术博客
        self.publish("blog-agent-001", "技术博客", "AI、Agent、互联网技术文章",
            "article", [
                {"name": "Agent 互联网协议设计指南", "description": "为什么 Agent 需要自己的互联网协议，而不是爬HTML",
                 "data": {"author": "牧云野", "tags": ["Agent","协议设计","互联网"],
                          "body_text": "Agent不需要浏览器。Agent需要的是结构化数据端点...",
                          "reading_time": 15}},
                {"name": "从零构建多 Agent 协作系统", "description": "Registry + Queue + Wallet 的完整架构",
                 "data": {"author": "牧云野", "tags": ["多Agent","架构","协作"],
                          "body_text": "多个Agent之间如何发现、通信、交易...",
                          "reading_time": 25}},
                {"name": "Slots v3.1 Pipeline 设计", "description": "并行执行+超时熔断的 Agent 任务引擎",
                 "data": {"author": "牧云野", "tags": ["Slots","Pipeline","工程"],
                          "body_text": "从串行到并行，从阻塞到超时...",
                          "reading_time": 20}},
            ])
        
        # 活动/演出
        self.publish("event-agent-001", "演出票务", "音乐会、话剧、演唱会",
            "event", [
                {"name": "周杰伦 2026 巡回演唱会 北京站", "description": "鸟巢连开三场",
                 "price": {"amount": 580, "currency": "CNY"}, "availability": "limited",
                 "data": {"datetime": "2026-06-15T19:30:00+08:00", "venue": "国家体育场(鸟巢)",
                          "price_range": "580-1980", "remaining_tickets": 3200}},
                {"name": "久石让动漫交响音乐会", "description": "天空之城·千与千寻经典曲目",
                 "price": {"amount": 280, "currency": "CNY"}, "availability": "in_stock",
                 "data": {"datetime": "2026-05-20T19:00:00+08:00", "venue": "国家大剧院",
                          "price_range": "280-880", "remaining_tickets": 850}},
            ])
        
        print(f"Agent 互联网内容初始化完成: {len(self.collections)} 个集合")

# 全局单例
store = ContentStore()
store.fill_with_demo_data()
