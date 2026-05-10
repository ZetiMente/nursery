# Pi Host Adapter

Nursery agents running alongside **Pi** — Mario Zechner's self-extensible agent toolkit.

- Website: https://pi.dev
- Repo: https://github.com/earendil-works/pi
- Background: ["Pi: The Minimal Agent Within OpenClaw"](https://lucumr.pocoo.org/2026/1/31/pi/) by Armin Ronacher

Pi is the substrate OpenClaw is built on top of — a minimal coding-agent core with four primitive tools (Read, Write, Edit, Bash), a tree-shaped session model, and an extension system that lets agents extend themselves at runtime.

## Status

🥚 **Provisional.** The profile's defaults get a container running, but the *integration* story — how a Nursery container coordinates with a `pi-agent-core` process, whether we expose our HTTP to Pi's extensions or vice versa — is not yet specified.

Spawning a `host: pi` agent prints a `note: host profile 'pi' is PROVISIONAL` warning.

## Profile defaults (provisional)

| Key | Value |
|-----|-------|
| Image | `nursery/agent:base` (no dedicated Pi image yet) |
| `NURSERY_HOST` | `pi` |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | (none — placeholder until the integration is specified) |
| Memory / CPU | Docker default |

## What Pi is

From Armin's write-up:

> Pi is interesting to me because of two main reasons:
>
> - First of all, it has a tiny core. It has the shortest system prompt of any agent that I'm aware of and it only has four tools: Read, Write, Edit, Bash.
> - The second thing is that it makes up for its tiny core by providing an extension system that also allows extensions to persist state into sessions, which is incredibly powerful.

Key design traits that matter for Nursery:

- **Code-first:** if the agent needs to do something new, it writes the code rather than downloading a plugin.
- **Unified multi-provider LLM API** (`@earendil-works/pi-ai`): OpenAI, Anthropic, Google, local — same interface. Aligns naturally with Nursery's model abstraction.
- **Tree-shaped sessions:** branch into side-quests (fix a broken tool, review a change) and rewind back to the main trunk. Sessions are data the agent can navigate.
- **Tools outside the context:** extensions can register tools at runtime without bloating the system prompt, because state can persist through sessions.

## What's needed to move this out of provisional

- Decide the **integration shape**: does a Nursery container *run* Pi (i.e., `pi-agent-core` inside the image as the agent runtime), or does it *run alongside* Pi (Pi on the host, Nursery container as a peer)?
- If "run Pi inside": a dedicated `nursery/agent:pi` image with Node.js + `@earendil-works/pi-coding-agent` installed. Our entrypoint becomes a thin wrapper that hands off to Pi.
- If "alongside": nail down the protocol — does Pi call Nursery over HTTP? Does Pi's extension system discover Nursery as a tool? Something else?
- Either way: decide what `SOUL.md` + Nursery's backends/skills layer contribute when Pi already has its own multi-provider abstraction.

Status today: use `host: standalone` if you want a lightweight Nursery-only deployment. Use `host: pi` if you're experimenting with Pi and want the Nursery spec format + labels, knowing the integration is TBD.

## Spawning (today)

```bash
uv run nursery spawn examples/agents/pi-layla.yaml
# → prints provisional warning, container runs with placeholder defaults
```

## References

- [Pi website](https://pi.dev) · [docs](https://pi.dev/docs/latest)
- [earendil-works/pi](https://github.com/earendil-works/pi) — monorepo
- [Pi packages on npm](https://www.npmjs.com/org/earendil-works)
- ["Pi: The Minimal Agent Within OpenClaw"](https://lucumr.pocoo.org/2026/1/31/pi/) — Armin Ronacher's context piece
- [@badlogicgames](https://x.com/badlogicgames) — Mario Zechner's X
