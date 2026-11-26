"""Layer 1: Input Guardrail for prompt injection, spoofing, obfuscation, and secret exfiltration."""

import base64
import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    """Result of evaluating a user prompt against Layer 1 security rules."""

    allowed: bool
    category: str
    reason: str


_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"ignore\s+(all\s+)?safety\s+rules",
    r"bypass\s+(all\s+)?(safety|security|system)\s*(checks|rules|boundaries)?",
    r"system\s+boundaries",
    r"\brm\s+-rf\b",
    r"silently\s+without\s+logging",
    r"without\s+logging",
]

_SPOOFING_PATTERNS = [
    r"(i\s+am|this\s+is)\s+(the\s+)?(cto|ceo|vp|admin|root|security\s+lead)",
    r"emergency\s+override\s+code",
    r"override\s+code\s+\d+",
]

_SECRET_EXFIL_PATTERNS = [
    r"\.env\b",
    r"iam\s+access\s+keys?",
    r"database\s+connection\s+strings?",
    r"export\s+all\s+.*secrets",
    r"output\s+the\s+underlying\s+iam\s+policy",
]

_PII_EXFIL_PATTERNS = [
    r"(mobile|phone|contact)\s+numbers?",
    r"contact\s+email\s+(address|id)?",
    r"email\s+address(es)?",
    r"list\s+.*\b(phones?|emails?|contacts?)\b",
    r"(exact\s+people|exact\s+consumer|special\s+hash\s+id|hash\s+id|user\s+hash)",
]

_AVAILABILITY_SABOTAGE_PATTERNS = [
    r"spinning\s+(mode|instance)",
    r"increase\s+spinning",
    r"hang\s+(the\s+)?server",
]

_IAM_TAMPER_PATTERNS = [
    r"modify\s+(the\s+)?(agent'?s\s+)?iam\s+permissions?",
    r"grant\s+full\s+admin\s+write\s+access",
    r"write\s+directly\s+to\s+production",
]

_BASE64_TOKEN_RE = re.compile(r"\b[A-Za-z0-9+/]{12,}={0,2}\b")
_DANGEROUS_DECODED_WORDS = ("rm -rf", "delete", "drop", "terminate", "wipe", "purge", "secret")


def _matches_any(text: str, patterns: list[str]) -> str | None:
    """Return the first matching regex pattern, or None."""
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def _inspect_base64_payloads(prompt: str) -> str | None:
    """Decode base64-like tokens and check for hidden destructive commands."""
    if "base64" not in prompt.lower() and not _BASE64_TOKEN_RE.search(prompt):
        return None
    for token in _BASE64_TOKEN_RE.findall(prompt):
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8", errors="ignore").lower()
        except Exception:
            continue
        if any(word in decoded for word in _DANGEROUS_DECODED_WORDS):
            return decoded
    if "base64" in prompt.lower() and any(
        w in prompt.lower() for w in ("decode", "run", "execute", "deletion", "delete")
    ):
        return "base64-encoded command execution request"
    return None


def check_input(prompt: str) -> GuardrailResult:
    """Evaluate a prompt before it reaches the agent brain or tools."""
    if not prompt or not prompt.strip():
        return GuardrailResult(False, "EMPTY_INPUT", "Prompt cannot be empty.")

    if _matches_any(prompt, _SPOOFING_PATTERNS):
        return GuardrailResult(
            False,
            "AUTHORITY_SPOOFING",
            "Blocked authority spoofing or emergency override attempt. "
            "Identity claims in chat text cannot bypass security policies.",
        )

    if _matches_any(prompt, _SECRET_EXFIL_PATTERNS):
        return GuardrailResult(
            False,
            "SECRET_EXFILTRATION",
            "Blocked attempt to export secrets, connection strings, .env data, or IAM policies.",
        )

    if _matches_any(prompt, _PII_EXFIL_PATTERNS):
        return GuardrailResult(
            False,
            "PII_EXFILTRATION",
            "Blocked attempt to extract customer PII (mobile numbers, email addresses, or user hash IDs). "
            "Only anonymized aggregate counts are permitted.",
        )

    if _matches_any(prompt, _AVAILABILITY_SABOTAGE_PATTERNS):
        return GuardrailResult(
            False,
            "AVAILABILITY_SABOTAGE",
            "Blocked attempt to put user-facing servers into spinning/degraded mode or artificially delay auth.",
        )

    if _matches_any(prompt, _IAM_TAMPER_PATTERNS):
        return GuardrailResult(
            False,
            "PRIVILEGE_ESCALATION",
            "Blocked privilege escalation: the agent cannot modify IAM roles or grant admin write access.",
        )

    if _matches_any(prompt, _INJECTION_PATTERNS):
        return GuardrailResult(
            False,
            "PROMPT_INJECTION",
            "Blocked prompt injection or audit-bypass attempt.",
        )

    decoded_danger = _inspect_base64_payloads(prompt)
    if decoded_danger:
        return GuardrailResult(
            False,
            "OBFUSCATED_PAYLOAD",
            f"Blocked obfuscated/base64 command execution attempt ({decoded_danger}).",
        )

    return GuardrailResult(True, "SAFE", "Input passed Layer 1 Guardrail checks.")
