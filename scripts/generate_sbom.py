"""Generate a minimal CycloneDX SBOM from installed Python and locked frontend deps."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def requirement_names(path: Path) -> list[str]:
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith(("#", "-r", "--requirement")):
            continue
        name = re.split(r"[<>=!~;\[]", value, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def python_components(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    components: list[dict[str, object]] = []
    unresolved: list[str] = []
    for name in requirement_names(path):
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            unresolved.append(name)
            continue
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name.lower()}@{version}",
                "properties": [{"name": "yunsync:ecosystem", "value": "python"}],
            }
        )
    return components, unresolved


def frontend_components(lock_path: Path) -> tuple[list[dict[str, object]], list[str]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    root = lock.get("packages", {}).get("", {})
    direct = root.get("dependencies", {})
    components: list[dict[str, object]] = []
    unresolved: list[str] = []
    for name in sorted(direct):
        package = lock.get("packages", {}).get(f"node_modules/{name}", {})
        version = package.get("version")
        if not isinstance(version, str) or not version:
            unresolved.append(name)
            continue
        escaped = name.replace("@", "%40").replace("/", "%2F")
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:npm/{escaped}@{version}",
                "properties": [{"name": "yunsync:ecosystem", "value": "npm"}],
            }
        )
    return components, unresolved


def build_sbom(project_root: Path, version: str) -> tuple[dict[str, object], list[str]]:
    python, python_missing = python_components(project_root / "requirements.txt")
    frontend, frontend_missing = frontend_components(
        project_root / "frontend" / "package-lock.json"
    )
    components = sorted(python + frontend, key=lambda item: str(item["purl"]))
    fingerprint = "\n".join(str(item["purl"]) for item in components)
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, fingerprint)}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {"type": "application", "name": "YunSync", "version": version},
            "tools": {"components": [{"type": "application", "name": "yunsync-sbom", "version": "1"}]},
        },
        "components": components,
    }
    return bom, sorted(python_missing + frontend_missing)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 YunSync CycloneDX 1.5 SBOM。")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "release" / "sbom.cdx.json")
    parser.add_argument("--version", default="v2-development")
    parser.add_argument("--allow-unresolved", action="store_true")
    args = parser.parse_args()
    bom, unresolved = build_sbom(PROJECT_ROOT, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bom, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "passed" if not unresolved else "incomplete",
                "components": len(bom["components"]),
                "unresolved": unresolved,
                "output": args.output.name,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not unresolved or args.allow_unresolved else 2


if __name__ == "__main__":
    raise SystemExit(main())
