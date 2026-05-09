# Scenario Runtime

*Design notes for running Nursery agents inside simulated contexts.*

This document captures the architecture gap between what Nursery has today and what a [Voyager](https://github.com/MineDojo/Voyager)-style lifelong-learning agent would need. It exists so the shape of the work is findable later, not to lock anything in.

**Status:** 🥚 Design notes only. No code. Phase ∞ work.

## What we have today

- **Workspace-as-identity** — persistent state per agent.
- **Soul-as-persona** — a `SOUL.md` that shapes voice and values.
- **Container-as-body** — disposable, reproducible runtime.
- **HTTP message interface** — `POST /message` with `text` and optional `history`; returns `{reply, thinking, meta}`.
- **Host profiles** — openclaw / hermes / pi, each with different defaults.
- **Backend abstraction** — Ollama today, cloud APIs later.

This is good enough for chat agents. It is **not** good enough for agents-in-scenarios.

## What Voyager implies we need

### 1. An environment-feedback protocol (not just messages)

Today's `POST /message` sends **text in, text out**. A scenario runtime needs to send **observations in, actions out**, and then resolve those actions in a world.

Sketch:

```
POST /step
{
  "observation": {
    "world_state": { ... },
    "last_action_result": { "success": true, "changes": [...] },
    "inventory": [...],
    "nearby_entities": [...]
  },
  "step": 42
}

→ 200
{
  "thought": "I notice there's iron nearby. Let me mine it.",
  "action": {
    "skill": "mineIronOre",
    "args": { "count": 3 }
  },
  "meta": { ... }
}
```

The agent no longer "replies" — it **acts**. The runtime is responsible for resolving that action and feeding back the next observation.

### 2. A skill library that's read-write, not read-only

Today's plan is to mount the host's skills directory **read-only**. Voyager writes new skills as it learns. That means:

- Each agent's workspace needs a private skill directory (`workspace/skills/`).
- Agents need a primitive to *save* a skill: "here's code that worked, here's the description, add it."
- Skills need an **index** (vector DB) for embedding-based retrieval.
- Optionally, a shared skill pool where agents can contribute — with careful isolation to prevent poisoning.

### 3. Skill retrieval by semantic similarity

Dumping every skill into every prompt is wasteful and doesn't scale. Voyager retrieves the top-*k* skills by embedding similarity to the current task description. Nursery needs:

- A local embedding model (sentence-transformers, or Ollama's embedding models).
- A vector store per agent (sqlite-vec, chromadb, or just faiss on disk).
- A retrieval step in the `POST /step` loop: *given this observation, which skills are most relevant?*

### 4. Self-verification that actually runs

`SKILL.md` already has a `## Verification` section. Today it's documentation. In a scenario runtime, verification becomes a **pass/fail assertion the runtime executes** after every skill invocation:

- Did the agent claim to mine 3 iron? Did the inventory actually change by 3 iron?
- Pass → the skill worked; mark it stable and add to the library.
- Fail → feed the delta back to the agent ("you got 1 iron, not 3"); let it rewrite.

This is the loop Voyager calls "iterative prompting with self-verification."

### 5. An automatic curriculum

Voyager's curriculum prompt asks: *given what you can already do, and what you can see, what's the most interesting novel thing to attempt?*

This is a **meta-skill**, and it should be bundled as a canonical Nursery skill so any scenario agent can use it:

```
skills/
└── nursery-curriculum/
    ├── SKILL.md
    └── prompts/
        └── propose-next-task.md
```

## Open questions

- **Environment protocol.** Do we standardize on a generic `/step` schema, or let each scenario define its own?
- **Scenario packaging.** How does a scenario ship? A skill bundle + an environment server? A Docker image that runs alongside the agent?
- **Action execution.** The agent emits an action; who resolves it? A scenario server? An external world (Minecraft via mineflayer, a browser via Playwright, a terminal sandbox)?
- **Reward / scoring.** Voyager uses task-completion as implicit reward. Do we need explicit scoring for evaluation runs?
- **Multi-agent scenarios.** What happens when two Nursery agents are in the same world? Coordination? Competition? Shared skill pool, or separate?

## What this is not

- A plan to ship. No code here. No PR that introduces a `/step` endpoint.
- A replacement for chat agents. The scenario runtime would be an **additional** mode, not a rewrite.
- A commitment to Minecraft. Voyager's choice of Minecraft is a great research substrate; Nursery's scenarios might be text-RPGs, social sims, terminal sandboxes, or something we haven't imagined yet.

## When this becomes real work

After Phase 3 (one channel, end-to-end), after Phase 4 (multi-agent isolation), after Phase 5 (host adapters). This is **Phase ∞** territory. Living here so we don't forget the shape.

## References

- Wang et al., *Voyager: An Open-Ended Embodied Agent with Large Language Models* — [paper](https://arxiv.org/abs/2305.16291), [code](https://github.com/MineDojo/Voyager)
- [agentskills.io](https://agentskills.io/) — the skill format we'll build on
- [MineDojo](https://minedojo.org/) — the broader project Voyager lives in
