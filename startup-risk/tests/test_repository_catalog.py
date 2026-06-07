from __future__ import annotations

import pytest

from startup_risk.scanners.repository_catalog import (
    STARTER_REPOSITORIES,
    STRESS_REPOSITORIES,
    TEST_REPOSITORIES,
    repositories_for_ecosystem,
    repositories_for_suite,
    repositories_by_slug_list,
    repository_by_slug,
)


def test_scanner_repository_catalog_has_unique_github_repos():
    slugs = [repo.slug for repo in TEST_REPOSITORIES]
    urls = [repo.url for repo in TEST_REPOSITORIES]

    assert len(TEST_REPOSITORIES) == 17
    assert len(slugs) == len(set(slugs))
    assert len(urls) == len(set(urls))
    assert all(url.startswith("https://github.com/") for url in urls)


def test_scanner_repository_catalog_exposes_starter_and_stress_suites():
    assert repositories_for_suite("starter") == STARTER_REPOSITORIES
    assert repositories_for_suite("stress") == STRESS_REPOSITORIES
    assert len(STARTER_REPOSITORIES) == 9
    assert len(STRESS_REPOSITORIES) == 8


def test_scanner_repository_catalog_covers_core_ecosystems():
    expected_ecosystems = {
        "npm",
        "python",
        "cargo",
        "go",
        "bundler",
        "gradle",
        "composer",
        "nuget",
    }
    actual_ecosystems = {
        ecosystem
        for repo in TEST_REPOSITORIES
        for ecosystem in repo.ecosystems
    }

    assert expected_ecosystems <= actual_ecosystems


def test_scanner_repository_catalog_filters_by_ecosystem():
    cargo_repos = repositories_for_ecosystem("cargo")
    python_repos = repositories_for_ecosystem("python")
    npm_repos = repositories_for_ecosystem("NPM")

    assert {repo.slug for repo in cargo_repos} >= {
        "BurntSushi/ripgrep",
        "rust-lang/rust",
    }
    assert "pallets/click" in {repo.slug for repo in python_repos}
    assert "microsoft/vscode" in {repo.slug for repo in npm_repos}


def test_scanner_repository_catalog_looks_up_by_slug():
    repo = repository_by_slug("MICROSOFT/VSCODE")

    assert repo.slug == "microsoft/vscode"
    assert repo.suite == "starter"
    assert "package.json" in repo.expected_dependency_files


def test_scanner_repository_catalog_rejects_unknown_slug():
    with pytest.raises(KeyError):
        repository_by_slug("unknown/repo")


def test_scanner_repository_catalog_parses_comma_separated_slug_list():
    repos = repositories_by_slug_list("pallets/click, BurntSushi/ripgrep")

    assert [repo.slug for repo in repos] == ["pallets/click", "BurntSushi/ripgrep"]


def test_scanner_repository_catalog_includes_small_python_iteration_repo():
    repo = repository_by_slug("pallets/click")

    assert repo.suite == "starter"
    assert repo.primary_languages == ("Python",)
    assert repo.ecosystems == ("python",)
    assert repo.expected_dependency_files == ("pyproject.toml",)
    assert "low-token" in repo.notes
