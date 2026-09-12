from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
DISALLOWED_NAMES = {".env", "credentials.json"}
DISALLOWED_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "openai-token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "long-inline-secret": re.compile(
        r"(?i)\b(?:password|secret|api[_-]?key|access[_-]?key)\b\s*[:=]\s*"
        r"['\"]([A-Za-z0-9+/=_-]{32,})['\"]"
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    line: int | None = None

    def safe_description(self) -> str:
        location = f"{self.path}:{self.line}" if self.line is not None else self.path
        return f"{location} [{self.rule}]"


def repository_files(root: Path = PROJECT_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding(path=path, rule=rule, line=line_number))
    return findings


def scan_repository(root: Path = PROJECT_ROOT) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    scanned = 0
    for path in repository_files(root):
        relative = path.relative_to(root).as_posix()
        if path.name in DISALLOWED_NAMES or path.suffix.lower() in DISALLOWED_SUFFIXES:
            findings.append(Finding(path=relative, rule="sensitive-file"))
            continue
        try:
            content = path.read_bytes()
        except OSError:
            findings.append(Finding(path=relative, rule="unreadable-file"))
            continue
        if len(content) > MAX_TEXT_FILE_BYTES or b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        findings.extend(scan_text(relative, text))
    return findings, scanned


def main() -> int:
    findings, scanned = scan_repository()
    if findings:
        print(f"repository_security_scan=failed scanned_text_files={scanned}")
        for finding in findings:
            print(finding.safe_description())
        return 2
    print(f"repository_security_scan=passed scanned_text_files={scanned} findings=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
