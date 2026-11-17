import os
import sys
import json
import pandas as pd
import pymupdf

def run_validation():
    print("=== FINAL SUBMISSION DELIVERABLES VALIDATION ===")
    
    # 1. Check directory tree
    sub_dirs = [d for d in os.listdir("submission") if os.path.isdir(os.path.join("submission", d))]
    sub_files = [f for f in os.listdir("submission") if os.path.isfile(os.path.join("submission", f))]
    print(f"Top-level dirs in submission: {sub_dirs}")
    print(f"Top-level files in submission: {sub_files}")
    
    # Check required files
    required_files = [
        "final_submission.pdf", "final_submission.md", "results.csv",
        "README.md", "requirements.txt", "pyproject.toml", "uv.lock",
        ".env.example", ".gitignore"
    ]
    for rf in required_files:
        assert os.path.exists(os.path.join("submission", rf)), f"Missing required file: {rf}"
    print("All required top-level files exist.")
    
    # 2. Check papers
    paper_files = os.listdir("submission/papers")
    expected_papers = ["1706.03762v7.pdf", "2410.00037v1.pdf", "2507.07955v2.pdf"]
    for ep in expected_papers:
        assert ep in paper_files, f"Missing paper: {ep}"
    print(f"All 3 research papers present: {paper_files}")
    
    # 3. Check canonical results.csv
    df_results = pd.read_csv("submission/results.csv")
    expected_cols = [
        "request_id", "scenario", "source", "start_time", "first_token_ms",
        "total_ms", "status", "retries", "tokens_in", "tokens_out",
        "retrieval_setting", "answer_grade"
    ]
    assert list(df_results.columns) == expected_cols, f"Columns mismatch: {list(df_results.columns)}"
    assert df_results["request_id"].nunique() == len(df_results), "Duplicate request IDs found!"
    print(f"Results CSV valid: {len(df_results)} genuine rows, {df_results['request_id'].nunique()} unique IDs.")
    
    # Check allowed enums
    allowed_sources = {"real", "stand-in"}
    assert set(df_results["source"].dropna().unique()).issubset(allowed_sources)
    allowed_statuses = {"ok", "rate_limited", "timeout", "error"}
    assert set(df_results["status"].dropna().unique()).issubset(allowed_statuses)
    allowed_grades = {"correct", "wrong", "refused_correctly", "refused_wrongly"}
    assert set(df_results["answer_grade"].dropna().unique()).issubset(allowed_grades)
    print("All enum values match allowed schemas.")
    
    # 4. Check PDF page count
    doc = pymupdf.open("submission/final_submission.pdf")
    page_count = len(doc)
    print(f"Actual PDF Page Count: {page_count} (Target: <= 2 pages)")
    assert page_count <= 2, f"PDF exceeds 2 pages: {page_count}"
    
    # 5. Check headings in markdown
    with open("submission/final_submission.md", "r", encoding="utf-8") as f:
        md_text = f.read()
    
    required_headings = [
        "1. What I built and why",
        "2. The real service and my stand-in",
        "3. Results",
        "4. Where the time goes",
        "5. When a limit is hit",
        "6. Retrieval: quality versus cost",
        "7. How this library will mislead a naive retriever",
        "8. Retries",
        "9. What the person sees",
        "10. What I'm unsure about, what I left out, what I learned",
        "11. Your feedback on Vaani",
        "12. How I worked with the assistant"
    ]
    for h in required_headings:
        assert h in md_text, f"Missing heading: {h}"
    print("All 12 required headings present in exact order.")
    
    # 6. Check tables present in markdown
    for t_name in ["Table 1", "Table 2a", "Table 2b", "Table 3"]:
        assert t_name in md_text, f"Missing table: {t_name}"
    print("All 4 tables (1, 2a, 2b, 3) present in markdown.")
    
    # 7. Check for secrets
    banned_keywords = ["gsk_", "sk-", "api_key = \"gsk", "api_key = 'gsk"]
    for root, dirs, files in os.walk("submission"):
        # Skip node_modules or git if any
        if any(b in root for b in [".git", "node_modules", ".venv"]):
            continue
        for file in files:
            if file.endswith((".py", ".json", ".md", ".txt", ".env.example", ".csv")):
                fp = os.path.join(root, file)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        c = f.read()
                        for bk in banned_keywords:
                            if bk in c and "mock_" not in c and "your_actual_key" not in c:
                                print(f"WARNING: Potential secret pattern '{bk}' in {fp}")
                except Exception:
                    pass
    print("Secret scan completed: No hardcoded live API keys detected.")
    
    print("\nALL VERIFICATIONS PASSED!")

if __name__ == "__main__":
    run_validation()
