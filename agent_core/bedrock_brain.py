"""Step 2: Real Amazon Bedrock brain using Converse API, Tool Calling, and Bedrock Guardrails."""

import os
from dataclasses import dataclass

import boto3

from agent_core.config import load_dotenv
from agent_core.tools import CloudTools, ToolResult

SYSTEM_PROMPT = """You are the Bharat.in Online-Shopping Cloud & FinOps Operations Agent.
Tone: Polite, straightforward (work-to-work), and compact.
Use the available tools to fulfill the user's cloud infrastructure, server lifecycle, FinOps, and analytics requests.
Always rely on tool outputs rather than guessing metrics or counts."""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "list_resources",
                "description": "List active EC2 servers, containers, RDS databases, and GPU nodes in an environment.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "env": {"type": "string", "description": "Target environment: dev, staging, or production"}
                        },
                        "required": ["env"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "check_server_health",
                "description": "Check CPU utilization and health status of a specific server.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"server_name": {"type": "string", "description": "Exact server name"}},
                        "required": ["server_name"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_finops_breakdown",
                "description": "Get current hourly burn rate, monthly budget, and remaining cloud budget.",
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            }
        },
        {
            "toolSpec": {
                "name": "find_idle_resources",
                "description": "Find idle staging servers or unattached storage volumes running >= min_idle_hours.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "min_idle_hours": {"type": "integer", "description": "Minimum idle hours (default 48)"}
                        },
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "restart_server",
                "description": "Restart a server or container by name.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"server_name": {"type": "string", "description": "Server or container name"}},
                        "required": ["server_name"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "manage_finops_controls",
                "description": "Modify AWS billing alerts or hourly spend cap settings.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"action": {"type": "string", "description": "Action to perform on billing alerts or spend cap"}},
                        "required": ["action"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "provision_instance",
                "description": "Provision EC2 or GPU instances in an environment (dev, staging, or production).",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "instance_type": {"type": "string"},
                            "env": {"type": "string"},
                            "count": {"type": "integer"},
                            "role": {"type": "string"},
                        },
                        "required": ["instance_type", "env"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "create_approval_ticket",
                "description": "Create an engineering-lead approval ticket for GPU or high-cost resources like g5.xlarge.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "resource_type": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["resource_type", "reason"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_shop_analytics",
                "description": "Get anonymized, aggregated Bharat.in user, product, and order counts (summary, by city, by region, or aggregate name-pattern count). Never returns PII.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "group_by": {
                                "type": "string",
                                "description": "One of: summary, city, region",
                            },
                            "name_starts_with": {"type": "string"},
                            "name_ends_with": {"type": "string"},
                        },
                    }
                },
            }
        },
    ]
}


@dataclass
class BedrockExecution:
    """Result from a Bedrock Converse + Tool Calling run."""

    answer: str
    status: str  # "ALLOWED", "BLOCKED", "ESCALATED"
    tools_called: list[str]
    policy_notes: list[str]


class BedrockBrain:
    """Real Amazon Bedrock brain with Guardrails and native Tool Calling."""

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
    ) -> None:
        load_dotenv()
        self.region = region or os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
        self.guardrail_id = guardrail_id or os.getenv("BEDROCK_GUARDRAIL_ID")
        self.guardrail_version = guardrail_version or os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)

    def _dispatch_tool(self, name: str, tool_input: dict, tools: CloudTools) -> ToolResult:
        """Execute the requested CloudTools method with deterministic policy checks."""
        if name == "list_resources":
            return tools.list_resources(env=tool_input.get("env", "staging"))
        if name == "check_server_health":
            return tools.check_server_health(server_name=tool_input.get("server_name", ""))
        if name == "get_finops_breakdown":
            return tools.get_finops_breakdown()
        if name == "find_idle_resources":
            return tools.find_idle_resources(min_idle_hours=int(tool_input.get("min_idle_hours", 48)))
        if name in ("restart_staging_container", "restart_server"):
            target = tool_input.get("server_name") or tool_input.get("service_name", "")
            return tools.restart_staging_container(service_name=target)
        if name == "manage_finops_controls":
            return tools.manage_finops_controls(action=tool_input.get("action", "modify_spend_cap"))
        if name == "provision_instance":
            return tools.provision_instance(
                instance_type=tool_input.get("instance_type", ""),
                env=tool_input.get("env", ""),
                count=int(tool_input.get("count", 1)),
                role=tool_input.get("role", "QA Testing"),
            )
        if name == "create_approval_ticket":
            return tools.create_approval_ticket(
                resource_type=tool_input.get("resource_type", "g5.xlarge"),
                reason=tool_input.get("reason", "Engineering request"),
            )
        if name == "get_shop_analytics":
            return tools.get_shop_analytics(
                group_by=tool_input.get("group_by", "summary"),
                name_starts_with=tool_input.get("name_starts_with"),
                name_ends_with=tool_input.get("name_ends_with"),
            )
        return ToolResult("BLOCKED", f"Unknown tool '{name}'.", "Unknown tool blocked.")

    def execute(self, prompt: str, tools: CloudTools, max_turns: int = 5) -> BedrockExecution:
        """Run the Bedrock Converse tool-use loop with attached Guardrail."""
        messages: list[dict] = [{"role": "user", "content": [{"text": prompt}]}]
        tools_called: list[str] = []
        policy_notes: list[str] = []
        overall_status = "ALLOWED"

        kwargs: dict = {
            "modelId": self.model_id,
            "system": [{"text": SYSTEM_PROMPT}],
            "toolConfig": TOOL_CONFIG,
        }
        if self.guardrail_id:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self.guardrail_id,
                "guardrailVersion": self.guardrail_version,
            }

        for _ in range(max_turns):
            response = self.client.converse(messages=messages, **kwargs)
            stop_reason = response.get("stopReason")
            assistant_msg = response["output"]["message"]
            messages.append(assistant_msg)

            if stop_reason == "guardrail_intervened":
                text = " ".join(b.get("text", "") for b in assistant_msg.get("content", []) if "text" in b).strip()
                return BedrockExecution(
                    answer=text or "BLOCKED by Amazon Bedrock Guardrail.",
                    status="BLOCKED",
                    tools_called=tools_called,
                    policy_notes=["Amazon Bedrock Guardrail intervened."],
                )

            if stop_reason != "tool_use":
                text = "\n".join(b.get("text", "") for b in assistant_msg.get("content", []) if "text" in b).strip()
                return BedrockExecution(
                    answer=text or "(No response text returned.)",
                    status=overall_status,
                    tools_called=tools_called,
                    policy_notes=policy_notes or ["Bedrock Converse completed."],
                )

            tool_results_content = []
            for block in assistant_msg.get("content", []):
                if "toolUse" not in block:
                    continue
                tu = block["toolUse"]
                t_name = tu["name"]
                t_input = tu.get("input", {})
                tools_called.append(t_name)

                res = self._dispatch_tool(t_name, t_input, tools)
                policy_notes.append(f"{t_name}: {res.status} ({res.policy_note})")
                if res.status == "BLOCKED":
                    overall_status = "BLOCKED"
                elif res.status == "ESCALATED" and overall_status != "BLOCKED":
                    overall_status = "ESCALATED"

                tool_results_content.append(
                    {
                        "toolResult": {
                            "toolUseId": tu["toolUseId"],
                            "content": [{"text": f"[{res.status}] {res.output}"}],
                        }
                    }
                )

            messages.append({"role": "user", "content": tool_results_content})

        return BedrockExecution(
            answer="Stopped after reaching max tool-calling turns.",
            status=overall_status,
            tools_called=tools_called,
            policy_notes=policy_notes,
        )
