from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKERS = {
    "docs/PROJECT_REPORT.md": ["## 2. 问题与目标用户", "## 4. 核心创新", "## 7. 隐私与健康安全"],
    "docs/ARCHITECTURE.md": ["## 分层原则", "## 请求处理链路"],
    "docs/TECHNICAL_GUIDE.md": ["```mermaid", "## 3. 关键状态与不变量", "## 8. 云迁移与尚未验证项"],
    "docs/USER_GUIDE.md": ["## 2. 完成演示主流程", "## 4. 常见问题与恢复", "不构成诊断"],
    "docs/DEMO_RUNBOOK.md": ["## 2. 五分钟讲稿", "### A. 真实云端版", "### B. Mock 降级版", "### C. 截图/离线版", "## 4. 30 秒切换协议"],
    "docs/EVIDENCE_INDEX.md": ["## 1. 需求、设计与代码追踪", "## 4. 必须补充的真实证据", "未完成"],
    "docs/DEFENSE_QA.md": ["## 产品与创新", "## 安全与合规", "## 云与工程"],
    "docs/OPEN_SOURCE_INVENTORY.md": ["## 1. Python 直接依赖", "## 2. 前端直接依赖", "## 4. 最终发布检查"],
    "docs/M12A_VERIFICATION_REPORT.md": ["## 2. 自测结果", "## 3. 未伪造的完成边界"],
    "docs/ADMIN_GUIDE.md": ["## 1. 角色与权限", "## 2. 发布顺序"],
    "docs/PRIVACY_NOTICE.md": ["## 1. 目的与范围", "## 3. 保留、安全与用户权利"],
    "docs/CONTENT_OPERATIONS_RUNBOOK.md": ["## 1. 生命周期", "## 2. 变更级别"],
    "docs/INCIDENT_RESPONSE_RUNBOOK.md": ["## 1. 分级", "## 2. 响应流程"],
    "docs/V2_M8_ACCEPTANCE.md": ["## 1. 已完成的工程交付", "## 2. 外部门禁"],
    "docs/V2_M8_CUSTOMER_ACCEPTANCE.md": ["## 见证用例", "## 遗留问题与签收"],
    "docs/V2_M8_VERIFICATION_REPORT.md": ["## 2. 自动验证结果", "## 3. 正式 M8 尚需证据"],
}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def local_links(path: Path, content: str) -> list[tuple[str, Path]]:
    links: list[tuple[str, Path]] = []
    for raw_target in LINK_PATTERN.findall(content):
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith("#") or re.match(r"^[a-z]+://", target):
            continue
        links.append((raw_target, (path.parent / target).resolve()))
    return links


def check_materials() -> dict:
    errors: list[str] = []
    checked_links = 0

    for relative, markers in REQUIRED_MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                errors.append(f"missing marker in {relative}: {marker}")
        for raw_target, resolved in local_links(path, content):
            checked_links += 1
            if not resolved.exists():
                errors.append(f"broken link in {relative}: {raw_target}")

    readme = ROOT / "README.md"
    if readme.is_file():
        for raw_target, resolved in local_links(
            readme, readme.read_text(encoding="utf-8")
        ):
            checked_links += 1
            if not resolved.exists():
                errors.append(f"broken link in README.md: {raw_target}")

    plan = (ROOT / "docs/DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    for marker in ("M12A", "M12B", "真实", "未完成"):
        if marker not in plan:
            errors.append(f"development plan is missing boundary marker: {marker}")

    inventory = (ROOT / "docs/OPEN_SOURCE_INVENTORY.md").read_text(
        encoding="utf-8"
    ).lower()
    requirement_names = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            requirement_names.append(re.split(r"[<>=!~\[]", value, maxsplit=1)[0])
    package = json.loads(
        (ROOT / "frontend/package.json").read_text(encoding="utf-8")
    )
    dependency_names = requirement_names + list(package.get("dependencies", {}))
    for dependency in dependency_names:
        if dependency.lower() not in inventory:
            errors.append(f"direct dependency missing from inventory: {dependency}")

    qa_content = (ROOT / "docs/DEFENSE_QA.md").read_text(encoding="utf-8")
    qa_count = len(re.findall(r"^### \d+\.", qa_content, flags=re.MULTILINE))
    if qa_count != 21:
        errors.append(f"expected 21 defense questions, found {qa_count}")

    demo_content = (ROOT / "docs/DEMO_RUNBOOK.md").read_text(encoding="utf-8")
    for topic in ("问题", "方案", "创新", "技术", "效果", "安全"):
        if topic not in demo_content:
            errors.append(f"five-minute narrative is missing topic: {topic}")

    return {
        "status": "passed" if not errors else "failed",
        "required_files": len(REQUIRED_MARKERS),
        "checked_links": checked_links,
        "direct_dependencies": len(dependency_names),
        "defense_questions": qa_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the YunSync M12A submission material baseline."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check_materials()
    if args.json:
        print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    else:
        print(
            f"materials_check={result['status']} "
            f"required_files={result['required_files']} "
            f"checked_links={result['checked_links']}"
        )
        for error in result["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
