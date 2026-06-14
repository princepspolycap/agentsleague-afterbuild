"""Smoke test for the Game Master Council (`agents/world_council.py`).

The council is the engine-tier group chat: the World Designer, Antagonist
Director, and Org Designer deliberate after a move and lock the run's forward
motion. This test proves, with no Azure credentials or MAF installed:

  1. The deliberation contract `/api/decision` and `/api/world/council` return -
     four grounded GM turns, the rival's move, and a non-empty forward motion.
  2. Roguelike persistence - the deliberation survives a StateStore save/load
     round-trip, so the evolving world is durable across reloads.

Use `--live` from a configured `DEMO_MODE=live` environment to require that at
least one GM turn was upgraded through the Microsoft Agent Framework group chat.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

SUBMISSION_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SUBMISSION_DIR))

from agents.world_council import convene_world_council  # noqa: E402
from state.schema import (  # noqa: E402
    AntagonistArc,
    AntagonistMove,
    AntagonistState,
    CompanyState,
    GameRunState,
    Stage,
    StateStore,
    WorldGraph,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_state() -> tuple[CompanyState, Stage, dict, AntagonistMove]:
    stage1 = Stage(
        id="stage_4_search",
        title="SEARCH: Forging the Automata Workforce",
        goal="Design a low-overhead MVP loop with the first digital workers.",
        owner_role="designer",
        success_metric="Ship a prototype loop with first passive-income signals.",
        status="completed",
        assigned_worker_title="Atlas the Builder",
        assigned_worker_id="worker_designer_1",
    )
    stage2 = Stage(
        id="stage_5_find",
        title="FIND: The Traction Signal",
        goal="Find the adoption channel the rival cannot fake.",
        owner_role="marketer",
        success_metric="Identify 3 reachable channels and one proof-backed launch.",
        status="not-started",
        assigned_worker_title="Vega the Marketer",
        assigned_worker_id="worker_marketer_1",
    )
    move = AntagonistMove(
        id="amove_stage_4_search_1",
        stage_id="stage_4_search",
        title="Bundle dumping on the clinic channel",
        tactic="undercut",
        pressure_type="market",
        target_metric="market_share",
        rival_role_title="Channel Enforcer",
        rival_pressure_lane="distribution",
        pressure_delta=8,
        counterplay="Lock an exclusive clinic partner before they do.",
    )
    arc = AntagonistArc(
        antagonist_name="The Infinite Trust",
        threat_level=42,
        escalation_stage="contesting",
        current_pressure="Bundling to choke your distribution.",
        moves=[move],
        open_counterplays=["Lock an exclusive clinic partner before they do."],
    )
    state = CompanyState(
        name="Solar Microgrids",
        description="Solar microgrids for rural clinics.",
        pitch="Solar microgrids that automate power for rural clinics.",
        antagonist=AntagonistState(name="The Infinite Trust"),
        world=WorldGraph(brief="Solar microgrids for rural clinics", stages=[stage1, stage2]),
        game=GameRunState(day_index=4, antagonist_arc=arc),
    )
    decision = {
        "stage_id": "stage_4_search",
        "stage_title": stage1.title,
        "option": "Ship the prototype now and defend the clinic channel",
        "tradeoff": "Accept more burn for speed",
        "consequence_summary": "Velocity rises but burn pressure climbs.",
        "consequence": {"summary": "Velocity rises but burn pressure climbs.", "rule_id": "decision.speed"},
    }
    state.world.decisions.append(decision)
    worker_report = {
        "signal": "Rural clinic solar demand surged 30% this quarter",
        "source": "World Generation Playbook",
        "tool": "web_search",
        "tools_called": ["web_search", "recall"],
    }
    return state, stage1, decision, move, worker_report


def check_contract(deliberation, move) -> None:
    roles = [t.role for t in deliberation.turns]
    require(len(deliberation.turns) == 4, f"expected 4 GM turns, got {len(deliberation.turns)}: {roles}")
    require(roles == ["narrator", "antagonist", "orgdesigner", "narrator"],
            f"unexpected GM turn order: {roles}")
    require(all(t.message.strip() for t in deliberation.turns), "a GM turn had an empty message")
    require(bool(deliberation.forward_motion.strip()), "forward_motion was empty")
    require(deliberation.antagonist_move_id == move.id,
            f"antagonist_move_id not wired: {deliberation.antagonist_move_id!r} != {move.id!r}")
    require(deliberation.threat_after == 42, f"threat_after wrong: {deliberation.threat_after}")
    require(deliberation.threat_before == 34,
            f"threat_before should be after-minus-delta (42-8=34), got {deliberation.threat_before}")
    require(deliberation.adapted_stage_ids == ["stage_5_find"],
            f"adapted_stage_ids not preserved: {deliberation.adapted_stage_ids}")
    rival_turn = deliberation.turns[1]
    require(move.title[:12].lower() in rival_turn.message.lower(),
            f"rival turn did not cite its move: {rival_turn.message!r}")
    # The forward motion must name the next beat so the run visibly advances.
    require("FIND" in deliberation.forward_motion or "Traction" in deliberation.forward_motion
            or "channel" in deliberation.forward_motion.lower(),
            f"forward_motion did not name the next beat: {deliberation.forward_motion!r}")


def check_persistence(state, deliberation) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        store = StateStore(filepath=path)
        state.game.council_log = [deliberation]
        store.state = state
        store.save()

        reloaded = StateStore(filepath=path).load()
        require(reloaded is not None, "state failed to reload")
        log = reloaded.game.council_log
        require(len(log) == 1, f"council_log did not persist (len={len(log)})")
        require(log[0].forward_motion == deliberation.forward_motion,
                "forward_motion changed across reload")
        require(len(log[0].turns) == len(deliberation.turns),
                "council turns lost across reload")
        require(log[0].turns[1].role == "antagonist",
                "rival turn lost its role across reload")


def main() -> int:
    parser = argparse.ArgumentParser(description="Game Master Council smoke test.")
    parser.add_argument("--live", action="store_true",
                        help="Require at least one GM turn upgraded through MAF.")
    args = parser.parse_args()

    state, stage, decision, move, worker_report = build_state()

    deliberation = convene_world_council(
        state, stage=stage, decision=decision, antagonist_move=move,
        adapted_stage_ids=["stage_5_find"], worker_report=worker_report, live=args.live)

    check_contract(deliberation, move)
    check_persistence(state, deliberation)

    if args.live:
        upgraded = [t for t in deliberation.turns if t.source in {"maf", "foundry"}]
        require(deliberation.source == "foundry" and upgraded,
                "live run requested but no GM turn was upgraded through the MAF group chat")
        print(f"OK (live): {len(upgraded)}/{len(deliberation.turns)} GM turns upgraded through MAF.")
    else:
        print("OK (offline): GM council contract + roguelike persistence verified.")
        print(f"  trigger:        {deliberation.trigger}")
        print(f"  rival move:     {deliberation.turns[1].message[:90]}")
        print(f"  forward motion: {deliberation.forward_motion[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
