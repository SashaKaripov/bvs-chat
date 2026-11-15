#!/usr/bin/env python3
"""Read services/web/app.js and check the chat API calls. No network."""

import re
import sys
from pathlib import Path


def fetch_calls(src: str):
    calls = []
    token = "fetch("
    start = 0
    while True:
        at = src.find(token, start)
        if at < 0:
            break
        depth = 0
        end = None
        for pos in range(at + len(token) - 1, len(src)):
            char = src[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        if end is None:
            break
        calls.append(src[at : end + 1])
        start = end + 1
    return calls


def method_of(call: str) -> str:
    found = re.search(r"""method\s*:\s*["']([A-Za-z]+)["']""", call)
    if not found:
        return "GET"
    return found.group(1).upper()


def first_string(call: str) -> str:
    found = re.search(r"""["']([^"']*)["']""", call)
    return found.group(1) if found else ""


def main() -> int:
    path = Path(__file__).resolve().parent / "app.js"
    src = path.read_text(encoding="utf-8")
    problems = []

    if "innerHTML" in src:
        problems.append("app.js contains innerHTML")
    if re.search(r"openrouter", src, re.IGNORECASE):
        problems.append("app.js contains openrouter")
    if re.search(r"https?://", src):
        problems.append("app.js contains an absolute host")

    calls = fetch_calls(src)
    if not calls:
        problems.append("app.js has no fetch calls")

    get_messages = False
    post_messages = False
    patch_messages = False
    delete_messages = False

    for call in calls:
        method = method_of(call)
        url = first_string(call)
        allowed = (
            url == "/api/messages"
            or url.startswith("/api/messages/")
            or url == "/api/health"
        )
        if not allowed:
            problems.append("unexpected fetch: " + call.splitlines()[0])
            continue
        if method == "GET" and url == "/api/messages":
            get_messages = True
        elif method == "POST" and url == "/api/messages":
            post_messages = True
        elif method == "PATCH" and "/api/messages/" in call:
            patch_messages = True
        elif method == "DELETE" and "/api/messages/" in call:
            delete_messages = True

    if not get_messages:
        problems.append("missing GET /api/messages")
    if not post_messages:
        problems.append("missing POST /api/messages")
    if not patch_messages:
        problems.append("missing PATCH /api/messages/")
    if not delete_messages:
        problems.append("missing DELETE /api/messages/")

    if problems:
        print("\n".join(problems))
        return 1

    print("GET /api/messages")
    print("POST /api/messages")
    print("PATCH /api/messages/")
    print("DELETE /api/messages/")
    print("no innerHTML")
    print("no openrouter")
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
