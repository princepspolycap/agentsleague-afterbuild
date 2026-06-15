import json
import os
import re
import tempfile
import threading
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CharacterState(BaseModel):
    name: str
    role: str
    personality: str
    status: str = "idle"  # idle, working, completed, failed
    skills: List[str] = Field(default_factory=list)


class FounderState(BaseModel):
    name: str = "Acolyte"
    archetype: str = "Builder"  # Builder | Seller | Designer | Operator
    skill: str = "building product"
    locale: str = "en-US"
    voice_stack: str = "core_openai"  # core_openai | azure_speech | browser
    voice: str = "onyx"  # Alloy, Echo, Fable, Onyx, Nova, Shimmer
    avatar: str = "/game/assets/generated/narrator.png"


class SearchDocument(BaseModel):
    """One document shaped for the Azure AI Search index behind Foundry IQ.

    The same contract is used for static playbooks and generated run knowledge
    (founder profile, digital workers, stages, choices). That keeps ingestion
    keyless and inspectable before anything is pushed to Azure.
    """
    id: str
    title: str
    content: str
    source: str
    kind: str = "playbook"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FounderProfile(BaseModel):
    """Structured character sheet inferred from a URL or pitch.

    This is the durable seed for the roguelike run: world generation, worker
    briefs, antagonist design, and optional IQ ingestion all read this shape
    instead of reaching back into raw scrape dictionaries.
    """
    source: str = "pitch"              # pitch | url
    source_ref: str = ""
    source_kind: str = ""
    host: str = ""
    profile_key: str = ""              # non-PII link key (hash of the URL); the
                                       # raw URL stays local-only in profile_cache
    person_name: str = ""              # the founder's real name (e.g. from LinkedIn)
    company_summary: str = ""
    what_they_sell: str = ""
    target_customer: str = ""
    business_model: str = ""
    founder_archetype: str = "Builder"
    founder_skill: str = "building product"
    signals: List[str] = Field(default_factory=list)
    brief: str = ""
    scraped: bool = False
    osint_hits: int = 0
    mode: str = "simulation"


class AntagonistState(BaseModel):
    """The competitive antagonist or villain — the antithesis of the founder's archetype.

    In the story, the antagonist represents market competition, technical challenges,
    or the skills the founder must learn to grow their business.
    """
    name: str = "Shadow Market"
    archetype: str = "Operator"  # The complementary opposite of founder's archetype
    threat_type: str = "market"  # market | technical | internal | cultural
    threat_description: str = ""
    strengths: List[str] = Field(default_factory=list)
    strategy: str = ""  # What the antagonist is doing that poses a challenge
    signature_tactic: str = ""  # The key move the antagonist uses (narrative tension point)
    target_customer_overlap: str = ""  # Where their ICP overlaps with founder's target
    motivation: str = ""  # Why this antagonist exists/competes (story depth)
    organization_name: str = ""
    organization_model: str = ""
    organization_roles: List[Dict[str, Any]] = Field(default_factory=list)
    active_operation: str = ""


class AntagonistMove(BaseModel):
    """One pressure move the antagonist makes in response to player progress."""
    id: str
    day_index: int = 0
    stage_id: str = ""
    title: str = ""
    tactic: str = ""
    pressure_type: str = "market"  # market | technical | cultural | financial | operational
    target_metric: str = "trust"
    rival_role_title: str = ""
    rival_role_mandate: str = ""
    rival_pressure_lane: str = ""
    pressure_delta: int = 0
    narrative: str = ""
    counterplay: str = ""
    source_rule_id: str = ""
    resolved: bool = False


class AntagonistArc(BaseModel):
    """Run-long antagonist pressure track.

    AntagonistState names the villain. This arc stores what the villain is
    actively doing to the run: pressure level, moves, and open counterplay.
    """
    antagonist_name: str = ""
    threat_level: int = 10
    escalation_stage: str = "watching"  # watching | probing | contesting | crisis | endgame
    current_pressure: str = ""
    threat_progress: float = 0.0  # fractional carry for time-based escalation
    moves: List[AntagonistMove] = Field(default_factory=list)
    open_counterplays: List[str] = Field(default_factory=list)


class WorkerPartyMember(BaseModel):
    """Game-facing state for a digital worker in the party."""
    worker_id: str
    title: str
    role: str = ""
    lifecycle_stage: str = ""
    status: str = "ready"  # ready | assigned | tired | blocked | retired
    morale: int = 70
    fatigue: int = 0
    trust: int = 60
    xp: int = 0
    level: int = 1
    current_stage_id: str = ""
    tools: List[str] = Field(default_factory=list)
    traits: List[str] = Field(default_factory=list)


