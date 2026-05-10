"""Nursery skill retrieval — embedding-indexed search over SKILL.md files.

This is INTENTIONALLY ADDITIVE, not a replacement for OpenClaw's or
Hermes's native skill systems. Those keep loading skills however they do,
and Nursery agents independently retrieve relevant skills by embedding
similarity and inject them into the system prompt.

Two systems running in parallel:
  1. Native framework (OpenClaw / Hermes) loads skills its way.
  2. Nursery's retriever also loads skills (possibly the same directory,
     possibly a different one) and injects top-k by semantic similarity.

Both can coexist; they don't fight because they act on different surfaces.

agentskills.io format:
    <skills_dir>/<skill_name>/SKILL.md
    with YAML frontmatter:
      ---
      name: skill-name
      description: one-line description
      platforms: [linux, macos]   # optional
      ---
      <markdown body>

What we store per skill:
    { name, description, body, path, embedding, platforms }

Opt-in via env var NURSERY_SKILLS_DIR. If unset, the retriever is inert
and chat() behaves identically to before.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger("nursery-agent.skills")

DEFAULT_EMBED_MODEL = "nomic-embed-text:latest"
DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"
INDEX_FILENAME = "skills-index.json"


# --------------------------------------------------------------------------
# Frontmatter parser (minimal, dependency-light — don't pull yaml twice)
# --------------------------------------------------------------------------


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter from a markdown file.

    Returns (metadata_dict, body). If there's no frontmatter, returns
    ({}, original_text). Uses PyYAML (already a project dep) for the
    metadata block only.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    frontmatter_text, body = m.group(1), m.group(2)

    try:
        import yaml  # type: ignore
    except ImportError:
        LOG.warning("skills: PyYAML missing, cannot parse frontmatter")
        return {}, body

    try:
        meta = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        LOG.warning("skills: malformed frontmatter: %s", e)
        return {}, body

    if not isinstance(meta, dict):
        return {}, body

    return meta, body


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: str
    platforms: list[str] = field(default_factory=list)
    # Computed at index time
    content_hash: str = ""
    embedding: list[float] = field(default_factory=list)

    def is_compatible_with_current_platform(self) -> bool:
        """Respect the agentskills.io platforms field."""
        if not self.platforms:
            return True
        sysname = platform.system().lower()
        # 'darwin' → 'macos' normalization, per the standard
        if sysname == "darwin":
            sysname = "macos"
        return sysname in [p.lower() for p in self.platforms]

    def short_inline(self, max_body_chars: int = 400) -> str:
        """Render a concise inline form for injection into a system prompt."""
        body = self.body.strip()
        if len(body) > max_body_chars:
            body = body[:max_body_chars].rstrip() + "..."
        return f"### {self.name}\n{self.description}\n\n{body}"


# --------------------------------------------------------------------------
# Skill index: scan → embed → persist → retrieve
# --------------------------------------------------------------------------


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _scan_skills(skills_dir: Path) -> list[Skill]:
    """Find all SKILL.md files under skills_dir/<name>/SKILL.md."""
    skills: list[Skill] = []
    if not skills_dir.exists():
        LOG.warning("skills: directory does not exist: %s", skills_dir)
        return skills

    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        # Only one level deep is the documented convention; deeper is fine too.
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError as e:
            LOG.warning("skills: cannot read %s: %s", skill_md, e)
            continue

        meta, body = _parse_frontmatter(text)

        name = meta.get("name") or skill_md.parent.name
        description = meta.get("description") or ""
        platforms = meta.get("platforms") or []
        if not isinstance(platforms, list):
            platforms = []
        if not isinstance(name, str) or not isinstance(description, str):
            LOG.warning("skills: %s has non-string name/description, skipping", skill_md)
            continue

        skill = Skill(
            name=name,
            description=description,
            body=body,
            path=str(skill_md),
            platforms=[str(p) for p in platforms],
            content_hash=_content_hash(description + "\n" + body),
        )
        if not skill.is_compatible_with_current_platform():
            LOG.info("skills: skip %s (platform restriction: %s)", name, platforms)
            continue
        skills.append(skill)

    return skills


def _embed_texts(
    texts: list[str],
    *,
    base_url: str,
    model: str,
) -> list[list[float]]:
    """Call Ollama /api/embed for a batch of texts. Returns one vector per input."""
    if not texts:
        return []

    url = f"{base_url.rstrip('/')}/api/embed"
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    result = json.loads(raw.decode("utf-8"))
    embeddings = result.get("embeddings") or []
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"embedding count mismatch: got {len(embeddings)} for {len(texts)} inputs"
        )
    return [list(v) for v in embeddings]


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Assumes non-zero vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na**0.5) * (nb**0.5))


def _save_index(skills: list[Skill], index_path: Path, embed_model: str) -> None:
    payload = {
        "version": 1,
        "embed_model": embed_model,
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "body": s.body,
                "path": s.path,
                "platforms": s.platforms,
                "content_hash": s.content_hash,
                "embedding": s.embedding,
            }
            for s in skills
        ],
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload), encoding="utf-8")


def _load_index(index_path: Path, embed_model: str) -> list[Skill] | None:
    if not index_path.exists():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != 1:
        return None
    if payload.get("embed_model") != embed_model:
        # A model change invalidates the index because dimensions/space differ.
        return None
    out: list[Skill] = []
    for s in payload.get("skills") or []:
        try:
            out.append(Skill(
                name=s["name"],
                description=s["description"],
                body=s["body"],
                path=s["path"],
                platforms=s.get("platforms") or [],
                content_hash=s.get("content_hash", ""),
                embedding=s.get("embedding") or [],
            ))
        except KeyError:
            continue
    return out


class SkillIndex:
    """Embedding-indexed collection of skills.

    Usage:
        idx = SkillIndex(skills_dir=Path("/skills"), workspace=Path("/workspace"))
        idx.build_or_load()     # idempotent; reuses cache when descriptions unchanged
        top = idx.retrieve("the user wants to know the weather", k=3)
        for s in top:
            print(s.name, s.description)
    """

    def __init__(
        self,
        skills_dir: Path,
        workspace: Path,
        *,
        embed_model: str = DEFAULT_EMBED_MODEL,
        ollama_url: str | None = None,
    ) -> None:
        self.skills_dir = skills_dir
        self.workspace = workspace
        self.embed_model = embed_model
        self.ollama_url = (
            ollama_url
            or os.environ.get("NURSERY_OLLAMA_URL")
            or DEFAULT_OLLAMA_URL
        )
        self.skills: list[Skill] = []
        self._index_path = workspace / ".nursery" / INDEX_FILENAME

    def build_or_load(self) -> None:
        """Build the index, reusing cached embeddings for unchanged skills."""
        scanned = _scan_skills(self.skills_dir)
        if not scanned:
            LOG.info("skills: no skills found in %s", self.skills_dir)
            self.skills = []
            return

        cached = _load_index(self._index_path, self.embed_model) or []
        cached_by_hash = {s.content_hash: s.embedding for s in cached if s.embedding}

        needs_embedding: list[Skill] = []
        for s in scanned:
            if s.content_hash in cached_by_hash:
                s.embedding = cached_by_hash[s.content_hash]
            else:
                needs_embedding.append(s)

        if needs_embedding:
            LOG.info(
                "skills: embedding %d / %d (reusing %d from cache)",
                len(needs_embedding), len(scanned), len(scanned) - len(needs_embedding),
            )
            try:
                texts = [s.description + "\n" + s.body[:500] for s in needs_embedding]
                vecs = _embed_texts(
                    texts,
                    base_url=self.ollama_url,
                    model=self.embed_model,
                )
                for s, v in zip(needs_embedding, vecs):
                    s.embedding = v
            except (urllib.error.URLError, RuntimeError) as e:
                LOG.warning("skills: embedding failed: %s (retrieval disabled)", e)
                # If embedding fails entirely, keep any we got from cache.
                scanned = [s for s in scanned if s.embedding]

        self.skills = scanned
        try:
            _save_index(self.skills, self._index_path, self.embed_model)
        except OSError as e:
            LOG.warning("skills: could not save index to %s: %s", self._index_path, e)

        LOG.info(
            "skills: index ready — %d skills from %s",
            len(self.skills), self.skills_dir,
        )

    def retrieve(self, query: str, k: int = 3) -> list[Skill]:
        """Return top-k skills by cosine similarity. Empty list if no index."""
        if not self.skills or not query.strip():
            return []

        try:
            vecs = _embed_texts(
                [query],
                base_url=self.ollama_url,
                model=self.embed_model,
            )
        except (urllib.error.URLError, RuntimeError) as e:
            LOG.warning("skills: query embedding failed: %s", e)
            return []
        if not vecs:
            return []
        qv = vecs[0]

        scored = [(s, _cosine(qv, s.embedding)) for s in self.skills if s.embedding]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        top = [s for s, _ in scored[:k]]
        LOG.info(
            "skills: retrieved top %d: %s",
            len(top), [(s.name, round(sc, 3)) for s, sc in scored[:k]],
        )
        return top


# --------------------------------------------------------------------------
# Convenience: construct from env
# --------------------------------------------------------------------------


def index_from_env(workspace: Path) -> SkillIndex | None:
    """Return an initialized SkillIndex if NURSERY_SKILLS_DIR is set, else None."""
    raw = os.environ.get("NURSERY_SKILLS_DIR")
    if not raw:
        return None
    skills_dir = Path(raw).resolve()
    if not skills_dir.exists():
        LOG.warning("skills: NURSERY_SKILLS_DIR=%s does not exist", skills_dir)
        return None

    embed_model = os.environ.get("NURSERY_EMBED_MODEL", DEFAULT_EMBED_MODEL)
    idx = SkillIndex(skills_dir=skills_dir, workspace=workspace, embed_model=embed_model)
    return idx


def render_skills_for_prompt(skills: list[Skill]) -> str:
    """Render retrieved skills for inclusion in a system prompt."""
    if not skills:
        return ""
    lines = [
        "# Relevant skills",
        "",
        "The following skills may be relevant to this request. Use them if they apply; ignore them if they don't.",
        "",
    ]
    for s in skills:
        lines.append(s.short_inline())
        lines.append("")
    return "\n".join(lines).strip()


if __name__ == "__main__":
    # Tiny dev-mode smoke tester: python -m nursery_agent.skills <dir> <query>
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) < 3:
        print("usage: python -m nursery_agent.skills <skills_dir> <query>", file=sys.stderr)
        sys.exit(2)
    skills_dir = Path(sys.argv[1]).resolve()
    workspace = Path(os.environ.get("NURSERY_WORKSPACE", "/tmp")).resolve()
    query = sys.argv[2]
    idx = SkillIndex(skills_dir=skills_dir, workspace=workspace)
    idx.build_or_load()
    top = idx.retrieve(query, k=3)
    if not top:
        print("(no matches)")
    for s in top:
        print(f"* {s.name}: {s.description}")
