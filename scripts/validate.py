"""Pre-flight validation — checks all critical imports and basic functionality."""
import sys
sys.path.insert(0, ".")

print("=== Import Check ===")
from app.index.build_index import build_and_store_index
from app.ast_analysis.skeleton import build_repository_skeleton
from app.retrieval.hybrid_retriever import create_hybrid_retriever, _build_bm25_retriever
from app.ingestion.chunker import chunk_documents_hybrid
from app.ast_analysis.extractor import extract_symbols
from app.ast_analysis.chunker import create_ast_chunks
from app.ast_analysis.languages import get_parser, is_ast_parseable
from llama_index.core.storage.docstore import SimpleDocumentStore
print("  All imports OK")

print("\n=== Extraction Test ===")
code = "def foo(): pass\nclass Bar:\n    def baz(self): return 1"
syms = extract_symbols(code, "python")
for s in syms:
    print(f"  {s.symbol_type}:{s.name}")
assert len(syms) >= 2, "Expected at least 2 symbols"

print("\n=== Chunker Test ===")
chunks = create_ast_chunks(syms, "test.py", "python", repo_id="test")
print(f"  {len(chunks)} chunks created")
assert all(c.metadata.get("chunk_strategy") == "ast" for c in chunks)
assert all(c.metadata.get("breadcrumb") for c in chunks)

print("\n=== SimpleDocumentStore Test ===")
ds = SimpleDocumentStore()
print(f"  {ds}")

print("\n=== ALL CHECKS PASSED ===")
