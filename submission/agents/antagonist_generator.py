"""Antagonist/Villain Generator — creates the story's competitive foil.

Given a founder's archetype and mission, generates a complementary antagonist that
represents the key challenge, competitor, or learning gap the founder must overcome.
This is the narrative tension point: every hero needs a worthy opponent.

Archetype pairings (founder ↔ antagonist):
  - Builder ↔ Seller (ships products but struggles to sell vs. sells but has no product)
  - Designer ↔ Operator (designs great UX but operational chaos vs. runs smooth ops but no innovation)
"""
from __future__ import annotations

import re
from typing import Dict, Any, Optional, List
from state.schema import AntagonistState


# Archetype opposites: the natural foil for each founder type
ARCHETYPE_OPPOSITES = {
    "Builder": "Seller",
    "Seller": "Builder",
    "Designer": "Operator",
    "Operator": "Designer",
}

# Rich antagonist profiles keyed by their archetype
ANTAGONIST_PROFILES = {
    "Builder": {
        "threat_type": "market",
        "name_templates": [
            "The Automation Cartel",
            "BuildCo Infinite",
            "The Technofeudal Syndicate",
            "DevOps Oligarchy",
        ],
        "threat_description": "A highly-capitalized technical conglomerate using AI and automated systems to eliminate labor costs and capture market share.",
        "signature_tactic": "Automated replacement: deploying zero-labor algorithmic replicas of your core service.",
        "strengths": [
            "rapid automation",
            "machine learning leverage",
            "infrastructure lock-in",
            "capital consolidation"
        ],
        "strategy": "Accumulate technical capital ($R > G$) to commoditize the developer tier and reduce switching costs.",
        "motivation": "Maximum accumulation: automating the production line to eliminate the wage expense.",
    },
    "Seller": {
        "threat_type": "market",
        "name_templates": [
            "The Shareholder Syndicate",
            "Closing Force Venture",
            "Venture Dynamics Inc",
            "The Infinite Trust",
        ],
        "threat_description": "A ruthless commercial force that prioritizes stock buybacks, debt-leveraged acquisitions, and aggressive account consolidation.",
        "signature_tactic": "Exclusivity lock-in: forcing customers into exclusive contracts to lock out organic alternatives.",
        "strengths": [
            "VC funding leverage",
            "corporate lobbying",
            "account acquisition",
            "monopolization paths"
        ],
        "strategy": "Blitzscale using massive quantitative-easing debt to starve and buy out community competitors.",
        "motivation": "Infinite growth: meeting the return expectations of the top 1% shareholders at all costs.",
    },
    "Designer": {
        "threat_type": "market",
        "name_templates": [
            "The Dopamine Cartel",
            "Engagement Lab",
            "Speculative Joy Inc",
            "The Hype Machine",
        ],
        "threat_description": "A venture-backed speculatively inflated competitor that sells hyper-delightful experiences built on addictive dopamine feedback loops.",
        "signature_tactic": "Cognitive capture: using addictive algorithmic design to trigger customer FOMO, alienation, and despair.",
        "strengths": [
            "behavioral manipulation",
            "speculative marketing",
            "viral distribution",
            "attention harvesting"
        ],
        "strategy": "Generate asset inflation by hyping virtual realities and AI bubbles to attract speculative investment.",
        "motivation": "Speculative exit: inflating stock valuation through pure hype before the bubble bursts.",
    },
    "Operator": {
        "threat_type": "market",
        "name_templates": [
            "Process Oligarchy",
            "Efficiency Bureau",
            "Lean Machine Consolidation",
            "The Equilibrium Crushing Group",
        ],
        "threat_description": "A ruthlessly optimized operations network designed to underprice you by outsourcing and slashing wages to the absolute minimum.",
        "signature_tactic": "Wage suppression: transforming high-paying creative work into piecework training tasks for automated algorithms.",
        "strengths": [
            "offshore outsourcing",
            "cost-minimization metrics",
            "supply chain control",
            "regulatory arbitrage"
        ],
        "strategy": "Consolidate distribution networks and lock out local cooperatives from the supply chains.",
        "motivation": "Operational dominance: eliminating human friction and wages to maximize returns per dollar.",
    }
}


