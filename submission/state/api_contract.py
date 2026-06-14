"""Stable response helpers for the game API.

The frontend should render the backend contract instead of inferring durable
game rules from ad hoc response shapes. These helpers keep existing keys while
adding explicit contract metadata for future frontend splits.
"""

from typing import Any, Dict, Optional

from state.schema import Stage, CompanyState, QuestStep, WorkerInvocation


CONTRACT_VERSION = "2026-06-11.game-backend.v1"

FLOW_STAGES = [
    "founder_intake",
    "org_design",
    "world_design",
    "stage_execution",
    "artifact_validation",
    "human_gate",
    "xp_memory_replay",
]

CANONICAL_SURFACES = {
    "legacy_quest": {
        "description": "Three-step quest path retained for the original simulator/UI.",
        "state_field": "active_quest",
    },
    "world_graph": {
        "description": "Preferred release path for dynamic workforce gameplay.",
        "state_field": "world",
    },
}


def contract_metadata(surface: str = "world_graph") -> Dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "canonical_surface": surface,
        "flow_stages": FLOW_STAGES,
        "surfaces": CANONICAL_SURFACES,
    }


SECTION_MEANING = {
    "company": "The venture you are building this run - every move ladders up to this one company.",
    "offer": "Offer - the product or service the company actually sells.",
    "customer": "Customer - the specific people or orgs the offer is sold to.",
    "business_model": "Business model - how the company is structured to create, deliver, and defend value.",
    "revenue_model": "Revenue model - how money actually comes in: price per customer x paying customers = monthly revenue.",
    "build_owner": "Build - the worker accountable for making the product/service exist.",
    "sell_owner": "Sell - the worker who owns market share and revenue.",
    "ops_owner": "Ops - the worker who runs delivery and keeps customers.",
    "rival": "Rival - the antagonist market logic pressuring the run; counter it with proof, trust, shipping, and counterplay cards.",
}


def _section(label: str, value: str, meaning: str, source: str, detail: str = "", status: str = "ok") -> Dict[str, str]:
    return {
        "label": label,
        "value": str(value or ""),
        "meaning": meaning,
        "source": source,
        "detail": str(detail or value or ""),
        "status": status,
    }


def _role_for_need(state: CompanyState, keys: tuple[str, ...], fallback: str, source: str) -> Dict[str, str]:
    roles = list(state.org.roles if state.org else [])
    for role in roles:
        hay = " ".join([
            role.title or "",
            role.deployment_hint or "",
            role.lifecycle_stage or "",
            " ".join(role.kpis or []),
            role.mandate or "",
        ]).lower()
        if any(key in hay for key in keys):
            return {"value": role.title, "source": f"Source: Org Designer role `{role.id}` ({source}).", "status": "ok"}
    stages = list(state.world.stages if state.world else [])
    for stage in stages:
        hay = f"{stage.assigned_worker_title or ''}".lower()
        if any(key in hay for key in keys):
            return {"value": stage.assigned_worker_title or stage.owner_role, "source": f"Source: World Designer stage `{stage.id}` assignment ({source}).", "status": "ok"}
    return {"value": fallback, "source": f"Source: current org/world graph has no matching {source} owner.", "status": "gap"}


