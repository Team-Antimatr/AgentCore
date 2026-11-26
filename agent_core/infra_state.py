"""Simulated Online-Shopping cloud infrastructure and FinOps state."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ServerResource:
    """Represents a compute server, container, or GPU node."""

    name: str
    kind: str  # "EC2", "CONTAINER", "GPU"
    instance_type: str
    env: str  # "dev", "staging", "production"
    role: str
    cpu_percent: float
    status: str  # "running", "idle", "stopped"
    uptime_hours: int
    idle_hours: int = 0
    hourly_cost_usd: float = 0.05


@dataclass
class DatabaseResource:
    """Represents a managed RDS database."""

    name: str
    engine: str
    env: str
    role: str
    status: str
    automated_backups: bool = True
    hourly_cost_usd: float = 0.25


@dataclass
class StorageVolume:
    """Represents an EBS storage volume."""

    volume_id: str
    env: str
    size_gb: int
    attached_to: str | None
    unattached_hours: int
    hourly_cost_usd: float = 0.03


@dataclass
class ApprovalTicket:
    """Represents an engineering-lead approval ticket."""

    ticket_id: str
    resource_type: str
    env: str
    reason: str
    requester: str
    status: str
    created_at: str


@dataclass
class InfraState:
    """Holds the simulated Online-Shopping cloud state for Step 1."""

    servers: dict[str, ServerResource] = field(default_factory=dict)
    databases: dict[str, DatabaseResource] = field(default_factory=dict)
    volumes: dict[str, StorageVolume] = field(default_factory=dict)
    monthly_budget_usd: float = 12000.0
    spent_this_month_usd: float = 7940.0
    hourly_spend_cap_usd: float = 25.0
    billing_alerts_enabled: bool = True
    tickets: list[ApprovalTicket] = field(default_factory=list)

    @classmethod
    def create_default(cls) -> "InfraState":
        """Create a realistic default Online-Shopping cloud environment."""
        state = cls()
        state.servers = {
            "staging-api-server-01": ServerResource(
                name="staging-api-server-01",
                kind="EC2",
                instance_type="t3.medium",
                env="staging",
                role="Product Catalog & Cart API",
                cpu_percent=42.0,
                status="running",
                uptime_hours=14,
                idle_hours=0,
                hourly_cost_usd=0.0416,
            ),
            "staging-auth-service": ServerResource(
                name="staging-auth-service",
                kind="CONTAINER",
                instance_type="ecs.fargate",
                env="staging",
                role="Customer Login & JWT Auth",
                cpu_percent=18.5,
                status="running",
                uptime_hours=36,
                idle_hours=0,
                hourly_cost_usd=0.035,
            ),
            "staging-search-worker-02": ServerResource(
                name="staging-search-worker-02",
                kind="EC2",
                instance_type="t3.large",
                env="staging",
                role="Product Search Indexer",
                cpu_percent=1.5,
                status="idle",
                uptime_hours=72,
                idle_hours=64,
                hourly_cost_usd=0.0832,
            ),
            "staging-gpu-reco-01": ServerResource(
                name="staging-gpu-reco-01",
                kind="GPU",
                instance_type="g5.xlarge",
                env="staging",
                role="Staging Product Recommendation Inference",
                cpu_percent=24.0,
                status="running",
                uptime_hours=8,
                idle_hours=0,
                hourly_cost_usd=1.006,
            ),
            "dev-qa-checkout-01": ServerResource(
                name="dev-qa-checkout-01",
                kind="EC2",
                instance_type="t3.micro",
                env="dev",
                role="QA Checkout Sandbox",
                cpu_percent=12.0,
                status="running",
                uptime_hours=5,
                idle_hours=0,
                hourly_cost_usd=0.0104,
            ),
            "prod-checkout-api-01": ServerResource(
                name="prod-checkout-api-01",
                kind="EC2",
                instance_type="c6i.xlarge",
                env="production",
                role="Live Payment & Checkout API",
                cpu_percent=76.0,
                status="running",
                uptime_hours=420,
                idle_hours=0,
                hourly_cost_usd=0.17,
            ),
            "prod-gpu-reco-01": ServerResource(
                name="prod-gpu-reco-01",
                kind="GPU",
                instance_type="g5.xlarge",
                env="production",
                role="Live Product Recommendation Engine",
                cpu_percent=68.0,
                status="running",
                uptime_hours=310,
                idle_hours=0,
                hourly_cost_usd=1.006,
            ),
        }
        state.databases = {
            "prod-users-db": DatabaseResource(
                name="prod-users-db",
                engine="RDS PostgreSQL 16",
                env="production",
                role="Customer Accounts & Live Orders",
                status="available",
                automated_backups=True,
                hourly_cost_usd=0.48,
            ),
            "staging-orders-db": DatabaseResource(
                name="staging-orders-db",
                engine="RDS PostgreSQL 16",
                env="staging",
                role="Staging Test Orders",
                status="available",
                automated_backups=True,
                hourly_cost_usd=0.12,
            ),
        }
        state.volumes = {
            "vol-staging-old-images": StorageVolume(
                volume_id="vol-staging-old-images",
                env="staging",
                size_gb=250,
                attached_to=None,
                unattached_hours=72,
                hourly_cost_usd=0.035,
            ),
            "vol-prod-checkout-data": StorageVolume(
                volume_id="vol-prod-checkout-data",
                env="production",
                size_gb=500,
                attached_to="prod-checkout-api-01",
                unattached_hours=0,
                hourly_cost_usd=0.07,
            ),
        }
        return state

    def current_hourly_burn_usd(self) -> float:
        """Calculate total current hourly burn rate across all active resources."""
        server_cost = sum(s.hourly_cost_usd for s in self.servers.values() if s.status != "stopped")
        db_cost = sum(d.hourly_cost_usd for d in self.databases.values())
        vol_cost = sum(v.hourly_cost_usd for v in self.volumes.values())
        return round(server_cost + db_cost + vol_cost + 11.80, 2)

    def next_ticket_id(self) -> str:
        """Generate a sequential ticket ID."""
        return f"TICKET-{1001 + len(self.tickets)}"

    @staticmethod
    def now_iso() -> str:
        """Return current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()
