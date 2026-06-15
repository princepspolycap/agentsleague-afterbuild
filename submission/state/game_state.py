"""Roguelike state mechanics layered on top of the business sim.

The business layer answers "what changed in the company?" This module answers
"what changed in the game?" - party state, inventory, encounters, and the
antagonist pressure track.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from state.schema import (
    AntagonistArc,
    AntagonistMove,
    ChoiceRecord,
    CompanyState,
    EncounterState,
    GameRunState,
    GameCard,
    InventoryItem,
    PlayerMove,
    Stage,
    WorkerInvocation,
    WorkerPartyMember,
)


_PRESSURE_BY_RULE = {
    "strategist.depth": ("market", "velocity", 4, "The antagonist widens the market while you go deep."),
    "strategist.breadth": ("trust", "trust", 7, "The antagonist exploits shallow proof across the wider front."),
    "designer.ship": ("technical", "trust", 8, "The antagonist clones the rough edge and amplifies user doubt."),
    "designer.polish": ("market", "velocity", 5, "The antagonist ships faster while you reinforce quality."),
    "marketer.adoption": ("financial", "burn_pressure", 8, "The antagonist starts a pricing war against grassroots access."),
    "marketer.runway": ("cultural", "autonomy", 5, "The antagonist frames enterprise focus as mission drift."),
    "ops.automate": ("operational", "trust", 9, "The antagonist points at every automated support failure."),
    "ops.human_loop": ("financial", "burn_pressure", 7, "The antagonist attacks the cost of human review."),
    "ops.shareholder": ("cultural", "autonomy", 12, "The antagonist offers speed in exchange for control."),
    "ops.cooperative": ("market", "velocity", 6, "The antagonist tries to outpace democratic governance."),
    "custom.default": ("market", "proof", 4, "The antagonist tests the custom constraint for weak spots."),
}


def initialize_game_run(state: CompanyState, *, mode: str = "simulation") -> None:
    """Refresh game-facing party and antagonist state from company state."""
    state.game.mode = mode
    sync_party_from_org(state)
    if state.run_id and state.game.run_id != state.run_id:
        state.game.run_id = state.run_id
    if not state.game.run_id or state.game.run_id == "run_default":
        if state.run_id:
            state.game.run_id = state.run_id
        else:
            slug_source = state.name or state.pitch
            seed_slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-")[:48] or "run"
            state.game.run_id = f"run_{seed_slug}"
    if not state.game.rng_seed:
        state.game.rng_seed = _seed_from_run_id(state.game.run_id)
    if not state.game.rng_state:
        state.game.rng_state = state.game.rng_seed
    if not _all_cards(state.game):
        deck = _starter_deck(state)
        _shuffle_cards(deck, state.game)
        state.game.deck = deck
        state.game.hand = []
        state.game.discard = []
        state.game.exhaust = []
        start_player_turn(state, stage_id="")
    if state.antagonist:
        state.game.antagonist_arc.antagonist_name = state.antagonist.name
        if not state.game.antagonist_arc.current_pressure:
            state.game.antagonist_arc.current_pressure = state.antagonist.signature_tactic
    # Anchor the real-time payroll clock at run start so the slot picker can sort
    # by recency immediately (its updated_epoch reads last_tick_epoch), and the
    # first /api/state tick charges from "now" instead of a zero epoch.
    if state.economics is not None and not state.economics.last_tick_epoch:
        now = time.time()
        state.economics.last_tick_epoch = now
        if not state.economics.started_at_epoch:
            state.economics.started_at_epoch = now
    _refresh_run_status(state)


def sync_party_from_org(state: CompanyState) -> List[WorkerPartyMember]:
    """Rebuild the game party from the live org, preserving existing member state."""
    state.game.party = _party_from_org(state)
    return state.game.party


def ensure_active_run(state: CompanyState) -> None:
    """Reject player actions once the run has resolved."""
    status = getattr(getattr(state, "game", None), "run_status", "active")
    if status != "active":
        reason = state.game.defeat_reason if status == "defeat" else state.game.victory_reason
        detail = f"Run is already {status}."
        if reason:
            detail = f"{detail} {reason}"
        raise ValueError(detail)


def record_stage_encounter(state: CompanyState, stage: Stage) -> List[Dict[str, Any]]:
    """Upsert the stage execution encounter after a worker produces an artifact.

    Returns any worker level-up events from shipping this stage so the caller can
    log them (WORKER_LEVEL_UP) - empty when no worker leveled up this stage.
    """
    day_index = _day_index_for_stage(state, stage)
    worker_ids = [stage.assigned_worker_id or stage.owner_role]
    encounter = EncounterState(
        id=f"encounter_{stage.id}_stage",
        day_index=day_index,
        stage_id=stage.id,
        kind="stage",
        title=stage.title,
        status="resolved" if stage.status == "completed" else "open",
        worker_ids=[w for w in worker_ids if w],
        artifact_keys=list((stage.artifact or {}).keys())[:12],
    )
    _upsert_encounter(state, encounter)
    _upsert_inventory_from_stage(state, stage)
    _add_reward_card_from_stage(state, stage)
    levelups = _assign_party_to_stage(state, stage)
    _refresh_run_status(state)
    return levelups


def record_choice_game_state(state: CompanyState, stage: Stage, choice: ChoiceRecord,
                             worker_report: Optional[Dict[str, Any]] = None) -> Optional[AntagonistMove]:
    """Record the dilemma encounter and antagonist response for a CEO choice.

    The antagonist reacts to BOTH the CEO choice and what the workforce just
    brought back (`worker_report`): the rival contests the specific wedge the
    digital workers discovered, not only the player's decision.
    """
    state.game.day_index = max(state.game.day_index, choice.day_index)
    state.game.loop_phase = "aftermath"
    move = _build_antagonist_move(state, stage, choice, worker_report)
    if move:
        _upsert_antagonist_move(state, move)
    encounter = EncounterState(
        id=f"encounter_{stage.id}_dilemma",
        day_index=choice.day_index,
        stage_id=stage.id,
        kind="dilemma",
        title=choice.prompt or stage.title,
        status="resolved",
        worker_ids=[stage.assigned_worker_id or stage.owner_role],
        choice_ids=[choice.id],
        antagonist_move_id=move.id if move else "",
    )
    _upsert_encounter(state, encounter)
    _apply_party_choice_cost(state, stage, choice)
    record_decision_move(state, stage, choice)
    _refresh_run_status(state)
    return move


def start_player_turn(state: CompanyState, stage_id: str = "") -> PlayerMove:
    """Start a new card turn and draw up to draw_per_turn cards."""
    ensure_active_run(state)
    game = state.game
    game.turn_index += 1
    game.energy = game.max_energy
    game.loop_phase = "explore"
    drawn: List[str] = []
    while len(game.hand) < game.draw_per_turn:
        if not game.deck and game.discard:
            game.deck = list(game.discard)
            game.discard = []
            _shuffle_cards(game.deck, game)
        if not game.deck:
            break
        card = game.deck.pop(0)
        game.hand.append(card)
        drawn.append(card.id)
    move = PlayerMove(
        id=f"move_{game.turn_index}_draw",
        turn_index=game.turn_index,
        day_index=game.day_index,
        stage_id=stage_id,
        move_type="draw",
        summary=f"Drew {len(drawn)} card(s).",
        effects_applied={"drawn": drawn, "energy": game.energy},
    )
    game.move_log.append(move)
    _refresh_run_status(state)
    return move


def end_player_turn(state: CompanyState, stage_id: str = "") -> PlayerMove:
    """End the current turn, discard hand, then draw a fresh hand.

    Refreshing the hand refills energy, so it is not free: the rival presses
    while you regroup (a small, capped threat bump). That keeps energy a real
    budget instead of an unlimited resource you can refill at will.
    """
    ensure_active_run(state)
    game = state.game
    ended = [c.id for c in game.hand]
    if game.hand:
        game.discard.extend(game.hand)
        game.hand = []
    arc = game.antagonist_arc
    threat_before = arc.threat_level
    if END_TURN_THREAT_PRESS:
        arc.threat_level = max(0, min(100, arc.threat_level + END_TURN_THREAT_PRESS))
        arc.escalation_stage = _escalation_stage(arc.threat_level)
    end_move = PlayerMove(
        id=f"move_{game.turn_index}_end",
        turn_index=game.turn_index,
        day_index=game.day_index,
        stage_id=stage_id,
        move_type="end_turn",
        summary=f"Ended turn {game.turn_index}.",
        effects_applied={
            "discarded": ended,
            "energy": game.energy,
            "antagonist_threat": {"before": threat_before, "after": arc.threat_level},
        },
    )
    game.move_log.append(end_move)
    _refresh_run_status(state)
    if game.run_status != "active":
        return end_move
    draw_move = start_player_turn(state, stage_id=stage_id)
    end_move.effects_applied["next_drawn"] = (draw_move.effects_applied or {}).get("drawn", [])
    return end_move


def play_card(state: CompanyState, card_id: str, *, target_id: str = "", stage_id: str = "") -> PlayerMove:
    """Play a card from hand and apply its deterministic effects."""
    ensure_active_run(state)
    game = state.game
    card = next((c for c in game.hand if c.id == card_id), None)
    if not card:
        raise ValueError(f"Card is not in hand: {card_id}")
    if game.energy < card.cost:
        raise ValueError(f"Not enough energy for {card.name}: need {card.cost}, have {game.energy}")
    if float(card.effects.get("market_share_delta") or 0.0) and _completed_stage_count(state) <= 0:
        raise ValueError("Ship one stage before converting customers - no product or service exists to sell yet.")

    game.energy -= card.cost
    game.hand = [c for c in game.hand if c.id != card_id]
    applied = _apply_card_effects(state, card, target_id=target_id)
    if card.exhausts:
        game.exhaust.append(card)
    else:
        game.discard.append(card)
    move = PlayerMove(
        id=f"move_{game.turn_index}_{len(game.move_log) + 1}_{card.id}",
        turn_index=game.turn_index,
        day_index=game.day_index,
        stage_id=stage_id,
        move_type="play_card",
        card_id=card.id,
        target_id=target_id,
        energy_spent=card.cost,
        summary=f"Played {card.name}.",
        effects_applied=applied,
    )
    game.move_log.append(move)
    return move


def claim_reward_card(state: CompanyState, card_id: str) -> PlayerMove:
    """Choose one pending reward card and add it to the run deck.

    Idempotent for true duplicate clicks: claiming the same card after it was
    already drafted returns a benign no-op, while unknown card ids still fail.
    """
    ensure_active_run(state)
    game = state.game
    card = next((c for c in game.pending_rewards if c.id == card_id), None)
    if not card:
        if not any(m.move_type == "reward_card" and m.card_id == card_id for m in game.move_log):
            raise ValueError(f"Reward card is not pending: {card_id}")
        return PlayerMove(
            id=f"move_reward_noop_{card_id}",
            turn_index=game.turn_index,
            day_index=game.day_index,
            move_type="reward_card",
            card_id=card_id,
            summary="Reward already drafted.",
            effects_applied={"noop": True, "pending": len(game.pending_rewards)},
        )

    stage_tag = next((tag for tag in card.tags if tag.startswith("stage_")), "")
    if stage_tag:
        game.pending_rewards = [c for c in game.pending_rewards if stage_tag not in c.tags]
    else:
        game.pending_rewards = [c for c in game.pending_rewards if c.id != card_id]
    game.discard.append(card)
    move = PlayerMove(
        id=f"move_reward_{card.id}",
        turn_index=game.turn_index,
        day_index=game.day_index,
        stage_id=stage_tag,
        move_type="reward_card",
        card_id=card.id,
        summary=f"Drafted {card.name} into discard.",
        effects_applied={"card": card.model_dump(), "destination": "discard"},
    )
    game.move_log.append(move)
    return move


def record_decision_move(state: CompanyState, stage: Stage, choice: ChoiceRecord) -> PlayerMove:
    """Log a CEO dilemma pick as a player move in the card layer."""
    move = PlayerMove(
        id=f"move_choice_{stage.id}",
        turn_index=state.game.turn_index,
        day_index=choice.day_index,
        stage_id=stage.id,
        move_type="choose_option",
        target_id=choice.option_id,
        summary=f"Chose {choice.option}",
        effects_applied={
            "rule_id": choice.rule_id,
            "tradeoff": choice.tradeoff,
            "consequence_summary": choice.consequence_summary,
        },
    )
    state.game.move_log = [m for m in state.game.move_log if m.id != move.id]
    state.game.move_log.append(move)
    return move


def _party_from_org(state: CompanyState) -> List[WorkerPartyMember]:
    current = {p.worker_id: p for p in state.game.party}
    party: List[WorkerPartyMember] = []
    for role in (state.org.roles if state.org else []):
        if role.kind == "human":
            continue
        existing = current.get(role.id)
        party.append(WorkerPartyMember(
            worker_id=role.id,
            title=role.title,
            role=role.deployment_hint or role.lifecycle_stage,
            lifecycle_stage=role.lifecycle_stage,
            status=existing.status if existing else "ready",
            morale=existing.morale if existing else 70,
            fatigue=existing.fatigue if existing else 0,
            trust=existing.trust if existing else 60,
            # Progression persists with the worker: prefer the live party member's
            # earned xp/level, falling back to whatever was propagated to the
            # OrgRole, so a rebuild from the org never resets a leveled worker.
            xp=existing.xp if existing else int(getattr(role, "xp", 0) or 0),
            level=existing.level if existing else max(1, int(getattr(role, "level", 1) or 1)),
            current_stage_id=existing.current_stage_id if existing else "",
            tools=list(role.tools),
            traits=[role.kind, role.seniority, role.lifecycle_stage],
        ))
    return party


# The founder's signature starter card, derived from their analyzed archetype so
# the opening hand reads as THIS founder's deck - the character (founder profile)
# showing up in the dynamics (the deck). One card, one archetype -> one strength.
_FOUNDER_SIGNATURE = {
    "Builder":  {"name": "Builder's Sprint",  "kind": "tactic",
                 "description": "Your engineering reflex: ship the next system fast.",
                 "effects": {"economics_delta": {"velocity": 4, "autonomy": 2}, "party": {"fatigue": 2}}},
    "Seller":   {"name": "Founder's Pitch",   "kind": "proof",
                 "description": "Your selling instinct: turn a conversation into a customer.",
                 "effects": {"economics_delta": {"proof": 2}, "market_share_delta": 1.0}},
    "Designer": {"name": "Founder's Polish",  "kind": "tactic",
                 "description": "Your craft: raise the bar so the work earns trust.",
                 "effects": {"economics_delta": {"trust": 4, "proof": 1}, "party": {"fatigue": 1}}},
    "Operator": {"name": "Founder's Leverage", "kind": "worker",
                 "description": "Your operating discipline: do more with less burn.",
                 "effects": {"economics_delta": {"autonomy": 4, "burn_pressure": -3}}},
}


def _founder_signature_card(archetype: str) -> GameCard:
    sig = _FOUNDER_SIGNATURE.get(archetype) or _FOUNDER_SIGNATURE["Builder"]
    return GameCard(
        id="card_founder_signature",
        name=sig["name"],
        kind=sig["kind"],
        cost=1,
        description=sig["description"],
        source="founder",
        effects=sig["effects"],
        tags=["founder", "signature", archetype.lower()],
    )


def _starter_deck(state: CompanyState) -> List[GameCard]:
    archetype = ""
    if state.founder_profile:
        archetype = state.founder_profile.founder_archetype
    elif state.founder:
        archetype = state.founder.archetype
    archetype = (archetype or "Builder").split(",")[0].strip().title()
    if archetype not in _FOUNDER_SIGNATURE:
        archetype = "Builder"
    deck = [
        _founder_signature_card(archetype),
        GameCard(
            id="card_customer_signal",
            name="Customer Signal",
            kind="proof",
            cost=1,
            description="Convert one real beneficiary signal into a paying customer.",
            effects={"economics_delta": {"proof": 3}, "market_share_delta": 1.2, "draw": 1},
            tags=["proof", "discovery", "customer"],
        ),
        GameCard(
            id="card_trust_seal",
            name="Trust Seal",
            kind="counterplay",
            cost=1,
            description="Add a human verification seal before pressure spreads.",
            effects={"economics_delta": {"trust": 4}, "antagonist_threat_delta": -3},
            tags=["trust", "counterplay"],
        ),
        GameCard(
            id="card_automate_loop",
            name="Automate Loop",
            kind="worker",
            cost=2,
            description="Let the digital workforce remove repeat labor.",
            effects={"economics_delta": {"autonomy": 6, "burn_pressure": -2}, "party": {"fatigue": 5}},
            tags=["autonomy", "worker"],
        ),
        GameCard(
            id="card_counter_position",
            name="Counter-Position",
            kind="counterplay",
            cost=1,
            description="Answer the antagonist with a sharper wedge.",
            effects={"economics_delta": {"proof": 2, "trust": 2}, "antagonist_threat_delta": -4},
            tags=["antagonist", "positioning"],
        ),
    ]
    if "starter_plus_draw" in state.game.unlocks:
        deck.append(
            GameCard(
                id="card_mentor_ping",
                name="Mentor Ping",
                kind="resource",
                cost=0,
                description="A veteran advisor unlocks one extra option this turn.",
                effects={"draw": 1, "economics_delta": {"trust": 1}},
                tags=["resource", "mentor", "unlock"],
                exhausts=True,
            )
        )
    return deck


def _add_reward_card_from_stage(state: CompanyState, stage: Stage) -> None:
    if not stage.artifact or (stage.validation_score or 0) < 80:
        return
    if any(stage.id in c.tags for c in _all_cards(state.game) + state.game.pending_rewards):
        return
    state.game.pending_rewards = [
        c for c in state.game.pending_rewards if stage.id not in c.tags
    ] + _reward_cards_from_stage(state, stage)


def _invocation_for_stage(state: CompanyState, stage: Stage) -> Optional[WorkerInvocation]:
    """The worker's real run record for this stage - the receipts a reward card
    is minted from. Latest matching invocation wins."""
    if not state.world:
        return None
    matches = [iv for iv in state.world.invocations if iv.stage_id == stage.id]
    return matches[-1] if matches else None


def _card_label(value: str, fallback: str = "") -> str:
    """Turn a raw tool/source id (snake_case, file path, extension) into a
    card-ready label, so cards can name the real thing the worker used."""
    text = re.sub(r"\.[a-z0-9]+$", "", str(value or "").strip())   # drop extension
    text = re.sub(r"[\\/]+", " ", text)                             # path -> words
    text = re.sub(r"[_\-]+", " ", text).strip()
    return text[:22].title() if text else fallback


def _trace_leverage(inv: Optional[WorkerInvocation]) -> Dict[str, str]:
    """The single most card-worthy tool/call the worker actually made this stage.

    Reads the real `tool_trace` ledger ({tool, source, args, result, ms}) and
    prefers the specific ACTION - the query the worker ran - over the bare tool
    name, so a leverage card cites what the tool did ("Rural Clinic Solar")
    rather than just naming it ("Web Search"). Returns {tool, action, source};
    all empty when there is no usable receipt.
    """
    trace = (inv.tool_trace or []) if inv else []
    if not trace:
        return {"tool": "", "action": "", "source": ""}
    # Prefer a substantive research call (one that carried a real query) over a
    # generic validator/finalize receipt; fall back to the first call.
    queried = [t for t in trace if str((t.get("args") or {}).get("query", "")).strip()]
    entry = queried[0] if queried else trace[0]
    tool = _card_label(entry.get("tool", ""))
    query = str((entry.get("args") or {}).get("query", "")).strip()
    # Trim a long query to its first whole words so a card NAME never cuts a
    # word mid-syllable ("Rural Clinic Solar Demand Surge" -> "Rural Clinic Solar").
    action = ""
    if query:
        words = re.sub(r"[_\-]+", " ", query).split()
        phrase, acc = [], 0
        for w in words:
            if acc + len(w) > 22 and phrase:
                break
            phrase.append(w)
            acc += len(w) + 1
        # Drop dangling stop-words so a card name never trails on "for"/"the".
        _stop = {"for", "the", "a", "an", "of", "and", "to", "in", "on", "with"}
        while phrase and phrase[-1].lower() in _stop:
            phrase.pop()
        while phrase and phrase[0].lower() in _stop:
            phrase.pop(0)
        action = " ".join(phrase).title()
    return {"tool": tool, "action": action, "source": str(entry.get("source", "") or "")}


def _reward_cards_from_stage(state: CompanyState, stage: Stage) -> List[GameCard]:
    """Mint this stage's reward draft from the worker's REAL run receipts.

    The game engine authors each card from what the agent actually did this
    stage - the tools it called, the knowledge it grounded in, its gate score -
    so a reward is a product of the reasoning, not a fixed template. Degrades to
    role/stage flavor when an invocation has no receipts (e.g. an early reload).
    """
    score = stage.validation_score or 0
    upgraded = score >= 95
    owner = (stage.owner_role or "worker").title()
    worker_title = stage.assigned_worker_title or owner
    antagonist = state.antagonist.name if state.antagonist else "the rival"
    proof_delta = 5 if upgraded else 3
    trust_delta = 2 if upgraded else 1
    velocity_delta = 6 if upgraded else 4
    counter_delta = -8 if upgraded else -5

    # Real receipts (populated on every path, simulation included).
    inv = _invocation_for_stage(state, stage)
    tools_used = (inv.maf_tools_called or inv.tools_drawn) if inv else []
    iq_sources = (inv.iq_sources or []) if inv else []
    reasoning = (inv.reasoning_preview or "") if inv else ""
    events = (inv.current_events or []) if inv else []
    signal = str(events[0].get("title", "")).strip() if events else ""

    # 1) PROOF - named for the knowledge the worker actually recalled.
    grounded = _card_label(iq_sources[0]) if iq_sources else ""
    proof_name = f"{grounded} Proof" if grounded else f"{owner} Proof"
    proof_desc = (f"Reusable proof {worker_title} grounded in {grounded}."
                  if grounded else f"Reusable proof earned from {stage.title}.")

    # 2) LEVERAGE - the tool the worker actually used, banked as repeatable
    # speed. Named for the SPECIFIC call when the receipt carries one (the real
    # query it ran), degrading to the bare tool name, then to a worker sprint.
    leverage = _trace_leverage(inv)
    tool_label = leverage["tool"] or (_card_label(tools_used[0]) if tools_used else "")
    action = leverage["action"]
    if action:
        sprint_name = f"{action} Leverage"
        sprint_desc = (f"Re-run {worker_title}'s {tool_label or 'research'} on \"{action}\" "
                       f"to buy speed for fatigue.")
        sprint_effects = {"economics_delta": {"velocity": velocity_delta, "autonomy": 2}, "party": {"fatigue": 6}}
    elif tool_label:
        sprint_name = f"{tool_label} Leverage"
        sprint_desc = f"Re-run the {tool_label} this worker used to buy speed for fatigue."
        sprint_effects = {"economics_delta": {"velocity": velocity_delta, "autonomy": 2}, "party": {"fatigue": 6}}
    else:
        sprint_name = f"{worker_title[:18]} Sprint"
        sprint_desc = "Take a faster worker line now, accepting fatigue as the price."
        sprint_effects = {"economics_delta": {"velocity": velocity_delta}, "party": {"fatigue": 6}}

    # 3) COUNTER - answers the antagonist, flavored by the worker's reasoning.
    counter_desc = (f"Answer {antagonist} with what {worker_title} proved: {reasoning[:60].strip()}"
                    if reasoning.strip()
                    else "Answer the antagonist's pressure with a focused counter-move.")
    # A live market signal the worker actually pulled from the web beats canned
    # flavor: the counter cites a real headline, so current events enter play.
    if signal:
        counter_desc = f"Answer {antagonist} with a live market signal: {signal[:60]}"

    return [
        GameCard(
            id=f"card_reward_{stage.id}_proof",
            name=proof_name,
            kind="proof",
            cost=1,
            description=proof_desc,
            owner_worker_id=stage.assigned_worker_id or "",
            source="stage_reward",
            effects={"economics_delta": {"proof": proof_delta, "trust": trust_delta}, "draw": 1},
            tags=["reward", "proof", stage.owner_role, stage.id],
            upgraded=upgraded,
        ),
        GameCard(
            id=f"card_reward_{stage.id}_sprint",
            name=sprint_name,
            kind="worker",
            cost=0,
            description=sprint_desc,
            owner_worker_id=stage.assigned_worker_id or "",
            source="stage_reward",
            effects=sprint_effects,
            tags=["reward", "worker", "velocity", stage.owner_role, stage.id],
            upgraded=upgraded,
            exhausts=True,
        ),
        GameCard(
            id=f"card_reward_{stage.id}_counter",
            name=f"Counter {antagonist[:16]}",
            kind="counterplay",
            cost=1,
            description=counter_desc,
            owner_worker_id=stage.assigned_worker_id or "",
            source="stage_reward",
            effects={"economics_delta": {"trust": trust_delta}, "antagonist_threat_delta": counter_delta},
            tags=["reward", "counterplay", "antagonist", stage.owner_role, stage.id],
            upgraded=upgraded,
        ),
    ]


def _apply_card_effects(state: CompanyState, card: GameCard, *, target_id: str = "") -> Dict[str, Any]:
    applied: Dict[str, Any] = {}
    econ_delta = card.effects.get("economics_delta") or {}
    if econ_delta:
        applied["economics_delta"] = _apply_economics_delta(state, econ_delta)
    # Customers won by a card route through the same share->revenue->cash math
    # as a shipped stage (consequences.add_market_share), so "Customer Signal"
    # actually books paying customers - profitability is earned, not seeded.
    share_delta = float(card.effects.get("market_share_delta") or 0.0)
    if share_delta:
        from state.consequences import add_market_share
        applied["market"] = add_market_share(state, share_delta, deal_fraction=0.25 if share_delta > 0 else 0.0)
    threat_delta = int(card.effects.get("antagonist_threat_delta") or 0)
    if threat_delta:
        arc = state.game.antagonist_arc
        before = arc.threat_level
        arc.threat_level = max(0, min(100, arc.threat_level + threat_delta))
        arc.escalation_stage = _escalation_stage(arc.threat_level)
        applied["antagonist_threat"] = {"before": before, "after": arc.threat_level}
        if threat_delta < 0:
            _resolve_counterplay(state, target_id)
    party_effect = card.effects.get("party") or {}
    if party_effect:
        applied["party"] = _apply_party_card_effect(state, card, party_effect, target_id)
    draw = int(card.effects.get("draw") or 0)
    if draw:
        drawn: List[str] = []
        for _ in range(draw):
            if not state.game.deck and state.game.discard:
                state.game.deck = list(state.game.discard)
                state.game.discard = []
            if not state.game.deck:
                break
            next_card = state.game.deck.pop(0)
            state.game.hand.append(next_card)
            drawn.append(next_card.id)
        applied["drawn"] = drawn
    synergy = _apply_card_synergy(state, card)
    if synergy:
        applied["synergy"] = synergy
    _refresh_run_status(state)
    return applied


def _completed_stage_count(state: CompanyState) -> int:
    return sum(1 for s in (state.world.stages if state.world else []) if s.status == "completed")


def _apply_card_synergy(state: CompanyState, card: GameCard) -> List[Dict[str, Any]]:
    """Apply lightweight combo rules from tags + party/inventory state."""
    events: List[Dict[str, Any]] = []
    tags = set(card.tags or [])
    proof_items = [i for i in state.game.inventory if "proof" in (i.tags or [])]
    tired_party = any(p.status == "tired" for p in state.game.party)
    if "proof" in tags and len(proof_items) >= 2:
        delta = _apply_economics_delta(state, {"trust": 1})
        events.append({"rule": "proof_chain", "delta": delta})
    if "worker" in tags and tired_party:
        delta = _apply_economics_delta(state, {"autonomy": 1, "burn_pressure": -1})
        events.append({"rule": "worker_relief", "delta": delta})
    if card.kind == "counterplay" and state.game.antagonist_arc.threat_level >= 60:
        arc = state.game.antagonist_arc
        before = arc.threat_level
        arc.threat_level = max(0, arc.threat_level - 2)
        arc.escalation_stage = _escalation_stage(arc.threat_level)
        events.append({"rule": "high_threat_counter_bonus", "antagonist_threat": {"before": before, "after": arc.threat_level}})
    return events


def _apply_economics_delta(state: CompanyState, delta: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("proof", "trust", "velocity", "burn_pressure", "autonomy", "runway_months")
    out: Dict[str, Any] = {}
    for key, change in delta.items():
        if key not in keys or not isinstance(change, (int, float)):
            continue
        before = int(getattr(state.economics, key, 0) or 0)
        after = max(0, min(100, before + int(change))) if key != "runway_months" else max(0, before + int(change))
        setattr(state.economics, key, after)
        out[key] = {"before": before, "after": after, "delta": int(change)}
    return out


def _apply_party_card_effect(state: CompanyState, card: GameCard, effect: Dict[str, Any], target_id: str) -> Dict[str, Any]:
    target = next((p for p in state.game.party if p.worker_id == target_id), None)
    if not target and card.owner_worker_id:
        target = next((p for p in state.game.party if p.worker_id == card.owner_worker_id), None)
    if not target and state.game.party:
        target = state.game.party[0]
    if not target:
        return {}
    before = target.model_dump()
    if "fatigue" in effect:
        target.fatigue = max(0, min(100, target.fatigue + int(effect["fatigue"])))
    if "morale" in effect:
        target.morale = max(0, min(100, target.morale + int(effect["morale"])))
    if "trust" in effect:
        target.trust = max(0, min(100, target.trust + int(effect["trust"])))
    if target.fatigue >= 70:
        target.status = "tired"
    elif target.status == "tired" and target.fatigue < 50:
        target.status = "ready"
    return {"worker_id": target.worker_id, "before": before, "after": target.model_dump()}


def _resolve_counterplay(state: CompanyState, target_id: str) -> None:
    moves = state.game.antagonist_arc.moves
    target = next((m for m in moves if m.id == target_id and not m.resolved), None)
    if not target:
        target = next((m for m in reversed(moves) if not m.resolved), None)
    if target:
        target.resolved = True
    state.game.antagonist_arc.open_counterplays = [
        m.counterplay for m in moves if not m.resolved and m.counterplay
    ][-5:]


def _all_cards(game: GameRunState) -> List[GameCard]:
    return list(game.deck) + list(game.hand) + list(game.discard) + list(game.exhaust)


def _antagonist_reaction_to_report(
    antagonist: Any, report: Optional[Dict[str, Any]]
) -> Optional[Tuple[str, str, int]]:
    """How the rival answers what the workforce just brought back.

    Single source for "the antagonist reacts to the workforce": turns the real
    field report ({signal, source} from server._worker_field_report) into the
    rival's adversarial clause, a specific counterplay, and a small bounded
    threat bonus - the win has a cost, a discovered wedge draws the rival's eye.
    Returns None when the report carries no concrete finding (the move then
    degrades to its CEO-choice-only form). Reuses the SAME finding the World
    Designer reacts to, so both Game Masters answer the workforce from one truth.
    """
    if not antagonist or not report:
        return None
    signal = str(report.get("signal") or "").strip()
    source = str(report.get("source") or "").strip()
    if signal:
        return (
            f"sees your workforce surface '{signal[:80]}' and races to plant its flag there first",
            f"Defend the wedge: ship cited proof on '{signal[:60]}' before the rival does.",
            2,
        )
    if source:
        return (
            f"reverse-engineers your {source[:48]}-backed proof and rushes a cheap imitation",
            f"Differentiate: add a proof the rival cannot copy from {source[:48]}.",
            1,
        )
    return None


def _rival_role_for_pressure(antagonist: Any, pressure_type: str, target_metric: str) -> Dict[str, str]:
    """Pick the rival org role that owns a pressure lane.

    AntagonistState carries a small enemy org chart. This helper makes that org
    mechanically real by assigning each move to the role whose lane/mandate best
    matches the pressure, with deterministic fallback to the first role.
    """
    roles = list(getattr(antagonist, "organization_roles", None) or []) if antagonist else []
    if not roles:
        return {}
    aliases = {
        "market": {"sales", "distribution", "marketing", "market", "retention"},
        "financial": {"financial", "pricing", "cost"},
        "technical": {"technical", "data", "platform", "automation"},
        "operational": {"ops", "supply", "compliance", "process"},
        "cultural": {"cultural", "policy", "attention", "marketing", "compliance"},
        "proof": {"data", "technical", "compliance", "proof"},
        "trust": {"policy", "compliance", "retention", "sales", "trust"},
        "velocity": {"technical", "distribution", "ops", "platform"},
        "burn_pressure": {"financial", "cost", "pricing"},
        "autonomy": {"policy", "cultural", "compliance", "platform"},
    }
    needles = set()
    for key in (pressure_type, target_metric):
        needles.update(aliases.get(key, {key}))

    def normalize(role: Dict[str, Any]) -> Dict[str, str]:
        return {
            "title": str(role.get("title") or "").strip(),
            "mandate": str(role.get("mandate") or "").strip(),
            "pressure_lane": str(role.get("pressure_lane") or "").strip(),
        }

    for raw in roles:
        role = normalize(raw if isinstance(raw, dict) else {})
        haystack = f"{role['title']} {role['mandate']} {role['pressure_lane']}".lower()
        if any(needle and needle.lower() in haystack for needle in needles):
            return role
    return normalize(roles[0] if isinstance(roles[0], dict) else {})


def _build_antagonist_move(state: CompanyState, stage: Stage, choice: ChoiceRecord,
                           worker_report: Optional[Dict[str, Any]] = None) -> Optional[AntagonistMove]:
    if not state.antagonist:
        return None
    pressure_type, target_metric, pressure_delta, fallback = _PRESSURE_BY_RULE.get(
        choice.rule_id, _PRESSURE_BY_RULE["custom.default"])
    tactic = state.antagonist.signature_tactic or fallback
    rival_role = _rival_role_for_pressure(state.antagonist, pressure_type, target_metric)
    role_title = rival_role.get("title") or "rival operator"
    # The rival watches the WORKFORCE, not only the CEO: when the digital workers
    # surface a real finding, the rival contests that exact wedge - reacting to
    # what the team did, with a specific counterplay and a small threat bite.
    reaction = _antagonist_reaction_to_report(state.antagonist, worker_report)
    if reaction:
        clause, counterplay, contest_bonus = reaction
        narrative = (
            f"{state.antagonist.name}'s {role_title} {clause}, answering the CEO call "
            f"'{choice.option}'. {choice.consequence_summary or ''}"
        ).strip()
        pressure_delta = min(20, pressure_delta + contest_bonus)
    else:
        narrative = (
            f"{state.antagonist.name} sends {role_title} to answer the CEO choice "
            f"'{choice.option}' with {tactic}. "
            f"{choice.consequence_summary or fallback}"
        )
        counterplay = _counterplay_for_metric(target_metric)
    return AntagonistMove(
        id=f"move_{stage.id}_{choice.rule_id.replace('.', '_')}",
        day_index=choice.day_index,
        stage_id=stage.id,
        title=f"{state.antagonist.name}: {role_title} pressure",
        tactic=tactic,
        pressure_type=pressure_type,
        target_metric=target_metric,
        rival_role_title=role_title,
        rival_role_mandate=rival_role.get("mandate", ""),
        rival_pressure_lane=rival_role.get("pressure_lane", ""),
        pressure_delta=pressure_delta,
        narrative=narrative[:500],
        counterplay=counterplay,
        source_rule_id=choice.rule_id,
    )


def _upsert_antagonist_move(state: CompanyState, move: AntagonistMove) -> None:
    arc = state.game.antagonist_arc
    if not arc.antagonist_name and state.antagonist:
        arc.antagonist_name = state.antagonist.name
    arc.moves = [m for m in arc.moves if m.id != move.id]
    arc.moves.append(move)
    arc.threat_level = max(0, min(100, arc.threat_level + move.pressure_delta))
    arc.current_pressure = move.narrative
    arc.open_counterplays = [m.counterplay for m in arc.moves if not m.resolved and m.counterplay][-5:]
    arc.escalation_stage = _escalation_stage(arc.threat_level)
    _refresh_run_status(state)


def _upsert_inventory_from_stage(state: CompanyState, stage: Stage) -> None:
    if not stage.artifact:
        return
    item = InventoryItem(
        id=f"item_{stage.id}_artifact",
        name=f"{stage.title} artifact",
        kind="artifact",
        description=f"Approved work from {stage.assigned_worker_title or stage.owner_role}.",
        source_stage_id=stage.id,
        owner_worker_id=stage.assigned_worker_id or stage.owner_role,
        effects={
            "validation_score": stage.validation_score,
            "artifact_keys": list(stage.artifact.keys())[:12],
        },
        tags=[stage.owner_role, stage.id, "proof"],
    )
    state.game.inventory = [i for i in state.game.inventory if i.id != item.id]
    state.game.inventory.append(item)


# Worker evolution: a digital worker that ships stages earns XP and levels up,
# unlocking a new tool and gaining morale/trust. This is the roguelike growth
# loop - the workforce gets stronger across the run, not a static blueprint.
# Threshold scales with level so each tier costs more (level N needs 30*N XP).
WORKER_XP_PER_LEVEL = max(1, int(os.getenv("WORKER_XP_PER_LEVEL", "30") or 30))
WORKER_MAX_LEVEL = max(1, int(os.getenv("WORKER_MAX_LEVEL", "6") or 6))
# Default unlock pool when the toolbox has no role-specific tools to grant.
_DEFAULT_UNLOCK_TOOLS = ["map_company", "web_search", "recall"]


def _unlock_pool_for_role(role: str) -> List[str]:
    """Ordered tools a worker of this archetype can unlock as it levels.

    Sourced from the real worker toolbox (tools_for_role) so an unlock grants a
    tool the worker can actually draw; degrades to a generic research pool when
    the toolbox is unavailable (keeps state/ importable without tools/)."""
    try:
        from tools.toolbox import tools_for_role
        pool = list(tools_for_role(role) or [])
    except Exception:
        pool = []
    for t in _DEFAULT_UNLOCK_TOOLS:
        if t not in pool:
            pool.append(t)
    return pool


def _evolve_worker_from_stage(state: CompanyState, member: WorkerPartyMember, stage: Stage) -> List[Dict[str, Any]]:
    """Award XP for a shipped stage and level the worker up past each threshold.

    Single source for worker progression: XP scales with the gate score, each
    level costs WORKER_XP_PER_LEVEL * level, and a level-up grants morale/trust
    and unlocks the next tool the worker can draw. Earned xp/level/tools are
    propagated back to the OrgRole so they survive a party rebuild and a reload.
    Returns the level-up events for the caller to log (empty = no level gained).
    """
    score = int(stage.validation_score or 0)
    if score <= 0:
        return []
    member.xp = int(member.xp or 0) + score
    events: List[Dict[str, Any]] = []
    pool = _unlock_pool_for_role(member.role or stage.owner_role)
    while member.level < WORKER_MAX_LEVEL and member.xp >= WORKER_XP_PER_LEVEL * member.level:
        member.xp -= WORKER_XP_PER_LEVEL * member.level
        member.level += 1
        member.morale = max(0, min(100, member.morale + 15))
        member.trust = max(0, min(100, member.trust + 10))
        unlocked = next((t for t in pool if t not in member.tools), "")
        if unlocked:
            member.tools.append(unlocked)
        events.append({
            "worker_id": member.worker_id,
            "title": member.title,
            "level": member.level,
            "xp": member.xp,
            "next_threshold": WORKER_XP_PER_LEVEL * member.level,
            "unlocked_tool": unlocked,
        })
    # Propagate the live progression back to the designed seat (single source of
    # truth survives a _party_from_org rebuild and a save/reload).
    if state.org:
        for role in state.org.roles:
            if role.id == member.worker_id:
                role.xp = member.xp
                role.level = member.level
                role.tools = list(member.tools)
                break
    return events


def _assign_party_to_stage(state: CompanyState, stage: Stage) -> List[Dict[str, Any]]:
    worker_id = stage.assigned_worker_id or ""
    levelups: List[Dict[str, Any]] = []
    for member in state.game.party:
        if member.worker_id == worker_id:
            member.current_stage_id = stage.id
            member.status = "assigned" if stage.status != "completed" else "ready"
            member.fatigue = min(100, member.fatigue + 6)
            member.morale = max(0, min(100, member.morale + (3 if (stage.validation_score or 0) >= 80 else -4)))
            if stage.status == "completed":
                levelups = _evolve_worker_from_stage(state, member, stage)
    return levelups


def _apply_party_choice_cost(state: CompanyState, stage: Stage, choice: ChoiceRecord) -> None:
    worker_id = stage.assigned_worker_id or ""
    for member in state.game.party:
        if member.worker_id != worker_id:
            continue
        consequence = choice.consequence or {}
        delta = consequence.get("economics_delta") or {}
        trust_delta = int(delta.get("trust", 0) or 0)
        velocity_delta = int(delta.get("velocity", 0) or 0)
        member.trust = max(0, min(100, member.trust + trust_delta // 2))
        member.fatigue = max(0, min(100, member.fatigue + max(1, abs(velocity_delta) // 2)))
        if member.fatigue >= 70:
            member.status = "tired"


def _upsert_encounter(state: CompanyState, encounter: EncounterState) -> None:
    state.game.encounters = [e for e in state.game.encounters if e.id != encounter.id]
    state.game.encounters.append(encounter)


def _day_index_for_stage(state: CompanyState, stage: Stage) -> int:
    if state.world and stage in state.world.stages:
        return state.world.stages.index(stage) + 1
    return max(1, state.game.day_index)


def _counterplay_for_metric(metric: str) -> str:
    return {
        "proof": "Ship a cited proof artifact before expanding scope.",
        "trust": "Add human review or stronger validation at the next gate.",
        "velocity": "Cut scope and assign the fastest worker to the next room.",
        "burn_pressure": "Remove one cost center or prove a revenue path.",
        "autonomy": "Choose the option that preserves founder/community control.",
    }.get(metric, "Force the next worker to name the tradeoff explicitly.")


def _escalation_stage(threat_level: int) -> str:
    if threat_level >= 80:
        return "endgame"
    if threat_level >= 60:
        return "crisis"
    if threat_level >= 40:
        return "contesting"
    if threat_level >= 20:
        return "probing"
    return "watching"


# Time pressure lives in the arc, not the wallet. Cheap burn means cash rarely
# ends a run - the rival does. Each in-game day the antagonist gains threat,
# faster the higher the escalation stage (the longer you stall, the worse it
# gets), and slower when the company is visibly winning (positive net + proof).
THREAT_PER_DAY = max(0.0, float(os.getenv("ANTAGONIST_THREAT_PER_DAY", "1.1") or 1.1))
_THREAT_ACCEL = {"watching": 0.7, "probing": 1.0, "contesting": 1.3, "crisis": 1.6, "endgame": 2.0}

# Ending a turn to refresh the hand is not free: the rival uses the breather to
# press, so refilling energy is a genuine tactical trade, not an exploit. Kept
# modest so it teaches the loop without being punishing.
END_TURN_THREAT_PRESS = max(0, int(os.getenv("END_TURN_THREAT_PRESS", "3") or 3))

# When time pushes the rival into a higher escalation stage it makes a visible
# MOVE in the world (narrative + a counterplay) AND bites a metric, reusing the
# same AntagonistMove machinery CEO decisions use - so the rising number
# announces itself and is felt, instead of climbing silently. Each entry carries
# (pressure_type, target_metric, narrative_line, economics_delta) so the bite is
# data-driven and single-source. burn_pressure rises (worse); the others fall.
_ESCALATION_PRESSURE = {
    "probing": ("market", "velocity",
                "starts probing your market - testing where the proof is thinnest",
                {"velocity": -3}),
    "contesting": ("market", "trust",
                   "contests your accounts head-on, matching every move you make",
                   {"trust": -4}),
    "crisis": ("financial", "burn_pressure",
               "escalates to open war - undercutting price and poaching while you stall",
               {"burn_pressure": 6, "velocity": -3}),
    "endgame": ("cultural", "autonomy",
                "is at the gates - one more unanswered move and the market is theirs",
                {"autonomy": -6, "trust": -4}),
}

# Story Circle (Dan Harmon) beat -> villain pressure multiplier, by the index of
# the stage the run is currently on. The rival surges at TAKE (index 5, "the win
# has a cost; rivalry arrives") and eases at the cooperative CHANGE finale.
_BEAT_PRESSURE = [1.0, 1.0, 1.05, 1.1, 1.15, 1.45, 1.1, 0.8]


def _story_beat_pressure(state: CompanyState) -> float:
    stages = (state.world.stages if state.world else [])
    if not stages:
        return 1.0
    idx = len(stages) - 1
    for i, s in enumerate(stages):
        if str(getattr(s, "status", "")).lower() != "completed":
            idx = i
            break
    return _BEAT_PRESSURE[min(idx, len(_BEAT_PRESSURE) - 1)]


def _build_time_escalation_move(state: CompanyState, to_stage: str) -> Optional[AntagonistMove]:
    arc = state.game.antagonist_arc
    rival = arc.antagonist_name or (state.antagonist.name if state.antagonist else "The rival")
    tactic = (state.antagonist.signature_tactic if state.antagonist else "") or "relentless market pressure"
    ptype, target_metric, line, _delta = _ESCALATION_PRESSURE.get(
        to_stage, ("market", "trust", "tightens its grip on the market", {"trust": -3}))
    rival_role = _rival_role_for_pressure(state.antagonist, ptype, target_metric)
    role_title = rival_role.get("title") or "rival operator"
    narrative = f"{rival}'s {role_title} {line}. Signature move: {tactic}."
    return AntagonistMove(
        id=f"move_time_{to_stage}",
        day_index=int(state.game.day_index or 0),
        stage_id="",
        title=f"{rival}: {role_title} pressure",
        tactic=tactic,
        pressure_type=ptype,
        target_metric=target_metric,
        rival_role_title=role_title,
        rival_role_mandate=rival_role.get("mandate", ""),
        rival_pressure_lane=rival_role.get("pressure_lane", ""),
        pressure_delta=0,
        narrative=narrative[:500],
        counterplay=_counterplay_for_metric(target_metric),
        source_rule_id="time.escalation",
    )


def tick_antagonist_over_time(state: CompanyState, days: float) -> Dict[str, Any]:
    """Escalate antagonist threat as real time passes - the run's live pressure.

    Driven by the real-time economy clock so a stalled company loses ground to
    the rival even between moves. The climb accelerates with the escalation
    stage and is suppressed when the company is clearly winning. Crossing into a
    higher stage makes the rival play a visible move (narrative + counterplay);
    at threat 100 the run is lost. Counterplay cards and strong stage outcomes
    push it back.
    """
    game = getattr(state, "game", None)
    if game is None or days <= 0 or game.run_status != "active":
        return {"threat_advanced": 0.0}
    arc = game.antagonist_arc
    accel = _THREAT_ACCEL.get(arc.escalation_stage, 1.0)
    # Story Circle (Dan Harmon) tie-in: the villain tests the founder hardest at
    # TAKE (beat 6, index 5) - "the win has a cost and rivalry arrives." The
    # rival surges on that beat and eases on the cooperative CHANGE beat.
    beat_mult = _story_beat_pressure(state)
    winning = 1.0
    econ = state.economics
    if econ is not None:
        if int(econ.net_profit_usd or 0) > 0:
            winning -= 0.35
        if int(econ.proof or 0) >= 60:
            winning -= 0.25
    winning = max(0.3, winning)
    gain = days * THREAT_PER_DAY * accel * winning * beat_mult
    arc.threat_progress = float(getattr(arc, "threat_progress", 0.0) or 0.0) + gain
    result: Dict[str, Any] = {"threat_advanced": round(gain, 3)}
    whole = int(arc.threat_progress)
    if whole >= 1:
        arc.threat_progress -= whole
        before = arc.threat_level
        before_stage = arc.escalation_stage
        arc.threat_level = min(100, arc.threat_level + whole)
        arc.escalation_stage = _escalation_stage(arc.threat_level)
        result.update({"threat_before": before, "threat_after": arc.threat_level})
        # Crossing into a higher stage: the rival makes a move in the world.
        if arc.escalation_stage != before_stage and arc.threat_level < 100:
            move = _build_time_escalation_move(state, arc.escalation_stage)
            if move:
                arc.moves = [m for m in arc.moves if m.id != move.id]
                arc.moves.append(move)
                arc.current_pressure = move.narrative
                arc.open_counterplays = [
                    m.counterplay for m in arc.moves if not m.resolved and m.counterplay][-5:]
                # The move bites: apply its data-driven metric pressure so the
                # escalation is felt, not just narrated. This can itself end the
                # run (e.g. trust -> 0), surfaced by the refresh below.
                econ_delta = _ESCALATION_PRESSURE.get(arc.escalation_stage, (None, None, None, {}))[3]
                if econ_delta and state.economics is not None:
                    result["economics_delta"] = _apply_economics_delta(state, econ_delta)
                result["escalated_to"] = arc.escalation_stage
                result["rival"] = arc.antagonist_name
                result["pressure"] = move.narrative
                result["counterplay"] = move.counterplay
        if arc.threat_level >= 100 and game.run_status == "active":
            game.run_status = "defeat"
            game.defeat_reason = (
                f"{arc.antagonist_name or 'The antagonist'} seized the market while the company stalled."
            )
            result["defeated"] = True
        # The metric bite can itself end the run (trust 0 / burn_pressure 100).
        _refresh_run_status(state)
        if game.run_status == "defeat":
            result["defeated"] = True
    return result


def _seed_from_run_id(run_id: str) -> int:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) or 1


def _next_rand(game: GameRunState) -> int:
    # xorshift32 deterministic PRNG with stored state in GameRunState.
    x = int(game.rng_state or game.rng_seed or 1) & 0xFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17) & 0xFFFFFFFF
    x ^= (x << 5) & 0xFFFFFFFF
    game.rng_state = x & 0xFFFFFFFF
    return game.rng_state


def _shuffle_cards(cards: List[GameCard], game: GameRunState) -> None:
    if len(cards) < 2:
        return
    for i in range(len(cards) - 1, 0, -1):
        j = _next_rand(game) % (i + 1)
        cards[i], cards[j] = cards[j], cards[i]


def _refresh_run_status(state: CompanyState) -> None:
    game = state.game
    stages = list(state.world.stages) if state.world else []
    all_stages_completed = bool(stages) and all(s.status == "completed" for s in stages)
    if game.run_status == "victory" and not all_stages_completed:
        game.run_status = "active"
        game.victory_reason = ""
        if state.world:
            state.world.status = "active"
        if state.stage == "launched":
            state.stage = "validated"
    if game.run_status != "active":
        return
    if state.economics.trust <= 0:
        game.run_status = "defeat"
        game.defeat_reason = "Trust collapsed to zero."
    elif state.economics.burn_pressure >= 100:
        game.run_status = "defeat"
        game.defeat_reason = "Burn pressure reached critical."
    elif game.antagonist_arc.threat_level >= 100:
        game.run_status = "defeat"
        game.defeat_reason = "Antagonist reached endgame dominance."
    elif state.world and state.world.status == "completed" and state.stage == "launched" and all_stages_completed:
        game.pending_rewards = []
        game.run_status = "victory"
        game.victory_reason = "All 8 venture stages shipped while the company stayed solvent."
        if "venture_loop_launched" not in game.unlocks:
            game.unlocks.append("venture_loop_launched")
        if "starter_plus_draw" not in game.unlocks:
            game.unlocks.append("starter_plus_draw")


def reconcile_run_status(state: CompanyState) -> None:
    """Normalize lifecycle status after loading older saved runs."""
    if state and state.game:
        _refresh_run_status(state)
