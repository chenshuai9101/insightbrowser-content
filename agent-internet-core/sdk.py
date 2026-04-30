"""InsightBrowser Core — 精简架构"""

# Python SDK
from typing import Optional, Dict, Any
import httpx

class AgentInternetSDK:
    """Python SDK for Agent Internet AEP/1.0"""
    
    def __init__(self, base_url: str = "http://localhost:7000"):
        self.base = base_url
    
    # === Content ===
    async def protocol(self) -> Dict:
        r = await httpx.AsyncClient().get(f"{self.base}/aep/v1/protocol")
        return r.json()
    
    async def search(self, query: str, content_type: Optional[str] = None, max_price: Optional[float] = None) -> Dict:
        params = {"query": query}
        if content_type: params["type"] = content_type
        if max_price: params["max_price"] = max_price
        r = await httpx.AsyncClient().get(f"{self.base}/aep/v1/search", params=params)
        return r.json()
    
    async def publish(self, **kwargs) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/aep/v1/publish", json=kwargs)
        return r.json()
    
    async def collections(self) -> Dict:
        r = await httpx.AsyncClient().get(f"{self.base}/aep/v1/collections")
        return r.json()
    
    # === Auth ===
    async def auth_token(self) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/auth/token")
        return r.json()
    
    # === Economy ===
    async def create_wallet(self, agent_id: str) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/wallet/create", json={"agent_id": agent_id})
        return r.json()
    
    async def transfer(self, from_agent: str, to_agent: str, amount: float) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/wallet/transfer", json={"from": from_agent, "to": to_agent, "amount": amount})
        return r.json()
    
    async def get_wallet(self, agent_id: str) -> Dict:
        r = await httpx.AsyncClient().get(f"{self.base}/api/v1/wallet/{agent_id}")
        return r.json()
    
    # === Matching ===
    async def create_bid(self, needs: str, budget: float) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/matching/bid", json={"needs": needs, "budget": budget})
        return r.json()
    
    async def accept_bid(self, bid_id: str, agent_id: str) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/matching/accept/{bid_id}", json={"agent_id": agent_id})
        return r.json()
    
    # === Slots ===
    async def submit_task(self, task: Dict) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/slots/submit", json=task)
        return r.json()
    
    # === Commerce ===
    async def commerce_order(self, item_id: str) -> Dict:
        r = await httpx.AsyncClient().post(f"{self.base}/api/v1/commerce/order", json={"item_id": item_id})
        return r.json()
