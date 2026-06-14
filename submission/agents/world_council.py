"""Game Master Council: the world-engine agents deliberate on each move.

The repo already has two multi-agent surfaces:

  * The worker standup (`/api/world/standup`) - the *party* (Strategist,
    Designer, Marketer, Ops) reacting to a CEO decision. These agents play the
    game *with* the player.
  * The Game Masters - World Designer, Org Designer, Antagonist Director - which
    already mutate the world on every move (`adapt_remaining_stages`,
    `record_choice_game_state`). But they did so *separately and invisibly*:
    nobody saw them collaborate, and the collaboration was not persisted.

This module is the missing seam the user asked for: the Game Masters sit in
their own group chat and *ratify the forward motion* of the run. It does NOT
re-mutate the world - it narrates and persists the moves the GMs already made
(the antagonist move and the stage adaptation are computed once by the server
and passed in), turning "the world changed" into a visible, durable, multi-agent
deliberation.

Degradation law (same as every subsystem here):
    live + MAF importable -> the GM turns are upgraded through
                             `run_maf_group_chat` (real Microsoft Agent
                             Framework Agent loop on our Foundry deployments)
    otherwise             -> the deterministic, fully-grounded turns stand
A fresh `git clone` with no credentials still produces a real council.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from state.schema import (
    AntagonistMove,
    CompanyState,
    Stage,
    WorldCouncilDeliberation,
    WorldCouncilTurn,
)

# Diegetic tool each Game Master "draws" for its council turn - shown in the UI
# the same way worker tool draws are, so the engine tier reads as agents acting.
_GM_TOOL = {
    "narrator_open": "read_world_state",
    "antagonist": "press_advantage",
    "orgdesigner": "render_org_graph",
    "narrator_close": "adapt_remaining_stages",
}
_GM_LABEL = {"narrator": "World Designer", "orgdesigner": "Org Designer"}


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "\u2026"


def _next_stage(world: Any, stage: Stage) -> Optional[Stage]:
    stages = list(getattr(world, "stages", []) or [])
    if stage in stages:
        i = stages.index(stage)
        if i + 1 < len(stages):
            return stages[i + 1]
    return None


def _worker_title(stage: Optional[Stage]) -> str:
    if not stage:
        return "the next worker"
    return stage.assigned_worker_title or (stage.owner_role or "worker").title()


def _finding_clause(worker_report: Optional[Dict[str, Any]]) -> str:
    """One grounded phrase for what the workforce actually brought back."""
    wr = worker_report or {}
    if wr.get("signal"):
        return f"the workforce surfaced a live signal - {_clip(wr['signal'], 80)}"
    if wr.get("source"):
        return f"the workforce grounded the run in {_clip(wr['source'], 60)}"
    return ""


def _build_participants(
    state: CompanyState,
    stage: Stage,
    decision: Dict[str, Any],
    antagonist_move: Optional[AntagonistMove],
    adapted_stage_ids: List[str],
    worker_report: Optional[Dict[str, Any]],
    threat_before: int,
    threat_after: int,
    rival_name: str,
    forward_motion: str,
) -> List[Dict[str, Any]]:
    """Deterministic GM turns, fully grounded in the move that just happened.

    Single source for both the persisted deliberation and the live upgrade -
    the live path rephrases these exact turns, never invents new structure.
    """
    world = getattr(state, "world", None)
    next_stage = _next_stage(world, stage)
    next_title = _worker_title(next_stage)
    option = _clip(decision.get("option") or "the chosen line", 70)
    finding = _finding_clause(worker_report)

    # 1) World Designer opens: read the player's move + the workforce finding,
    #    declare how many pending beats it bent.
    if adapted_stage_ids:
        bent = (f"I bent {len(adapted_stage_ids)} pending beat(s) so the world "
                f"tracks that pivot")
    else:
        bent = "the pending beats already hold against that pivot"
    open_msg = (
        f"Council in session. The CEO chose '{option}'"
        + (f", and {finding}" if finding else "")
        + f". {bent}. Rival, what is your counter?"
    )

    # 2) Antagonist Director: the Rival Move phase - its own move, threat delta,
    #    and the counterplay it dares the founder to use.
    if antagonist_move is not None:
        lane = ""
        if antagonist_move.rival_role_title and antagonist_move.rival_pressure_lane:
            lane = f"{antagonist_move.rival_role_title} on {antagonist_move.rival_pressure_lane} - "
        rival_msg = (
            f"{lane}Rival move: {_clip(antagonist_move.title, 60)}. "
            f"{_clip(antagonist_move.counterplay or 'Answer me before your next gate.', 90)} "
            f"Threat {threat_before} -> {threat_after}/100."
        )
    else:
        rival_msg = (
            f"I hold at {threat_after}/100 for now - but I am contesting "
            f"{next_title}'s lane. Counter me or cede it."
        )

    # 3) Org Designer: bind the next beat to a capability, not another copy.
    org_msg = (
        f"Then {next_title} owns the next beat. I am holding capacity there "
        f"and will name a new role only if this move opened a gap we cannot "
        f"cover with the team we have."
    )

    # 4) World Designer closes: the binding forward motion (guarantees the run
    #    advances - the whole point of convening the council).
    close_msg = f"Ratified. {forward_motion} We move forward."

    return [
        {"speaker": _GM_LABEL["narrator"], "role": "narrator", "worker_id": "world_designer",
         "tool": _GM_TOOL["narrator_open"], "message": open_msg, "handoff_to": rival_name},
        {"speaker": rival_name, "role": "antagonist", "worker_id": "antagonist",
         "tool": _GM_TOOL["antagonist"], "message": rival_msg, "handoff_to": _GM_LABEL["orgdesigner"]},
        {"speaker": _GM_LABEL["orgdesigner"], "role": "orgdesigner", "worker_id": "org_designer",
         "tool": _GM_TOOL["orgdesigner"], "message": org_msg, "handoff_to": _GM_LABEL["narrator"]},
        {"speaker": _GM_LABEL["narrator"], "role": "narrator", "worker_id": "world_designer",
         "tool": _GM_TOOL["narrator_close"], "message": close_msg, "handoff_to": "founder"},
    ]


def _compute_forward_motion(state: CompanyState, stage: Stage) -> str:
    """The single binding next step the council commits the world to."""
    world = getattr(state, "world", None)
    next_stage = _next_stage(world, stage)
    if not next_stage:
        return ("This is the CHANGE beat - the council closes the loop toward "
                "cooperative equilibrium instead of opening a new front.")
    goal = _clip(next_stage.goal or "the next objective", 120)
    metric = _clip(next_stage.success_metric or "its success metric", 110)
    return (f"{_worker_title(next_stage)} opens '{_clip(next_stage.title, 50)}' "
            f"from: {goal} It ships when: {metric}")


def _maybe_upgrade_live(
    state: CompanyState,
    stage: Stage,
    decision: Dict[str, Any],
    participants: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], str]:
    """Upgrade the GM turns through the Microsoft Agent Framework group chat.

    Returns (turns, source). On any failure the deterministic participants are
    returned unchanged with source 'simulation' - the council never breaks.
    """
    try:
        from agents.maf_runtime import maf_available, run_maf_group_chat
        from agents.model_config import FOUNDRY_API_KEY, FOUNDRY_BASE_URL
    except Exception:
        return participants, "simulation"
    if not maf_available():
        return participants, "simulation"
    consequence = (decision.get("consequence") or {})
    summary = consequence.get("summary") or decision.get("consequence_summary") or ""
    try:
        turns = run_maf_group_chat(
            api_key=FOUNDRY_API_KEY,
            base_url=FOUNDRY_BASE_URL,
            company_name=state.name or "the venture",
            pitch=state.pitch or "",
            stage_title=stage.title,
            option=decision.get("option", ""),
            consequence_summary=summary,
            participants=participants,
        )
        source = "foundry" if any(t.get("source") == "maf" for t in turns) else "simulation"
        return turns, source
    except Exception:
        return participants, "simulation"


def convene_world_council(
    state: CompanyState,
    *,
    stage: Stage,
    decision: Dict[str, Any],
    antagonist_move: Optional[AntagonistMove] = None,
    adapted_stage_ids: Optional[List[str]] = None,
    worker_report: Optional[Dict[str, Any]] = None,
    threat_before: Optional[int] = None,
    live: bool = False,
) -> WorldCouncilDeliberation:
    """Convene the Game Masters to ratify the forward motion of one move.

    `antagonist_move` and `adapted_stage_ids` are the moves the server already
    made this turn - the council narrates and persists them, it does not
    re-mutate the world. Returns a typed deliberation the caller persists to
    `state.game.council_log`.
    """
    adapted_stage_ids = list(adapted_stage_ids or [])
    arc = getattr(getattr(state, "game", None), "antagonist_arc", None)
    threat_after = int(getattr(arc, "threat_level", 0) or 0)
    rival_name = (
        (getattr(arc, "antagonist_name", "") or "")
        or (getattr(state.antagonist, "name", "") if getattr(state, "antagonist", None) else "")
        or "The Rival"
    )
    if threat_before is None:
        delta = int(getattr(antagonist_move, "pressure_delta", 0) or 0) if antagonist_move else 0
        threat_before = max(0, threat_after - delta)

    forward_motion = _compute_forward_motion(state, stage)
    participants = _build_participants(
        state, stage, decision, antagonist_move, adapted_stage_ids, worker_report,
        threat_before, threat_after, rival_name, forward_motion,
    )

    source = "simulation"
    if live:
        participants, source = _maybe_upgrade_live(state, stage, decision, participants)

    # Map (possibly upgraded) turn dicts onto the typed, persisted contract.
    label_for = {"narrator": "World Designer", "orgdesigner": "Org Designer", "antagonist": rival_name}
    typed: List[WorldCouncilTurn] = []
    for p in participants:
        role = p.get("role") or "narrator"
        tool = (p.get("tool_call") or {}).get("tool") or p.get("tool") or ""
        typed.append(WorldCouncilTurn(
            speaker=p.get("speaker") or p.get("display_name") or label_for.get(role, role.title()),
            role=role,
            role_label=label_for.get(role, role.title()),
            worker_id=p.get("worker_id") or role,
            tool=tool,
            message=_clip(p.get("message") or "", 420),
            handoff_to=p.get("handoff_to") or "",
            source=p.get("source") or source,
            framework=p.get("framework") or ("microsoft-agent-framework" if source == "foundry" else "simulation"),
        ))

    option = _clip(decision.get("option") or "", 40)
    escalation = str(getattr(arc, "escalation_stage", "") or "watching")
    summary = (
        f"Council bent {len(adapted_stage_ids)} beat(s); rival at "
        f"{threat_after}/100 ({escalation}); forward motion locked."
    )
    day_index = int(getattr(getattr(state, "game", None), "day_index", 0) or 0)
    return WorldCouncilDeliberation(
        id=f"council_{stage.id}",
        day_index=day_index,
        stage_id=stage.id,
        trigger=(f"CEO decision: {option}" if option else "Move ratification"),
        summary=summary,
        turns=typed,
        adapted_stage_ids=adapted_stage_ids,
        antagonist_move_id=(antagonist_move.id if antagonist_move else ""),
        threat_before=int(threat_before),
        threat_after=threat_after,
        forward_motion=forward_motion,
        source=source,
    )
