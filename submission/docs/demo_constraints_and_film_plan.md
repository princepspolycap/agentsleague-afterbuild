# Demo Constraints + The One Film - reference sheet

Everything the demo must satisfy, in one place: competition rules, the
narrative spine, the setup checklist, and the plan for regenerating the
intro as ONE continuous film with Google Flow (Veo) clips whose audio and
visuals are designed together.

---

## 1. Competition constraints (from live_battle_challenge.md)

Hard requirements the judges check:

| Constraint | Where we satisfy it |
|---|---|
| Multi-agent RPG with a Game Master orchestrator | World Designer = GM; parameterized Workers = party |
| All reasoning agents on Microsoft Foundry | every reasoning call goes through Foundry deployments (model_config.py) |
| Game Master: narrates, routes, applies rules, updates state | world_designer.py + server loop + StateStore |
| Character agents: personality, abilities, tools | designed digital workers, per-role prompts + toolbox draws |
| Foundry IQ retrieval | agents/retrieval.py over knowledge/ (rail citations) |
| Code interpreter / deterministic tools | validators behind the Toolbox |
| Player choices with consequences | dilemma gates -> decisions ride into the next brief (MAF memory) |
| World/quest/character state | CompanyState / WorldGraph / OrgBlueprint |
| Forkable, MIT, runs after git clone | simulation fallbacks everywhere; no key required to play |
| Human-in-the-loop | verification gate; nothing counts until the seal |

Rubric weights: Accuracy 20 / Reasoning 20 / Reliability 20 /
Creativity 15 / UX 15 / Community 10. The UX 15% is what the full-screen
rework and the film serve directly.

## 2. The narrative spine (locked - do not fork it again)

One sentence: *you are invited into a story too big to command - terraform
the Sahara, automate basic needs - and the only instrument that scales is
a league of reasoning agents working as your digital workers; found one
company on one front, decide at every gate, and your experience becomes a
business that runs while you sleep.*

Beats (film -> game, one thread):

1. **Invitation** - "Welcome to your hero's journey." (sahara)
2. **The catch** - too big to command; chaotic social contracts (premise)
3. **The vow** - no belly hungry / no head unroofed / no back unclad / no
   soul enslaved (needs)
4. **The mechanism** - agency of digital workers; your skill becomes a
   business (workforce)
5. **The flywheel** - everyone gets paid fairly; consented work (flywheel)
6. **How it thinks** - reasoning on Foundry: IQ, code interpreter,
   orchestration (foundry)
7. **The law** - a human holds the seal (gate)
8. **The title** - "Your company is the dungeon" -> *choose your front* (title)
9. **Founding screen** (the game) - missions + archetype + pitch, World
   Designer visibly waiting
10. **The descent** - org -> world -> chapters with reasoning theater,
    dilemma gates, rubric-scored verification gates -> income beat.

The film's last spoken line cues the founding screen; the game's first
line answers it. That seam is load-bearing - never reintroduce a second
welcome.

## 3. Setup checklist (demo day)

- [ ] `submission/.env` filled (FOUNDRY_BASE_URL, key or `az login`,
      NARRATOR/STRATEGIST/DESIGNER/MARKETER/OPS/NPC models, TTS_*,
      IMAGE_*, DEMO_MODE=live)
- [ ] server: `.venv/bin/python -m uvicorn tools.server:app --port 8070
      --app-dir submission`
- [ ] `/api/mode` shows `live: true`; HUD chip green
- [ ] baked narration mp3s present (`lore/narration/*.mp3`)
- [ ] Veo clips present (`lore/video/*.mp4`, local-only)
- [ ] one full playthrough in simulation (pull the key) - everything still
      runs: this is the reliability story
- [ ] reset state before going on stage (`/api/reset`)
- [ ] browser at 100% zoom, full-screen window, audio unmuted
- [ ] fallback: if wifi dies, DEMO_MODE=simulation plays the whole game

## 4. The One Film - Gemini Omni regeneration plan

Model facts (researched June 10, 2026):

- **Gemini Omni** (announced I/O 2026, May 19; Omni Flash live in Flow for
  Pro subscribers): any-to-any - text/images/audio/video in, physics-aware
  video **with native audio** out, conversationally editable. ~10s per
  clip; SynthID watermarked; Omni Pro teased.
- **Veo 3.1 in Flow**: native audio now rides through *Extend*,
  *Frames-to-Video* and *Ingredients-to-Video* - so a continuous film with
  carried sound is exactly what Flow scenebuilder is for.

The decision: **stop layering**. No more separate baked mp3 + muted clip +
typed intertitle. The narration is written INTO each shot prompt as spoken
voice-over; Omni/Veo generates picture and voice together; shots are
chained with Extend so it cuts like one cinematic. League-of-Legends rule:
invoke, don't explain.

