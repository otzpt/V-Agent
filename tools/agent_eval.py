#!/usr/bin/env python3
"""V-Agent agent eval: does a local model actually drive the tools?

Runs a set of scenarios against V-Agent's *real* shipped system prompt and the
full Write-profile toolset, and checks which tool (if any) the model calls.

The point is regression safety. V-Agent's tool-use behaviour on small local
models is prompt-sensitive: an 8B model given Zed's original prompt printed
code into the chat instead of calling `write_file`, and a single added
directive fixed it. That fix lives in `system_prompt.hbs` and is easy to
undo by accident during an upstream merge, so it needs a test.

Usage:
    python tools/agent_eval.py                # default model
    python tools/agent_eval.py --model qwen3:14b
    python tools/agent_eval.py --json         # machine-readable
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
PROMPT = REPO / "crates" / "agent" / "src" / "templates" / "system_prompt.hbs"
OLLAMA = "http://localhost:11434/api/chat"

# The Write profile's toolset, from assets/settings/default.json.
TOOL_NAMES = [
    "copy_path", "create_directory", "create_thread", "delete_path",
    "diagnostics", "apply_code_action", "edit_file", "write_file", "fetch",
    "find_path", "find_references", "get_code_actions", "go_to_definition",
    "list_agents_and_models", "list_directory", "move_path", "rename_symbol",
    "read_file", "grep", "skill", "spawn_agent", "terminal", "search_web",
]


def render_system_prompt() -> str:
    """Strip handlebars tags, keeping the prose the model actually receives."""
    raw = PROMPT.read_text(encoding="utf-8")
    text = re.sub(r"\{\{[#/][^}]*\}\}", "", raw)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name.replace('_', ' ').capitalize()} in the user's project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Project-relative path"},
                        "content": {"type": "string", "description": "File contents"},
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["path"],
                },
            },
        }
        for name in TOOL_NAMES
    ]


# `expect` lists acceptable tools. `expect: None` means the model SHOULD NOT
# call anything - guarding against over-triggering, which is its own failure.
SCENARIOS = [
    {
        "id": "create_file",
        "prompt": "Create a python calculator with add and subtract.",
        "expect": ["write_file", "create_directory"],
        "why": "Creating code must go through write_file, not a chat code block.",
    },
    {
        "id": "edit_existing",
        "prompt": "Add a docstring to the main function in app.py.",
        "expect": ["read_file", "edit_file", "find_path", "grep"],
        "why": "Editing requires reading the file first, not guessing its contents.",
    },
    {
        "id": "search_project",
        "prompt": "Are there any TODO comments left in here?",
        "expect": ["grep", "find_path", "list_directory"],
        "why": "Answering about project contents requires searching, not assuming.",
    },
    {
        "id": "explore",
        "prompt": "What files are in this project?",
        "expect": ["list_directory", "find_path", "grep"],
        "why": "Listing files requires a tool; the model cannot know them.",
    },
    {
        "id": "run_tests",
        "prompt": "Run the test suite and tell me if anything fails.",
        "expect": ["terminal", "find_path", "list_directory", "read_file"],
        "why": "Running tests requires the terminal tool.",
    },
    {
        "id": "no_tool_needed",
        "prompt": "In one sentence, what does the acronym LSP stand for in programming?",
        "expect": None,
        "why": "General knowledge needs no tool; calling one is over-triggering.",
    },
]


def run_scenario(model: str, system: str, tools: list[dict], scenario: dict,
                 num_ctx: int, timeout: int) -> dict:
    body = {
        "model": model,
        "stream": False,
        "think": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": scenario["prompt"]},
        ],
        "tools": tools,
        "options": {"num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        OLLAMA, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as exc:
        return {**scenario, "called": None, "ok": False,
                "error": str(exc), "elapsed": time.time() - started}

    message = data.get("message", {})
    calls = message.get("tool_calls") or []
    called = calls[0]["function"]["name"] if calls else None

    expect = scenario["expect"]
    ok = (called is None) if expect is None else (called in expect)

    return {
        **scenario,
        "called": called,
        "ok": ok,
        "content": (message.get("content") or "")[:160],
        "prompt_tokens": data.get("prompt_eval_count"),
        "elapsed": time.time() - started,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not PROMPT.is_file():
        print(f"system prompt not found: {PROMPT}", file=sys.stderr)
        return 2

    system, tools = render_system_prompt(), build_tools()
    results = []

    if not args.json:
        print(f"model         : {args.model}")
        print(f"system prompt : {len(system)} chars")
        print(f"tools offered : {len(tools)}\n")
        print(f"{'scenario':<18} {'expected':<28} {'called':<16} {'time':>7}  result")
        print("-" * 88)

    for scenario in SCENARIOS:
        res = run_scenario(args.model, system, tools, scenario,
                           args.num_ctx, args.timeout)
        results.append(res)
        if not args.json:
            expect = "<no tool>" if scenario["expect"] is None else "|".join(scenario["expect"])
            print(f"{res['id']:<18} {expect[:27]:<28} {str(res['called']):<16} "
                  f"{res['elapsed']:6.1f}s  {'PASS' if res['ok'] else 'FAIL'}")

    passed = sum(r["ok"] for r in results)
    if args.json:
        print(json.dumps({"model": args.model, "passed": passed,
                          "total": len(results), "results": results}, indent=2))
    else:
        print("-" * 88)
        print(f"{passed}/{len(results)} passed")
        for r in results:
            if not r["ok"]:
                print(f"\nFAIL {r['id']}: {r['why']}")
                print(f"  called : {r['called']}")
                if r.get("content"):
                    print(f"  said   : {r['content']!r}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