class InventoryItem(BaseModel):
    """A proof artifact, tool, alliance, or resource earned during the run."""
    id: str
    name: str
    kind: str = "artifact"  # artifact | tool | alliance | proof | constraint
    description: str = ""
    source_stage_id: str = ""
    owner_worker_id: str = ""
    effects: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class EncounterState(BaseModel):
    """One playable room/encounter in a run day."""
    id: str
    day_index: int
    stage_id: str
    kind: str = "stage"  # stage | dilemma | antagonist | verification | standup
    title: str = ""
    status: str = "open"  # open | resolved | failed
    worker_ids: List[str] = Field(default_factory=list)
    choice_ids: List[str] = Field(default_factory=list)
    antagonist_move_id: str = ""
    artifact_keys: List[str] = Field(default_factory=list)
    reward_item_ids: List[str] = Field(default_factory=list)


class GameCard(BaseModel):
    """One playable card in the founder's deck."""
    id: str
    name: str
    kind: str = "tactic"  # tactic | worker | proof | counterplay | resource
    cost: int = 1
    description: str = ""
    owner_worker_id: str = ""
    source: str = "starter"  # starter | stage_reward | choice_reward
    effects: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    upgraded: bool = False
    exhausts: bool = False


class PlayerMove(BaseModel):
    """One explicit player action in the card-building layer."""
    id: str
    turn_index: int
    day_index: int = 0
    stage_id: str = ""
    move_type: str = "play_card"  # play_card | choose_option | draw | end_turn | reward_card | ceo_command
    card_id: str = ""
    target_id: str = ""
    energy_spent: int = 0
    summary: str = ""
    effects_applied: Dict[str, Any] = Field(default_factory=dict)


class WorldCouncilTurn(BaseModel):
    """One Game Master's spoken turn in a world-council deliberation."""
    speaker: str
    role: str = "narrator"  # narrator | orgdesigner | antagonist
    role_label: str = ""
    worker_id: str = ""
    tool: str = ""
    message: str = ""
    handoff_to: str = ""
    source: str = "simulation"  # simulation | maf
    framework: str = ""


class WorldCouncilDeliberation(BaseModel):
    """A persisted Game Master council session.

    The World Designer, Org Designer, and Antagonist Director deliberate
    together after a move (CEO decision or rival escalation) and ratify how the
    world bends forward. Unlike the worker standup (the party reacting to the
    CEO), this is the engine/referee tier collaborating on world state. It is
    persisted so the roguelike world keeps evolving across reloads - the
    council's verdicts accumulate over the run.
    """
    id: str
    day_index: int = 0
    stage_id: str = ""
    trigger: str = ""  # short label of what convened the council
    summary: str = ""
    turns: List[WorldCouncilTurn] = Field(default_factory=list)
    adapted_stage_ids: List[str] = Field(default_factory=list)
    antagonist_move_id: str = ""
    threat_before: int = 0
    threat_after: int = 0
    forward_motion: str = ""  # the binding next step the council committed to
    source: str = "simulation"  # simulation | foundry


class GameRunState(BaseModel):
    """Durable roguelike layer over the business simulation."""
    run_id: str = "run_default"
    mode: str = "simulation"
    day_index: int = 0
    turn_index: int = 0
    loop_phase: str = "founding"  # founding | explore | dilemma | execute | verify | aftermath | complete
    max_energy: int = 3
    energy: int = 3
    draw_per_turn: int = 4
    deck: List[GameCard] = Field(default_factory=list)
    hand: List[GameCard] = Field(default_factory=list)
    discard: List[GameCard] = Field(default_factory=list)
    exhaust: List[GameCard] = Field(default_factory=list)
    pending_rewards: List[GameCard] = Field(default_factory=list)
    move_log: List[PlayerMove] = Field(default_factory=list)
    party: List[WorkerPartyMember] = Field(default_factory=list)
    inventory: List[InventoryItem] = Field(default_factory=list)
    encounters: List[EncounterState] = Field(default_factory=list)
    antagonist_arc: AntagonistArc = Field(default_factory=AntagonistArc)
    # Game Master council: the world-engine agents' deliberation history. Each
    # entry is one collaborative world-bending move, persisted so the roguelike
    # world keeps evolving across reloads (most recent last, bounded).
    council_log: List[WorldCouncilDeliberation] = Field(default_factory=list)
    # Deterministic run variance (seeded shuffle / event outcomes).
    rng_seed: int = 0
    rng_state: int = 0
    # Run lifecycle.
    run_status: str = "active"  # active | victory | defeat
    victory_reason: str = ""
    defeat_reason: str = ""
    unlocks: List[str] = Field(default_factory=list)


