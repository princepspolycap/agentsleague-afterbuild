# Challenge Canvas & the Narrator-Director

How the story moves forward, who paints the center canvas, and how we turn each
chapter into a real *challenge* told through cards, images, Mermaid diagrams,
and narration. This is the part that matters: walking the player through a world.

---

## 1. Who moves the story forward

There are two layers. Keep them separate in your head.

### The author (build-time, once per run)

- **World Designer / Master Narrator** ([agents/world_designer.py](../agents/world_designer.py),
  [agents/foundry_agents.py](../agents/foundry_agents.py#L222)) runs **once** at
  `/api/world/design`. It decomposes the mission into an 8-stage `WorldGraph`
  (Dan Harmon's Story Circle). Each stage carries `title`, `goal`,
  `success_metric`, `owner_role`, `suggested_tools`, `depends_on`.
- This is the **script**. It never touches the screen directly.

### The director (run-time, once per chapter)

- The **Story Controller** in [ui/game/story.js](../ui/game/story.js) is the
  thing actually moving the story forward on screen. The key function is
  `runNextChapter()` ([story.js](../ui/game/story.js#L2702)). It is the
  director: it reads the next stage, paints the canvas, briefs the worker, calls
  `/api/world/run-next`, then renders the result.
- The **Worker Factory** ([agents/worker_factory.py](../agents/worker_factory.py))
  is the backend half of the director: it picks the right Foundry deployment for
  the stage's `owner_role`, runs the worker, validates the artifact, and returns
  the invocation evidence.

> **One-liner:** The World Designer writes the script; the Story Controller is
> the director that stages each scene; the workers are the actors. The canvas
> (`#diagram`) is the stage they all perform on.

---

## 2. The canvas today

`#diagram` is the center stage. Today the director paints it with exactly three
kinds of content, in this order, per chapter:

| Phase | Renderer | What shows |
|---|---|---|
| Brief | `renderScenarioCanvas(ch, ownerName)` ([story.js](../ui/game/story.js#L518)) | A **scenario card**: chapter title, goal, success metric, toolbox, owner portrait. This is the challenge framing. |
| Think | `theaterOpen` / `theaterReveal` | Reasoning theater overlay: the model's chain-of-thought + thinking tokens. |
| Payoff | `renderMermaid(def)` / `renderSvg(svg)` ([story.js](../ui/game/story.js#L289)) | The worker's artifact as a **Mermaid diagram or SVG chart** (`diagramForArtifact`). |

So we already have **card + diagram + chart + narration**. What's missing for
"walking the player through a world" is: **images**, a **first-class challenge
model**, and a **single render contract** so the narrator can push any of these
on demand instead of the four hardcoded shapes.

---

## 3. The Scene render contract (the thing to build)

Right now the director hardcodes "card, then theater, then diagram". We want the
**narrator/worker to emit a typed list of scene beats** that the canvas knows how
to render. One contract, many renderers. This is the SOLID seam.

```jsonc
// returned per chapter alongside the artifact (or streamed)
"scene": [
  { "type": "card",    "card": { "kicker": "...", "title": "...", "rows": [["Goal","..."]] } },
  { "type": "image",   "src": "/game/assets/...", "caption": "...", "alt": "..." },
  { "type": "mermaid", "def": "graph TD; A-->B" },
  { "type": "chart",   "svg": "<svg>...</svg>" },
  { "type": "narrate", "text": "...", "voice": "strategist" }
]
```

Front-end: one dispatcher `renderScene(beat)` that switches on `beat.type` and
calls the existing renderers. We already have `renderMermaid`, `renderSvg`,
`renderScenarioCanvas`, `narrate` — wrap them behind this dispatcher and add one
new renderer, `renderImage`. Net new code is small; mostly it's routing.

### Renderers needed

- `card` -> generalize `renderScenarioCanvas` to take a card payload (not just a
  chapter). Same DOM, data-driven rows.
- `image` -> **new.** `renderImage({src, caption, alt})` into `#diagram` with the
  same `world-canvas fade-scene` wrapper so transitions match. Source priority:
  pre-generated stage art in `ui/game/assets/generated/`, then a generated image
  endpoint (Foundry image deployment, behind a simulation fallback that picks a
  themed placeholder so a fresh `git clone` still looks right).
- `mermaid` / `chart` -> existing, no change.
- `narrate` -> existing.

---

## 4. The challenge model (worker vs. challenge, and how it's won)

Each chapter is a **challenge**, not just a task. A challenge has stakes, a foil,
and a win condition the player can feel. Define it on the stage:

```jsonc
{
  "id": "stage_3_go",
  "title": "GO: Crossing into the Owned World Commons",
  "owner_role": "strategist",
  "goal": "...",
  "success_metric": "...",
  // NEW challenge fields:
  "challenge": {
    "antagonist": "The Attention Cartel",          // from antagonist_generator
    "stakes": "If the wedge is fuzzy, the launch dissolves into the feed.",
    "win_condition": "validation_score >= 70 AND artifact has 1 wedge + 1 anti-villain promise",
    "art_prompt": "a lone founder planting a flag on an owned hill above a sea of platform logos",
    "beats": ["card", "image", "narrate", "mermaid"]   // the scene script for this challenge
  }
}
```

### How a challenge is won (the loop, already mostly here)

1. **Frame** — director paints the challenge card + antagonist + stakes image.
2. **Reason** — worker runs on Foundry; theater shows the chain-of-thought.
3. **Produce** — worker returns a JSON artifact.
4. **Validate** — `code_interpreter_wrappers` validators score it
   ([tools/code_interpreter_wrappers.py](../tools/code_interpreter_wrappers.py)).
   The `validation_score` vs. `win_condition` is the win/lose.
5. **Verify (human gate)** — the player approves at a verification gate. XP /
   resources move (`nudgeResources`). This is the reliability story.
6. **Render payoff** — diagram/chart of the artifact lands on the canvas; the
   antagonist is shown weakened or the world map advances.

The win is **earned visually**: low score => the antagonist art stays dominant
and narration is tense; high score + gate-approve => the world art advances and
the company graph grows a node (`completedStages` / `companyGraphDef`).

---

## 5. Where images come from

Order of preference (Foundry-first, always runnable):

1. **Pre-generated stage art** committed under `ui/game/assets/generated/`
   (already the pattern for character portraits). Deterministic, zero-cost, ships
   in the repo. Best for the demo.
2. **Foundry image deployment** (live mode only) driven by `challenge.art_prompt`,
   cached to disk so a stage's art is stable across replays.
3. **Themed placeholder** keyed by `owner_role` color when neither is available,
   so simulation mode after a clean clone still renders a coherent stage.

Never block the loop on image generation — render the card immediately, swap the
image in when ready (same pattern as narration racing speech).

---

## 6. Implementation plan (small, in-place, refactor-first)

Ordered so each step is shippable on its own.

1. **Extract the dispatcher.** Add `renderScene(beat)` in `story.js` that routes
   to the existing renderers. Refactor `runNextChapter` to drive the canvas
   through it instead of calling renderers directly. *No behavior change yet.*
2. **Generalize the card.** Make `renderScenarioCanvas` consume a `card` payload
   so the narrator can push arbitrary cards, not only the chapter brief.
3. **Add `renderImage`.** New renderer + the 3-tier image source resolver above.
   Ship with committed placeholder art so it works offline immediately.
4. **Add `challenge` to the stage schema** ([state/schema.py](../state/schema.py))
   and have the World Designer populate `antagonist`, `stakes`, `win_condition`,
   `art_prompt`, `beats`. Keep a simulation fallback that fills these
   deterministically from the existing antagonist generator.
5. **Drive the scene from `challenge.beats`.** The director plays the beat list
   through `renderScene`, falling back to today's hardcoded order when absent.
6. **Wire the win condition** into resource nudges + the verification gate copy so
   beating a challenge reads as beating the antagonist.

Each step keeps the simulation path green (run
`python3 submission/tools/run_quest_simulation.py`) and the JS check clean
(`node --check submission/ui/game/story.js`).

---

## 7. Definition of done

- The narrator can push a **card, an image, a Mermaid diagram, an SVG chart, and
  narration** onto the canvas through one `renderScene` contract.
- Every chapter reads as a **challenge** with a named antagonist, visible stakes,
  and a win condition tied to the validator score + human gate.
- Winning a challenge **advances the world visually** (art + company graph) and
  losing keeps the antagonist dominant — the storytelling is in the images and
  narration, not in prose dumps.
- Still runs after a fresh `git clone` in simulation mode with committed art.