def _mission_terms(mission_brief: str, exclude: Optional[set] = None) -> List[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "your",
        "our", "their", "company", "business", "startup", "venture", "service",
        "product", "build", "building", "using", "create", "help", "helps",
        # Generic role / bio words that read as nonsense when branded onto a
        # rival ("The Founder Syndicate"), plus filler from generic audiences.
        "founder", "cofounder", "co-founder", "ceo", "cto", "coo", "chief",
        "owner", "president", "director", "manager", "lead", "head", "principal",
        "consultant", "advisor", "adviser", "partner", "freelance", "freelancer",
        "people", "person", "serves", "serving", "work", "works", "mission",
        "collaborators", "customers", "clients", "team", "teams", "operators",
        "future", "public", "profile", "signal", "signals",
        # Platform / host / scrape-noise words that are not a real market.
        "linkedin", "twitter", "github", "facebook", "instagram", "medium",
        "youtube", "www", "com", "http", "https", "page", "website", "site",
        "detailed", "content", "readable", "authentication", "domain",
        "unreachable", "restricted", "default", "homepage",
        # Filler/function words that leak from the prose fallback summaries.
        "without", "cross", "referenced", "pieced", "together", "open", "web",
        "findings", "about", "around", "before", "after", "online", "small",
        "first", "digital", "operating", "could", "piece", "assembled",
    }
    blocked = {w.lower() for w in (exclude or set())}
    words = [
        w.strip(".,:;!?()[]{}\"'@&").replace("'s", "").replace("\u2019s", "")
        for w in (mission_brief or "").replace("/", " ").replace("-", " ").split()
    ]
    terms: List[str] = []
    seen: set = set()
    for w in words:
        low = w.lower()
        # Skip id-like tokens (anything with a digit) and stop/blocked words.
        if len(w) < 4 or re.search(r"\d", w) or low in stop or low in blocked or low in seen:
            continue
        seen.add(low)
        terms.append(w.title())
    return terms[:4]


def _name_tokens(*names: str) -> set:
    """Lowercase word tokens from the founder's name/brand, used to keep the
    rival from ever being named after the player (e.g. 'The Princeps Syndicate').
    """
    tokens: set = set()
    for name in names:
        for word in re.split(r"[^A-Za-z0-9]+", str(name or "")):
            if len(word) >= 3:
                tokens.add(word.lower())
    return tokens


def clean_person_name(name: str) -> str:
    """Strip handle/id artifacts from a founder name so the rival never targets
    'Jordan Rivera 9f8e'. Drops tokens containing digits (LinkedIn id tails) and
    title-cases the rest. Mirrors founder_analyst._humanize_handle so every path
    that names the player agrees. Returns '' when nothing human-readable remains.
    """
    raw = str(name or "").strip()
    if not raw:
        return ""
    parts = [p for p in re.split(r"[\s\-_]+", raw) if p and not re.search(r"\d", p)]
    cleaned = " ".join(w.capitalize() for w in parts)
    return cleaned[:60]


def _antithesis_name(
    base_names: List[str],
    archetype: str,
    mission_brief: str,
    target_customer: str,
    founder_name: str = "",
) -> str:
    """The deterministic fallback name for the rival (no LLM).

    The rival is the founder's antithesis - "you if you'd taken the money" - so
    its name is the opposite-archetype force itself (The Shareholder Syndicate,
    The Automation Cartel, ...), picked with per-run variety. It is NEVER glued
    together from the founder's brand or mission tokens (that produced nonsense
    like "The Princeps Shareholder Syndicate"). Real per-player naming is the
    live model's job in forge_antagonist; this clean archetypal name is the
    coherent, forkable fallback when no model is available.
    """
    if not base_names:
        return "The Shadow Market"
    # Vary the chosen force per founder/run so two players rarely share a rival,
    # while keeping every option a coherent, designed antithesis name.
    seed = f"{archetype}|{founder_name}|{target_customer}|{mission_brief}"
    return base_names[sum(ord(c) for c in seed) % len(base_names)]



def _rival_org(archetype: str, name: str, mission_brief: str, target_customer: str, founder_name: str = "") -> Dict[str, Any]:
    target = target_customer or "your target customers"
    # The contested "market" is the customer category, never the founder's own
    # brand (excluded), so the rival reads as fighting over a real market.
    exclude = _name_tokens(founder_name)
    market_terms = _mission_terms(target_customer, exclude) or _mission_terms(mission_brief, exclude)
    market = " ".join(market_terms[:2]) if market_terms else "the market"
    role_sets = {
        "Builder": [
            ("Automation CTO", "Clones your workflow with cheaper infrastructure.", "technical"),
            ("Data Moat Lead", "Locks up proprietary usage data before you can learn.", "data"),
            ("Platform Integrations", "Bundles the rival into channels you need.", "distribution"),
        ],
        "Seller": [
            ("Enterprise Closer", f"Signs exclusivity with {target}.", "sales"),
            ("Pricing Enforcer", "Starts a discount war to starve your runway.", "financial"),
            ("Lobbyist", "Frames your cooperative model as risky or amateur.", "policy"),
        ],
        "Designer": [
            ("Attention Designer", "Turns the category into a dopamine loop.", "cultural"),
            ("Launch Hype Lead", "Floods the market with spectacle before proof.", "marketing"),
            ("Retention Manipulator", "Makes switching emotionally expensive.", "retention"),
        ],
        "Operator": [
            ("Cost Cutter", "Undercuts you with outsourced delivery.", "ops"),
            ("Supply Gatekeeper", "Controls the vendors and channels you rely on.", "supply"),
            ("Process Auditor", "Weaponizes compliance friction against you.", "compliance"),
        ],
    }
    roles = [
        {"title": title, "mandate": mandate, "pressure_lane": lane}
        for title, mandate, lane in role_sets.get(archetype, role_sets["Seller"])
    ]
    # Name the player directly so the threat reads as personal - the rival is
    # coming for *them*, not an abstract "the player". Cleaned so handle/id
    # artifacts (e.g. 'Jordan Rivera 9f8e') never leak into the villain prose.
    challenger = clean_person_name(founder_name) or "the founder"
    return {
        "organization_name": f"{name} Counter-Org",
        "organization_model": (
            f"A rival operating team trying to capture the {market} opportunity before "
            f"{challenger}'s digital workforce can turn it into durable, trusted revenue."
        ),
        "organization_roles": roles,
        "active_operation": f"Contest {market} demand, poach {target}, and force {challenger} to prove trust before scaling.",
    }


