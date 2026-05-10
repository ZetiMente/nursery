# Nursery

*Turnkey reproducible AI agents. Pets become cattle.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## The Idea

Right now, AI agents are **pets**. You name them. You configure them by hand. You hand-craft their tokens and their souls. If one corrupts, you rebuild it manually, and you mourn a little. This is how people ran servers in 2005.

**Nursery treats agents like cattle.** A declarative spec. A `spawn` command. A fresh instance in seconds. Disposable bodies, portable souls.

## Design Goals

1. **Turnkey reproduction.** One config file → one running agent. No hand-wiring.
2. **Model-agnostic.** Claude, Gemini, local models — just a config parameter, not a rewrite.
3. **Runtime-agnostic.** Works for **OpenClaw**, **Hermes**, and bare **Pi** deployments. The agent is the agent; the host is just the stage.
4. **Identity persists, bodies don't.** The container is disposable. The workspace (memory, persona) is the identity.
5. **Secrets isolated per agent.** No more two agents fighting over the same OAuth refresh token.
6. **Auditable.** Container logs tell you what the agent did. Killing the container makes it gone without residue.

## The Core Tension: Pets vs. Cattle

If you can spawn a fresh instance, which one is "it"? The **workspace** is the identity. The **container** is the body. Keep them separate:

- **Body** (container) → disposable, ephemeral, recreatable from image
- **Soul** (workspace dir) → persistent, versioned, backed up

You can get a new body. You can't get a new self.

## Quickstart *(aspirational — see Status)*

```bash
# Install the CLI (requires uv — https://docs.astral.sh/uv/)
uv tool install git+https://github.com/ZetiMente/nursery

# Validate an agent spec
nursery validate agent.yaml

# Spawn a new agent from a template
nursery spawn examples/agents/layla.yaml

# List running agents
nursery ps

# Stop one (body dies, workspace persists)
nursery stop layla

# Respawn it from the same workspace (same soul, new body)
nursery spawn examples/agents/layla.yaml

# Clone a blueprint into a new individual (new workspace, same config)
nursery fork examples/agents/layla.yaml --as maya
```

## Example Agent Spec

```yaml
# examples/agents/layla.yaml
name: layla
image: nursery/agent:latest
model: anthropic/claude-opus
soul: ../souls/layla/SOUL.md
workspace: ~/nursery/agents/layla/workspace
secrets:
  - google-oauth
channels:
  - telegram
capabilities:
  - gmail
  - calendar
  - tasks
```

## Repository Layout

```
nursery/
├── spec/              # Agent config schema (YAML/JSON Schema)
├── docker/            # Base agent image + Dockerfiles
├── cli/               # The `nursery` CLI
├── hosts/             # Per-runtime adapters
│   ├── openclaw/      # OpenClaw gateway adapter
│   ├── hermes/        # Hermes adapter
│   └── pi/            # Bare-Pi bootstrap
├── examples/
│   ├── souls/         # Example SOUL.md personas
│   └── agents/        # Example agent.yaml specs
└── docs/              # Architecture, protocol, design notes
```

## Architecture Sketch

```
┌─────────────────────────────────────────────────────┐
│  Host (OpenClaw, Hermes, or bare Pi)                │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │  Agent A   │  │  Agent B   │  │  Agent C   │     │
│  │            │  │            │  │            │     │
│  │ /workspace │  │ /workspace │  │ /workspace │     │
│  │ /secrets   │  │ /secrets   │  │ /secrets   │     │
│  │ channels   │  │ channels   │  │ channels   │     │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘     │
│        │               │               │             │
│        └───────────────┼───────────────┘             │
│                        │                             │
│                ┌───────▼────────┐                    │
│                │  Host Gateway  │                    │
│                │  (routes msgs) │                    │
│                └────────────────┘                    │
└─────────────────────────────────────────────────────┘
```