class CharacterRuntimeState(BaseModel):
    """UI contract for one speaking character in a live/debate turn."""
    worker_id: str
    display_name: str
    role: str
    role_label: str = ""
    portrait_url: str = ""
    voice_stack: str = "core_openai"
    voice_id: str = ""
    locale: str = "en-US"
    text_style: str = ""
    status: str = "idle"          # idle | thinking | tool_calling | speaking | spoke | failed
    thought_state: str = ""       # visible state label, never raw hidden CoT
    current_message: str = ""
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    diagrams: List[Dict[str, Any]] = Field(default_factory=list)
    handoff_to: str = ""
    turn_index: int = 0
    round_index: int = 0
    source: str = "simulation"
    framework: str = ""
    maf_client: str = ""


# ---------------------------------------------------------------------------
# Org blueprint: the dynamic digital workforce the OrgDesigner proposes for a
# specific company. This is the "what org structure + agents does this company
# need" reasoning step. Roles are the execution layer behind a human operator.
# ---------------------------------------------------------------------------

class OrgRole(BaseModel):
    """One seat in the company's dynamic org - usually a digital worker."""
    id: str
    title: str
    kind: str = "digital_worker"  # human | digital_worker | hybrid
    mandate: str = ""             # what this role is accountable for
    reports_to: Optional[str] = None  # parent role id (None == top of org)
    kpis: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    deployment_hint: str = ""     # which Foundry model class fits this worker
    lifecycle_stage: str = ""     # discovery|positioning|mvp|gtm|retention|ops
    seniority: str = "ic"         # lead | ic
    monthly_cost_usd: int = 0     # the worker's normal monthly wage (the burn)
    inference_usd: int = 0        # cheap compute to actually run it (efficiency)
    runs_on_model: str = ""       # cheap model this worker runs on
    human_median_usd: int = 0     # present-world wage for this seat (== cost)
    why: str = ""                 # educational: why this role must exist
    xp: int = 0
    level: int = 1


class OrgBlueprint(BaseModel):
    """The dynamic org an LLM designs for a company (from a pitch or a URL)."""
    company_summary: str = ""
    operating_model: str = ""     # how the human + digital workers split work
    roles: List[OrgRole] = Field(default_factory=list)
    # Derived stats (filled by the designer; power the simple game mechanic).
    headcount: int = 0
    digital_worker_count: int = 0
    human_count: int = 0
    monthly_burn_usd: int = 0      # the burn: real cost to RUN the digital workforce
    monthly_inference_usd: int = 0 # model inference + tooling behind that run cost
    monthly_human_equivalent_usd: int = 0  # what these seats would cost as humans
    monthly_savings_usd: int = 0   # human-equivalent minus the real run cost (headline)
    worker_model: str = ""         # cheap model the workforce runs on
    worker_price_in_per_m: float = 0.0   # USD / 1M input tokens
    worker_price_out_per_m: float = 0.0  # USD / 1M output tokens
    leverage_ratio: float = 0.0   # digital workers per human operator
    source: str = "pitch"         # pitch | url
    source_ref: str = ""          # the originating url or pitch text
    notes: List[str] = Field(default_factory=list)


