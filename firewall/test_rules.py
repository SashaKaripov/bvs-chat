#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXPECTED = {
    "web": [
        ("allow", "tcp", "chat-api", "8000"),
        ("allow", "udp", "any", "53"),
        ("allow", "tcp", "any", "53"),
        ("deny", "tcp", "any", "5432"),
        ("deny", "tcp", "any", "6379"),
        ("deny", "tcp", "any", "5672"),
        ("deny", "tcp", "any", "15672"),
        ("deny", "tcp", "any", "443"),
    ],
    "chat-api": [
        ("allow", "tcp", "postgres-router", "5432"),
        ("allow", "tcp", "redis", "6379"),
        ("allow", "tcp", "rabbitmq-1", "5672"),
        ("allow", "tcp", "rabbitmq-2", "5672"),
        ("allow", "tcp", "rabbitmq-3", "5672"),
        ("allow", "udp", "any", "53"),
        ("allow", "tcp", "any", "53"),
        ("deny", "tcp", "any", "443"),
        ("deny", "tcp", "any", "15672"),
        ("deny", "tcp", "postgres-primary", "5432"),
        ("deny", "tcp", "postgres-standby", "5432"),
    ],
    "worker": [
        ("allow", "tcp", "postgres-router", "5432"),
        ("allow", "tcp", "redis", "6379"),
        ("allow", "tcp", "rabbitmq-1", "5672"),
        ("allow", "tcp", "rabbitmq-2", "5672"),
        ("allow", "tcp", "rabbitmq-3", "5672"),
        ("allow", "tcp", "any", "443"),
        ("allow", "udp", "any", "53"),
        ("allow", "tcp", "any", "53"),
        ("deny", "tcp", "any", "15672"),
    ],
}

SHELLS = ("apply.sh", "break-legit.sh", "restore-legit.sh", "demo-deny.sh")


def parse_rules(text):
    roles = {}
    order = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "role" and len(parts) == 2:
            current = parts[1]
            if current not in roles:
                order.append(current)
                roles[current] = []
            continue
        roles[current].append(tuple(parts))
    return order, roles


def main():
    failures = []
    order, roles = parse_rules((ROOT / "rules.conf").read_text(encoding="utf-8"))
    if order != ["web", "chat-api", "worker"] or roles != EXPECTED:
        failures.append("rules.conf mismatch")

    apply = (ROOT / "apply.sh").read_text(encoding="utf-8")
    if "iptables -P OUTPUT DROP" not in apply:
        failures.append("apply.sh missing OUTPUT DROP")
    if "REJECT" not in apply or "ACCEPT" not in apply:
        failures.append("apply.sh missing REJECT or ACCEPT")

    for name in SHELLS:
        result = subprocess.run(["sh", "-n", str(ROOT / name)], capture_output=True, text=True)
        if result.returncode != 0:
            failures.append(f"sh -n {name}: {(result.stderr or '').strip()}")

    if failures:
        print("FAIL")
        for item in failures:
            print(item)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
