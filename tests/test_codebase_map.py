"""Tests for local codebase map."""

from pathlib import Path

from guider.codebase_map import build_codebase_map
from guider.service import GuiderService
from guider.storage.database import Database


def _make_sample_repo(root: Path) -> None:
    (root / "src" / "demo").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "ignored.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "demo" / "cli.py").write_text(
        "def main():\n    return 0\n\nclass App:\n    def run(self):\n        pass\n",
        encoding="utf-8",
    )
    (root / "src" / "demo" / "service.py").write_text(
        "class DemoService:\n    def map(self):\n        return {}\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project.scripts]\ndemo = "demo.cli:main"\n',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".venv\n.env\n", encoding="utf-8")


class TestBuildCodebaseMap:
    def test_tree_ignores_venv_and_env(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        result = build_codebase_map(tmp_path, max_depth=4)
        paths = _collect_paths(result["tree"])
        assert "src/demo/cli.py" in paths or any(p.endswith("cli.py") for p in paths)
        assert not any(".venv" in p for p in paths)
        assert not any(p.endswith(".env") for p in paths)
        assert result["summary"]["file_count"] >= 3
        assert result["summary"]["languages"].get("python", 0) >= 2

    def test_symbols_extracted(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        result = build_codebase_map(tmp_path)
        modules = {m["path"]: m for m in result["modules"]}
        assert any("cli.py" in p for p in modules)
        cli = next(m for m in result["modules"] if m["path"].endswith("cli.py"))
        names = {s["name"] for s in cli["symbols"]}
        assert "main" in names
        assert "App" in names

    def test_entrypoints_and_hints(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        result = build_codebase_map(tmp_path)
        assert result["entrypoints"]
        assert any("cli.py" in e for e in result["entrypoints"])
        assert result["hints"]

    def test_hashmap_indexes(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        result = build_codebase_map(tmp_path)
        assert result["fingerprint"]
        assert result["modules_by_path"]
        cli_path = next(p for p in result["modules_by_path"] if p.endswith("cli.py"))
        assert result["modules_by_path"][cli_path]["symbols"]
        # O(1) symbol lookup
        assert "App" in result["symbol_index"]
        assert any(p.endswith("cli.py") for p in result["symbol_index"]["App"])
        assert "DemoService" in result["symbol_index"]
        assert "main" in result["symbol_index"]


class TestServiceMapCodebase:
    def test_cache_and_refresh(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        svc = GuiderService(db=Database(tmp_path / "t.db"))
        first = svc.map_codebase(str(tmp_path))
        second = svc.map_codebase(str(tmp_path))
        assert first["cached"] is False
        assert second["cached"] is True
        assert first["fingerprint"] == second["fingerprint"]
        third = svc.map_codebase(str(tmp_path), refresh=True)
        assert third["cached"] is False
        assert third["workspace"] == str(tmp_path.resolve())

    def test_fingerprint_invalidates_on_change(self, tmp_path: Path) -> None:
        _make_sample_repo(tmp_path)
        svc = GuiderService(db=Database(tmp_path / "t.db"))
        first = svc.map_codebase(str(tmp_path))
        (tmp_path / "src" / "demo" / "cli.py").write_text(
            "def main():\n    return 1\n\nclass App:\n    pass\n",
            encoding="utf-8",
        )
        second = svc.map_codebase(str(tmp_path))
        assert second["cached"] is False
        assert second["fingerprint"] != first["fingerprint"]


def _collect_paths(nodes: list, acc: list | None = None) -> list:
    acc = acc if acc is not None else []
    for n in nodes:
        acc.append(n["path"])
        if n.get("children"):
            _collect_paths(n["children"], acc)
    return acc
