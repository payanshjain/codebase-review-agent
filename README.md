# Codebase Q&A RAG Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Groq API](https://img.shields.io/badge/LLM-Groq-orange.svg)](https://groq.com)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-Chroma-green.svg)](https://www.trychroma.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful, production-style Retrieval-Augmented Generation (RAG) agent for your local codebase. This API allows you to index a local repository, ask grounded questions about its architecture, and run automated AI code reviews.

---

## 🚀 Features

- **Local Code Indexing**: Automatically parses, chunks, and embeds local code repositories.
- **Hybrid Retrieval System**: Combines Vector Search (Semantic) and BM25 (Keyword) using Reciprocal Rank Fusion (RRF) for highly accurate context retrieval.
- **AI Code Reviewer**: Run automated code reviews to detect bugs, security issues, and get refactoring suggestions.
- **Cost-Effective Stack**: Uses free local embeddings via HuggingFace and fast, free-tier LLM inference via the Groq API.

## 🛠️ Tech Stack

| Component | Technology | Cost |
|-----------|----------|------|
| **Embeddings** | HuggingFace local (`BAAI/bge-small-en-v1.5`) | Free (Runs locally on CPU) |
| **LLM Inference** | Groq API (`llama-3.1-8b-instant`) | Free tier at [console.groq.com](https://console.groq.com) |
| **Vector DB** | ChromaDB (Local Disk) | Free |
| **Framework** | FastAPI + Uvicorn | Free |

## 📁 Project Structure

```text
codebase-qa-rag/
├─ app/
│  ├─ api/          # API Routes (FastAPI)
│  ├─ core/         # Configuration & LLM/Embedding Providers
│  ├─ index/        # Vector Store Indexing Logic
│  ├─ ingestion/    # Code Parsing & Chunking
│  ├─ qa/           # Question-Answering Generation
│  ├─ retrieval/    # Hybrid Search (Vector + BM25)
│  ├─ review/       # AI Code Review Tools
│  └─ schemas/      # Pydantic Data Models
├─ data/            # Local DB Storage (ChromaDB & BM25 Docstore)
├─ scripts/         # Utility scripts
├─ .env.example     # Environment variable template
├─ requirements.txt # Python dependencies
└─ run.py           # Application Entry Point
```

## 💻 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- A [free Groq API Key](https://console.groq.com/keys)

### 2. Local Setup

Clone the repository and navigate to the project directory:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# 2. Install dependencies
# Note: The first installation will download PyTorch & sentence-transformers (~1-2 GB).
pip install -r requirements.txt

# 3. Configure Environment Variables
cp .env.example .env
```
Open the `.env` file and set your `GROQ_API_KEY`:
```ini
GROQ_API_KEY=gsk_your_api_key_here
```

### 3. Run the Server

Start the FastAPI application:
```bash
python run.py
```
View the interactive API documentation at: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 📡 API Reference & End-to-End Test

You can test the application via the interactive Swagger UI (`/docs`) or using tools like Postman/cURL.

### 1. Index a Repository
`POST /index`
```json
{
  "repo_path": "/path/to/your/local/codebase"
}
```
*Note: The first time you run this, it will download the HuggingFace embedding model (~130 MB). Indexing happens locally on your CPU.*

### 2. Ask a Question
`POST /ask`
```json
{
  "question": "How does hybrid retrieval work in this project?"
}
```

### 3. Run an AI Code Review
`POST /review`
```json
{
  "code": "def divide(a, b):\n    return a / b",
  "language": "python",
  "filename": "math_utils.py",
  "context": "Utility function used in payment calculations"
}
```
*Returns structured issues containing category, severity, description, and actionable suggestions.*

### 4. Health Check
`GET /health` -> Returns system status, loaded providers, and model configurations.

---

## 🔧 Configuration (.env)

The hybrid retrieval behavior can be adjusted in your `.env` file:
- `VECTOR_TOP_K`: Number of candidates vector search returns before fusion.
- `BM25_TOP_K`: Number of candidates keyword search returns before fusion.
- `RETRIEVAL_TOP_K`: Final number of chunks passed to the LLM.
- `HYBRID_FUSION_MODE`: Currently supports `reciprocal_rerank` (RRF).

*Important: If you change embedding models or enable hybrid retrieval for the first time, delete the `data/` directory and re-run `POST /index`.*

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **`503` GROQ_API_KEY missing** | Ensure you copied `.env.example` to `.env` and added your key. Restart the server. |
| **Slow first `POST /index`** | This is normal! HuggingFace is downloading the embedding model. Use a small repo for your first test. |
| **`401` Invalid Groq key** | Verify or regenerate your key at the Groq Console. |
| **`429` Groq rate limit** | Wait 30-60 seconds, or use a smaller repository / lower `RETRIEVAL_TOP_K`. |
| **Out of Memory on Indexing** | Ensure `EMBEDDING_DEVICE=cpu` is set in your `.env`. |

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## 📝 License
This project is [MIT](https://opensource.org/licenses/MIT) licensed.
