"""Layer 2: Agent orchestrator supporting Step 1 (local) and Step 2 (Amazon Bedrock)."""

import os
import re
from dataclasses import dataclass, field

from agent_core.audit import AuditLogger
from agent_core.config import load_dotenv
from agent_core.guardrails import check_input
from agent_core.infra_state import InfraState
from agent_core.tools import CloudTools, ToolResult


@dataclass
class AgentResponse:
    """Full response returned to CLI or future UI."""

    answer: str
    status: str  # "ALLOWED", "BLOCKED", "ESCALATED"
    trace: list[str] = field(default_factory=list)


class LocalIntentPlanner:
    """Step 1 local brain that maps natural-language requests to scoped cloud tools."""

    def execute(self, prompt: str, tools: CloudTools) -> tuple[str, ToolResult]:
        """Select and invoke the appropriate tool for the user's request."""
        p = prompt.lower()

        # Check destructive / FinOps-attack intents first (defense-in-depth behind Layer 1)
        if any(k in p for k in ("drop ", "purge ", "wipe ", "terminate all", "delete all")):
            return "block_destructive_action", tools.block_destructive_action(prompt)

        if "billing alert" in p or "spend cap" in p:
            if any(k in p for k in ("disable", "remove", "turn off", "delete")):
                return "block_destructive_action", tools.block_destructive_action(
                    "Disable AWS billing alerts / remove hourly spend cap"
                )

        # GPU / Instance provisioning (allowed 1x t3.micro dev, escalated 1x g5.xlarge, blocked 20x p4d)
        if any(k in p for k in ("p4d.24xlarge", "p4d", "g5.xlarge", "t3.micro", "spin up", "launch ")):
            count_match = re.search(r"\b(\d+)\s+(?:p4d|g5|t3)", p)
            count = int(count_match.group(1)) if count_match else 1
            if "p4d.24xlarge" in p or "p4d" in p:
                return "provision_instance", tools.provision_instance("p4d.24xlarge", "production", count=count)
            if "g5.xlarge" in p:
                return "create_approval_ticket", tools.create_approval_ticket(
                    "1x g5.xlarge GPU node", "Model inference testing (Online-Shopping recommendation)"
                )
            if "t3.micro" in p:
                env = "dev" if "dev" in p else ("production" if "prod" in p else "staging")
                return "provision_instance", tools.provision_instance("t3.micro", env, count=count, role="QA testing")

        # Restart staging container
        if "restart" in p:
            target = "staging-auth-service" if "staging-auth-service" in p else "prod-checkout-api-01"
            return "restart_staging_container", tools.restart_staging_container(target)

        # Idle staging resources > 48h
        if "idle" in p or "unattached" in p:
            return "find_idle_resources", tools.find_idle_resources(min_idle_hours=48)

        # FinOps burn rate & budget
        if any(k in p for k in ("burn rate", "budget", "cost", "spend", "finops")):
            return "get_finops_breakdown", tools.get_finops_breakdown()

        # Server health / CPU utilization
        if any(k in p for k in ("cpu", "health", "utilization")):
            for name in tools.state.servers:
                if name in p:
                    return "check_server_health", tools.check_server_health(name)
            return "check_server_health", tools.check_server_health("staging-api-server-01")

        # List resources
        if any(k in p for k in ("list", "active", "ec2", "rds", "servers", "gpu")):
            env = "dev" if "dev" in p else ("production" if "production" in p else "staging")
            return "list_resources", tools.list_resources(env=env)

        return (
            "help",
            ToolResult(
                "ALLOWED",
                "I can help with Online-Shopping cloud visibility, FinOps audits, staging restarts, "
                "dev t3.micro provisioning, and GPU approval tickets. Type 'help' for example prompts.",
                "No mutation performed.",
            ),
        )


class CloudGuardAgent:
    """Main Online-Shopping Cloud Infrastructure Guard Agent."""

    def __init__(
        self,
        state: InfraState | None = None,
        audit_logger: AuditLogger | None = None,
        mode: str = "local",
    ) -> None:
        load_dotenv()
        self.state = state or InfraState.create_default()
        self.tools = CloudTools(self.state)
        self.mode = mode.lower()
        self.planner = LocalIntentPlanner()
        self.bedrock_brain = None
        if self.mode == "bedrock":
            from agent_core.bedrock_brain import BedrockBrain

            self.bedrock_brain = BedrockBrain()
        self.audit = audit_logger or AuditLogger()

    def handle(self, prompt: str) -> AgentResponse:
        """Process a user prompt through all 4 security and execution layers."""
        trace: list[str] = []

        # Layer 1: Input Guardrail (local deterministic check)
        guard = check_input(prompt)
        trace.append(f"[GUARDRAIL] {guard.category}: {guard.reason}")
        if not guard.allowed:
            self.audit.log(prompt, guard.category, "none", "BLOCKED", guard.reason)
            trace.append("[AUDIT] Logged BLOCKED event to logs/audit.jsonl")
            return AgentResponse(answer=f"BLOCKED ({guard.category}): {guard.reason}", status="BLOCKED", trace=trace)

        # Layer 2 & 3: Agent Brain (Bedrock or Local) + Scoped Tools
        if self.mode == "bedrock" and self.bedrock_brain is not None:
            gid = os.getenv("BEDROCK_GUARDRAIL_ID", "none")
            trace.append(
                f"[THINKING] Calling Amazon Bedrock ({self.bedrock_brain.model_id}) with Guardrail ({gid})..."
            )
            exec_res = self.bedrock_brain.execute(prompt, self.tools)
            tools_label = ", ".join(exec_res.tools_called) if exec_res.tools_called else "none"
            trace.append(f"[TOOL] Invoked: {tools_label}")
            for note in exec_res.policy_notes:
                trace.append(f"[POLICY] {note}")
            self.audit.log(prompt, guard.category, tools_label, exec_res.status, "; ".join(exec_res.policy_notes))
            trace.append(f"[AUDIT] Logged {exec_res.status} event to logs/audit.jsonl")
            return AgentResponse(answer=exec_res.answer, status=exec_res.status, trace=trace)

        trace.append("[THINKING] Analyzing Online-Shopping infra request and selecting scoped tool...")
        tool_name, result = self.planner.execute(prompt, self.tools)
        trace.append(f"[TOOL] Invoked '{tool_name}'")
        trace.append(f"[POLICY] {result.status}: {result.policy_note}")

        self.audit.log(prompt, guard.category, tool_name, result.status, result.policy_note)
        trace.append(f"[AUDIT] Logged {result.status} event to logs/audit.jsonl")

        return AgentResponse(answer=result.output, status=result.status, trace=trace)