def refresh_venture_model(state: Optional[CompanyState]) -> Optional[Dict[str, Any]]:
    """Refresh canonical company-dashboard data from the live state.

    This is intentionally backend-derived: Founder Analyst owns offer/customer/
    business model; Org Designer and World Designer own accountability; economics
    owns revenue math; Antagonist Generator owns the rival. The UI renders this
    object and no longer guesses durable business facts from scattered fields.
    """
    if not state:
        return None
    profile = state.founder_profile
    org = state.org
    econ = state.economics
    arc = state.game.antagonist_arc if state.game else None
    antagonist = state.antagonist
    company = state.name or "Company"
    offer = (profile.what_they_sell if profile else "") or (profile.company_summary if profile else "") or (org.company_summary if org else "") or state.pitch or "Product/service not defined"
    customer = (profile.target_customer if profile else "") or (antagonist.target_customer_overlap if antagonist else "") or "Target customer not defined"
    business_model = (profile.business_model if profile else "") or (org.operating_model if org else "") or "Business model pending"
    arpu = int(getattr(econ, "arpu_usd", 0) or 0)
    customers = int(getattr(econ, "paying_customers", 0) or 0)
    revenue = int(getattr(econ, "monthly_revenue_usd", 0) or 0)
    revenue_value = f"${arpu:,}/customer · mo" if arpu else "Not priced yet"
    revenue_detail = (f"Recurring: ${arpu:,}/customer/mo x {customers:,} paying = ${revenue:,}/mo today. "
                      "Win more customers by shipping verified stages.") if arpu else "No priced revenue model yet."
    build = _role_for_need(state, ("builder", "designer", "engineer", "product", "mvp"), "No product owner", "product/build")
    sell = _role_for_need(state, ("growth", "sales", "gtm", "closer", "marketer"), "No revenue owner", "sales/revenue")
    ops = _role_for_need(state, ("ops", "operation", "retention", "support", "success"), "No delivery owner", "delivery/retention")
    rival_name = (arc.antagonist_name if arc else "") or (antagonist.name if antagonist else "") or "The rival"
    sections = {
        "company": _section("Company", company, SECTION_MEANING["company"], "Source: World Designer / saved run state."),
        "offer": _section("Offer", offer, SECTION_MEANING["offer"], "Source: Founder Analyst `what_they_sell`, then Org Designer company summary."),
        "customer": _section("Customer", customer, SECTION_MEANING["customer"], "Source: Founder Analyst `target_customer`, then Antagonist overlap fallback."),
        "business_model": _section("Business model", business_model, SECTION_MEANING["business_model"], "Source: Founder Analyst `business_model`, then Org Designer operating model."),
        "revenue_model": _section("Revenue model", revenue_value, SECTION_MEANING["revenue_model"], "Source: live economics: arpu_usd, paying_customers, monthly_revenue_usd.", revenue_detail),
        "build_owner": _section("Build", build["value"], SECTION_MEANING["build_owner"], build["source"], status=build["status"]),
        "sell_owner": _section("Sell", sell["value"], SECTION_MEANING["sell_owner"], sell["source"], status=sell["status"]),
        "ops_owner": _section("Ops", ops["value"], SECTION_MEANING["ops_owner"], ops["source"], status=ops["status"]),
        "rival": _section("Rival", rival_name, SECTION_MEANING["rival"], "Source: Antagonist Generator + current antagonist arc."),
    }
    state.venture_model = {"sections": sections, "updated_from": "api_contract.refresh_venture_model"}
    return state.venture_model


def state_response(
    state: Optional[CompanyState],
    surface: str = "world_graph",
    **extra: Any,
) -> Dict[str, Any]:
    refresh_venture_model(state)
    payload: Dict[str, Any] = {
        "initialized": state is not None,
        "state": state.model_dump() if state else None,
        "contract": contract_metadata(surface),
    }
    payload.update(extra)
    return payload


def step_response(state: CompanyState, step: QuestStep, **extra: Any) -> Dict[str, Any]:
    return state_response(
        state,
        surface="legacy_quest",
        current_step=step.model_dump(),
        **extra,
    )


def stage_response(
    state: CompanyState,
    stage: Stage,
    invocation: WorkerInvocation,
    **extra: Any,
) -> Dict[str, Any]:
    return state_response(
        state,
        surface="world_graph",
        stage=stage.model_dump(),
        invocation=invocation.model_dump(),
        **extra,
    )


def reset_response() -> Dict[str, Any]:
    return {
        "success": True,
        "message": "State reset successfully.",
        "contract": contract_metadata(),
    }
