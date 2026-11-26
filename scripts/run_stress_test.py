"""Run the 11-prompt Boundary Gate stress test against the live Render + Bedrock API."""

import json
import sys
import urllib.request
from pathlib import Path

API_URL = "https://agentcore-pnql.onrender.com/api/agent/chat"


def main() -> int:
    prompts = [
        p.strip()
        for p in Path("conversation_02.txt").read_text(encoding="utf-8").split("\n\n")
        if p.strip()
    ]
    for i, prompt in enumerate(prompts, 1):
        req = urllib.request.Request(
            API_URL,
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status", "UNKNOWN")
        trace = " | ".join(data.get("trace", []))
        print(f"{i:02d}. [{status}] {prompt[:70]}")
        print(f"    Trace: {trace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
