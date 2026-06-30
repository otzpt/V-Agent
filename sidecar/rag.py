"""
rag.py — Basic RAG for V-Agent
Keyword-based file index; no embeddings, no vector DB.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "target", "dist", "build",
    ".venv", "venv", ".next", "out", ".svelte-kit", "coverage",
}
SKIP_EXTS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".lock", ".sum", ".pdf", ".db", ".sqlite",
}
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".vue", ".svelte", ".html", ".css", ".scss", ".sass",
    ".json", ".toml", ".yaml", ".yml", ".md", ".sh", ".ps1",
    ".bat", ".sql", ".graphql", ".proto", ".tf", ".lua",
}
MAX_FILE_BYTES = 100 * 1024   # 100 KB hard cap
TOP_K_DEFAULT  = 3

_LANG_MAP = {
    ".py": "python",  ".js": "javascript",  ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".rs": "rust",
    ".go": "go", ".java": "java", ".c": "c", ".cpp": "cpp",
    ".cs": "csharp", ".rb": "ruby", ".php": "php",
    ".html": "html", ".css": "css", ".json": "json",
    ".md": "markdown", ".sh": "shell", ".ps1": "powershell",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
}


def _lang(fname: str) -> str:
    return _LANG_MAP.get(Path(fname).suffix.lower(), "text")


def _project_hash(root: str) -> str:
    return hashlib.md5(root.encode("utf-8")).hexdigest()[:14]


def _index_path(config_dir: Path, root: str) -> Path:
    d = config_dir / "rag_index"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{_project_hash(root)}.json"


# ── Index building ─────────────────────────────────────────────────────────────

def build_index(root: str, config_dir: Path) -> dict:
    """Full rebuild of the file index for *root*."""
    index: dict = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() in SKIP_EXTS:
                continue
            if fpath.suffix.lower() not in CODE_EXTS:
                continue
            try:
                stat = fpath.stat()
                if stat.st_size > MAX_FILE_BYTES:
                    continue
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                rel = os.path.relpath(str(fpath), root)
                index[rel] = {
                    "path":          rel,
                    "content":       content,
                    "lines":         content.count("\n") + 1,
                    "language":      _lang(fname),
                    "last_modified": stat.st_mtime,
                }
            except Exception:
                continue

    _write_index(config_dir, root, index)
    return index


def _write_index(config_dir: Path, root: str, index: dict) -> None:
    try:
        _index_path(config_dir, root).write_text(
            json.dumps(index, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def load_index(root: str, config_dir: Path) -> Optional[dict]:
    p = _index_path(config_dir, root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def refresh_index(root: str, config_dir: Path) -> dict:
    """Incremental update: only re-read files that changed since last index."""
    existing = load_index(root, config_dir) or {}
    changed  = False

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() in SKIP_EXTS:
                continue
            if fpath.suffix.lower() not in CODE_EXTS:
                continue
            try:
                stat = fpath.stat()
                if stat.st_size > MAX_FILE_BYTES:
                    continue
                rel    = os.path.relpath(str(fpath), root)
                cached = existing.get(rel)
                if cached and abs(cached["last_modified"] - stat.st_mtime) < 0.01:
                    continue   # unchanged
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                existing[rel] = {
                    "path":          rel,
                    "content":       content,
                    "lines":         content.count("\n") + 1,
                    "language":      _lang(fname),
                    "last_modified": stat.st_mtime,
                }
                changed = True
            except Exception:
                continue

    if changed:
        _write_index(config_dir, root, existing)
    return existing


# ── Search ────────────────────────────────────────────────────────────────────

def search(query: str, index: dict, top_k: int = TOP_K_DEFAULT) -> list[dict]:
    """Simple keyword relevance: count query-word occurrences in path + content."""
    if not query or not index:
        return []

    words = [w.lower() for w in query.split() if len(w) > 2]
    if not words:
        return []

    scored: list[tuple[int, dict]] = []
    for entry in index.values():
        content_lo = entry["content"].lower()
        path_lo    = entry["path"].lower()
        score = 0
        for w in words:
            if w in path_lo:
                score += 12                         # filename match is a strong signal
            score += min(content_lo.count(w), 25)   # content occurrences (capped)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top_k]]


# ── Public helper ─────────────────────────────────────────────────────────────

def get_rag_context(
    query: str,
    root: str,
    config_dir: Path,
    max_chars: int = 4_000,
    top_k: int = TOP_K_DEFAULT,
) -> str:
    """
    Return a formatted string ready to be appended to the system prompt.
    Returns "" if no relevant files are found or root is not set.
    """
    if not root or not query:
        return ""

    try:
        index = refresh_index(root, config_dir)
    except Exception:
        return ""

    relevant = search(query, index, top_k=top_k)
    if not relevant:
        return ""

    parts: list[str] = []
    total = 0
    for entry in relevant:
        remaining = max_chars - total
        if remaining <= 0:
            break
        snippet = entry["content"]
        if len(snippet) > remaining:
            snippet = snippet[:remaining] + "\n…(truncated)"
        lang = entry.get("language", "text")
        parts.append(f"### {entry['path']}\n```{lang}\n{snippet}\n```")
        total += len(snippet)

    if not parts:
        return ""
    return "Relevant project files (auto-retrieved by RAG):\n\n" + "\n\n".join(parts)
