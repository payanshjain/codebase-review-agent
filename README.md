# Codebase Q&A RAG (MVP)

A beginner-friendly, production-style MVP for asking grounded questions about a local code repository.

## Stack (Path B — free-friendly)

| Component | Provider | Cost |
|-----------|----------|------|
| **Embeddings** | HuggingFace local (`BAAI/bge-small-en-v1.5`) | Free (runs on CPU) |
| **Answers** | Groq API (`llama-3.1-8b-instant`) | Free tier at [console.groq.com](https://console.groq.com) |
| **Vector DB** | ChromaDB (local disk) | Free |

## Project Structure

```text
codebase-qa-rag/
├─ app/
│  ├─ api/
│  │  └─ routes.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ providers.py
│  │  └─ provider_errors.py
│  ├─ ingestion/
│  ├─ index/
│  ├─ retrieval/
│  ├─ qa/
│  ├─ schemas/
│  └─ main.py
├─ data/chroma/
├─ .env.example
├─ requirements.txt
└─ run.py
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   First install downloads PyTorch + sentence-transformers (~1–2 GB). This is normal.
3. Get a **free Groq API key**: [https://console.groq.com/keys](https://console.groq.com/keys)
4. Copy env template and add your key:
   ```bash
   copy .env.example .env
   ```
   Edit `.env` and set `GROQ_API_KEY=gsk_...`
5. Run server:
   ```bash
   python run.py
   ```
6. Open docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## End-to-end test

**Step 1 — Index a repo** (`POST /index`)

```json
{
  "repo_path": "C:/Users/payan/Desktop/Codebase Agent"
}
```

The first index run downloads the embedding model (~130 MB). Indexing is **local** (no embedding API cost).

**Step 2 — Ask a question** (`POST /ask`)

```json
{
  "question": "How does repository indexing work in this project?"
}
```

## Current API

- `GET /health` → status, providers, model names
- `POST /index` → parse, chunk, embed (HuggingFace), store in Chroma
- `POST /ask` → **hybrid** retrieve (vector + BM25), answer via Groq
- `POST /review` → AI code review (bugs, security, complexity, refactoring)

### Code review example

```json
{
  "code": "def divide(a, b):\n    return a / b",
  "language": "python",
  "filename": "math_utils.py",
  "context": "Utility function used in payment calculations"
}
```

Returns structured `issues` with category, severity, title, description, and suggestions.

## Hybrid retrieval (vector + BM25)

| Method | Good at |
|--------|---------|
| **Vector** | Semantic similarity (“how is auth handled?”) |
| **BM25** | Exact tokens (`get_settings`, `POST /index`, class names) |
| **Fusion** | Combines both ranked lists into one top-k set |

Config in `.env`:

- `VECTOR_TOP_K` / `BM25_TOP_K` — how many candidates each method returns before fusion
- `RETRIEVAL_TOP_K` — final chunk count sent to Groq
- `HYBRID_FUSION_MODE=reciprocal_rerank` — standard RRF fusion

After this change, **re-run `POST /index`** so the docstore (`data/storage/`) is created for BM25.

## Why `app/core/providers.py` exists

Single place to swap models later:

- `configure_embedding_model()` → HuggingFace on CPU
- `create_llm()` → Groq chat model

## Important: re-index after provider change

If you change embedding models or enable hybrid retrieval for the first time, delete `data/chroma/` and `data/storage/`, then run `POST /index` again.

## Troubleshooting

### `503` — GROQ_API_KEY missing

Copy `.env.example` to `.env`, set a real Groq key, restart the server.  
`GET /health` should show `"configured": true`.

### Slow first `POST /index`

Normal. HuggingFace downloads the model and embeds every chunk on CPU. Use a small repo for testing.

### `401` — Invalid Groq key

Regenerate at [console.groq.com/keys](https://console.groq.com/keys) and update `.env`.

### `429` — Groq rate limit

Wait 30–60 seconds or use a smaller repo / lower `RETRIEVAL_TOP_K`.

### Out of memory during embedding

Set `EMBEDDING_DEVICE=cpu` in `.env` (default). Avoid indexing huge repos on low-RAM machines.
