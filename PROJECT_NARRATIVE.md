# Project Narrative - Your Company Is the Dungeon

Public narrative for the Microsoft Agents League Battle #2 submission. Internal
demo logistics and outreach planning live under the ignored `submission/private/`
folder.

## One-Sentence Pitch

**Your Company Is the Dungeon** is a side-scrolling, multi-agent reasoning game
where a player pitches a business idea, a Microsoft Foundry-powered Game Master
decomposes it into a quest line, and specialist worker agents produce real
artifacts that the player must verify before XP is awarded.

The player decides. The agents execute. The human verifies.

## Challenge Fit

The Battle #2 prompt asks for a role-play game adventure powered by reasoning
agents. This project keeps that shape and changes the domain:

| Challenge concept | This submission |
|---|---|
| Game Master agent | Org Designer + World Designer |
| Character agents | Strategy, product, growth, and operations workers |
| Campaign lore | Business-launch playbooks through Foundry IQ/local fallback |
| Dice rolls and checks | Deterministic artifact validators |
| Shared world state | Company, quest, world, memory, and replay state |
| Human decisions | Verification gates before XP or progress |

The result is still a role-play game, but the dungeon is the company the player
is building.

## Current Loop

1. The player enters a business pitch or company URL.
2. The Org Designer creates a digital workforce for that venture.
3. The World Designer decomposes the venture into chapters.
4. Each worker recalls knowledge, receives memory, uses tools, and produces an
   artifact.
5. Validators score the artifact.
6. The player approves or rejects the gate.
7. Approved gates write memory and unlock the next chapter.

## Official Battle #2 Rubric

The live-battle rubric in
[`starter-kits/2-reasoning-agents/live_battle_challenge.md`](starter-kits/2-reasoning-agents/live_battle_challenge.md)
uses these weights:

| Criterion | Weight |
|---|---:|
| Accuracy and Relevance | 25% |
| Reasoning and Multi-step Thinking | 25% |
| Reliability and Safety | 20% |
| Creativity and Originality | 15% |
| User Experience and Presentation | 15% |

Detailed mapping is in
[`submission/docs/rubric_mapping.md`](submission/docs/rubric_mapping.md).

## Microsoft Platform Links

The public source list for Microsoft platform pieces, evaluation options,
submission process, and optional Agent 365 governance is maintained in
[`submission/docs/microsoft_platform_references.md`](submission/docs/microsoft_platform_references.md).

## Running Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r submission/requirements.txt

python3 submission/tools/run_quest_simulation.py --pitch "Your idea"
```

No Azure credentials are required for simulation mode. A configured
`submission/.env` switches the same code paths toward live Microsoft Foundry
deployments.
