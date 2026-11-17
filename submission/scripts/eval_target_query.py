import json
from pathlib import Path
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import HybridRetriever

query = "What BLEU score did the Transformer base model achieve on English-to-German?"
print(f"============================================================")
print(f"EVALUATING QUERY: {query}")
print(f"============================================================")

dense = DenseRetriever()
bm25 = BM25Retriever("data/indexes/bm25/bm25_index.json")
facts = FactStore("data/indexes/fact_store.db")
hybrid = HybridRetriever(dense_retriever=dense, bm25_retriever=bm25, fact_store=facts, rrf_k=60)

# 1. Dense retrieval alone
print("\n--- [1] DENSE RETRIEVAL ALONE (Top 10) ---")
dense_res = dense.query(query, top_k=10)
for i, r in enumerate(dense_res):
    has_273 = "27.3" in r.get("content", "")
    is_target = r.get("chunk_id") == "1706.03762v7_lc_0026"
    print(f"Rank {i+1:2d} | Score: {r.get('score', 0):.4f} | ID: {r.get('chunk_id')} | p.{r.get('page_number')} | sec: {r.get('section')} | target: {is_target} | 27.3: {has_273}")

# 2. BM25 retrieval alone
print("\n--- [2] BM25 RETRIEVAL ALONE (Top 10) ---")
bm25_res = bm25.query(query, top_k=10)
for i, r in enumerate(bm25_res):
    has_273 = "27.3" in r.get("content", "")
    is_target = r.get("chunk_id") == "1706.03762v7_lc_0026"
    print(f"Rank {i+1:2d} | Score: {r.get('score', 0):.4f} | ID: {r.get('chunk_id')} | p.{r.get('page_number')} | sec: {r.get('section')} | target: {is_target} | 27.3: {has_273}")

# 3. FactStore retrieval alone
print("\n--- [3] FACTSTORE RETRIEVAL ALONE (Top 10) ---")
fact_res = facts.search(query, top_k=10)
print(f"FactStore results returned: {len(fact_res)}")
for i, r in enumerate(fact_res):
    has_273 = "27.3" in r.get("content", "")
    is_target = r.get("chunk_id") == "1706.03762v7_lc_0026"
    print(f"Rank {i+1:2d} | Score: {r.get('score', 0):.4f} | ID: {r.get('chunk_id')} | target: {is_target} | 27.3: {has_273}")

# 4. Hybrid RRF at top_k = 5, 8, 10
print("\n--- [4] HYBRID RRF RETRIEVAL (Top 10) ---")
hybrid_res_10 = hybrid.retrieve(query, top_k=10)
for i, r in enumerate(hybrid_res_10):
    has_273 = "27.3" in r.get("content", "")
    is_target = r.get("chunk_id") == "1706.03762v7_lc_0026"
    channels = "+".join(r.get("retrieval_channels", []))
    print(f"Rank {r.get('rank', i+1):2d} | Score: {r.get('score', 0):.4f} | Channels: {channels:12s} | ID: {r.get('chunk_id')} | p.{r.get('page_number')} | sec: {r.get('section')} | target: {is_target} | 27.3: {has_273}")

print("\n--- SUMMARY OF TARGET CHUNK (1706.03762v7_lc_0026) ACROSS CHANNELS ---")
target_dense_rank = next((i+1 for i, r in enumerate(dense.query(query, top_k=50)) if r.get("chunk_id") == "1706.03762v7_lc_0026"), None)
target_bm25_rank = next((i+1 for i, r in enumerate(bm25.query(query, top_k=50)) if r.get("chunk_id") == "1706.03762v7_lc_0026"), None)
target_hybrid_rank = next((r.get("rank") for r in hybrid.retrieve(query, top_k=50) if r.get("chunk_id") == "1706.03762v7_lc_0026"), None)

print(f"Dense Rank: {target_dense_rank} (previously: >20)")
print(f"BM25 Rank: {target_bm25_rank} (previously: 12)")
print(f"Hybrid Rank: {target_hybrid_rank} (previously: 18)")

print(f"\nPresent in Top 5? {target_hybrid_rank is not None and target_hybrid_rank <= 5}")
print(f"Present in Top 8? {target_hybrid_rank is not None and target_hybrid_rank <= 8}")
print(f"Present in Top 10? {target_hybrid_rank is not None and target_hybrid_rank <= 10}")

facts.close()
