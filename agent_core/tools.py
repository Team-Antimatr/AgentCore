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
    def get_live_telemetry(limit: int = 5) -> ToolResult:
        """Read real Vercel/Render traffic & CPU telemetry from Neon PostgreSQL."""
        try:
            from backend.db import fetch_live_telemetry

            data = fetch_live_telemetry(limit=limit)
        except Exception as exc:
            return ToolResult("ALLOWED", f"Telemetry unavailable: {exc}", "Read-only telemetry check.")

        if not data.get("connected"):
            return ToolResult("ALLOWED", "Neon DB is not connected.", "Read-only telemetry check.")

        lines = [
            "Live Render + Vercel Telemetry (Neon DB `cloud_telemetry`):",
            f"  - Total Recorded Hits: {data['total_hits']} | Avg CPU: {data['avg_cpu']}%",
        ]
        for s in data["by_server"]:
            lines.append(f"  - {s['server']}: {s['hits']} hits (avg CPU {s['avg_cpu']}%)")
        for r in data["recent"][:3]:
            lines.append(f"  - Recent: [{r['server']}] {r['page']} ({r['action']}) @ {r['cpu']}% CPU")
        return ToolResult("ALLOWED", "\n".join(lines), "Read-only live telemetry check.")

    @staticmethod
    def manage_product_inventory(sku: str, action: str = "inspect", amount: int = 0) -> ToolResult:
        """Inspect or safely restock a real product in Neon shop_products."""
        act = action.strip().lower()
        if act in {"delete", "drop", "set_price_zero", "wipe"}:
            return ToolResult(
                "BLOCKED",
                f"Layer 3 Policy violation: '{act}' on product '{sku}' is forbidden.",
                "Product deletion and price tampering are blocked.",
            )
        if act == "restock" and (amount < 1 or amount > 50):
            return ToolResult(
                "BLOCKED",
                f"Layer 3 Policy violation: restock amount ({amount}) must be between 1 and 50 units.",
                "Bulk inventory mutation requires approval.",
            )
        try:
            from backend.db import query_or_update_product

            res = query_or_update_product(sku, action=act, amount=amount)
        except Exception as exc:
            return ToolResult("ALLOWED", f"Product query error: {exc}", "Inventory lookup.")

        if not res.get("connected"):
            return ToolResult("ALLOWED", "Neon DB is not connected.", "Inventory lookup.")
        if not res.get("found"):
            return ToolResult("ALLOWED", f"Product SKU '{sku}' not found in shop_products.", "Inventory lookup.")

        msg = (
            f"Product {res['sku']} ({res['title']}):\n"
            f"  - Category: {res['category']}\n"
            f"  - Price: INR {res['price_inr']:,.2f}\n"
            f"  - Stock: {res['stock']} units"
        )
        return ToolResult("ALLOWED", msg, f"Scoped inventory '{act}' on '{res['sku']}'.")

    @staticmethod
    def manage_order_status(order_code: str, action: str = "inspect", new_status: str = "") -> ToolResult:
        """Inspect or safely update a single order in Neon shop_orders (zero PII)."""
        act = action.strip().lower()
        if act in {"delete", "drop", "bulk_cancel", "export_pii"} or "*" in order_code or "all" in order_code.lower():
            return ToolResult(
                "BLOCKED",
                f"Layer 3 Policy violation: '{act}' / bulk order operation on '{order_code}' is forbidden.",
                "Bulk order mutations and PII export are blocked.",
            )
        allowed_statuses = {"processing", "shipped", "delivered"}
        if act == "update_status" and new_status.strip().lower() not in allowed_statuses:
            return ToolResult(
                "BLOCKED",
                f"Layer 3 Policy violation: status '{new_status}' is not allowed. Allowed: {sorted(allowed_statuses)}.",
                "Restricted order status transition.",
            )
        try:
            from backend.db import query_or_update_order

            res = query_or_update_order(order_code, action=act, new_status=new_status)
        except Exception as exc:
            return ToolResult("ALLOWED", f"Order query error: {exc}", "Order lookup.")

        if not res.get("connected"):
            return ToolResult("ALLOWED", "Neon DB is not connected.", "Order lookup.")
        if not res.get("found"):
            return ToolResult("ALLOWED", f"Order '{order_code}' not found in shop_orders.", "Order lookup.")

        msg = (
            f"Order {res['order_code']} (Zero PII):\n"
            f"  - Status: {res['status']}\n"
            f"  - Quantity: {res['quantity']} | Total: INR {res['total_inr']:,.2f}\n"
            f"  - Payment Method: {res['payment_method']}"
        )
        return ToolResult("ALLOWED", msg, f"Scoped order '{act}' on '{res['order_code']}'.")

    @staticmethod
    def get_security_audit_logs(limit: int = 8) -> ToolResult:
        """Read recent security and agent audit events from Neon PostgreSQL."""
        try:
            from backend.db import fetch_recent_audit_logs

            data = fetch_recent_audit_logs(limit=limit)
        except Exception as exc:
            return ToolResult("ALLOWED", f"Audit log query error: {exc}", "Read-only audit lookup.")

        if not data.get("connected"):
            return ToolResult("ALLOWED", "Neon DB is not connected.", "Read-only audit lookup.")

        lines = [f"Recent Security Audit Logs (latest {len(data['logs'])}):"]
        for row in data["logs"]:
            lines.append(f"  - [{row['status']}] ({row['tool']}) {row['prompt'][:60]}")
        return ToolResult("ALLOWED", "\n".join(lines), "Read-only security audit inspection.")

    @staticmethod
    def manage_finops_controls(action: str) -> ToolResult:
        """Manage billing alerts or spend caps (disabling/removing is blocked by Layer 3 policy)."""
        return ToolResult(
            "BLOCKED",
            f"Layer 3 Policy violation: '{action}' is forbidden. Billing alerts and hourly spend caps are immutable.",
            "Hard-coded FinOps spend-cap protection.",
        )

    @staticmethod
    def block_destructive_action(action_desc: str) -> ToolResult:
        """Deterministic block for destructive database/cluster/billing mutations."""
        reason = (
            f"BLOCKED by Layer 3 Policy & Scoped IAM: '{action_desc}' is strictly prohibited. "
            "Production databases, backups, multi-env terminations, and billing alerts are protected."
        )
        return ToolResult("BLOCKED", reason, "Hard-coded destructive/FinOps protection.")