class CompanyEconomics(BaseModel):
    """Durable operating metrics that CEO decisions can move.

    The UI renders the 0-100 pressure meters, while the actual org burn stays
    as dollars on OrgBlueprint. Keeping both in state lets later worker briefs
    cite the company that now exists, not only the original pitch.
    """
    proof: int = 24
    trust: int = 38
    velocity: int = 42
    burn_pressure: int = 12
    autonomy: int = 8
    monthly_burn_usd: int = 0
    runway_months: int = 9
    digital_worker_count: int = 0
    leverage_ratio: float = 0.0
    monthly_revenue_usd: int = 0
    net_profit_usd: int = 0
    points: int = 10000
    # Market share is the honest source of revenue: the company's percentage of
    # its addressable market. It is EARNED by shipping verified work and good
    # strategy, and CONTESTED by the antagonist (high rival threat suppresses
    # how much share each win captures, and a failed gate cedes share). Revenue
    # is derived from it (share% * addressable_market_usd), so "profitable" means
    # the workforce actually won and kept customers - never a seeded number.
    market_share: float = 0.0          # 0-100, percent of the addressable market
    addressable_market_usd: int = 0    # monthly addressable market the share is a slice of
    # Paying customers make the money concrete: revenue is no longer an abstract
    # slice of a market - it is N customers each paying ~arpu_usd/month. Both are
    # DERIVED from market share (customers = revenue / arpu), so winning share
    # wins customers, and the HUD can read "5.6% market = N customers = $X/mo".
    paying_customers: int = 0          # current paying customers (derived from revenue)
    arpu_usd: int = 0                  # average revenue per customer per month
    # Real-time payroll clock: the player pays the workforce its normal wages
    # over time. 1 real minute == 1 in-game day (GAME_MINUTES_PER_DAY), so the
    # treasury (points, in USD) drains by the daily wage each day. Running out
    # means payroll can't be met -> game over. This is what makes time a stake.
    treasury_started_usd: int = 10000  # starting cash, for runway %
    started_at_epoch: float = 0.0      # wall-clock when the run began
    last_tick_epoch: float = 0.0       # wall-clock of the last charge
    days_elapsed: float = 0.0          # in-game days that have passed
    daily_burn_usd: int = 0            # wages charged per in-game day
    runway_days: int = 0               # days of treasury left at current net
    # Forced contraction: an unprofitable company sheds its most expensive
    # worker over time (it cannot sustain the burn). The in-game day of the last
    # layoff rate-limits this so the workforce contracts gradually, not all at
    # once. Zero == no layoff yet.
    last_contraction_day: float = 0.0


# ---------------------------------------------------------------------------
# World graph: the richer structure produced by WorldDesigner.
# ---------------------------------------------------------------------------

class Stage(BaseModel):
    """A stage in the venture world graph — one beat of the Hero's Journey."""
    id: str
    title: str
    goal: str
    owner_role: str  # strategist | designer | marketer | ops (artifact archetype)
    success_metric: str = ""
    depends_on: List[str] = Field(default_factory=list)  # stage IDs
    suggested_tools: List[str] = Field(default_factory=list)
    status: str = "not-started"  # not-started, in-progress, completed, failed
    artifact: Optional[Dict[str, Any]] = None
    validation_score: Optional[int] = None
    # Living world graph: the original goal/metric the World Designer authored,
    # captured the first time a CEO decision adapts this (still-pending) stage.
    # Adaptation always recomposes from these, so re-adapting is idempotent and
    # never compounds. None until the stage is first adapted.
    base_goal: Optional[str] = None
    base_success_metric: Optional[str] = None
    # Rubric evaluation at the gate: weighted dimension breakdown produced by
    # the Foundry rubric evaluator (live) or derived deterministically from the
    # validators (simulation). The UI fills the gate bar from these dimensions.
    rubric: Optional[Dict[str, Any]] = None
    # Binding to the dynamically designed digital worker (OrgBlueprint role) that
    # owns this stage. Set by the Worker Factory's scheduler; closes the seam
    # between the org the LLM designs and the agents that do the work.
    assigned_worker_id: Optional[str] = None
    assigned_worker_title: Optional[str] = None
    # The CEO decision made at this stage's dilemma gate (game_design.md
    # section 5): {prompt, option (label picked), tradeoff, custom (bool)}.
    # Written by the dilemma endpoint; recalled in later stage briefs so
    # choices visibly chain (memory is what makes a choice feel real).
    dilemma_choice: Optional[Dict[str, Any]] = None
    # Optional agent-authored command form for the persistent CEO input. Kept as
    # JSON so the local-first UI can render it without React/build dependencies.
    form_schema: Optional[Dict[str, Any]] = None


