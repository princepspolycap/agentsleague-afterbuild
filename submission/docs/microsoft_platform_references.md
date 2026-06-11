# Microsoft Platform References

Public source list and integration notes for the Agents League submission. Keep
private logistics, quota notes, deployment names, and outreach plans in
`submission/private/`.

## Agents League And Submission

| Topic | Link | How we use it |
|---|---|---|
| Agents League Hack @ AI Skills Fest | [Microsoft Reactor series](https://developer.microsoft.com/en-us/reactor/series/s-1658/) | Confirms the June 2026 hackathon framing, three tracks, live battles, Discord, GitHub submissions, Microsoft Foundry, M365, Copilot Studio, and IQ tools. |
| Agents League registration | [Hackathon registration](https://info.microsoft.com/Agents-League-Hackathon-Registration.html) | Registration/submission entry point. Some content may require Microsoft form access. |
| Agents League repository | [microsoft/agentsleague](https://github.com/microsoft/agentsleague) | Public contest repo, starter kits, issue templates, and disclaimer. |
| Creative Apps track | [starter kit](../../starter-kits/1-creative-apps/README.md) | GitHub Copilot/VS Code track. Useful for explaining the "creative app" side of the contest, but not our primary scoring path. |
| Reasoning Agents track | [starter kit](../../starter-kits/2-reasoning-agents/README.md) and [live battle spec](../../starter-kits/2-reasoning-agents/live_battle_challenge.md) | Primary source for this submission: multi-agent RPG, Microsoft Foundry, reasoning, tools, state, Foundry IQ, and evaluation rubric. |
| Enterprise Agents track | [starter kit](../../starter-kits/3-enterprise-agents/README.md) | Microsoft 365 Copilot/Copilot Studio path. Useful for a post-battle enterprise wrapper. |
| Disclaimer | [DISCLAIMER.md](../../DISCLAIMER.md) | Public repo hygiene: no confidential information, credentials, internal data, or proprietary details. |

## Microsoft Agent Stack

| Surface | Link | Role in this repo |
|---|---|---|
| Microsoft Agent Framework | [overview](https://learn.microsoft.com/en-us/agent-framework/overview/) | Python/.NET framework for agents and multi-agent workflows. Our workers use Agent Framework primitives when available. |
| Microsoft Agent Framework + Foundry provider | [Foundry provider docs](https://learn.microsoft.com/en-us/agent-framework/agents/providers/microsoft-foundry) | Preferred project-endpoint path for Foundry-backed workers. |
| Foundry IQ | [what is Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq) | Required grounding primitive for the Reasoning Agents track; local knowledge files remain the forkable fallback. |
| Foundry Toolbox | [toolbox docs](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox) | Optional managed toolbox/MCP surface. `TOOLBOX_URL` can route our local catalog through a managed Foundry Toolbox. |
| Foundry MCP tools | [MCP tool docs](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol) | External tool path for future hosted integrations. |
| Foundry evaluations | [portal evaluations](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluate-generative-ai-app?view=foundry&preserve-view=true) and [SDK/cloud evaluation](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/cloud-evaluation?view=foundry&tabs=python) | Recommended next layer after local smoke tests: task completion, groundedness, tool selection, tool success, safety, and trace evaluation. |
| Microsoft 365 Copilot agents | [agents overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agents-overview) | Explains declarative vs custom engine agents. Our current build maps to a custom-engine pattern. |
| Agent Builder in Microsoft 365 Copilot | [Agent Builder docs](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-build-agents) | Low-code declarative agent path; useful for a lightweight M365 wrapper, not the core Battle #2 runtime. |
| Microsoft Copilot Studio | [overview](https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-what-is-copilot-studio) | Low-code agent and workflow builder. Useful for an enterprise-facing version or follow-up demo. |
| Copilot Studio evaluations | [create test sets](https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-create) | If we publish a Copilot Studio wrapper, use its single-turn/multi-turn test sets and custom methods. |
| Microsoft 365 Agents Toolkit | [overview](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/overview-agents-toolkit) | Pro-code publishing path for Microsoft 365 Copilot/Teams agents. Not required for the Reasoning Agents battle. |
| Agent 365 | [overview](https://learn.microsoft.com/en-us/microsoft-agent-365/overview) | Nice-to-have governance/control-plane story: observe, secure, and govern registered agents. Likely requires Microsoft 365/admin sign-in and is post-battle unless a tenant is ready. |

## Dependency Set To Keep

These packages already match the Microsoft-facing story:

| Package | Why it stays |
|---|---|
| `agent-framework-core` | Agent abstraction, tools, context providers, sessions. |
| `agent-framework-openai` | OpenAI-compatible Foundry fallback path. |
| `agent-framework-foundry` | Foundry project endpoint and Foundry Agent Service provider path. |
| `azure-ai-projects` | Foundry project SDK surface for agents, indexes, and evaluations. |
| `azure-identity` | AAD auth through `DefaultAzureCredential`; avoids committing secrets. |
| `openai` | Compatible client for the Foundry `/openai/v1` path. |
| `fastapi` / `uvicorn` | Local demo server and browser UI API. |

## Evaluation Plan

Keep the local smoke tests as the first gate:

```bash
.venv/bin/python submission/tools/run_quest_simulation.py --pitch "Your idea"
.venv/bin/python submission/tools/demo_smoke_test.py --base http://127.0.0.1:8050
```

Then add a judge-facing eval layer:

1. Local rubric eval over 5-10 founder pitches.
2. Foundry evaluation over either full conversations, individual turns, or traces.
3. Copilot Studio evals only if we publish a Copilot Studio wrapper.

## Agent 365 Handling

Agent 365 is not needed to satisfy Battle #2. Treat it as a late-stage enterprise
governance hook:

1. Keep the current game and Foundry evidence path primary.
2. If a Microsoft 365 tenant and Agent 365 access are available, register the
   hosted or M365 wrapper agent so it appears in inventory.
3. Use Agent 365 only for the governance story: identity, lifecycle,
   observability, access, and policy.
4. Do not block the public submission on Agent 365 login or tenant availability.

## Public Hygiene

Before pushing:

1. `git status --ignored` should show `.env`, `submission/private/`, generated
   state, local assets, and cache files ignored.
2. No deployment names, quota notes, personal planning, prep-call links, or
   private URLs should appear outside `submission/private/`.
3. Public docs should cite Microsoft docs and repo files, not private notes.
