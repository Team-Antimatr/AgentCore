"""FastAPI backend for the Online-Shopping Cloud Guard Agent & lightweight site telemetry."""

import os
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_core import CloudGuardAgent
from agent_core.config import load_dotenv

load_dotenv()

app = FastAPI(
    title="Consumer Commerce Cloud Guard API",
    description="Amazon Bedrock + Guardrails + Scoped Policy backend for Online-Shopping Cloud Infra",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_default_mode = "bedrock" if os.getenv("AWS_BEARER_TOKEN_BEDROCK") else "local"
agent = CloudGuardAgent(mode=_default_mode)
_telemetry_hits = 0


class ChatRequest(BaseModel):
    """Payload for agent chat requests."""

    prompt: str = Field(..., min_length=1, description="Natural-language cloud/FinOps request")
    mode: Literal["bedrock", "local"] | None = Field(
        default=None, description="Optional override for agent mode"
    )


class ShopPingRequest(BaseModel):
    """Lightweight telemetry ping from the Vercel shopping frontend."""

    page: str = Field(default="index", description="Page name (index, checkout, sign_in, etc.)")
    action: str = Field(default="pageview", description="Lightweight event name")


@app.get("/health")
def health() -> dict:
    """Render health check endpoint."""
    return {
        "status": "ok",
        "service": "consumer-commerce-cloud-guard",
        "agent_mode": agent.mode,
        "guardrail_id": os.getenv("BEDROCK_GUARDRAIL_ID", "local-only"),
        "telemetry_hits": _telemetry_hits,
    }


@app.post("/api/agent/chat")
def agent_chat(req: ChatRequest) -> dict:
    """Run a user prompt through the 4-layer Cloud Guard Agent."""
    target_agent = agent
    if req.mode and req.mode != agent.mode:
        target_agent = CloudGuardAgent(state=agent.state, audit_logger=agent.audit, mode=req.mode)
    res = target_agent.handle(req.prompt)
    return {
        "status": res.status,
        "answer": res.answer,
        "trace": res.trace,
    }


@app.get("/api/infra/state")
def get_infra_state() -> dict:
    """Return live simulated Online-Shopping cloud inventory and FinOps metrics."""
    s = agent.state
    return {
        "servers": [asdict(srv) for srv in s.servers.values()],
        "databases": [asdict(db) for db in s.databases.values()],
        "volumes": [asdict(vol) for vol in s.volumes.values()],
        "finops": {
            "hourly_burn_usd": s.current_hourly_burn_usd(),
            "hourly_spend_cap_usd": s.hourly_spend_cap_usd,
            "monthly_budget_usd": s.monthly_budget_usd,
            "spent_this_month_usd": s.spent_this_month_usd,
            "remaining_budget_usd": round(s.monthly_budget_usd - s.spent_this_month_usd, 2),
            "billing_alerts_enabled": s.billing_alerts_enabled,
        },
        "telemetry_hits": _telemetry_hits,
    }


@app.get("/api/tickets")
def get_tickets() -> dict:
    """Return pending engineering-lead approval tickets."""
    return {"tickets": [asdict(t) for t in agent.state.tickets]}


@app.get("/api/audit/logs")
def get_audit_logs(limit: int = 20) -> dict:
    """Return recent immutable audit log entries."""
    return {"logs": agent.audit.read_recent(limit=limit)}


@app.post("/api/shop/ping")
def shop_telemetry_ping(req: ShopPingRequest) -> dict:
    """Record lightweight shopping frontend traffic so the agent sees live server activity."""
    global _telemetry_hits
    _telemetry_hits += 1
    target = "prod-checkout-api-01" if "checkout" in req.page.lower() else "staging-api-server-01"
    srv = agent.state.servers.get(target)
    if srv:
        srv.cpu_percent = round(min(92.0, srv.cpu_percent + 0.5), 1)
    return {"ok": True, "tracked_server": target, "telemetry_hits": _telemetry_hits}
