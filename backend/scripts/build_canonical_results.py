import pandas as pd
import numpy as np

# Load 119 load test rows
df_load = pd.read_csv('experiments/results.csv')

# Load 192 retrieval rows
df_ret = pd.read_csv('experiments/retrieval/retrieval_results_stage8b2.csv')

ret_rows = []
for idx, r in df_ret.iterrows():
    # Map answer_grade
    ag_raw = str(r['answer_grade']).strip()
    if ag_raw == 'correct_and_cited':
        ag = 'correct'
    elif ag_raw == 'wrong':
        ag = 'wrong'
    elif ag_raw == 'correct_refusal':
        ag = 'refused_correctly'
    elif ag_raw == 'wrong_refusal':
        ag = 'refused_wrongly'
    else:
        ag = ''

    # Config map
    cfg = str(r['configuration']).replace('config_', '')
    req_id = f"ret_8b2_{cfg}_{r['question_id']}"

    ret_rows.append({
        'request_id': req_id,
        'scenario': 'retrieval_eval',
        'source': 'stand-in',
        'start_time': '', # not measured
        'first_token_ms': r['ttft_ms'] if not pd.isna(r['ttft_ms']) else '',
        'total_ms': r['total_latency_ms'],
        'status': 'ok',
        'retries': int(r['correction_attempts']) if not pd.isna(r['correction_attempts']) else 0,
        'tokens_in': int(r['tokens_in']),
        'tokens_out': int(r['tokens_out']),
        'retrieval_setting': cfg,
        'answer_grade': ag
    })

df_ret_canonical = pd.DataFrame(ret_rows)
canonical_combined = pd.concat([df_load, df_ret_canonical], ignore_index=True)

print("Combined shape:", canonical_combined.shape)
print("Unique request IDs:", canonical_combined['request_id'].nunique(), "out of", len(canonical_combined))
print("Sources:", canonical_combined['source'].value_counts().to_dict())
print("Statuses:", canonical_combined['status'].value_counts().to_dict())
print("Answer grades:", canonical_combined['answer_grade'].value_counts(dropna=False).to_dict())
print("Scenarios:", canonical_combined['scenario'].value_counts().to_dict())
expected_cols = [
    'request_id', 'scenario', 'source', 'start_time', 'first_token_ms',
    'total_ms', 'status', 'retries', 'tokens_in', 'tokens_out',
    'retrieval_setting', 'answer_grade'
]
print("Columns match schema exactly:", list(canonical_combined.columns) == expected_cols)

# Save to submission/results.csv
canonical_combined.to_csv('submission/results.csv', index=False)
print("Saved successfully to submission/results.csv")
