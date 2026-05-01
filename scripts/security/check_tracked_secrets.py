# scripts/security/check_tracked_secrets.py
"""
仓库密钥泄露守卫

本脚本只扫描 Git 已跟踪文件，避免把本地 `.env`、构建产物和依赖缓存误判为问题。
它用于 CI 和本地提交前检查，目标是拦截高置信度密钥，而不是替代 GitHub secret
scanning、云厂商密钥管理或生产环境配置审计。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# --- 扫描规则 ---

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIPPED_FILENAMES = {
    "pnpm-lock.yaml",
    "uv.lock",
}

SKIPPED_SUFFIXES = {
    ".ico",
    ".jpg",
    ".jpeg",
    ".lock",
    ".pdf",
    ".png",
    ".webp",
    ".zip",
}

PLACEHOLDER_MARKERS = (
    "${",
    "<",
    ">",
    "change-me",
    "changeme",
    "dummy",
    "example",
    "fake",
    "local",
    "not_usable",
    "placeholder",
    "pending_password",
    "sample",
    "test",
    "your-",
    "your_",
)


@dataclass(frozen=True)
class SecretPattern:
    """高置信度密钥模式。"""

    name: str
    regex: re.Pattern[str]


SECRET_PATTERNS = [
    SecretPattern(
        name="private_key",
        regex=re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |)?PRIVATE KEY-----"),
    ),
    SecretPattern(
        name="github_token",
        regex=re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    ),
    SecretPattern(
        name="aws_access_key",
        regex=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    SecretPattern(
        name="wechat_app_secret_assignment",
        regex=re.compile(
            r"(?i)\b(?:wechat|wx)[A-Za-z0-9_-]*secret\b\s*[:=]\s*['\"]?[0-9a-f]{32}['\"]?",
        ),
    ),
    SecretPattern(
        name="sensitive_assignment",
        regex=re.compile(
            r"(?ix)"
            r"\b[A-Za-z0-9_-]*(?:secret|password|token|api[_-]?key|access[_-]?key|private[_-]?key)"
            r"[A-Za-z0-9_-]*\b"
            r"\s*[:=]\s*['\"]"
            r"(?P<value>[A-Za-z0-9_./+=:-]{24,})"
            r"['\"]",
        ),
    ),
]


@dataclass(frozen=True)
class SecretFinding:
    """密钥扫描命中结果。"""

    path: str
    line_number: int
    pattern_name: str


# --- Git 文件枚举 ---

def list_tracked_files() -> list[Path]:
    """返回仓库中已经被 Git 跟踪的文件。"""

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    raw_files = result.stdout.decode("utf-8").split("\0")
    return [REPO_ROOT / item for item in raw_files if item]


def should_scan(path: Path) -> bool:
    """判断某个文件是否适合做文本密钥扫描。"""

    if path.name in SKIPPED_FILENAMES:
        return False
    if path.suffix.lower() in SKIPPED_SUFFIXES:
        return False
    return True


# --- 扫描执行 ---

def is_placeholder_match(line: str, pattern: SecretPattern) -> bool:
    """过滤文档和示例配置中的占位值。"""

    if pattern.name != "sensitive_assignment":
        return False
    normalized = line.lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def scan_file(path: Path) -> list[SecretFinding]:
    """扫描单个文本文件。"""

    relative_path = path.relative_to(REPO_ROOT).as_posix()
    findings: list[SecretFinding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings

    for line_number, line in enumerate(lines, start=1):
        for pattern in SECRET_PATTERNS:
            if pattern.regex.search(line) and not is_placeholder_match(line, pattern):
                findings.append(
                    SecretFinding(
                        path=relative_path,
                        line_number=line_number,
                        pattern_name=pattern.name,
                    ),
                )
    return findings


def main() -> int:
    """执行密钥扫描并返回进程退出码。"""

    findings: list[SecretFinding] = []
    for path in list_tracked_files():
        if should_scan(path):
            findings.extend(scan_file(path))

    if not findings:
        print("No high-confidence tracked secrets found.")
        return 0

    print("Potential tracked secrets found:", file=sys.stderr)
    for finding in findings:
        print(
            f"- {finding.path}:{finding.line_number} ({finding.pattern_name})",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