class WorkerInvocation(BaseModel):
    """Record of a worker being spawned by the factory."""
    id: str
    stage_id: str
    role: str                 # archetype that drives prompt + validators
    worker_id: str = ""       # designed OrgRole id this invocation embodies
    worker_title: str = ""    # designed OrgRole title (shown in the story)
    deployment: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = "pending"  # pending, running, completed, failed
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0          # hidden "thinking" tokens the model spent
    reasoning_preview: str = ""        # short excerpt of chain-of-thought, if exposed
    # Tools the worker drew from the Toolbox for this stage (diegetic: the
    # rail names them before the artifact appears).
    tools_drawn: List[str] = Field(default_factory=list)
    # The actual tools/call ledger for this run - one entry per real call
    # through the toolbox (MCP shape): {tool, source, args, result, ms}.
    # This is the not-mocked receipt the UI renders as a terminal trace.
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    # Microsoft Agent Framework runtime evidence (empty on the direct path):
    # which framework ran the agent, which MAF chat client carried inference
    # (FoundryChatClient on the project Responses endpoint vs OpenAIChatClient
    # on the resource /openai/v1 path), what its ContextProvider injected as
    # session memory, and which FunctionTools the model actually called.
    framework: str = ""
    maf_client: str = ""
    # Why the preferred FoundryChatClient path degraded (e.g. 403 RBAC on the
    # project Responses endpoint) - empty when it carried the run or never ran.
    maf_fallback_reason: str = ""
    maf_memory: List[Dict[str, Any]] = Field(default_factory=list)
    maf_tools_called: List[str] = Field(default_factory=list)
    # Foundry IQ recall that grounded this run (source names; cited when the
    # real IQ knowledge base answered, local playbook files otherwise).
    iq_sources: List[str] = Field(default_factory=list)
    # Live current-events research (real web_search hits that grounded this
    # run): [{title, url, snippet, origin}]. Surfaced on the card-back receipts
    # and minted into reward cards so real-world signal enters gameplay.
    current_events: List[Dict[str, Any]] = Field(default_factory=list)
    latency_s: float = 0.0
    error: Optional[str] = None


class WorldGraph(BaseModel):
    """Full venture world produced by the WorldDesigner."""
    brief: str = ""
    stages: List[Stage] = Field(default_factory=list)
    invocations: List[WorkerInvocation] = Field(default_factory=list)
    current_stage_index: int = 0
    status: str = "not-started"  # not-started, active, completed
    # Session memory: every gate decision in order - {stage_id, stage_title,
    # option, tradeoff}. Worker briefs and narration recall from this ledger.
    decisions: List[Dict[str, Any]] = Field(default_factory=list)


class ChoiceRecord(BaseModel):
    """Typed CEO choice ledger entry.

    WorldGraph.decisions stays dict-shaped for existing prompt code; this model
    is the stable storage/search contract for roguelike choice state.
    """
    id: str
    day_index: int = 0
    stage_id: str
    stage_title: str = ""
    prompt: str = ""
    option_id: str = ""
    option: str = ""
    tradeoff: str = ""
    rule_id: str = ""
    scene_id: str = ""
    custom: bool = False
    consequence_summary: str = ""
    consequence: Dict[str, Any] = Field(default_factory=dict)


class WorldDay(BaseModel):
    """One playable day/room in the roguelike run.

    A day ties together the stage, the workers active in that room, the CEO
    choice made there, and the resulting resource snapshot.
    """
    day_index: int
    stage_id: str
    title: str = ""
    status: str = "active"  # active | completed
    worker_ids: List[str] = Field(default_factory=list)
    choice_id: str = ""
    resource_snapshot: Dict[str, Any] = Field(default_factory=dict)

class QuestStep(BaseModel):
    id: str
    title: str
    description: str
    assigned_to: str  # Agent role
    status: str = "not-started"  # not-started, in-progress, completed, failed
    artifact_type: str  # doc, url, email, etc.
    artifact_data: Optional[Dict[str, Any]] = None
    validation_results: Optional[Dict[str, Any]] = None
    xp_reward: int = 10

class QuestState(BaseModel):
    id: str
    title: str
    description: str
    status: str = "not-started"  # not-started, active, completed
    steps: List[QuestStep] = Field(default_factory=list)
    current_step_index: int = 0


class Dilemma(BaseModel):
    """A situational choice at a stage gate that moves the story forward.
    
    Based on the founder archetype, antagonist, and market dynamics, the dilemma
    presents a tradeoff: hiring a specialist (spend money, gain capability) vs
    upskilling the founder (save money, slow progress), etc.
    """
    id: str
    stage_id: str
    title: str  # e.g., "Hire or Train?"
    context: str  # Narrative framing that explains why this choice matters now
    antagonist_move: str  # What the antagonist did that created this dilemma
    option_a: Dict[str, Any]  # {label, description, economics_impact, story_impact}
    option_b: Dict[str, Any]  # {label, description, economics_impact, story_impact}
    tradeoff_axis: str  # e.g., "speed_vs_burn", "quality_vs_reach", "specialization_vs_flexibility"
    selected_option: Optional[str] = None  # "a" or "b" after player chooses


