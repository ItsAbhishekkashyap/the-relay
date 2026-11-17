import csv
import json
from pathlib import Path
from collections import Counter

def audit_csv():
    csv_path = Path("experiments/retrieval/retrieval_results.csv")
    assert csv_path.exists(), "CSV file does not exist!"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"Total rows in CSV: {len(reader)}")
    assert len(reader) == 128, f"Expected 128 rows, got {len(reader)}"

    # Check question-config uniqueness
    pairs = [(r["question_id"], r["configuration"]) for r in reader]
    pair_counts = Counter(pairs)
    duplicates = [p for p, count in pair_counts.items() if count > 1]
    print(f"Duplicate (question_id, configuration) pairs: {len(duplicates)}")
    assert len(duplicates) == 0, f"Found duplicates: {duplicates}"

    # Check configuration coverage
    configs = sorted(list(set(r["configuration"] for r in reader)))
    print(f"Configurations present ({len(configs)}): {configs}")
    expected_configs = ["config_a_dense", "config_b_bm25", "config_c_hybrid", "config_d_full_hybrid"]
    assert configs == expected_configs, f"Unexpected configs: {configs}"

    for c in configs:
        count = sum(1 for r in reader if r["configuration"] == c)
        print(f"  {c}: {count} rows")
        assert count == 32, f"Expected 32 rows for {c}, got {count}"

    # Check questions coverage
    qids = sorted(list(set(r["question_id"] for r in reader)))
    print(f"Unique questions: {len(qids)}")
    assert len(qids) == 32, f"Expected 32 questions, got {len(qids)}"

    # Check answerable vs unanswerable
    ans_qids = set(r["question_id"] for r in reader if r["answerable"] == "True")
    unans_qids = set(r["question_id"] for r in reader if r["answerable"] == "False")
    print(f"Answerable questions: {len(ans_qids)}")
    print(f"Unanswerable questions: {len(unans_qids)}")
    assert len(ans_qids) == 26, f"Expected 26 answerable, got {len(ans_qids)}"
    assert len(unans_qids) == 6, f"Expected 6 unanswerable, got {len(unans_qids)}"

    # Verify summary metrics reproducibility
    with open("experiments/retrieval/retrieval_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)

    for c in configs:
        c_rows = [r for r in reader if r["configuration"] == c]
        ans_rows = [r for r in c_rows if r["answerable"] == "True"]
        unans_rows = [r for r in c_rows if r["answerable"] == "False"]

        # Recall@1
        r1_csv = sum(1 for r in ans_rows if r["rank_first_relevant"] == "1") / 26.0
        r1_sum = summary["configurations"][c]["recall_at_1"]
        assert round(r1_csv, 4) == r1_sum, f"Recall@1 mismatch for {c}: {r1_csv} vs {r1_sum}"

        # Recall@5
        r5_csv = sum(1 for r in ans_rows if r["rank_first_relevant"] in ["1", "2", "3", "4", "5"]) / 26.0
        r5_sum = summary["configurations"][c]["recall_at_5"]
        assert round(r5_csv, 4) == r5_sum, f"Recall@5 mismatch for {c}: {r5_csv} vs {r5_sum}"

        # Correct & Cited
        cac_csv = sum(1 for r in c_rows if r["answer_grade"] == "correct_and_cited")
        cac_sum = summary["configurations"][c]["correct_and_cited_count"]
        assert cac_csv == cac_sum, f"Correct & cited count mismatch for {c}: {cac_csv} vs {cac_sum}"

        # Wrong
        w_csv = sum(1 for r in c_rows if r["answer_grade"] == "wrong")
        w_sum = summary["configurations"][c]["wrong_count"]
        assert w_csv == w_sum, f"Wrong count mismatch for {c}: {w_csv} vs {w_sum}"

        # Correct Refusals
        cr_csv = sum(1 for r in unans_rows if r["answer_grade"] == "correct_refusal")
        cr_sum = summary["configurations"][c]["correct_refusal_count"]
        assert cr_csv == cr_sum, f"Correct refusal count mismatch for {c}: {cr_csv} vs {cr_sum}"

    print("All 128 rows and summary metrics verified 100% reproducible!")

if __name__ == "__main__":
    audit_csv()