def generate_antagonist(
    founder_archetype: str,
    founder_skill: str = "",
    mission_brief: str = "",
    target_customer: str = "",
    founder_name: str = "",
) -> AntagonistState:
    """Create a worthy antagonist based on the founder's archetype.

    The antagonist represents:
    - The market gap the founder must fill (what they're NOT naturally good at)
    - A competing force with the opposite strength
    - A narrative reason for the dilemmas the player will face

    Args:
        founder_archetype: One of Builder, Seller, Designer, Operator
        founder_skill: What the founder does well (used to refine the threat)
        mission_brief: The founder's mission/pitch (adds specificity)
        target_customer: Who the founder serves (helps define the antagonist's overlap)
        founder_name: The player's real name (e.g. from their LinkedIn). Used to
            target them personally AND excluded from the rival's name so the
            villain is never accidentally named after the player.

    Returns:
        An AntagonistState ready to persist in company state.
    """
    antagonist_archetype = ARCHETYPE_OPPOSITES.get(founder_archetype, "Seller")
    profile = ANTAGONIST_PROFILES.get(antagonist_archetype, {})

    # The deterministic fallback name is the clean opposite-archetype force
    # itself ("you if you'd taken the money"); live generation personalizes it.
    name_templates = profile.get("name_templates", ["The Shadow Market"])
    name = _antithesis_name(name_templates, antagonist_archetype, mission_brief, target_customer, founder_name)

    # Refine threat description based on mission if available
    threat_description = profile.get("threat_description", "A formidable competitor has entered the market.")
    if mission_brief:
        target = target_customer or "your market segment"
        threat_description = (
            f"A {antagonist_archetype.lower()}-first competitor targeting {target} "
            f"is executing on {mission_brief.split(':')[0].lower()}."
        )

    # Create the antagonist
    org = _rival_org(antagonist_archetype, name, mission_brief, target_customer, founder_name)
    antagonist = AntagonistState(
        name=name,
        archetype=antagonist_archetype,
        threat_type=profile.get("threat_type", "market"),
        threat_description=threat_description,
        strengths=profile.get("strengths", []),
        strategy=profile.get("strategy", "Outcompete on their core strength."),
        signature_tactic=profile.get("signature_tactic", "Execute faster and better."),
        target_customer_overlap=target_customer or "similar customer segment",
        motivation=profile.get("motivation", "Beat the incumbent."),
        organization_name=org["organization_name"],
        organization_model=org["organization_model"],
        organization_roles=org["organization_roles"],
        active_operation=org["active_operation"],
    )

    return antagonist


def analyze_archetype_gap(founder_archetype: str) -> Dict[str, Any]:
    """Explain what the founder's archetype is naturally weak at.

    Used for narrative framing and dilemma generation.
    """
    gaps = {
        "Builder": {
            "weakness": "sales and customer connection",
            "growth_path": "learn to sell what you build",
            "danger": "ships great product nobody knows about",
        },
        "Seller": {
            "weakness": "product design and UX",
            "growth_path": "learn to design experiences",
            "danger": "sells solutions that frustrate users",
        },
        "Designer": {
            "weakness": "operations and business mechanics",
            "growth_path": "learn to scale operations",
            "danger": "beautiful things that don't reach the market",
        },
        "Operator": {
            "weakness": "innovation and differentiation",
            "growth_path": "learn to build new things",
            "danger": "runs efficient machinery without a clear purpose",
        },
    }
    return gaps.get(founder_archetype, gaps["Builder"])
