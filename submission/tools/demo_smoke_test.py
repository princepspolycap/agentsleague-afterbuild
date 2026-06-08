"""End-to-end demo smoke test: exercise every live demo path over HTTP.

This drives the same API the browser UI calls, so a green run proves the
on-stage flows actually work - not just that the models respond. It covers the
three entry points a presenter can hit:

  1. Quest manual:  /api/init -> (execute -> approve) x3
  2. World autoplay: /api/world/autoplay (design + run all chapters)

For each path it asserts the demo-critical invariants:
  - every step/chapter ends 'completed'
  - every artifact is non-empty
  - every validation score is a real number (never None)
  - the run reaches its terminal stage (validated / launched)

Usage (server must already be running on the given base URL):
    ../.venv/bin/python tools/demo_smoke_test.py --base http://127.0.0.1:8050

Exit code 0 = all paths green. Non-zero = a demo path is broken; the failing
assertion is printed. Works against both live and simulation servers - in
simulation it proves the forkable fallback path; in live it proves Foundry.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


class SmokeError(Exception):
    """Raised when a demo invariant fails."""


def _post(base: str, path: str, body: dict | None = None, timeout: int = 240) -> dict:
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _get(base: str, path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(base + path, timeout=timeout) as resp:
        return json.loads(resp.read())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def check_quest_path(base: str, pitch: str) -> None:
    """Init a quest, then execute+approve every step like the manual demo."""
    print("\n[1/2] QUEST MANUAL PATH")
    _post(base, "/api/reset")
    out = _post(base, "/api/init", {"pitch": pitch, "company_name": "SmokeCo"})
    steps = (out.get("state", {}).get("active_quest") or {}).get("steps", [])
    _require(len(steps) == 3, f"expected 3 quest steps, got {len(steps)}")
    print(f"  decomposed -> {', '.join(s['assigned_to'] for s in steps)}")

    for i in range(3):
        ex = _post(base, "/api/step/execute")
        st = ex.get("current_step", {})
        artifact = st.get("artifact_data") or {}
        vr = st.get("validation_results") or {}
        score = vr.get("score")
        role = st.get("assigned_to", "?")
        _require(bool(artifact), f"step {i+1} ({role}) produced an empty artifact")
        _require(isinstance(score, (int, float)), f"step {i+1} ({role}) score is {score!r}, not a number")
        print(f"  step{i+1} {role:<11} score={score} keys={list(artifact)[:3]}")
        _post(base, "/api/step/approve")

    state = _get(base, "/api/state")["state"]
    _require(state["stage"] == "validated", f"quest did not reach 'validated' (stage={state['stage']})")
    _require((state.get("active_quest") or {}).get("status") == "completed", "quest status not 'completed'")
    print(f"  OK -> stage=validated xp={state['xp']} level={state['level']}")


def check_world_path(base: str, pitch: str) -> None:
    """Run the full World autoplay (design + execute all chapters)."""
    print("\n[2/2] WORLD AUTOPLAY PATH")
    _post(base, "/api/reset")
    t = time.time()
    out = _post(base, "/api/world/autoplay", {"pitch": pitch, "company_name": "SmokeWorld"})
    dt = time.time() - t
    state = out["state"]
    world = state.get("world") or {}
    chapters = world.get("chapters", [])
    _require(len(chapters) >= 3, f"expected >=3 chapters, got {len(chapters)}")

    for ch in chapters:
        artifact = ch.get("artifact") or {}
        score = ch.get("validation_score")
        _require(ch["status"] == "completed", f"chapter {ch['id']} status={ch['status']} (not completed)")
        _require(bool(artifact), f"chapter {ch['id']} produced an empty artifact")
        _require(isinstance(score, (int, float)), f"chapter {ch['id']} score is {score!r}, not a number")
        print(f"  {ch['id']:<18} {ch['owner_role']:<11} score={score} keys={list(artifact)[:3]}")

    _require(world.get("status") == "completed", f"world status={world.get('status')} (not completed)")
    _require(state["stage"] == "launched", f"world did not reach 'launched' (stage={state['stage']})")
    print(f"  OK -> stage=launched xp={state['xp']} level={state['level']} ({dt:.1f}s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end demo smoke test.")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="Server base URL")
    parser.add_argument("--pitch", default="A budgeting app that turns bank transactions into weekly money coaching tips")
    parser.add_argument("--skip-world", action="store_true", help="Skip the slower World autoplay path")
    args = parser.parse_args()

    print(f"Demo smoke test against {args.base}")
    try:
        _get(args.base, "/api/state")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: server not reachable at {args.base} ({exc})")
        return 2

    try:
        check_quest_path(args.base, args.pitch)
        if not args.skip_world:
            check_world_path(args.base, args.pitch)
    except SmokeError as exc:
        print(f"\nFAIL: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL (unexpected): {exc}")
        return 1

    print("\nALL DEMO PATHS GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