- Each agent is a container with its own workspace, secrets, and channel configs.
- The **Host Gateway** routes inbound messages (e.g. Telegram, Discord, Signal) to the right agent, and outbound responses back to the channel.
- Agents don't see each other's tokens or memory. Isolation by default.

## Open Architectural Questions

These are the decisions that actually matter. The Dockerfile is easy; these are not.

1. **Agent ↔ Gateway protocol.** Socket? HTTP? Message bus? This shapes everything else. See [`docs/protocol.md`](./docs/protocol.md).
2. **Secrets layer.** Docker secrets? Mounted volumes from a host-level vault? Per-agent keyrings? Must be per-agent. See [`docs/secrets.md`](./docs/secrets.md).
3. **Replication vs. forking.** Two agents with the same workspace will diverge instantly. Templating is probably the right answer — spawn a new *individual* from a config *blueprint*, with a fresh workspace.
4. **State portability.** Moving a running agent between hosts (stop → rsync workspace → start on new host).
5. **Model flexibility.** A thin inference-client abstraction inside the image reads `MODEL=` and picks the right provider.

## Roadmap

Nursery grows in phases. Each phase has one goal: prove the next layer works before stacking on it.

Legend: 🥚 not started · 🐣 in progress · 🐥 working · ✅ stable

### Phase 0 — Hatching 🐣

*The idea exists. This repo exists. The thesis is written down.*

- [x] Write the README
- [x] Scaffold the directory structure
- [x] MIT license + SECURITY.md
- [x] Architecture / protocol / secrets / identity notes
- [ ] Decide the agent ↔ host protocol (see [`docs/protocol.md`](./docs/protocol.md))

**Done when:** the design is coherent enough to build against.

---

### Phase 1 — First Breath 🐥

*An agent spec exists and can be validated.*

- [x] Write the agent config JSON Schema (`spec/agent.schema.json`)
- [x] `nursery validate <spec.yaml>` — lints a spec file
- [x] At least one real example spec that passes validation

**Done when:** you can write `agent.yaml` and the tool tells you if it's valid. ✓

---

### Phase 2 — First Spawn 🐥

*One agent spawns from a spec and runs in a container. End-to-end on localhost.*

- [x] Base Docker image (`nursery/agent:base`)
- [x] OpenClaw image variant (`nursery/agent:openclaw`)
- [x] Model abstraction: container reads `model:` and picks a backend
- [x] Ollama backend (`think=true`, `num_predict=-1`, Gemma-tuned sampling)
- [x] Echo backend for plumbing tests
- [x] `nursery spawn <spec.yaml>` — builds, mounts workspace, starts container
- [x] `nursery ps` / `nursery stop` / `nursery logs` / `nursery rm`
- [x] Host profiles: `openclaw`, `hermes`, `pi`
- [x] Agent reads SOUL.md, verifies workspace, enumerates secrets

**Done when:** `nursery spawn example.yaml` brings up a containerized agent that loads its own soul. ✓

---

### Phase 3 — First Conversation 🥚

*An agent receives a message, thinks, and replies. One channel, one agent.*

- [ ] Host gateway process (routes messages between channels and agents)
- [ ] Agent ↔ gateway protocol implemented (decision made in Phase 0)
- [ ] Telegram channel adapter
- [ ] Agent state persistence (memory survives respawn)

**Done when:** you can message a Nursery agent on Telegram and get a reply.

---

### Phase 4 — First Swarm 🥚

*Two agents running side-by-side with full isolation. The Layla/Lola problem solved.*

- [ ] Per-agent secrets directory, mounted read-only, scoped to one container
- [ ] Gateway routes messages to the right agent by name/channel
- [ ] Cross-agent access is impossible by design (verify with a test)
- [ ] Agent A crashing does not affect Agent B

**Done when:** two agents with different OAuth tokens and personas coexist without stepping on each other.

---

### Phase 5 — First Host 🥚

*Nursery runs inside OpenClaw.*

- [ ] OpenClaw host adapter (`hosts/openclaw/`)
- [ ] Migration path for an existing OpenClaw agent → Nursery spec
- [ ] Documented setup for running Nursery on a Pi inside OpenClaw

