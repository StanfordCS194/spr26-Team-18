"""Static scanners."""

from startup_risk.scanners.repository_catalog import (
    STARTER_REPOSITORIES,
    STRESS_REPOSITORIES,
    TEST_REPOSITORIES,
    ScannerTestRepository,
    repositories_for_ecosystem,
    repositories_for_suite,
    repository_by_slug,
)

__all__ = [
    "ScannerTestRepository",
    "STARTER_REPOSITORIES",
    "STRESS_REPOSITORIES",
    "TEST_REPOSITORIES",
    "repositories_for_ecosystem",
    "repositories_for_suite",
    "repository_by_slug",
]