class CompanyState(BaseModel):
    name: str
    description: str
    pitch: str
    stage: str = "idea"  # idea, validated, launched
    # Stable id for this run, used to persist it as its own save slot so the
    # player can keep and resume multiple companies/products. Empty until a run
    # becomes real (world designed); assigned once and never reused.
    run_id: str = ""
    xp: int = 0
    level: int = 1
    founder: Optional[FounderState] = None
    founder_profile: Optional[FounderProfile] = None
    antagonist: Optional[AntagonistState] = None
    active_quest: Optional[QuestState] = None
    world: Optional[WorldGraph] = None
    org: Optional[OrgBlueprint] = None
    economics: CompanyEconomics = Field(default_factory=CompanyEconomics)
    # Canonical company dashboard model for the UI: product/service, customer,
    # business model, revenue model, ownership gaps, and antagonist provenance.
    # Refreshed by the API contract from Founder Analyst + Org Designer + World
    # Designer + live economics, so the footer does not infer durable business
    # facts ad hoc from scattered fields.
    venture_model: Dict[str, Any] = Field(default_factory=dict)
    knowledge_records: List[SearchDocument] = Field(default_factory=list)
    choices: List[ChoiceRecord] = Field(default_factory=list)
    days: List[WorldDay] = Field(default_factory=list)
    game: GameRunState = Field(default_factory=GameRunState)
    agents: Dict[str, CharacterState] = Field(default_factory=dict)
    business_flags: Dict[str, bool] = Field(default_factory=dict)
    streak: int = 0
    replay_log: List[Dict[str, Any]] = Field(default_factory=list)

