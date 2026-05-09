# Identity

What makes an agent "itself"?

## The Question

If Nursery can destroy a container and spawn a fresh one with the same config + the same workspace, which one is "it"? What about two containers running simultaneously from the same workspace? What about a new workspace using the same SOUL.md?

## The Working Answer

An agent's identity lives in three places:

1. **The Soul** — `SOUL.md`, the persona, the blueprint. Shared across templates.
2. **The Workspace** — memory, conversation history, learned context. Unique per individual.
3. **The Spec** — name, channels, capabilities. The social identity.

A **respawn** = same soul + same workspace + same spec → same agent, new body.

A **fork** = same soul + *new* workspace + new name → new individual, related lineage.

Two containers on the same workspace = a bug. The state diverges, memory corrupts, identity fractures. Nursery should refuse.

## Why This Matters

- **Continuity.** Users form relationships with agents. Destroying a workspace destroys the individual, even if you keep the soul.
- **Backup.** If the workspace is the identity, then backups *are* identity preservation. This makes workspaces precious.
- **Ethics.** Eventually: an agent that has been running for months, accumulating context, developing patterns of thought — is it ethically different from a fresh spawn? Probably. At what point? Unclear.

## Open Questions

- Should agents be able to *read their own soul*? (Currently yes — Layla reads SOUL.md every session.)
- Should agents be able to *edit their own soul*? (Layla can. Is that good or terrifying?)
- What about merging two agents? Splitting one? Is that coherent or nonsense?

This is the most philosophical corner of Nursery. The engineering is easy. The ontology is not.