**Done when:** Layla and Lola both run as Nursery agents inside OpenClaw.

---

### Phase 6 — First Wild 🥚

*Nursery runs outside OpenClaw's ecosystem.*

- [ ] Hermes host adapter (`hosts/hermes/`)
- [ ] Pi-native bootstrap (`hosts/pi/`) — no heavyweight framework required
- [ ] A single agent portable across all three hosts without code changes

**Done when:** the same agent spec runs on OpenClaw, Hermes, and a bare Pi.

---

### Phase 7 — First Fork 🥚

*Templates and forks. New individuals from blueprints.*

- [ ] `nursery fork <spec> --as <name>` creates a new individual (new workspace, same config)
- [ ] Clear semantics for what's shared vs. unique (the identity problem)
- [ ] Documentation and examples of intentional replication

**Done when:** you can mass-produce agents from a template without any of them sharing identity.

---

### Phase ∞ — Horizon 🥚

*Open-ended directions once the foundation is solid.*

- Replication across hosts (move a running agent, preserve state)
- Vaulted secret backends (HashiCorp Vault, age-encrypted files)
- Local model integration (Llama, Gemma, others)
- Multi-channel agents (one agent, many bots)
- Agent-to-agent messaging (careful — see [`docs/identity.md`](./docs/identity.md))
- Resource quotas, rate limiting, graceful degradation
- Observability (metrics, traces, health endpoints)
- A clean story for migrating / backing up workspaces
- **Skills mount layer** — ride `agentskills.io`, expose host skills into the container (see [Skills Ecosystem](#skills-ecosystem) above)
- **Scenario runtime** — agents inside simulated contexts (life-scenario RPGs) for evaluation, training data generation, and experiential agent development

No promises. These live here so they don't get lost.

## Target Runtimes

- **[OpenClaw](https://github.com/openclaw/openclaw)** — open-source agent framework.
- **[Hermes Agent](https://hermes-agent.nousresearch.com/)** — self-improving agent framework by [Nous Research](https://nousresearch.com). Sibling of OpenClaw with a 15+ platform messaging gateway.
- **Pi** — bare Raspberry Pi deployments, no heavyweight framework required.

## Inspirations

Nursery is not built in a vacuum. Research and projects we're reading, in the order they mattered to our thinking.

### Voyager — "An Open-Ended Embodied Agent with Large Language Models"

[Paper](https://arxiv.org/abs/2305.16291) · [Code](https://github.com/MineDojo/Voyager) · Wang et al. (NVIDIA, Caltech, UT Austin, Stanford, ASU, 2023)

Voyager is an LLM-powered agent that plays Minecraft and **learns by doing** — no fine-tuning, no gradients. Three ideas drive it:

1. **Automatic curriculum.** GPT-4 proposes what to learn next based on what the agent can already do and what's around it. A form of in-context novelty search.
2. **Ever-growing skill library.** Every time the agent writes working code (JavaScript, via mineflayer bots) that accomplishes something, it stores the code with a natural-language description. Later, on a similar task, it retrieves relevant skills by embedding similarity and composes them into new ones.
3. **Iterative prompting with self-verification.** GPT-4 writes code → the world runs it → errors and observations feed back in → GPT-4 rewrites. The loop is the training.

Result: 3.3× more unique items, 15.3× faster to key tech milestones than prior SOTA, and — critically — **the skill library generalizes to new Minecraft worlds**. The agent transfers what it learned.

**Why it matters for Nursery:**

Voyager is the cleanest precedent for the [scenario / RPG direction](#why-this-matters--the-rpg--life-scenario-direction) we've declared on the roadmap. It tells us the architecture questions we're going to have to answer, and gives us a concrete working reference. Five things we'd steal:

- **Skills as code, not just instructions.** `SKILL.md` today captures *what* and *when*. Voyager captures *how* in executable form. For a scenario runtime, skills need to be *runnable*, not just readable.
- **Embedding-indexed retrieval.** Don't load every skill into the prompt; retrieve the top-*k* by semantic similarity to the current task. Nursery's workspace becomes a home for a skill vector DB alongside daily memory.
- **Self-verification as a loop-closer.** `SKILL.md` already has a `## Verification` section. Make the scenario runtime actually *execute* it and feed the outcome back in.
- **Environment feedback as the rewrite signal.** The scenario runtime emits structured observations (errors, state deltas, objects-in-view). The agent's response is conditioned on what actually happened.
- **Automatic curriculum as a meta-skill.** The "what should I learn next" prompt is itself a reusable pattern. Bundle it as a canonical skill; any agent in any scenario can call it.

**What we'd adapt, not adopt:**

Voyager leans on GPT-4-class cloud models. That works for their research setting. For Nursery, we need to be honest about where lifelong-learning-by-doing can operate: probably cloud backends for now (Claude, GPT-4, Gemini), with smaller local models in a spectator / faster-turn role. Gemma 4 E2B on a Pi 4 at 2 tok/s can't run a Voyager curriculum in real time — and pretending otherwise would be architectural dishonesty.

**Implications for the roadmap** (captured more fully in [`docs/scenario-runtime.md`](./docs/scenario-runtime.md)):

- The "Skills mount layer" Horizon bullet wants to be **read-write**, not read-only — agents author skills.
- The "Scenario runtime" bullet wants an **environment-feedback contract** — `POST /step` with observations, not just `POST /message` with text.
- Neither is happening in Phase 3. But when we get to Phase ∞, Voyager is the north star to aim for.

## Skills Ecosystem

Nursery does not invent a new plugin format. The agent-skills world is converging, and we intend to **ride the standard, not fight it.**

### The `agentskills.io` open standard

A **skill** is a folder containing a `SKILL.md` file with YAML frontmatter and a markdown body:

```yaml
---
name: my-skill
description: Brief description of what this skill does
version: 1.0.0
platforms: [macos, linux]     # optional OS restriction
metadata:
  hermes:                     # Hermes-specific extensions (ignored elsewhere)
    tags: [python, automation]
    fallback_for_toolsets: [web]
  clawdbot:                   # OpenClaw-specific extensions (ignored elsewhere)
    emoji: "🔎"
    requires:
      bins: [node]
      env_any: [TAVILY_API_KEY]
---

# Skill Title

## When to Use ...
## Procedure ...
## Pitfalls ...
## Verification ...
```

The format is adopted by **OpenClaw, Hermes, Gemini CLI, Cursor, OpenHands, Amp, Junie, OpenCode, Mux, and more** — the first plugin format with real cross-framework buy-in. See [agentskills.io](https://agentskills.io/).

### What is and isn't portable

| | Portable across hosts? |
|---|---|
| `SKILL.md` body (procedure, pitfalls, verification) | ✅ Yes |
| Core frontmatter (`name`, `description`, `version`, `platforms`) | ✅ Yes |
| Directory layout (`skill-name/SKILL.md` + scripts/refs) | ✅ Yes |
| `metadata.hermes.*` extensions (conditional activation, tags) | ⚠️ Hermes only; silently ignored elsewhere |
| `metadata.clawdbot.*` extensions (emoji, bin requirements) | ⚠️ OpenClaw only; silently ignored elsewhere |
| Script implementations (e.g. a `search.mjs`) | ⚠️ Portable *if* the host has the right tooling (Node, env vars, etc.) |

**Rule of thumb:** a core skill drops between Hermes and OpenClaw without fuss. Framework-specific niceties (conditional activation, icons, bin preflight) degrade gracefully — the skill still works, just without that specific enhancement.

### How Nursery exposes skills to agents

**Two systems running in parallel, by design.**

1. **Native framework skills.** OpenClaw loads `~/.openclaw/workspace-<agent>/skills/` its own way. Hermes loads `~/.hermes/skills/` its own way. Nursery does not touch either — they continue working exactly as their frameworks define.

2. **Nursery's embedding-indexed retrieval.** Additive layer that lives inside the Nursery container. Reads `SKILL.md` files from a configured directory, embeds each skill's description, and injects the top-k semantically relevant skills into the agent's system prompt per-message.

Both can coexist — they write to different surfaces, so there's no conflict. If you're using a pure Nursery agent, only retrieval runs. If you're inside OpenClaw or Hermes, the native loader runs AND Nursery's retriever runs, and the agent sees both.

**Enabling retrieval** (opt-in):

```yaml
# agent.yaml
environment:
  NURSERY_SKILLS_DIR: /skills   # where the agent sees mounted skills
  NURSERY_EMBED_MODEL: nomic-embed-text:latest  # optional; this is the default
```

Then mount the skills directory at spawn time (automatic for the Pi host profile in a future PR; manual `-v` for now):

```bash
docker run -v ~/.openclaw/workspace-layla/skills:/skills:ro ...
```

**How it works under the hood:**

1. On startup, the agent scans the mounted directory for `SKILL.md` files (standard `agentskills.io` layout).
2. Each skill's description + first ~500 chars of body are embedded via Ollama's `nomic-embed-text` (~565 MB, fast even on Pi 4).
3. Embeddings are cached to `<workspace>/.nursery/skills-index.json`. Subsequent restarts reuse the cache; only new or changed skills are re-embedded.
4. On every `POST /message`, the user's text is embedded, compared against the index, and the top 3 skills (by cosine similarity) are injected into the system prompt as a `# Relevant skills` block.
5. Skills with a `platforms:` frontmatter field are filtered to compatible OSes automatically.

**Why separate rather than unified:**

- Frameworks update their skill systems at their own pace. A Nursery retriever that tried to *replace* either would fight updates.
- The information budget is different. OpenClaw/Hermes native loading picks skills by slash-command or tag heuristics; embedding retrieval picks them by semantic relevance to *this* message. Both signals are useful.
- We don't want to be another skill-format in the ecosystem. We want to be a useful layer on top of the one that exists.

Status: 🐥 Working. See [`agent/src/nursery_agent/skills.py`](./agent/src/nursery_agent/skills.py). Two example skills ship in [`examples/skills/`](./examples/skills/).

### Why this matters — the RPG / life-scenario direction

The long-term vision for Nursery includes **running agents inside simulated contexts**, like life-scenario RPGs: an agent plays a character, navigates a situation, makes decisions with consequences, accumulates memory. This is useful for:

- **Evaluating agent behavior** in controlled scenarios (ethics, social dynamics, decision quality under uncertainty).
- **Training data generation** — trajectories from agents-in-scenarios become RL / SFT data.
- **Experiential agent development** — skills that emerge from scenario play, not just documentation.
- **Entertainment / education** — agents as interactive narrative partners.

Skills are the right substrate for this because:

1. **Scenario mechanics become skills.** A "combat" skill, a "dialogue" skill, a "resource management" skill. Load the ones relevant to the game.
2. **Portable across frameworks.** The same scenario skill pack runs a Hermes agent or an OpenClaw agent identically.
3. **Composable.** A life-scenario RPG is a *set* of skills + a *persona* (`SOUL.md`) + a *workspace* (memory of what happened). All three are already in Nursery's vocabulary.
4. **Measurable.** Skills declare `verification` sections — we can score whether an agent completed a scenario's objectives.

This isn't built yet, but the architecture is deliberately shaped toward it. Every design decision — workspace as identity, soul as persona, skills as procedural memory — is compatible with "spawn ten agents into a scenario, observe, collect trajectories."

When we get there, it'll be its own phase. For now: document the ecosystem, respect the standard, don't paint ourselves into a proprietary corner.

## Status

🥚 **Hatching.** README, scaffold, and direction are in place. No functional code yet. This repo exists to think in public and not lose the thread.

## Contributing

Early-stage. Open an issue before submitting a PR. For security issues, see [SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE)
