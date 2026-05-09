# Secrets

Agents need tokens (OAuth, API keys, channel bots) but must never leak them, share them, or bake them into images.

## Principles

1. **Never in the image.** Base images are public; secrets are not.
2. **Never in the repo.** `.gitignore` is aggressive about this. CI should scan.
3. **Never in the spec.** `agent.yaml` references secrets *by name*, not by value.
4. **Per-agent, not shared.** Each agent has its own mount. No cross-agent reading.
5. **Rotatable without rebuild.** Updating a secret should not require rebuilding a container.

## Current Thinking

```yaml
# agent.yaml
secrets:
  - google-oauth
  - notion-api
```

On the host, those names resolve to mounted files:

```
/var/nursery/secrets/<agent-name>/google-oauth.json
/var/nursery/secrets/<agent-name>/notion-api.env
```

The agent container mounts its *own* secrets dir read-only at `/run/secrets/`. Other agents cannot read it.

## Open Questions

- **Storage backend.** Plain files on disk? A vault (HashiCorp, age-encrypted)? Docker secrets? Depends on threat model.
- **Rotation.** How does an agent know a secret changed? File-watch? SIGHUP? Just restart?
- **Shared-but-scoped secrets.** Some tokens (e.g. a shared Notion workspace) might be legitimately shared across agents with the user's consent. Handle this without undermining isolation.
- **Bootstrap.** The very first secret (e.g. OAuth refresh token) has to come from somewhere. An interactive `nursery auth <agent>` command that handles OAuth flows on behalf of the spec?
