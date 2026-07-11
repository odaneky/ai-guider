"""Local-first codebase map for agent orientation (no LLM, no project file writes)."""

from __future__ import annotations

import ast
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".eggs",
    ".idea",
    ".vscode",
    "coverage",
    ".next",
    ".turbo",
    "target",
    "vendor",
}

SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".DS_Store",
}

SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

LANG_BY_EXT = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".sh": "shell",
}

ENTRYPOINT_NAME_HINTS = {
    "main.py",
    "cli.py",
    "app.py",
    "server.py",
    "__main__.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.rs",
}


def build_codebase_map(
    root: Path,
    *,
    max_depth: int = 4,
    max_files: int = 200,
    max_symbol_files: int = 80,
) -> dict:
    """Build a structure + key-path symbol map for a workspace root."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    ignore_globs = _load_gitignore_basenames(root)
    files: List[Path] = []
    dirs: List[Path] = []
    tree = _walk_tree(
        root,
        root,
        depth=0,
        max_depth=max_depth,
        max_files=max_files,
        files_out=files,
        dirs_out=dirs,
        ignore_globs=ignore_globs,
    )

    languages = Counter()
    for f in files:
        lang = LANG_BY_EXT.get(f.suffix.lower())
        if lang:
            languages[lang] += 1

    entrypoints = _detect_entrypoints(root, files)
    modules = _extract_python_symbols(root, files, max_symbol_files=max_symbol_files)
    modules_by_path = {m["path"]: m for m in modules}
    symbol_index = _build_symbol_index(modules)
    hints = _build_hints(root, files, entrypoints, languages)
    fingerprint = workspace_fingerprint(root, files, max_depth=max_depth)

    return {
        "workspace": str(root),
        "fingerprint": fingerprint,
        "summary": {
            "languages": dict(languages.most_common()),
            "file_count": len(files),
            "dir_count": len(dirs),
            "max_depth": max_depth,
            "symbol_count": sum(len(m["symbols"]) for m in modules),
            "indexed_symbols": len(symbol_index),
        },
        "tree": tree,
        "entrypoints": entrypoints,
        "modules": modules,
        "modules_by_path": modules_by_path,
        "symbol_index": symbol_index,
        "hints": hints,
    }


def workspace_fingerprint(
    root: Path,
    files: List[Path] | None = None,
    *,
    max_depth: int = 4,
    max_files: int = 200,
) -> str:
    """Stable fingerprint from (rel_path, size, mtime) of scanned files."""
    root = root.resolve()
    if files is None:
        ignore_globs = _load_gitignore_basenames(root)
        files = []
        dirs: List[Path] = []
        _walk_tree(
            root,
            root,
            depth=0,
            max_depth=max_depth,
            max_files=max_files,
            files_out=files,
            dirs_out=dirs,
            ignore_globs=ignore_globs,
        )

    h = hashlib.sha256()
    h.update(f"depth:{max_depth}\n".encode())
    records: List[str] = []
    for f in files:
        try:
            st = f.stat()
            rel = str(f.relative_to(root))
            records.append(f"{rel}|{st.st_size}|{int(st.st_mtime_ns)}")
        except OSError:
            continue
    for line in sorted(records):
        h.update(line.encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def _build_symbol_index(modules: List[dict], *, max_entries: int = 500) -> Dict[str, List[str]]:
    """Map short symbol name → file paths (O(1) agent lookup)."""
    index: Dict[str, List[str]] = defaultdict(list)
    for mod in modules:
        path = mod["path"]
        for sym in mod.get("symbols") or []:
            name = sym.get("name") or ""
            # Index both full name and trailing segment (Class.method → method, Class)
            keys = {name}
            if "." in name:
                keys.add(name.split(".")[-1])
                keys.add(name.split(".")[0])
            for key in keys:
                if not key or key.startswith("_"):
                    continue
                paths = index[key]
                if path not in paths:
                    paths.append(path)
            if len(index) >= max_entries:
                break
        if len(index) >= max_entries:
            break
    # Cap paths per symbol for payload size
    return {k: v[:10] for k, v in sorted(index.items())[:max_entries]}


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".")


def _should_skip_file(path: Path) -> bool:
    name = path.name
    if name in SKIP_FILE_NAMES:
        return True
    if name.startswith(".env"):
        return True
    if name.endswith(SECRET_SUFFIXES):
        return True
    return False


def _load_gitignore_basenames(root: Path) -> Set[str]:
    """Cheap gitignore subset: exact basename / top-level path segments to skip."""
    skip: Set[str] = set()
    gi = root / ".gitignore"
    if not gi.is_file():
        return skip
    try:
        text = gi.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return skip
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.rstrip("/")
        # Only simple tokens (no complex globs)
        if "/" in line or "*" in line or "?" in line or "[" in line:
            # Allow trailing /** style by taking first segment
            first = line.split("/")[0].replace("*", "").replace("?", "")
            if first and first not in (".", ".."):
                skip.add(first)
            continue
        skip.add(line)
    return skip


def _walk_tree(
    root: Path,
    current: Path,
    *,
    depth: int,
    max_depth: int,
    max_files: int,
    files_out: List[Path],
    dirs_out: List[Path],
    ignore_globs: Set[str],
) -> List[dict]:
    if depth > max_depth or len(files_out) >= max_files:
        return []

    nodes: List[dict] = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []

    for entry in entries:
        if len(files_out) >= max_files:
            break
        name = entry.name
        if entry.is_dir():
            if _should_skip_dir(name) or name in ignore_globs:
                continue
            rel = str(entry.relative_to(root))
            dirs_out.append(entry)
            children = _walk_tree(
                root,
                entry,
                depth=depth + 1,
                max_depth=max_depth,
                max_files=max_files,
                files_out=files_out,
                dirs_out=dirs_out,
                ignore_globs=ignore_globs,
            )
            nodes.append({"path": rel, "type": "dir", "children": children})
        elif entry.is_file():
            if _should_skip_file(entry):
                continue
            if name in ignore_globs:
                continue
            rel = str(entry.relative_to(root))
            files_out.append(entry)
            nodes.append({"path": rel, "type": "file"})
    return nodes


def _detect_entrypoints(root: Path, files: List[Path]) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()

    def add(rel: str) -> None:
        if rel not in seen:
            seen.add(rel)
            found.append(rel)

    # pyproject.toml scripts
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for match in re.finditer(
            r'^\s*[\w-]+\s*=\s*["\']([\w.]+):([\w]+)["\']',
            text,
            re.MULTILINE,
        ):
            module = match.group(1).replace(".", "/")
            # guider.cli -> src/guider/cli.py or guider/cli.py
            for prefix in ("src/", ""):
                candidate = root / f"{prefix}{module}.py"
                if candidate.is_file():
                    add(str(candidate.relative_to(root)))
                    break

    # package.json main
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            text = pkg.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        m = re.search(r'"main"\s*:\s*"([^"]+)"', text)
        if m:
            rel = m.group(1).lstrip("./")
            if (root / rel).is_file():
                add(rel)

    for f in files:
        rel = str(f.relative_to(root))
        name = f.name.lower()
        if name in ENTRYPOINT_NAME_HINTS:
            add(rel)
        if rel.endswith("mcp/server.py") or rel.endswith("mcp\\server.py"):
            add(rel)

    return found[:20]


def _is_key_python_path(root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    if path.suffix != ".py":
        return False
    if len(parts) == 1:
        return True
    if parts[0] in ("src", "lib", "app", "pkg"):
        return True
    if "mcp" in parts or "cli" in path.name:
        return True
    return False


def _extract_python_symbols(
    root: Path, files: List[Path], *, max_symbol_files: int
) -> List[dict]:
    candidates = [f for f in files if _is_key_python_path(root, f)]
    # Prefer shorter / more central paths
    candidates.sort(key=lambda p: (len(p.parts), str(p)))
    modules: List[dict] = []
    for path in candidates[:max_symbol_files]:
        symbols = _parse_python_file(path)
        if not symbols:
            continue
        modules.append(
            {
                "path": str(path.relative_to(root)),
                "role": "module",
                "symbols": symbols,
            }
        )
    return modules


def _parse_python_file(path: Path) -> List[dict]:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: List[dict] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append({"kind": "class", "name": node.name, "line": node.lineno})
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and not item.name.startswith("__"):
                        continue
                    symbols.append(
                        {
                            "kind": "method",
                            "name": f"{node.name}.{item.name}",
                            "line": item.lineno,
                        }
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue
            symbols.append({"kind": "function", "name": node.name, "line": node.lineno})
    # Cap symbols per file for payload size
    return symbols[:40]


def _build_hints(
    root: Path,
    files: List[Path],
    entrypoints: List[str],
    languages: Counter,
) -> List[str]:
    hints: List[str] = []
    rels = {str(f.relative_to(root)) for f in files}

    if any(r.startswith("src/") for r in rels):
        hints.append("Python/src layout detected — primary code under src/")
    if any("mcp/" in r or r.endswith("mcp/server.py") for r in rels):
        hints.append("MCP server present — start at mcp/server.py for tool surface")
    if any(r.endswith("cli.py") for r in rels):
        hints.append("CLI entry present — see cli.py for commands")
    if (root / "tests").is_dir() or any(r.startswith("tests/") for r in rels):
        hints.append("Tests live under tests/")
    if languages.get("python"):
        hints.append(f"Dominant language: python ({languages['python']} files scanned)")
    if entrypoints:
        hints.append(f"Likely entrypoints: {', '.join(entrypoints[:5])}")
    if not hints:
        hints.append("Scan complete — use tree + modules to orient before deep reads")
    return hints
