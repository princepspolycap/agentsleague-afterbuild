"""Deterministic, venture-aware dilemma source - the single offline fallback.

One home for the CEO decision-gate dilemma when the live narrator model is not
available (simulation, or a live-path failure). Keyed by the sealed stage's
owner_role so each beat of the 8-stage arc poses a *different* tradeoff, and
interpolated with the run's real nouns - the named antagonist, its CURRENT
evolving pressure, the target customer, the company - so two ventures never read
identically.

Each option carries the explicit consequence rule_id for its owner_role (and the
rule's match tokens in its text as a backstop), so the shared
``_enrich_dilemma_options`` sink in the server resolves the right deterministic
consequence with no guessing. This is the single dilemma engine: it replaces
both the old ``DILEMMA_TEMPLATES``/``generate_dilemma`` path and the server's
``_CANNED_DILEMMAS``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from state.schema import CompanyState, Stage


# One dilemma per stage owner_role. Option text embeds {tokens} filled from live
# run state; rule_id pins the deterministic consequence (and the rule's own match
# tokens are echoed in the text as a resolution backstop). {pressure_clause} is a
# full sentence (the arc's CURRENT evolving pressure), so prompts lead with it
# rather than forcing it into "{antagonist} is ..." grammar.
_DILEMMAS_BY_ROLE: Dict[str, Dict[str, Any]] = {
    "strategist": {
        "title": "Depth or Breadth?",
        "axis": "depth_vs_breadth",
        "prompt": "{pressure_clause} Which escape vector do you commit {company} to next?",
        "options": [
            {"id": "depth", "rule_id": "strategist.depth",
             "option": "Depth: own one {customer} niche end to end",
             "tradeoff": "stabilized loop, slower reach"},
            {"id": "breadth", "rule_id": "strategist.breadth",
             "option": "Breadth: map adjacent beachheads fast for reach",
             "tradeoff": "wider escape nodes, shallower proof"},
        ],
    },
    "designer": {
        "title": "Ship or Polish?",
        "axis": "speed_vs_quality",
        "prompt": "The prototype is at 70%. {pressure_clause} Deploy now or harden it?",
        "options": [
            {"id": "ship", "rule_id": "designer.ship",
             "option": "Ship the 70% loop now and learn from real users",
             "tradeoff": "host instability, faster learning"},
            {"id": "polish", "rule_id": "designer.polish",
             "option": "Polish to 95% - three more weeks of quality hardening",
             "tradeoff": "stabilized loop, higher burn"},
        ],
    },
    "marketer": {
        "title": "Adoption or Runway?",
        "axis": "volume_vs_value",
        "prompt": "{pressure_clause} How does {company} price for {customer}?",
        "options": [
            {"id": "adoption", "rule_id": "marketer.adoption",
             "option": "Low price for grassroots adoption volume",
             "tradeoff": "thin margins, support load"},
            {"id": "runway", "rule_id": "marketer.runway",
             "option": "Fewer, bigger enterprise accounts for runway",
             "tradeoff": "longer pipeline, secured runway"},
        ],
    },
    "ops": {
        "title": "Automate or Steward?",
        "axis": "leverage_vs_trust",
        "prompt": "Support load is scaling. {pressure_clause} How do you run it?",
        "options": [
            {"id": "automate", "rule_id": "ops.automate",
             "option": "Automate the support path to protect margin",
             "tradeoff": "risk to host trust at the edges"},
            {"id": "human_loop", "rule_id": "ops.human_loop",
             "option": "Keep a human in the loop to protect the promise",
             "tradeoff": "burn pressure, ethical alignment"},
        ],
    },
}

# The 8th beat (CHANGE) is always owner_role "ops", so ops.shareholder /
# ops.cooperative are valid consequence rules for it - the run's ending fork.
_FINAL_DILEMMA: Dict[str, Any] = {
    "title": "Cooperative or Shareholder?",
    "axis": "cooperative_vs_shareholder",
    "prompt": "The infinite-growth machine offers {company} a clean exit. {pressure_clause} What becomes the new normal?",
    "options": [
        {"id": "shareholder", "rule_id": "ops.shareholder",
         "option": "Take shareholder capital and blitzscale the grid",
         "tradeoff": "speed gained, autonomy sold"},
        {"id": "cooperative", "rule_id": "ops.cooperative",
         "option": "Form the worker-cooperative equilibrium alliance",
         "tradeoff": "slower growth, durable trust"},
    ],
}


def _is_final_stage(stage: Stage) -> bool:
    sid = (getattr(stage, "id", "") or "").lower()
    return sid == "stage_8_change" or "change" in sid


# Third-person, narrator-voiced description of what the rival is doing at each
# escalation stage. Clean and short by construction, so the dilemma always reads
# legibly - unlike the verbose move.narrative, which can leak internal nouns.
_ESCALATION_ACTION = {
    "watching": "circling your market for an opening",
    "probing": "probing where your proof is thinnest",
    "contesting": "contesting every account you touch",
    "crisis": "in open war - undercutting price and poaching customers",
    "endgame": "at the gates, one unanswered move from taking the market",
}


def _venture_tokens(state: CompanyState) -> Dict[str, str]:
    """Real nouns from the live run so the dilemma is venture-specific.

    pressure_clause cites the antagonist arc's EVOLVING state (escalation stage
    and live threat) - the same signals the standup villain reads - rendered as
    one clean narrator sentence. It deliberately avoids the verbose, leak-prone
    move.narrative so the gate stays legible; signature_tactic is the curated
    fallback before any arc exists.
    """
    ant = getattr(state, "antagonist", None)
    game = getattr(state, "game", None)
    arc = getattr(game, "antagonist_arc", None) if game else None
    antagonist = (getattr(arc, "antagonist_name", "") or getattr(ant, "name", "")
                  or "The Market").strip()
    customer = (getattr(ant, "target_customer_overlap", "") or "your market").strip()
    company = (getattr(state, "name", "") or "your company").strip()

    stage = (getattr(arc, "escalation_stage", "") or "").strip().lower() if arc else ""
    threat = int(getattr(arc, "threat_level", 0) or 0) if arc else 0
    if stage in _ESCALATION_ACTION:
        clause = f"{antagonist} is {_ESCALATION_ACTION[stage]} (threat {threat}/100)."
    else:
        clause = _as_sentence(getattr(ant, "signature_tactic", "")) or f"{antagonist} is closing in."
    return {"antagonist": antagonist, "pressure_clause": clause,
            "pressure": clause.rstrip("."), "customer": customer, "company": company}


def _as_sentence(text: str) -> str:
    """Normalize a fragment to one capitalized, period-terminated sentence."""
    text = (text or "").strip()
    if not text:
        return ""
    text = text[:1].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


def _fill(text: str, tokens: Dict[str, str]) -> str:
    out = text or ""
    for key, val in tokens.items():
        out = out.replace("{" + key + "}", val)
    return out


def build_stage_dilemma(
    state: CompanyState,
    stage: Stage,
    next_stage: Optional[Stage] = None,
) -> Dict[str, Any]:
    """The single deterministic, venture-aware dilemma for a sealed stage.

    Returns the canonical dict the /api/dilemma endpoint consumes
    ({prompt, options, source, title, tradeoff_axis, antagonist_move}); each
    option carries the owner_role's consequence rule_id for the shared enrich
    sink to resolve. Pure dict-building over known templates - never raises - so
    it is a safe last-resort fallback.
    """
    role = getattr(stage, "owner_role", "") or "strategist"
    template = _FINAL_DILEMMA if _is_final_stage(stage) else \
        _DILEMMAS_BY_ROLE.get(role) or _DILEMMAS_BY_ROLE["strategist"]
    tokens = _venture_tokens(state)
    options = [
        {
            "id": o["id"],
            "rule_id": o["rule_id"],
            "option": _fill(o["option"], tokens)[:160],
            "tradeoff": _fill(o["tradeoff"], tokens)[:120],
        }
        for o in template["options"]
    ]
    return {
        "prompt": _fill(template["prompt"], tokens)[:240],
        "options": options,
        "title": template["title"],
        "tradeoff_axis": template["axis"],
        "antagonist_move": tokens["pressure"],
        "source": "generated",
    }
