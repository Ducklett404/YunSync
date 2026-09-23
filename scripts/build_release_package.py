from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".npm-cache",
    ".ruff_cache",
    ".tools",
    ".venv",
    "__pycache__",
    "node_modules",
    "release",
    "htmlcov",
}
EXCLUDED_NAMES = {".env"}
EXCLUDED_SUFFIXES = {".db", ".pyc", ".pyo", ".tsbuildinfo"}


def included_files(root: Path) -> list[Path]:
    files: list[Path] = []
    resolved_root = root.resolve()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if relative.parts[:2] == ("backend", "data"):
            continue
        if not path.is_file() or path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        resolved = path.resolve()
        if resolved_root not in resolved.parents:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def archive_entry(name: str, content: bytes) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info, content


def build_package(output: Path, version: str, *, require_clean: bool = True) -> dict[str, object]:
    output = output.resolve()
    if PROJECT_ROOT not in output.parents:
        raise ValueError("输出文件必须位于项目目录内")
    output.parent.mkdir(parents=True, exist_ok=True)
    working_tree_status = git_value("status", "--porcelain")
    if require_clean and working_tree_status:
        raise ValueError("正式发布包只能从干净的 Git 工作区生成")
    files = included_files(PROJECT_ROOT)
    manifest = {
        "format": "yunsync-release-manifest-v1",
        "version": version,
        "commit": git_value("rev-parse", "HEAD"),
        "branch": git_value("branch", "--show-current"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "working_tree_clean": working_tree_status == "",
        "file_count": len(files),
        "exclusions": {
            "secret_env": True,
            "database_files": True,
            "git_history": True,
            "dependency_directories": True,
        },
    }
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            info, content = archive_entry(relative, path.read_bytes())
            archive.writestr(info, content)
        info, content = archive_entry(
            "RELEASE_MANIFEST.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        archive.writestr(info, content)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".manifest.json")
    checksum = output.with_suffix(output.suffix + ".sha256")
    manifest["archive"] = output.name
    manifest["sha256"] = digest
    sidecar.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="构建不含运行时秘密和数据库的 YunSync 发布包。")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "release" / "YunSync-V2.0.zip")
    parser.add_argument("--version", default="V2.0")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="仅用于本地草稿；正式发布不得使用。",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    manifest = build_package(output, args.version, require_clean=not args.allow_dirty)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
