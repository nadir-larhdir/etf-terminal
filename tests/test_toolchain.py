"""The local toolchain must match the one CI installs.

`mypy` only sees pandas' real types when `pandas-stubs` is installed. Without it pandas
is `Any`, every pandas call type-checks trivially, and `make check` passes locally while
CI fails on the same commit. These tests fail fast when the environment has drifted.
"""

from __future__ import annotations

import pathlib
from importlib.metadata import PackageNotFoundError, version

import pytest

REQUIREMENTS = pathlib.Path("requirements.txt")
REQUIREMENTS_DEV = pathlib.Path("requirements-dev.txt")

# Imported at runtime but easy to have locally and forget to declare.
DECLARED_RUNTIME_IMPORTS = {"statsmodels": "fixed_income/rv/spread_diagnostics.py"}


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


@pytest.mark.parametrize(("module", "used_by"), sorted(DECLARED_RUNTIME_IMPORTS.items()))
def test_optionally_imported_modules_are_declared_dependencies(module: str, used_by: str) -> None:
    """`spread_diagnostics` imports statsmodels in a try/except and degrades to None.

    Undeclared, that degradation is silent: every ADF result is None and the stability
    score takes its penalty branch for every pair.
    """
    assert module in _packages(REQUIREMENTS), f"{module} is imported by {used_by} but undeclared"


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
