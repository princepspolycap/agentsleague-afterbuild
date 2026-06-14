"""Smoke checks for the UI/game/backend gap fixes.

Runs fully offline in simulation mode. It verifies the seams that were easy to
regress while tightening the playable loop:

1. Analyze -> world design stays one run_id / save-slot scope.
2. TTS cache helpers are deterministic and reusable.
3. Long idle economy catch-up is capped and does not trigger surprise layoffs.
4. Route-room choices have deterministic effects and stay tied to a stage.
5. Hire/fire receipts keep economics and org state in sync.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


SUBMISSION_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SUBMISSION_DIR))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    base = tempfile.mkdtemp(prefix="agentsleague_gap_smoke_")
    os.environ["CAMPAIGN_STATE_FILE"] = str(Path(base) / "state.json")
    os.environ["CAMPAIGN_MEMORY_FILE"] = str(Path(base) / "memory.json")
    os.environ["DEMO_MODE"] = "simulation"
    os.environ["ECONOMY_MAX_CATCHUP_DAYS"] = "2"

    from fastapi.testclient import TestClient  # noqa: WPS433
    import tools.server as server  # noqa: WPS433

    client = TestClient(server.app)

    def post(path: str, body: dict | None = None) -> dict:
        response = client.post(path, json=body or {})
        if response.status_code != 200:
            raise RuntimeError(f"{path} -> {response.status_code}: {response.text[:500]}")
        return response.json()

    def post_status(path: str, body: dict | None = None) -> int:
        return client.post(path, json=body or {}).status_code

    def get(path: str) -> dict:
        response = client.get(path)
        if response.status_code != 200:
            raise RuntimeError(f"{path} -> {response.status_code}: {response.text[:500]}")
        return response.json()

    key = server._tts_cache_key("hello world", "onyx", "calm")
    server._tts_cache_put(key, b"audio-bytes", "tts-test")
    require(server._tts_cache_get(key) == (b"audio-bytes", "tts-test"), "TTS cache round trip failed")

    analyze = post("/api/founder/analyze", {
        "pitch": "Solar microgrids for rural clinics",
        "company_name": "QuestForge Ltd.",
        "founder_name": "Ada",
    })
    analyze_run_id = analyze["state"]["run_id"]
    require(analyze_run_id, "analyze did not assign a run_id")

    design = post("/api/world/design", {
        "pitch": "Solar microgrids for rural clinics",
        "company_name": "QuestForge Ltd.",
        "founder_name": "Ada",
    })
    state_payload = design["state"]
    require(state_payload["run_id"] == analyze_run_id, "world design forked a new run_id")
    require(state_payload["org"]["digital_worker_count"] >= 2, "world design did not retain/build an org")
    slots = get("/api/slots")["slots"]
    require(analyze_run_id in {slot["run_id"] for slot in slots}, "active run was not mirrored to slots")

    memory = json.loads(Path(os.environ["CAMPAIGN_MEMORY_FILE"]).read_text())
    run_ids = {m.get("payload", {}).get("run_id") for m in memory if m.get("payload", {}).get("run_id")}
    require(run_ids == {analyze_run_id}, f"memory leaked across run scopes: {run_ids}")

    room_ids = state_payload["game"]["available_room_ids"]
    require(room_ids, "no route rooms available after world design")
    room = post("/api/game/room/choose", {"room_id": room_ids[-1]})["move"]
    require(room["effects_applied"].get("room_id") == room_ids[-1], "room choice receipt lost room_id")
    require(room["stage_id"], "room choice is not tied to a stage")
    next_room_ids = list(room["effects_applied"].get("next_ids") or [])
    require(next_room_ids, "chosen room did not expose next route ids")
    require(
        post_status("/api/game/room/choose", {"room_id": next_room_ids[0]}) == 400,
        "route map allowed choosing a future room before the current stage shipped",
    )
    run_next = post("/api/world/run-next")
    require(run_next["stage"]["id"] == room["stage_id"], "run-next did not execute the chosen room's stage")
    unlocked = run_next["state"]["game"]["available_room_ids"]
    require(unlocked == next_room_ids, f"stage completion did not unlock next route rooms: {unlocked} != {next_room_ids}")

    options = get("/api/org/options")["options"]
    require(options and all(o["monthly_cost_usd"] >= 0 for o in options), "hire options missing costs")
    hire = post("/api/org/hire", {"role_key": "sales"})
    hired_id = hire["receipt"]["hired_id"]
    require(hire["receipt"]["runway_days"] == hire["state"]["economics"]["runway_days"], "hire runway drifted")
    require(any(r["id"] == hired_id for r in hire["state"]["org"]["roles"]), "hired worker not in org")
    fire = post("/api/org/fire", {"role_id": hired_id})
    require(fire["receipt"]["runway_days"] == fire["state"]["economics"]["runway_days"], "fire runway drifted")
    require(all(r["id"] != hired_id for r in fire["state"]["org"]["roles"]), "fired worker still in org")

    state = server.store.load()
    before_points = state.economics.points
    before_workers = state.org.digital_worker_count
    state.economics.last_tick_epoch = time.time() - (60 * 60 * 24)
    server.store.save()
    tick = server._advance_clock(server.store.load())
    after = server.store.load()
    require(tick["days_advanced"] == 2.0, f"idle catch-up was not capped: {tick}")
    require(tick["wall_clock_days"] > 100 and tick["idle_days_skipped"] > 100, "idle skip was not reported")
    require(after.economics.points < before_points, "capped active days did not charge treasury")
    require(after.org.digital_worker_count == before_workers, "idle catch-up triggered a surprise contraction")

    print("OK: system gap smoke passed")
    print(f"  run_id: {analyze_run_id}")
    print(f"  idle skipped: {tick['idle_days_skipped']} in-game days")
    print(f"  route room: {room['effects_applied'].get('kind')} / {room['stage_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())