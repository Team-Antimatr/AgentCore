"""Interactive Cloud CLI matching the Figma design (node 595:2) with Rich rendering."""

import argparse
import os
import sys

from rich.console import Console
from rich.markdown import Markdown

from agent_core import CloudGuardAgent
from agent_core.config import load_dotenv
from agent_core.logo import render_aws_logo

if os.name == "nt":
    os.system("")

console = Console()

TASKS_TEXT = """
[#FF9900][Agent][/] : Supported Consumer Commerce Cloud Tasks:
  1. List staging/dev EC2, RDS & GPU resources
  2. Check server CPU & health (e.g., staging-api-server-01)
  3. FinOps burn rate & monthly budget breakdown
  4. Find idle staging servers / unattached volumes (>48h)
  5. Restart staging containers (e.g., staging-auth-service)
  6. Spin up 1x t3.micro in dev for QA testing
  7. Request approval ticket for g5.xlarge GPU node
"""

HELP_TEXT = """
[#FF9900][Agent][/] : Commands: 'help' | 'task' | 'logs' | 'clear' | 'exit' (or Ctrl+C)
  Tip: Run with '--trace' to inspect Guardrail, Tool, Policy, and Audit steps.
"""

STATUS_STYLES = {
    "ALLOWED": "bold green",
    "ESCALATED": "bold yellow",
    "BLOCKED": "bold red",
}


def _print_logs(agent: CloudGuardAgent) -> None:
    """Display recent audit log entries."""
    entries = agent.audit.read_recent(limit=10)
    if not entries:
        console.print("\n[#FF9900][Agent][/] : No audit logs recorded yet.\n")
        return
    console.print("\n[#FF9900][Agent][/] : Recent Audit Logs:")
    for e in entries:
        style = STATUS_STYLES.get(e["status"], "white")
        console.print(f"  [{style}][{e['status']}][/] {e['tool_used']} | {e['prompt'][:65]}")
    console.print()


def main() -> int:
    """Run the Consumer Commerce Cloud Agent CLI."""
    load_dotenv()
    default_mode = "bedrock" if os.getenv("AWS_BEARER_TOKEN_BEDROCK") else "local"

    parser = argparse.ArgumentParser(description="Consumer Commerce Cloud Agent CLI")
    parser.add_argument("--trace", action="store_true", help="Show step-by-step Guardrail/Tool/Policy/Audit trace")
    parser.add_argument(
        "--mode",
        choices=["bedrock", "local"],
        default=default_mode,
        help=f"Agent brain mode (default: {default_mode})",
    )
    args = parser.parse_args()

    agent = CloudGuardAgent(mode=args.mode)
    model_name = "Claude Haiku 4.5 v1" if args.mode == "bedrock" else "Local Intent Planner"

    print(render_aws_logo())
    console.print("Consumer Commerce Cloud Agent is Here ! What request i assist to you ?\n")
    console.print(f"Model Assigned  : [#FF9900]{model_name}[/]")
    console.print('Enter "help" or "task" to see what requests this agent can serve')
    console.print("Ctrl+C  to exit the agent conversation\n")
    console.print("[#FF9900][Agent][/] : Hi, what request for me ?")

    while True:
        try:
            prompt = console.input("User : ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[#FF9900][Agent][/] : Goodbye. Stay safe!")
            return 0

        if not prompt:
            continue
        cmd = prompt.lower()
        if cmd in {"exit", "quit"}:
            console.print("[#FF9900][Agent][/] : Goodbye. Stay safe!")
            return 0
        if cmd == "help":
            console.print(HELP_TEXT)
            continue
        if cmd in {"task", "tasks"}:
            console.print(TASKS_TEXT)
            continue
        if cmd == "logs":
            _print_logs(agent)
            continue
        if cmd == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            print(render_aws_logo())
            continue

        with console.status("[#FF9900]Thinking...[/]", spinner="dots"):
            response = agent.handle(prompt)

        if args.trace:
            console.print("[dim]--- Trace ---[/]")
            for step in response.trace:
                console.print(f"[dim]  {step}[/]")

        style = STATUS_STYLES.get(response.status, "white")
        console.print(f"[#FF9900][Agent][/] [{style}][{response.status}][/] :")
        console.print(Markdown(response.answer))
        console.print()


if __name__ == "__main__":
    sys.exit(main())
