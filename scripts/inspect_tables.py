import json
import pandas as pd

with open('experiments/retrieval/retrieval_summary_stage8b2.json', 'r') as f:
    r_sum = json.load(f)

print("=== TABLE 3 CONFIGURATIONS (from retrieval_summary_stage8b2.json) ===")
for cfg, d in r_sum['configurations'].items():
    print(f"\nConfig: {cfg} - {d['configuration_name']}")
    print(f"  Questions Evaluated: {d['questions_evaluated']}")
    print(f"  Correct & Cited: {d['correct_and_cited_percentage']:.1f}%")
    print(f"  Wrong: {d['wrong_answer_percentage']:.1f}%")
    print(f"  Correct Refusal: {d['correct_refusal_percentage']:.1f}%")
    print(f"  Avg Tokens In: {d['avg_tokens_in']:.1f}, Avg Tokens Out: {d['avg_tokens_out']:.1f}, Total: {d['avg_tokens_in'] + d['avg_tokens_out']:.1f}")
    print(f"  Avg TTFT: {d['avg_ttft_ms']:.1f}ms, Avg Total Latency: {d['avg_total_latency_ms']:.1f}ms")
    print(f"  Recall@5: {d['recall_at_5']:.4f}, MRR: {d['mrr']:.4f}")
