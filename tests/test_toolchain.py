"""The local toolchain must match the one CI installs.

`mypy` only sees pandas' real types when `pandas-stubs` is installed. Without it pandas
is `Any`, every pandas call type-checks trivially, and `make check` passes locally while
CI fails on the same commit. These tests fail fast when the environment has drifted.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from importlib.metadata import (
    PackageNotFoundError,
    packages_distributions,
    version,
)

import pytest

REQUIREMENTS = pathlib.Path("requirements.txt")
REQUIREMENTS_DEV = pathlib.Path("requirements-dev.txt")

LOCAL_PACKAGES = {
    "config",
    "db",
    "stores",
    "services",
    "fixed_income",
    "dashboard",
    "scripts",
    "tests",
    "main",
}

# Imports that may legitimately be absent because the code degrades without them.
OPTIONAL_IMPORTS = {
    "nest_asyncio": "Jupyter-only convenience in finra_client; the ImportError is passed",
}


def _packages(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _required_packages() -> list[str]:
    return _packages(REQUIREMENTS_DEV)


def test_the_requirements_files_are_the_source_of_truth() -> None:
    assert REQUIREMENTS.exists() and REQUIREMENTS_DEV.exists()
    assert _packages(REQUIREMENTS) and _packages(REQUIREMENTS_DEV)


@pytest.mark.parametrize("package", _packages(REQUIREMENTS))
def test_every_runtime_dependency_is_declared_and_installed(package: str) -> None:
    """A runtime import that is installed locally but undeclared ships broken."""
    try:
        version(package.split("[")[0])
    except PackageNotFoundError:
        pytest.fail(f"{package!r} is in requirements.txt but not installed here")


def _declared_distributions() -> set[str]:
    return {
        package.split("[")[0].lower().replace("_", "-")
        for path in (REQUIREMENTS, REQUIREMENTS_DEV)
        for package in _packages(path)
    }


def _third_party_imports() -> dict[str, list[str]]:
    """Every non-stdlib, non-local module imported anywhere in the project."""
    found: dict[str, list[str]] = {}
    for path in pathlib.Path(".").rglob("*.py"):
        if any(part in {".venv", "venv", "notebooks", ".git"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a syntax error fails elsewhere
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules = [node.module]
            else:
                continue
            for module in modules:
                root = module.split(".")[0]
                if root in LOCAL_PACKAGES or root in sys.stdlib_module_names:
                    continue
                found.setdefault(root, []).append(str(path))
    return found


def test_the_project_imports_third_party_code_at_all() -> None:
    assert _third_party_imports(), "import scan found nothing; the audit would pass vacuously"


@pytest.mark.parametrize("module", sorted(_third_party_imports()))
def test_every_third_party_import_is_a_declared_dependency(module: str) -> None:
    """Relying on a transitive dependency is fragile: an upgrade upstream can drop it.

    statsmodels was imported this way and undeclared, so a clean install produced None
    for every ADF result and understated every RV stability score.
    """
    if module in OPTIONAL_IMPORTS:
        pytest.skip(f"{module}: {OPTIONAL_IMPORTS[module]}")

    distributions = {
        dist.lower().replace("_", "-") for dist in packages_distributions().get(module, [module])
    }
    used_by = sorted(set(_third_party_imports()[module]))[:3]
    assert (
        distributions & _declared_distributions()
    ), f"{module} is imported by {used_by} but is in neither requirements file"


@pytest.mark.parametrize("package", _required_packages())
def test_every_dev_dependency_ci_installs_is_installed_here(package: str) -> None:
    """Run `pip install -r requirements-dev.txt` if this fails."""
    try:
        version(package)
    except PackageNotFoundError:
        pytest.fail(
            f"{package!r} is in requirements-dev.txt but not installed. "
            "Local checks are weaker than CI until you run: "
            "pip install -r requirements-dev.txt"
        )


def test_pandas_stubs_is_present_so_mypy_sees_real_pandas_types() -> None:
    """Called out separately because its absence is silent: mypy still exits 0."""
    try:
        version("pandas-stubs")
    except PackageNotFoundError:
        pytest.fail("pandas-stubs missing; mypy would type pandas as Any and pass wrongly")
