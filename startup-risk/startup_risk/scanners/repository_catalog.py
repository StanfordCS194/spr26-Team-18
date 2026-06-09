from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RepositorySuite = Literal["starter", "stress"]


@dataclass(frozen=True)
class ScannerTestRepository:
    slug: str
    url: str
    suite: RepositorySuite
    primary_languages: tuple[str, ...]
    ecosystems: tuple[str, ...]
    expected_dependency_files: tuple[str, ...]
    notes: str


TEST_REPOSITORIES: tuple[ScannerTestRepository, ...] = (
    ScannerTestRepository(
        slug="microsoft/vscode",
        url="https://github.com/microsoft/vscode",
        suite="starter",
        primary_languages=("TypeScript", "JavaScript"),
        ecosystems=("npm",),
        expected_dependency_files=("package.json", "package-lock.json"),
        notes="Large npm application with third-party notices and generated license metadata.",
    ),
    ScannerTestRepository(
        slug="django/django",
        url="https://github.com/django/django",
        suite="starter",
        primary_languages=("Python",),
        ecosystems=("python",),
        expected_dependency_files=("pyproject.toml",),
        notes="Mature Python project with useful non-lockfile dependency metadata.",
    ),
    ScannerTestRepository(
        slug="pallets/click",
        url="https://github.com/pallets/click",
        suite="starter",
        primary_languages=("Python",),
        ecosystems=("python",),
        expected_dependency_files=("pyproject.toml",),
        notes="Small mature Python package for low-token scanner iteration.",
    ),
    ScannerTestRepository(
        slug="BurntSushi/ripgrep",
        url="https://github.com/BurntSushi/ripgrep",
        suite="starter",
        primary_languages=("Rust",),
        ecosystems=("cargo",),
        expected_dependency_files=("Cargo.toml", "Cargo.lock"),
        notes="Focused Rust target for Cargo dependency extraction and registry license lookup.",
    ),
    ScannerTestRepository(
        slug="kubernetes/kubernetes",
        url="https://github.com/kubernetes/kubernetes",
        suite="starter",
        primary_languages=("Go",),
        ecosystems=("go",),
        expected_dependency_files=("go.mod", "go.sum"),
        notes="Large Go module target with substantial third-party dependency surface.",
    ),
    ScannerTestRepository(
        slug="rails/rails",
        url="https://github.com/rails/rails",
        suite="starter",
        primary_languages=("Ruby",),
        ecosystems=("bundler", "rubygems"),
        expected_dependency_files=("Gemfile", "Gemfile.lock", "*.gemspec"),
        notes="Ruby ecosystem target with Gemfile, lockfile, and gemspec patterns.",
    ),
    ScannerTestRepository(
        slug="spring-projects/spring-boot",
        url="https://github.com/spring-projects/spring-boot",
        suite="starter",
        primary_languages=("Java", "Kotlin"),
        ecosystems=("gradle", "maven"),
        expected_dependency_files=("build.gradle", "build.gradle.kts", "pom.xml"),
        notes="Java and Gradle multi-module project for JVM dependency parsing.",
    ),
    ScannerTestRepository(
        slug="apache/airflow",
        url="https://github.com/apache/airflow",
        suite="starter",
        primary_languages=("Python", "TypeScript"),
        ecosystems=("python", "npm"),
        expected_dependency_files=("pyproject.toml", "package.json"),
        notes="Mixed Python and frontend monorepo with realistic web-app dependency layout.",
    ),
    ScannerTestRepository(
        slug="laravel/framework",
        url="https://github.com/laravel/framework",
        suite="starter",
        primary_languages=("PHP",),
        ecosystems=("composer",),
        expected_dependency_files=("composer.json",),
        notes="PHP Composer target for basic PHP ecosystem coverage.",
    ),
    ScannerTestRepository(
        slug="elastic/kibana",
        url="https://github.com/elastic/kibana",
        suite="stress",
        primary_languages=("TypeScript", "JavaScript"),
        ecosystems=("npm",),
        expected_dependency_files=("package.json", "yarn.lock"),
        notes="Huge npm monorepo for performance and lockfile scale testing.",
    ),
    ScannerTestRepository(
        slug="gitlabhq/gitlabhq",
        url="https://github.com/gitlabhq/gitlabhq",
        suite="stress",
        primary_languages=("Ruby", "JavaScript", "Go"),
        ecosystems=("bundler", "npm", "go"),
        expected_dependency_files=("Gemfile", "Gemfile.lock", "package.json", "go.mod"),
        notes="Large mixed application with multiple dependency ecosystems.",
    ),
    ScannerTestRepository(
        slug="dotnet/aspnetcore",
        url="https://github.com/dotnet/aspnetcore",
        suite="stress",
        primary_languages=("C#", "JavaScript"),
        ecosystems=("nuget", "npm"),
        expected_dependency_files=("*.csproj", "packages.lock.json", "package.json"),
        notes=".NET and frontend target for NuGet coverage.",
    ),
    ScannerTestRepository(
        slug="apache/superset",
        url="https://github.com/apache/superset",
        suite="stress",
        primary_languages=("Python", "TypeScript"),
        ecosystems=("python", "npm"),
        expected_dependency_files=("pyproject.toml", "requirements*.txt", "package.json"),
        notes="Python and npm web application with realistic dependency complexity.",
    ),
    ScannerTestRepository(
        slug="grafana/grafana",
        url="https://github.com/grafana/grafana",
        suite="stress",
        primary_languages=("Go", "TypeScript"),
        ecosystems=("go", "npm"),
        expected_dependency_files=("go.mod", "go.sum", "package.json"),
        notes="Go backend plus TypeScript frontend for mixed dependency scanning.",
    ),
    ScannerTestRepository(
        slug="hashicorp/terraform",
        url="https://github.com/hashicorp/terraform",
        suite="stress",
        primary_languages=("Go",),
        ecosystems=("go",),
        expected_dependency_files=("go.mod", "go.sum"),
        notes="Focused Go module target with a production-grade dependency graph.",
    ),
    ScannerTestRepository(
        slug="rust-lang/rust",
        url="https://github.com/rust-lang/rust",
        suite="stress",
        primary_languages=("Rust", "Python", "JavaScript"),
        ecosystems=("cargo", "python", "npm"),
        expected_dependency_files=("Cargo.toml", "Cargo.lock"),
        notes="Very large Rust repository with subprojects and tooling complexity.",
    ),
    ScannerTestRepository(
        slug="electron/electron",
        url="https://github.com/electron/electron",
        suite="stress",
        primary_languages=("C++", "TypeScript", "Python"),
        ecosystems=("npm", "python"),
        expected_dependency_files=("package.json", "yarn.lock"),
        notes="Native code plus npm and Python tooling with third-party notices.",
    ),
)