Script v2 (five scenes - "the catch" and "the seal" cards cut; the seal
is now one phrase inside "how it thinks"):

| # | scene | VO (spoken by the model, in-shot) | visual core |
|---|---|---|---|
| 1 | sahara | "Welcome to your hero's journey. You are to chart a path within a world that terraforms the Sahara desert and automates basic needs. At your disposal: a league of reasoning agents - your digital workers. The journey is ambitious. What it needs - is you." | aerial dawn over dunes, water threads lighting, push toward a green seam |
| 2 | needs | "A vision this size is never commanded into existence. It is aligned - by a vow. No belly goes hungry. No head goes without a roof. No back is unclad. And no soul is enslaved to survival." | one continuous pan: oven, water channel, solar field, lit shelter |
| 3 | workforce | "The mechanism is an agency of digital workers. Bind your real skill to a worker that executes, and your experience becomes a business that runs while you sleep - and everyone gets paid, fairly." | one human desk, constellation of worker avatars fanning open, threads pulsing |
| 4 | foundry | "Every agent here reasons on Microsoft Foundry - memory it can cite, checks it cannot fake, and one law above them all: nothing counts until you approve it." | descent into a luminous foundry-library; a hand seals a gate as one beat within the shot |
| 5 | title | "Found a company on one front of the mission. Take the CEO's chair. Clear it room by room with your workforce. Your company is the dungeon. Now - choose your front, and tell us what you bring." | pull back: the lit gate is the entrance of a dungeon-tower company under stars; hold |

Voice direction (append to every shot prompt): *"Narrator: a low, warm,
unhurried male storyteller speaking softly, close-mic, by firelight -
inviting, never announcing. Slow pace, natural pauses at dashes and
periods, near-whisper on the final line. Subtle cinematic score under the
voice, dusk-toned, swelling gently at scene ends. No other dialogue."*

Continuity rules (unchanged): one camera language (slow push/drift, dusk
palette - deep indigo + amber, matches the UI), each shot generated by
*extending* the previous or starting from its final frame, no text in
frame.

Fallback chain stays intact: the five re-baked narration mp3s
(gpt-4o-mini-tts) still ship committed and play over stills for any fork
without the clips - the Omni film is the premium layer on top
(`lore/video/<scene>.mp4`, local-only), and when a clip carries its own
voice the runtime should play the clip UNMUTED and skip the baked take
(intro.js change: prefer clip audio when present).

Production notes:

- Generate in the existing Flow project (PRO account) for style continuity
  with the established dark-navy/teal-gold geometric look - or pivot the
  whole film photoreal in a new project; pick ONE, never mix.
- ~2 generations per shot budget; do 1 and 5 first (anchors), then 2-4.
- Export 1080p landscape, name `<scene>.voiced.mp4` when the clip carries
  its own narration (preferred over the silent `<scene>.mp4`), drop into
  `submission/ui/assets/generated/lore/video/` - the intro auto-upgrades
  and plays it UNMUTED, skipping the baked take.

## 4a. Veo 3.1 / Omni craft reference (researched June 10, 2026)

Sources: Google Cloud "Ultimate prompting guide for Veo 3.1" (Oct 2025) +
LTX Veo 3.1 prompt guide. The rules that move quality the most:

**The five-part formula (front-loaded, in this order):**
`[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance] + [Audio]`
The model reads structure literally - what you name first gets the most
attention. Lead with the shot.

**Camera as its own sentence.** Write "The camera pushes in slowly" as a
standalone clause, never buried inside subject description. Veo knows
dolly / tracking / crane / aerial / pan / POV / push-in / pull-back - use
the real terms. One camera move per shot; more reads as chaos.

**Audio is prompted, not added.** Native audio rides the generation.
Structure it as a labelled block at the end:
- Dialogue / VO in **quotation marks**, preceded by a voice description
  ("a low, warm, unhurried male storyteller says, '...'"). Quoting the
  exact words is what makes the model speak them verbatim.
