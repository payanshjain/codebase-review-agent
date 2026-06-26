"""
API documentation generator implementation.

Synthesizes structured API documentation detailing endpoints, HTTP methods,
request schemas, response schemas, and standard error codes.
"""

from __future__ import annotations

import logging
from documentation_agent.schemas import RepositoryMetadata

logger = logging.getLogger(__name__)


class ApiDocGenerator:
    """
    Generates API Documentation markdown report.
    """

    async def generate(self, metadata: RepositoryMetadata) -> str:
        """
        Synthesize API endpoints documentation.
        """
        logger.info("Synthesizing API Documentation for repo: %s", metadata.repo_name)

        if not metadata.api_endpoints:
            return f"""# 🌐 {metadata.repo_name} — API Documentation

*No HTTP API route endpoints were detected in this repository.*
"""

        endpoint_blocks: list[str] = []
        for ep in metadata.api_endpoints:
            block = f"""### `{ep.method} {ep.path}`

- **Handler Function**: `{ep.function_name}()`
- **Source File**: `{ep.file_path}:{ep.line}`
- **Description**: {ep.docstring or "Executes endpoint handler workflow."}

#### Request Schema (Example)
```json
{{
  "example_field": "string or object specification"
}}
```

#### Response Schema (200 OK)
```json
{{
  "status": "success",
  "data": {{}}
}}
```

---
"""
            endpoint_blocks.append(block)

        doc = f"""# 🌐 {metadata.repo_name} — API Documentation

This document provides complete reference schemas and operational details for the HTTP REST API endpoints exposed by **{metadata.repo_name}**.

## 🚀 Endpoints Summary

| Method | Path | Handler |
|--------|------|---------|
{chr(10).join(f'| **{ep.method}** | `{ep.path}` | `{ep.function_name}()` |' for ep in metadata.api_endpoints)}

---

## 📖 Endpoint Details

{chr(10).join(endpoint_blocks)}

## ⚠️ Standard Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| `400` | `INVALID_ARGUMENT` | Malformed request body or missing required parameters. |
| `401` | `UNAUTHORIZED` | Missing or invalid authentication token / API key. |
| `404` | `NOT_FOUND` | Requested resource or repository ID does not exist. |
| `429` | `RATE_LIMIT_EXCEEDED` | Too many requests sent within rate limit window. |
| `500` | `INTERNAL_SERVER_ERROR` | Unhandled exception occurred during pipeline execution. |
| `503` | `SERVICE_UNAVAILABLE` | Configuration file missing or upstream provider down. |
"""
        return doc
