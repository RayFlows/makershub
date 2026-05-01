# tests/test_engineering_standards.py
"""
工程化约定守卫测试

本文件把后端文件头、模块说明和基础目录 README 约定转成自动化测试，
避免后续开发因为上下文切换或赶进度降低可维护性标准。
"""

from __future__ import annotations

from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]


def iter_python_files() -> list[Path]:
    """列出需要遵守文件头规范的 Python 文件。"""

    roots = [
        API_ROOT / "app",
        API_ROOT / "migrations",
        API_ROOT / "tests",
    ]
    files: list[Path] = []
    for root in roots:
        files.extend(
            file
            for file in root.rglob("*.py")
            if "__pycache__" not in file.parts
        )
    return sorted(files)


def test_python_files_have_path_header_and_module_docstring() -> None:
    """所有后端 Python 文件都应包含路径头和模块级说明。"""

    missing_header: list[str] = []
    missing_docstring: list[str] = []

    for file in iter_python_files():
        relative_path = file.relative_to(API_ROOT).as_posix()
        lines = file.read_text(encoding="utf-8").splitlines()
        expected_header = f"# {relative_path}"
        if not lines or lines[0] != expected_header:
            missing_header.append(relative_path)
        if len(lines) < 2 or not lines[1].startswith('"""'):
            missing_docstring.append(relative_path)

    assert missing_header == []
    assert missing_docstring == []


def test_python_infrastructure_directories_have_readme() -> None:
    """包含 Python 文件的后端目录应有 README 说明边界和职责。"""

    missing_readme: list[str] = []
    for directory in sorted((API_ROOT / "app").rglob("*")):
        if not directory.is_dir() or "__pycache__" in directory.parts:
            continue
        has_python_file = any(child.suffix == ".py" for child in directory.iterdir() if child.is_file())
        if has_python_file and not (directory / "README.md").exists():
            missing_readme.append(directory.relative_to(API_ROOT).as_posix())

    assert missing_readme == []
