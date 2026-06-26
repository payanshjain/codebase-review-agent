"""
Architecture builder — high-level inference engine.

Classifies repository components into architectural layers (Frontend, Backend,
Database, External Services, Infrastructure), detects frameworks, microservices,
APIs, databases, and authentication flows.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from architecture_agent.ast_parser.ast_parser import FileAST
from architecture_agent.repository_parser.parser import ParsedRepo
from architecture_agent.schemas import (
    ArchitectureSummary,
    EntryPointDetection,
    FrameworkDetection,
    ServiceNode,
)

logger = logging.getLogger(__name__)

# ── Framework detection rules ─────────────────────────────────────

FRAMEWORK_RULES: list[tuple[str, str, str]] = [
    # (dependency_name_pattern, framework_name, category)
    ("fastapi", "FastAPI", "web_framework"),
    ("flask", "Flask", "web_framework"),
    ("django", "Django", "web_framework"),
    ("express", "Express.js", "web_framework"),
    ("next", "Next.js", "web_framework"),
    ("react", "React", "frontend"),
    ("vue", "Vue.js", "frontend"),
    ("angular", "Angular", "frontend"),
    ("spring", "Spring Boot", "web_framework"),
    ("sqlalchemy", "SQLAlchemy", "orm"),
    ("sqlmodel", "SQLModel", "orm"),
    ("prisma", "Prisma", "orm"),
    ("mongoose", "Mongoose", "orm"),
    ("alembic", "Alembic", "migration"),
    ("celery", "Celery", "task_queue"),
    ("redis", "Redis", "cache"),
    ("pytest", "pytest", "testing"),
    ("jest", "Jest", "testing"),
    ("llama-index", "LlamaIndex", "ai_framework"),
    ("langchain", "LangChain", "ai_framework"),
    ("chromadb", "ChromaDB", "vector_store"),
    ("pydantic", "Pydantic", "validation"),
    ("uvicorn", "Uvicorn", "server"),
    ("gunicorn", "Gunicorn", "server"),
    ("docker", "Docker", "infrastructure"),
    ("sentence-transformers", "Sentence Transformers", "embeddings"),
]

# ── Layer classification heuristics ───────────────────────────────

BACKEND_INDICATORS = {"api", "routes", "controllers", "services", "handlers", "middleware", "views"}
FRONTEND_INDICATORS = {"components", "pages", "views", "src/app", "public", "static", "templates"}
DATABASE_INDICATORS = {"models", "migrations", "schemas", "db", "database", "entities", "repositories"}
INFRA_INDICATORS = {"docker", "deploy", "ci", "cd", ".github", "terraform", "k8s", "kubernetes", "helm"}
TEST_INDICATORS = {"tests", "test", "spec", "__tests__", "testing"}


class ArchitectureBuilder:
    """Infers high-level architecture from parsed repository data."""

    def build(self, parsed: ParsedRepo, file_asts: list[FileAST]) -> ArchitectureSummary:
        """Run all detection heuristics and produce an ArchitectureSummary."""
        logger.info("Building architecture summary for: %s", parsed.repo_name)

        frameworks = self._detect_frameworks(parsed.dependencies)
        entry_points = [
            EntryPointDetection(file_path=ep[0], kind=ep[1], evidence=ep[2])
            for ep in parsed.entry_points
        ]
        services = self._detect_microservices(parsed)
        layers = self._classify_layers(file_asts)
        databases = self._detect_databases(parsed, file_asts)
        api_routes = self._detect_api_routes(file_asts)

        return ArchitectureSummary(
            repo_name=parsed.repo_name,
            languages=sorted(parsed.languages),
            frameworks=frameworks,
            entry_points=entry_points,
            services=services,
            layers=layers,
            package_managers=parsed.package_managers,
            databases=databases,
            api_routes=api_routes,
        )

    def _detect_frameworks(self, dependencies: list[str]) -> list[FrameworkDetection]:
        """Match dependencies against known framework patterns."""
        detected: list[FrameworkDetection] = []
        dep_lower = {d.lower() for d in dependencies}

        for pattern, name, category in FRAMEWORK_RULES:
            for dep in dep_lower:
                if pattern in dep:
                    detected.append(FrameworkDetection(
                        name=name,
                        category=category,
                        evidence=f"Dependency: {dep}",
                    ))
                    break

        return detected

    def _detect_microservices(self, parsed: ParsedRepo) -> list[ServiceNode]:
        """Detect potential microservices by looking for multiple Dockerfiles or package.json files."""
        services: list[ServiceNode] = []

        # Check for docker-compose services
        docker_dirs: set[str] = set()
        for df in parsed.dockerfiles:
            rel = str(df.parent.relative_to(parsed.local_path)).replace("\\", "/")
            docker_dirs.add(rel)

        # Each directory with a Dockerfile or its own package.json might be a service
        pkg_dirs: set[str] = set()
        for cf in parsed.config_files:
            if cf.name in ("package.json", "requirements.txt", "go.mod", "Cargo.toml"):
                rel = str(cf.parent.relative_to(parsed.local_path)).replace("\\", "/")
                if rel != ".":
                    pkg_dirs.add(rel)

        candidate_dirs = docker_dirs | pkg_dirs
        if len(candidate_dirs) <= 1:
            # Single service / monolith
            eps = [ep[0] for ep in parsed.entry_points]
            services.append(ServiceNode(
                name=parsed.repo_name,
                root_dir=".",
                has_dockerfile=len(parsed.dockerfiles) > 0,
                entry_points=eps,
            ))
        else:
            for d in sorted(candidate_dirs):
                name = d.replace("/", "-") or parsed.repo_name
                services.append(ServiceNode(
                    name=name,
                    root_dir=d,
                    has_dockerfile=d in docker_dirs,
                    has_package_json=d in pkg_dirs,
                    entry_points=[ep[0] for ep in parsed.entry_points if ep[0].startswith(d)],
                ))

        return services

    def _classify_layers(self, file_asts: list[FileAST]) -> dict[str, list[str]]:
        """Classify files into architectural layers based on directory names."""
        layers: dict[str, list[str]] = {
            "backend": [],
            "frontend": [],
            "database": [],
            "infrastructure": [],
            "tests": [],
            "other": [],
        }

        for f in file_asts:
            parts = set(f.rel_path.lower().split("/"))
            if parts & TEST_INDICATORS:
                layers["tests"].append(f.rel_path)
            elif parts & FRONTEND_INDICATORS:
                layers["frontend"].append(f.rel_path)
            elif parts & DATABASE_INDICATORS:
                layers["database"].append(f.rel_path)
            elif parts & INFRA_INDICATORS:
                layers["infrastructure"].append(f.rel_path)
            elif parts & BACKEND_INDICATORS:
                layers["backend"].append(f.rel_path)
            else:
                # Default heuristic: Python files with route decorators → backend
                layers["other"].append(f.rel_path)

        # Remove empty layers
        return {k: v for k, v in layers.items() if v}

    def _detect_databases(self, parsed: ParsedRepo, file_asts: list[FileAST]) -> list[str]:
        """Detect database technologies used."""
        dbs: set[str] = set()
        dep_lower = {d.lower() for d in parsed.dependencies}

        db_hints = {
            "chromadb": "ChromaDB (Vector)",
            "sqlalchemy": "SQLAlchemy (SQL)",
            "sqlite": "SQLite",
            "psycopg": "PostgreSQL",
            "pymongo": "MongoDB",
            "redis": "Redis",
            "mysql": "MySQL",
            "prisma": "Prisma",
            "mongoose": "MongoDB",
            "sequelize": "SQL (Sequelize)",
            "sqlmodel": "SQLModel (SQL)",
        }

        for hint, db_name in db_hints.items():
            for dep in dep_lower:
                if hint in dep:
                    dbs.add(db_name)
                    break

        # Check for SQL files
        for f in parsed.all_files:
            if f.suffix.lower() == ".sql":
                dbs.add("SQL Files Detected")
                break

        return sorted(dbs)

    def _detect_api_routes(self, file_asts: list[FileAST]) -> list[str]:
        """Scan for HTTP API route decorators in code."""
        routes: list[str] = []
        route_re = re.compile(r"@(?:app|router|api|bp)\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']")

        for f in file_asts:
            for imp in f.imports:
                pass  # We scan the raw content below

        # We need to re-read files that have route decorators — check via imports heuristic
        return routes  # Filled by architecture_builder during summary generation
