"""The local toolchain must match the one CI installs.

`mypy` only sees pandas' real types when `pandas-stubs` is installed. Without it pandas
is `Any`, every pandas call type-checks trivially, and `make check` passes locally while
CI fails on the same commit. These tests fail fast when the environment has drifted.
"""

from __future__ import annotations

import pathlib
from importlib.metadata import PackageNotFoundError, version

import pytest

REQUIREMENTS_DEV = pathlib.Path("requirements-dev.txt")


def _required_packages() -> list[str]:
    lines = REQUIREMENTS_DEV.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_the_dev_requirements_file_is_the_source_of_truth() -> None:
    assert REQUIREMENTS_DEV.exists()
    assert _required_packages()


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
