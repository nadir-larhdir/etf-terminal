"""Fixed-income domain layer: ETF objects, analytics, and relative-value models.

Intentionally empty of re-exports — importing from the package root would force every
submodule to load the ETF object, which cycles back through the shared primitives.
Import from the specific subpackage instead (`fixed_income.etfs`, `fixed_income.series`).
"""
