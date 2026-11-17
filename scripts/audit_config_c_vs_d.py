import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
import sqlite3
from pathlib import Path
from app.retrieval.fact_store import FactStore
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.hybrid_retriever import HybridRetriever

def audit_config_c_vs_d():
    print("=" * 80)
    print("AUDITING FACTSTORE CONTRIBUTION IN CONFIG D")
    print("=" * 80)

    facts = FactStore("data/indexes/fact_store.db")
    dense = DenseRetriever()
    bm25 = BM25Retriever("data/indexes/bm25/bm25_index.json")

    with open("experiments/retrieval/evaluation_questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Hybrid instances
    retriever_c = HybridRetriever(dense_retriever=dense, bm25_retriever=bm25, fact_store=None)
    retriever_d = HybridRetriever(dense_retriever=dense, bm25_retriever=bm25, fact_store=facts)

    q_with_fact_hits = 0
    unique_fact_results = set()
    unique_relevant_fact_results = set()
    q_changed_top5 = 0
    q_improved_rank = 0
    q_introduced_irrelevant = 0
    q_diff_between_c_and_d = 0

    print(f"\nTotal questions: {len(questions)}")
    print(f"Total FactStore records in DB: {facts.count()}")

    for q in questions:
        qid = q["question_id"]
        q_text = q["question"]
        expected_cids = set(q.get("expected_chunk_ids", []))
        expected_pid = q.get("paper_id")

        # Direct search on FactStore
        fact_hits = facts.search(q_text, top_k=20)
        
        # Retrieval under Config C
        res_c = retriever_c.retrieve(q_text, top_k=5, candidate_k=20, enable_dense=True, enable_bm25=True, enable_facts=False)
        top5_c = [d["chunk_id"] for d in res_c]

        # Retrieval under Config D
        res_d = retriever_d.retrieve(q_text, top_k=5, candidate_k=20, enable_dense=True, enable_bm25=True, enable_facts=True)
        top5_d = [d["chunk_id"] for d in res_d]

        has_fact_hits = len(fact_hits) > 0
        if has_fact_hits:
            q_with_fact_hits += 1
            for h in fact_hits:
                cid = h["chunk_id"]
                unique_fact_results.add(cid)
                if cid in expected_cids:
                    unique_relevant_fact_results.add(cid)

        # Check if top 5 changed
        if top5_c != top5_d:
            q_changed_top5 += 1
            q_diff_between_c_and_d += 1
            print(f"\n[DIFF] {qid}:")
            print(f"   Config C top 5: {top5_c}")
            print(f"   Config D top 5: {top5_d}")

            # Check if rank improved for a relevant chunk
            rank_c = next((i+1 for i, cid in enumerate(top5_c) if cid in expected_cids), None)
            rank_d = next((i+1 for i, cid in enumerate(top5_d) if cid in expected_cids), None)

            if rank_d and (rank_c is None or rank_d < rank_c):
                q_improved_rank += 1
                print(f"   -> Improved rank from {rank_c} to {rank_d}")
            elif rank_c and (rank_d is None or rank_d > rank_c):
                q_introduced_irrelevant += 1
                print(f"   -> Degraded rank from {rank_c} to {rank_d}")
        else:
            # Top 5 identical
            pass

    print("\n" + "=" * 80)
    print("AUDIT FINDINGS:")
    print("=" * 80)
    print(f"1. Questions where FactStore returned >= 1 result: {q_with_fact_hits} / {len(questions)}")
    print(f"2. Total unique FactStore chunk results returned across all questions: {len(unique_fact_results)}")
    print(f"3. Unique relevant results contributed by FactStore: {len(unique_relevant_fact_results)}")
    print(f"4. Questions where FactStore changed the final top-5: {q_changed_top5}")
    print(f"5. Questions where FactStore improved the rank of a relevant passage: {q_improved_rank}")
    print(f"6. Questions where FactStore introduced irrelevant results: {q_introduced_irrelevant}")
    print(f"7. Questions where Config D performed differently from Config C: {q_diff_between_c_and_d}")
    print("=" * 80)

if __name__ == "__main__":
    audit_config_c_vs_d()