- `SFX:` for discrete sounds tied to a visual beat ("a soft chime as the
  seal lands").
- `Audio:` / `Score:` for the bed ("dusk-toned orchestral score swelling
  gently beneath the voice").
- Tie sound to action with timing words ("as the gate seals") to fix sync.

**Negatives stated positively.** "vast empty dunes with no people, no
text, no logos" beats "no man-made structures".

**Length 75-125 words.** Past ~175 the model starts dropping
instructions. One subject, one move, one payoff beat per shot.

**Continuity across the 5 shots** (so it cuts like one film):
- Repeat the exact style sentence verbatim in every prompt: *"Minimal
  flat geometric vector art, dark navy night, teal and gold light
  accents, no text, no logos."*
- Repeat the exact voice sentence verbatim so the narrator sounds like
  one person: *"a low, warm, unhurried male storyteller speaking softly,
  close-mic, by firelight - inviting, never announcing."*
- Use **last-frame -> next first-frame** (Frames-to-Video / Extend) so
  each shot begins where the previous ended; the dusk palette + slow
  push are the through-line.

**Shooting prompts (copy-paste into Flow; VO is verbatim from the table):**

1. **sahara** - "Aerial drone shot, slow continuous push forward over vast
   golden Sahara dunes at first light. Thin luminous teal water channels
   thread through the sand and soft green growth follows them toward a
   distant city of light on the horizon; the camera rises gently as the
   green seam widens. Minimal flat geometric vector art, dark navy dawn
   sky, teal and gold light accents, vast poetic scale, no people, no
   text, no logos. Audio: a low, warm, unhurried male storyteller speaking
   softly, close-mic, by firelight says, 'Welcome to your hero's journey.
   You are to chart a path within a world that terraforms the Sahara
   desert and automates basic needs. At your disposal: a league of
   reasoning agents - your digital workers. The journey is ambitious. What
   it needs - is you.' Dusk-toned orchestral score swelling gently beneath
   the voice."

2. **needs** - "Slow tracking shot drifting left to right across one
   continuous nocturnal landscape: a warm-lit oven, a flowing water
   channel, a field of solar panels, a softly glowing shelter, each
   igniting as the camera passes. Minimal flat geometric vector art, dark
   navy night, teal and gold light accents, calm and reverent, no people,
   no text, no logos. Audio: a low, warm, unhurried male storyteller
   speaking softly, close-mic, by firelight says slowly with long pauses,
   'A vision this size is never commanded into existence. It is aligned -
   by a vow. No belly goes hungry. No head goes without a roof. No back is
   unclad. And no soul is enslaved to survival.' Dusk-toned strings
   beneath the voice, swelling on the final line."

3. **workforce** - "Wide shot, slow push-in on a single human silhouette
   at one desk in deep, space-like darkness. Above them a constellation of
   glowing digital-worker avatars slowly fans open, each tethered to the
   human by a fine thread of light that pulses as work flows outward.
   Minimal flat geometric vector art, dark navy void, teal and gold light
   accents, intimate then expansive, no text, no logos. Audio: a low,
   warm, unhurried male storyteller speaking softly, close-mic, by
   firelight says, 'The mechanism is an agency of digital workers. Bind
   your real skill to a worker that executes, and your experience becomes
   a business that runs while you sleep - and everyone gets paid, fairly.'
   Soft pulsing ambient hum and dusk-toned score beneath the voice."

4. **foundry** - "Slow descent shot sinking into a vast luminous
   foundry-library, a reactor-core of pure reasoning, deep geometric
   machinery rotating slowly, orbited by small agent lights. Near the end
   a single human hand presses a glowing seal onto a monumental gate;
   rings of light ripple outward as patient agent silhouettes wait behind
   it. Minimal flat geometric vector art, dark navy, teal and gold light
   accents, awe and quiet power, no text, no logos. SFX: a soft resonant
   chime as the seal lands. Audio: a low, warm, unhurried male storyteller
   speaking softly, close-mic, by firelight says, 'Every agent here
   reasons on Microsoft Foundry - memory it can cite, checks it cannot
   fake, and one law above them all: nothing counts until you approve it.'
   Low resonant hum and dusk-toned score beneath the voice."

5. **title** - "Crane shot pulling back and rising: the lit gate is
   revealed as the entrance of a dungeon-tower company sinking deep into
   the earth, floors lit like circuit boards igniting one by one beneath a
   vast field of stars; a tiny founder silhouette stands at the threshold
   and the camera holds on the tower. Minimal flat geometric vector art,
   dark navy night, teal and gold light accents, monumental and inviting,
   no text, no logos. Audio: a low, warm, unhurried male storyteller
   speaking softly, close-mic, by firelight, slowing to near-whisper on
   the last line, says, 'Found a company on one front of the mission. Take
   the CEO's chair. Clear it room by room with your workforce. Your
   company is the dungeon. Now - choose your front, and tell us what you
   bring.' Dusk-toned score swelling, then settling to quiet."

## 5. Full-screen design (shipped with this commit)

The game now uses the film's screen language: the scene is the entire
viewport; header, footer, and the ops rail float above it as glass
overlays; the rail collapses (R / button) for pure-cinema moments and
returns for telemetry moments (reasoning theater, gates). One visual
world from first frame to income beat - no dashboard seam.
