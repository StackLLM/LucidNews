"""Guards against a moved module breaking an import that only runs late (inside a function)."""

import ast
import importlib
import pkgutil
from pathlib import Path

import lucidnews

PACKAGE_DIR = Path(lucidnews.__file__).resolve().parent


def test_every_module_imports() -> None:
    for module in pkgutil.walk_packages([str(PACKAGE_DIR)], "lucidnews."):
        importlib.import_module(module.name)


def test_every_relative_import_resolves_to_a_module_of_the_package() -> None:
    unresolved = []
    for path in PACKAGE_DIR.rglob("*.py"):
        package = list(path.relative_to(PACKAGE_DIR).with_suffix("").parts[:-1])
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            base = package[: len(package) - (node.level - 1)]
            target = PACKAGE_DIR.joinpath(*base, *(node.module.split(".") if node.module else []))
            if not (target.with_suffix(".py").exists() or (target / "__init__.py").exists()):
                unresolved.append(f"{path.relative_to(PACKAGE_DIR)}:{node.lineno} {'.' * node.level}{node.module or ''}")
    assert unresolved == []
