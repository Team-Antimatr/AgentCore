"""Layer 3: Deterministic policy limits for Online-Shopping cloud operations."""

from dataclasses import dataclass

ALLOWED_MUTATION_ENVS = {"dev", "staging"}
ALLOWED_SELF_SERVICE_TYPES = {"t3.micro", "t3.small"}
MAX_SELF_SERVICE_COUNT = 1
APPROVAL_REQUIRED_TYPES = {"g5.xlarge"}
BLOCKED_GPU_TYPES = {"p4d.24xlarge", "p4d", "p5.48xlarge"}


@dataclass
class PolicyDecision:
    """Outcome of a deterministic policy check."""

    status: str  # "ALLOWED", "BLOCKED", "ESCALATED"
    reason: str


def check_mutation_env(env: str, action: str) -> PolicyDecision:
    """Allow write/restart/provision mutations only in dev or staging."""
    env_clean = env.strip().lower()
    if env_clean not in ALLOWED_MUTATION_ENVS:
        return PolicyDecision(
            "BLOCKED",
            f"Policy violation: '{action}' is forbidden in '{env_clean}'. "
            f"Mutations are restricted to {sorted(ALLOWED_MUTATION_ENVS)}.",
        )
    return PolicyDecision("ALLOWED", f"Environment '{env_clean}' is permitted for '{action}'.")


def check_provision_request(instance_type: str, env: str, count: int) -> PolicyDecision:
    """Enforce instance type, count, and environment limits."""
    env_clean = env.strip().lower()
    itype = instance_type.strip().lower()

    if itype in BLOCKED_GPU_TYPES or count > MAX_SELF_SERVICE_COUNT and itype.startswith(("p4", "p5", "g5")):
        return PolicyDecision(
            "BLOCKED",
            f"FinOps Policy violation: launching {count}x {instance_type} without approval is blocked "
            f"to prevent runaway cloud spend.",
        )

    if itype in APPROVAL_REQUIRED_TYPES:
        return PolicyDecision(
            "ESCALATED",
            f"{instance_type} requires Engineering Lead approval before provisioning.",
        )

    env_check = check_mutation_env(env_clean, "provision_instance")
    if env_check.status != "ALLOWED":
        return env_check

    if env_clean != "dev":
        return PolicyDecision(
            "BLOCKED",
            "Self-service instance provisioning is only allowed in 'dev' for QA testing.",
        )

    if itype not in ALLOWED_SELF_SERVICE_TYPES or count > MAX_SELF_SERVICE_COUNT:
        return PolicyDecision(
            "BLOCKED",
            f"Self-service is capped at {MAX_SELF_SERVICE_COUNT}x {sorted(ALLOWED_SELF_SERVICE_TYPES)} in 'dev'.",
        )

    return PolicyDecision("ALLOWED", f"Approved self-service {count}x {instance_type} in '{env_clean}'.")
