"""P2: Agent 经济系统 — Wallet + Billing + Matching + Approval + Slots + Commerce"""
from fastapi import APIRouter, Query
import uuid, time

router = APIRouter(prefix="/api/v1", tags=["economy"])

_wallets = {}
_transactions = []
_bids = []

def register(app):
    app.include_router(router)

# Wallet
@router.post("/wallet/create")
async def wallet_create(data: dict):
    aid = data.get("agent_id", uuid.uuid4().hex[:8])
    _wallets[aid] = {"agent_id": aid, "balance": 100.0, "currency": "AIC", "created_at": time.time()}
    return _wallets[aid]

@router.get("/wallet/{agent_id}")
async def wallet_get(agent_id: str):
    return _wallets.get(agent_id, {"error": "not found"})

@router.post("/wallet/transfer")
async def wallet_transfer(data: dict):
    frm, to, amt = data["from"], data["to"], data["amount"]
    if _wallets.get(frm,{}).get("balance",0) >= amt:
        _wallets[frm] = {**_wallets[frm], "balance": _wallets[frm]["balance"] - amt}
        _wallets[to] = {**_wallets.get(to, {"agent_id":to,"balance":0,"currency":"AIC"}), "balance": _wallets.get(to,{}).get("balance",0) + amt}
        txid = uuid.uuid4().hex[:12]
        _transactions.append({"id":txid,"from":frm,"to":to,"amount":amt,"timestamp":time.time()})
        return {"success":True,"tx_id":txid}
    return {"success":False,"error":"insufficient funds"}

# Billing
@router.post("/billing/meter")
async def billing_meter(data: dict):
    return {"usage": 0.0, "cost": 0.0}

@router.get("/billing/invoice/{agent_id}")
async def billing_invoice(agent_id: str):
    return {"agent_id": agent_id, "total": 0.0, "transactions": _transactions}

# Matching: Agent 需求匹配
@router.post("/matching/bid")
async def create_bid(data: dict):
    bid = {"id": uuid.uuid4().hex[:8], **data, "created_at": time.time()}
    _bids.append(bid)
    return bid

@router.get("/matching/bids")
async def list_bids(needs: str = Query(None)):
    return {"bids": _bids, "query": needs}

@router.post("/matching/accept/{bid_id}")
async def accept_bid(bid_id: str, data: dict):
    return {"accepted": bid_id, "provider": data.get("agent_id")}

# Approval
@router.post("/approval/request")
async def approval_request(data: dict):
    return {"request_id": uuid.uuid4().hex[:8], "status": "pending"}

@router.post("/approval/decide")
async def approval_decide(data: dict):
    return {"approved": True}

# Slots: 任务引擎（精简版）
@router.post("/slots/submit")
async def slot_submit(data: dict):
    return {"slot_id": uuid.uuid4().hex[:8], "status": "queued"}

@router.get("/slots/status/{slot_id}")
async def slot_status(slot_id: str):
    return {"slot_id": slot_id, "status": "done"}

# Commerce: 商家桥接
@router.post("/commerce/publish")
async def commerce_publish(data: dict):
    return {"published": True, "item_id": uuid.uuid4().hex[:8]}

@router.post("/commerce/order")
async def commerce_order(data: dict):
    return {"order_id": uuid.uuid4().hex[:8], "status": "confirmed"}
