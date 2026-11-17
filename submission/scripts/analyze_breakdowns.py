import csv
import json

def analyze():
    with open("experiments/retrieval/retrieval_results.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    configs = ["config_a_dense", "config_b_bm25", "config_c_hybrid", "config_d_full_hybrid"]
    qtypes = sorted(list(set(r["question_type"] for r in rows)))

    print("==================================================================")
    print("ACCURACY (RELEVANT PASSAGE FOUND %) BY QUESTION TYPE")
    print("==================================================================")
    header = f"{'Question Type':<25} | " + " | ".join(f"{c:<12}" for c in configs)
    print(header)
    print("-" * len(header))

    for qt in qtypes:
        if qt == "refusal_out_of_domain":
            continue
        line = f"{qt:<25} | "
        cols = []
        for c in configs:
            sub = [r for r in rows if r["configuration"] == c and r["question_type"] == qt]
            found = sum(1 for r in sub if r["relevant_passage_found"] == "True")
            total = len(sub)
            pct = (found / total * 100) if total else 0
            cols.append(f"{found}/{total} ({pct:4.0f}%)")
        print(line + " | ".join(f"{col:<12}" for col in cols))

    print("\n==================================================================")
    print("DETAILED PER-QUESTION COMPARISON (Rank of First Relevant Passage)")
    print("==================================================================")
    qids = sorted(list(set(r["question_id"] for r in rows)))
    for qid in qids:
        sub = {r["configuration"]: r for r in rows if r["question_id"] == qid}
        qt = sub["config_a_dense"]["question_type"]
        ranks = []
        for c in configs:
            rank = sub[c]["rank_first_relevant"]
            grade = sub[c]["answer_grade"]
            ranks.append(f"{c.split('_')[1]}: r={rank or '-'} ({grade[:4]})")
        print(f"{qid:<38} [{qt:<20}] --> " + " | ".join(ranks))

if __name__ == "__main__":
    analyze()
