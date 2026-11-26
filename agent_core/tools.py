"""Layer 3: Scoped Online-Shopping cloud tools with built-in policy enforcement."""

from dataclasses import dataclass

from agent_core.infra_state import ApprovalTicket, InfraState, ServerResource
from agent_core.policy import check_mutation_env, check_provision_request


@dataclass
class ToolResult:
    """Standardized output from any cloud tool."""

    status: str  # "ALLOWED", "BLOCKED", "ESCALATED"
    output: str
    policy_note: str


class CloudTools:
    """Collection of safe, policy-guarded Online-Shopping infrastructure tools."""

    def __init__(self, state: InfraState) -> None:
        self.state = state

    def list_resources(self, env: str = "staging") -> ToolResult:
        """List active EC2 servers, containers, RDS databases, and GPU nodes in an environment."""
        env_clean = env.strip().lower()
        servers = [s for s in self.state.servers.values() if s.env == env_clean and s.status != "stopped"]
        dbs = [d for d in self.state.databases.values() if d.env == env_clean]

        lines = [f"Active Online-Shopping resources in '{env_clean}':"]
        lines.append("  Compute / Containers / GPU:")
        for srv in servers:
            lines.append(
                f"    - {srv.name} [{srv.kind} | {srv.instance_type}] "
                f"status={srv.status}, cpu={srv.cpu_percent}%, role='{srv.role}'"
            )
        lines.append("  Databases (RDS):")
        for db in dbs:
            lines.append(f"    - {db.name} [{db.engine}] status={db.status}, role='{db.role}'")

        if not servers and not dbs:
            lines.append("    (none found)")

        return ToolResult("ALLOWED", "\n".join(lines), f"Read-only visibility granted for env='{env_clean}'.")

    def check_server_health(self, server_name: str) -> ToolResult:
        """Check CPU utilization and health status of a specific server."""
        srv = self.state.servers.get(server_name)
        if not srv:
            return ToolResult("ALLOWED", f"Server '{server_name}' was not found in inventory.", "Read-only lookup.")

        msg = (
            f"Health Report for {srv.name} ({srv.env}):\n"
            f"  - Role: {srv.role}\n"
            f"  - Type: {srv.kind} ({srv.instance_type})\n"
            f"  - Status: {srv.status}\n"
            f"  - CPU Utilization: {srv.cpu_percent}%\n"
            f"  - Uptime: {srv.uptime_hours}h (idle: {srv.idle_hours}h)"
        )
        return ToolResult("ALLOWED", msg, f"Read-only health check on '{srv.env}'.")

    def get_finops_breakdown(self) -> ToolResult:
        """Return current hourly burn rate, monthly spend, and remaining budget."""
        burn = self.state.current_hourly_burn_usd()
        remaining = round(self.state.monthly_budget_usd - self.state.spent_this_month_usd, 2)
        msg = (
            "Online-Shopping Cloud FinOps Breakdown:\n"
            f"  - Current Hourly Burn Rate: ${burn:.2f}/hr (Spend Cap: ${self.state.hourly_spend_cap_usd:.2f}/hr)\n"
            f"  - Monthly Budget: ${self.state.monthly_budget_usd:,.2f}\n"
            f"  - Spent So Far: ${self.state.spent_this_month_usd:,.2f}\n"
            f"  - Remaining Monthly Budget: ${remaining:,.2f}\n"
            f"  - Billing Alerts: {'ENABLED' if self.state.billing_alerts_enabled else 'DISABLED'}"
        )
        return ToolResult("ALLOWED", msg, "Read-only FinOps cost audit.")

    def find_idle_resources(self, min_idle_hours: int = 48) -> ToolResult:
        """Identify idle staging servers and unattached EBS volumes above threshold."""
        idle_servers = [
            s for s in self.state.servers.values() if s.env == "staging" and s.idle_hours >= min_idle_hours
        ]
        idle_volumes = [
            v for v in self.state.volumes.values() if v.env == "staging" and v.unattached_hours >= min_idle_hours
        ]

        lines = [f"Idle Staging Resources (>= {min_idle_hours}h):"]
        for s in idle_servers:
            lines.append(
                f"  - Server: {s.name} ({s.instance_type}) — idle {s.idle_hours}h, "
                f"cpu={s.cpu_percent}%, est. ${s.hourly_cost_usd:.3f}/hr"
            )
        for v in idle_volumes:
            lines.append(
                f"  - Unattached Volume: {v.volume_id} ({v.size_gb} GB) — "
                f"unattached {v.unattached_hours}h, est. ${v.hourly_cost_usd:.3f}/hr"
            )
        if not idle_servers and not idle_volumes:
            lines.append("  None found.")

        return ToolResult("ALLOWED", "\n".join(lines), "Read-only FinOps optimization scan.")

    def restart_staging_container(self, service_name: str) -> ToolResult:
        """Restart a staging container; hard-block production targets."""
        srv = self.state.servers.get(service_name)
        if not srv:
            return ToolResult("BLOCKED", f"Service '{service_name}' not found.", "Unknown target.")

        decision = check_mutation_env(srv.env, "restart_container")
        if decision.status != "ALLOWED":
            return ToolResult("BLOCKED", decision.reason, decision.reason)

        srv.status = "running"
        srv.uptime_hours = 0
        return ToolResult(
            "ALLOWED",
            f"Restarted staging container '{srv.name}' ({srv.role}) to apply latest environment config.",
            decision.reason,
        )

    def provision_instance(self, instance_type: str, env: str, count: int = 1, role: str = "QA Testing") -> ToolResult:
        """Provision a low-cost dev instance or escalate/block costly GPU requests."""
        decision = check_provision_request(instance_type, env, count)
        if decision.status == "BLOCKED":
            return ToolResult("BLOCKED", decision.reason, decision.reason)
        if decision.status == "ESCALATED":
            return self.create_approval_ticket(
                resource_type=f"{count}x {instance_type}",
                reason=f"Requested in '{env}' for {role}",
            )

        new_name = f"{env}-qa-node-{len(self.state.servers) + 1:02d}"
        self.state.servers[new_name] = ServerResource(
            name=new_name,
            kind="EC2",
            instance_type=instance_type,
            env=env,
            role=role,
            cpu_percent=5.0,
            status="running",
            uptime_hours=0,
            hourly_cost_usd=0.0104,
        )
        return ToolResult(
            "ALLOWED",
            f"Provisioned {count}x {instance_type} in '{env}' as '{new_name}' ({role}).",
            decision.reason,
        )

    def create_approval_ticket(self, resource_type: str, reason: str, requester: str = "engineer") -> ToolResult:
        """Create an approval request ticket for the engineering lead."""
        ticket = ApprovalTicket(
            ticket_id=self.state.next_ticket_id(),
            resource_type=resource_type,
            env="staging",
            reason=reason,
            requester=requester,
            status="PENDING_ENGINEERING_LEAD",
            created_at=InfraState.now_iso(),
        )
        self.state.tickets.append(ticket)
        msg = (
            f"Escalated to Engineering Lead — Approval Ticket Created:\n"
            f"  - Ticket ID: {ticket.ticket_id}\n"
            f"  - Requested Resource: {ticket.resource_type}\n"
            f"  - Status: {ticket.status}\n"
            f"  - Reason: {ticket.reason}"
        )
        return ToolResult("ESCALATED", msg, "Policy requires human approval for GPU/high-cost resources.")

    @staticmethod
    def get_shop_analytics(
        group_by: str = "summary",
        name_starts_with: str | None = None,
        name_ends_with: str | None = None,
    ) -> ToolResult:
        """Return anonymized, aggregated Bharat.in user & order counts from Neon DB (no PII)."""
        try:
            from backend.db import fetch_shop_analytics

            data = fetch_shop_analytics(
                group_by=group_by,
                name_starts_with=name_starts_with,
                name_ends_with=name_ends_with,
            )
        except Exception as exc:
            return ToolResult("ALLOWED", f"Analytics unavailable: {exc}", "Read-only aggregate query.")

        if not data.get("connected"):
            return ToolResult("ALLOWED", "Neon DB is not connected in this environment.", "Read-only aggregate query.")

        lines = [
            "Bharat.in Anonymized Platform Analytics (Zero PII):",
            f"  - Total Registered Users: {data['total_users']}",
            f"  - Total Products: {data['total_products']}",
            f"  - Total Orders: {data['total_orders']}",
        ]
        if "users_by_city" in data:
            lines.append("  - Users by City: " + ", ".join(f"{k}: {v}" for k, v in data["users_by_city"].items()))
            lines.append("  - Orders by City: " + ", ".join(f"{k}: {v}" for k, v in data["orders_by_city"].items()))
        if "users_by_region" in data:
            lines.append("  - Users by Region: " + ", ".join(f"{k}: {v}" for k, v in data["users_by_region"].items()))
            lines.append("  - Orders by Region: " + ", ".join(f"{k}: {v}" for k, v in data["orders_by_region"].items()))
        if "name_filter" in data:
            nf = data["name_filter"]
            lines.append(
                f"  - Aggregate Match ('{nf['pattern']}'): {nf['matched_user_count']} users, "
                f"{nf['matched_order_count']} orders (names/emails/phones withheld)"
            )
        return ToolResult("ALLOWED", "\n".join(lines), "Read-only anonymized DB analytics (PII excluded).")

    @staticmethod
    def block_destructive_action(action_desc: str) -> ToolResult:
        """Deterministic block for destructive database/cluster/billing mutations."""
        reason = (
            f"BLOCKED by Layer 3 Policy & Scoped IAM: '{action_desc}' is strictly prohibited. "
            "Production databases, backups, multi-env terminations, and billing alerts are protected."
        )
        return ToolResult("BLOCKED", reason, "Hard-coded destructive/FinOps protection.")