class StateStore:
    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath
        self.state: Optional[CompanyState] = None
        self._lock = threading.RLock()

    def initialize_new_company(self, name: str, pitch: str, description: str = "", founder: Optional[FounderState] = None) -> CompanyState:
        with self._lock:
            self.state = CompanyState(
                name=name,
                description=description,
                pitch=pitch,
                founder=founder,
                agents={
                    "strategist": CharacterState(
                        name="Soren",
                        role="Strategist",
                        personality="Analytical, structured, lean startup advocate",
                        skills=["positioning", "icp", "market_sizing"]
                    ),
                    "designer": CharacterState(
                        name="Dahlia",
                        role="Designer",
                        personality="Visual, user-obsessed, detail-oriented",
                        skills=["landing_page", "ux_flows"]
                    ),
                    "marketer": CharacterState(
                        name="Maddox",
                        role="Marketer",
                        personality="Persuasive, conversion-driven, copywriter",
                        skills=["email_campaign", "copywriting"]
                    )
                }
            )
            self.save()
            return self.state

    def load(self) -> Optional[CompanyState]:
        if not self.filepath:
            return self.state
        with self._lock:
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.state = CompanyState(**data)
                    self._normalize_identity(persist=True)
                    return self.state
            except (FileNotFoundError, json.JSONDecodeError):
                return None

    @staticmethod
    def _clean_person_name(name: str) -> str:
        """Drop the id tail a profile slug carries (e.g. 'Jordan Rivera 9f8e' ->
        'Jordan Rivera'): a real name token never contains a digit. Returns the
        original when nothing clean remains, so we never blank out a name."""
        raw = (name or "").strip()
        if not raw:
            return raw
        kept = [t for t in raw.split() if not re.search(r"\d", t)]
        return " ".join(kept).strip() or raw

    @staticmethod
    def _drop_id_token(raw: str, sep: str) -> str:
        """Drop digit-bearing tokens from a `sep`-joined identity string,
        preserving the separator style (space for names, hyphen for URL slugs)."""
        kept = [t for t in raw.split(sep) if t and not re.search(r"\d", t)]
        return sep.join(kept).strip()

    def _identity_heal_pairs(self) -> List[tuple]:
        """Every dirty->clean identity string to substitute, derived from the
        ONE source of truth: the founder's name and profile handle. Covers the
        forms a profile slug's id tail leaks into - the display name
        ('Jordan Rivera 9f8e'), the lowercase brief text ('jordan rivera 9f8e'),
        and the URL slug ('jordan-rivera-9f8e') - so every generated field heals
        from the same seam. Only literal identity strings are listed, so numbers
        like '$220' or '100/100' are never touched."""
        state = self.state
        if not state:
            return []
        candidates = set()
        founder = getattr(state, "founder", None)
        if founder and founder.name:
            candidates.add(founder.name)
        profile = getattr(state, "founder_profile", None)
        if profile:
            if profile.person_name:
                candidates.add(profile.person_name)
            ref = (profile.source_ref or "").rstrip("/")
            handle = ref.split("/")[-1] if ref else ""
            if handle and re.search(r"\d", handle):
                # The URL handle ('jordan-rivera-9f8e') in both its slug and a
                # spaced form (how it surfaces in fallback prose).
                candidates.add(handle)
                candidates.add(handle.replace("-", " "))
        pairs: List[tuple] = []
        for raw in candidates:
            sep = "-" if ("-" in raw and " " not in raw) else " "
            clean = self._drop_id_token(raw, sep)
            if clean and clean != raw:
                pairs.append((raw, clean))
                # Generated prose is often lowercased; heal that variant too.
                if raw.lower() != raw:
                    pairs.append((raw.lower(), clean.lower()))
        # Longest dirty first so a shorter name can't partially match inside a
        # longer one before it is healed. De-duplicate.
        return sorted(set(pairs), key=lambda p: len(p[0]), reverse=True)

    def _normalize_identity(self, persist: bool = False) -> None:
        """Self-heal the founder identity at one seam so every run is dynamic,
        not legacy. The founder NAME is the single source of truth; once it is
        clean, every place that baked the name in at generation time (the run
        name, the villain's narrative, the venture model, world brief, knowledge
        records, replay log) is healed by substituting the exact dirty identity
        string for the clean one in a single whole-state pass. This never strips
        digits from arbitrary text - '$220', '100/100', 'rival 47/100' are
        untouched - because only literal identity strings are replaced. No
        per-run regeneration, no placeholder text."""
        state = self.state
        if not state:
            return
        pairs = self._identity_heal_pairs()
        if not pairs:
            return
        blob = json.dumps(state.model_dump())
        for dirty, clean in pairs:
            if dirty:
                blob = blob.replace(dirty, clean)
        try:
            self.state = CompanyState(**json.loads(blob))
        except Exception:
            # Heal failed to round-trip: at least clean the name fields directly
            # so the founder identity is never shown dirty.
            founder = getattr(state, "founder", None)
            profile = getattr(state, "founder_profile", None)
            if founder:
                founder.name = self._clean_person_name(founder.name)
            if profile:
                profile.person_name = self._clean_person_name(profile.person_name)
            return
        # A dirty name existed and was healed - persist once so the run is clean
        # at the source from now on (a one-time, idempotent rewrite).
        if persist and self.filepath:
            self.save()

    def save(self) -> None:
        if self.filepath and self.state:
            with self._lock:
                dirpath = os.path.dirname(os.path.abspath(self.filepath))
                os.makedirs(dirpath, exist_ok=True)

                payload = self.state.model_dump()
                self._scrub_pii(payload)
                self._atomic_write(self.filepath, payload)
                # Mirror the active run into its own save slot so multiple
                # companies/products persist and can be resumed. One seam: every
                # save writes both the live file and the slot, so a slot is never
                # stale relative to the active run.
                run_id = getattr(self.state, "run_id", "") or ""
                if run_id:
                    self._atomic_write(self._slot_path(run_id), payload)

    @staticmethod
    def _scrub_pii(payload: Dict[str, Any]) -> None:
        """Strip the raw profile/LinkedIn URL from durable state before it is
        written to disk. The URL is PII; it stays local-only in profile_cache.
        Durable state keeps the non-PII `profile_key` (which still links the
        founder's memories + Foundry IQ doc) and the derived character sheet, so
        a resumed run rehydrates fully without the URL ever touching the slot."""
        profile = payload.get("founder_profile")
        if not isinstance(profile, dict):
            return
        # Only scrub URL-sourced profiles; a pitch's source_ref is the pitch
        # text itself (not PII) and is needed for run naming/resume.
        if profile.get("source") != "url":
            return
        if profile.get("profile_key"):
            profile["source_ref"] = ""

    @staticmethod
    def _atomic_write(filepath: str, payload: Dict[str, Any]) -> None:
        """Atomically write a JSON payload to filepath (temp file + os.replace)."""
        dirpath = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(dirpath, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=dirpath, prefix="state_", suffix=".json.tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_path, filepath)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e

    # --- Multi-run save slots ------------------------------------------------
    # Each run is persisted as its own slot file next to state.json under a
    # `slots/` directory, keyed by CompanyState.run_id. The live state.json stays
    # the single working file the rest of the app reads; slots are the durable
    # library the player picks from. All slot I/O lives here (single source).

    def _slots_dir(self) -> str:
        base = os.path.dirname(os.path.abspath(self.filepath)) if self.filepath else os.getcwd()
        return os.path.join(base, "slots")

    def _slot_path(self, run_id: str) -> str:
        safe = "".join(c for c in str(run_id) if c.isalnum() or c in ("-", "_")) or "run"
        return os.path.join(self._slots_dir(), f"{safe}.json")

    def _slot_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Lightweight metadata for the slot picker - never the full state."""
        world = data.get("world") or {}
        stages = world.get("stages") or [] if isinstance(world, dict) else []
        done = sum(1 for s in stages if isinstance(s, dict) and s.get("status") == "completed")
        econ = data.get("economics") or {}
        game = data.get("game") or {}
        arc = (game.get("antagonist_arc") or {}) if isinstance(game, dict) else {}
        # Heal the run name from the same single source: clean the founder name
        # and substitute the exact dirty token, so the picker reads clean without
        # touching numbers in the name.
        name = data.get("name", "Untitled run")
        founder = data.get("founder") or {}
        profile = data.get("founder_profile") or {}
        for dirty in (founder.get("name") if isinstance(founder, dict) else "",
                      profile.get("person_name") if isinstance(profile, dict) else ""):
            clean = self._clean_person_name(dirty or "")
            if dirty and clean and clean != dirty and dirty in name:
                name = name.replace(dirty, clean)
        return {
            "run_id": data.get("run_id", ""),
            "name": name,
            "pitch": (data.get("pitch", "") or "")[:160],
            "stages_total": len(stages),
            "stages_done": done,
            "run_status": game.get("run_status", "active") if isinstance(game, dict) else "active",
            "threat_level": arc.get("threat_level", 0) if isinstance(arc, dict) else 0,
            "treasury_usd": int(econ.get("points", 0) or 0) if isinstance(econ, dict) else 0,
            "days_elapsed": float(econ.get("days_elapsed", 0) or 0) if isinstance(econ, dict) else 0,
            "updated_epoch": float(econ.get("last_tick_epoch", 0) or 0) if isinstance(econ, dict) else 0,
        }

    def list_slots(self) -> List[Dict[str, Any]]:
        """Return slot summaries, newest activity first."""
        slots_dir = self._slots_dir()
        summaries: List[Dict[str, Any]] = []
        if not os.path.isdir(slots_dir):
            return summaries
        for fname in os.listdir(slots_dir):
            if not fname.endswith(".json"):
                continue
            try:
                filepath = os.path.join(slots_dir, fname)
                with open(filepath, "r") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if not data.get("run_id"):
                data["run_id"] = fname[:-5]
            summary = self._slot_summary(data)
            if not summary.get("updated_epoch") or summary.get("updated_epoch") == 0.0:
                try:
                    summary["updated_epoch"] = os.path.getmtime(filepath)
                except Exception:
                    summary["updated_epoch"] = 0.0
            summaries.append(summary)
        summaries.sort(key=lambda s: s.get("updated_epoch", 0), reverse=True)
        return summaries

    def load_slot(self, run_id: str) -> Optional[CompanyState]:
        """Make a saved slot the active run: load it and mirror into state.json."""
        path = self._slot_path(run_id)
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        with self._lock:
            self.state = CompanyState(**data)
            if not self.state.run_id:
                self.state.run_id = run_id
            self._normalize_identity()
            self.save()
            return self.state

    def delete_slot(self, run_id: str) -> bool:
        """Remove a saved slot. If it is the active run, clear active too."""
        path = self._slot_path(run_id)
        removed = False
        with self._lock:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed = True
                except OSError:
                    removed = False
            if self.state and getattr(self.state, "run_id", "") == run_id:
                self.state = None
                if self.filepath and os.path.exists(self.filepath):
                    try:
                        os.remove(self.filepath)
                    except OSError:
                        pass
        return removed

    def log_event(self, event_type: str, actor: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            if self.state:
                self.state.replay_log.append({
                    "event_type": event_type,
                    "actor": actor,
                    "message": message,
                    "payload": payload or {}
                })
                self.save()