STARTER_REPOSITORIES: tuple[ScannerTestRepository, ...] = tuple(
    repo for repo in TEST_REPOSITORIES if repo.suite == "starter"
)
STRESS_REPOSITORIES: tuple[ScannerTestRepository, ...] = tuple(
    repo for repo in TEST_REPOSITORIES if repo.suite == "stress"
)


def repositories_for_suite(suite: RepositorySuite) -> tuple[ScannerTestRepository, ...]:
    return tuple(repo for repo in TEST_REPOSITORIES if repo.suite == suite)


def repositories_for_ecosystem(ecosystem: str) -> tuple[ScannerTestRepository, ...]:
    normalized = ecosystem.lower()
    return tuple(
        repo
        for repo in TEST_REPOSITORIES
        if normalized in {item.lower() for item in repo.ecosystems}
    )


def repository_by_slug(slug: str) -> ScannerTestRepository:
    normalized = slug.lower()
    for repo in TEST_REPOSITORIES:
        if repo.slug.lower() == normalized:
            return repo
    raise KeyError(f"Unknown scanner test repository: {slug}")


def repositories_by_slug_list(slugs: str) -> tuple[ScannerTestRepository, ...]:
    """Return catalog repositories from a comma-separated slug list."""
    selected = tuple(
        repository_by_slug(slug.strip())
        for slug in slugs.split(",")
        if slug.strip()
    )
    if not selected:
        raise KeyError("No repository slugs were provided.")
    return selected
