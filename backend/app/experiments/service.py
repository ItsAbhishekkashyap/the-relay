"""Service for reading and aggregating saved empirical experiment data.

Enforces read-only access to historical CSV and JSON experiment artifacts.
Never generates fabricated fallback metrics. Clearly distinguishes real Groq
measurements from stand-in simulator runs, and Stage 6 retrieval from Stage 8B.2.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Base path for historical experiment artifacts
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_experiments_dir() -> Path:
    """Resolve experiments directory whether running from repo root or backend/."""
    candidates = [
        PROJECT_ROOT / "experiments",
        PROJECT_ROOT.parent / "experiments",
    ]
    for c in candidates:
        if c.exists():
            return c
    return PROJECT_ROOT / "experiments"


EXPERIMENTS_DIR = _resolve_experiments_dir()

# Canonical file paths
PATH_RESULTS_CSV = EXPERIMENTS_DIR / "results.csv"
PATH_LOAD_SUMMARY_JSON = EXPERIMENTS_DIR / "reports" / "load_experiment_summary.json"
PATH_GROQ_BASELINE_SUMMARY_JSON = (
    EXPERIMENTS_DIR / "real_service" / "reports" / "groq_baseline_summary.json"
)
PATH_RETRIEVAL_SUMMARY_S6_JSON = EXPERIMENTS_DIR / "retrieval" / "retrieval_summary.json"
PATH_RETRIEVAL_SUMMARY_S8B2_JSON = (
    EXPERIMENTS_DIR / "retrieval" / "retrieval_summary_stage8b2.json"
)
PATH_RETRIEVAL_RESULTS_S6_CSV = EXPERIMENTS_DIR / "retrieval" / "retrieval_results.csv"
PATH_RETRIEVAL_RESULTS_S8B2_CSV = (
    EXPERIMENTS_DIR / "retrieval" / "retrieval_results_stage8b2.csv"
)


def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Safely read JSON file without throwing, returning None on missing/malformed file."""
    if not path.is_file():
        logger.warning(f"Experiment JSON file not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error(f"Failed to read experiment JSON file {path}: {exc}")
        return None


def _safe_read_csv(path: Path) -> Optional[List[Dict[str, Any]]]:
    """Safely read CSV file into list of dicts without throwing."""
    if not path.is_file():
        logger.warning(f"Experiment CSV file not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as exc:
        logger.error(f"Failed to read experiment CSV file {path}: {exc}")
        return None


def get_experiments_overview() -> Dict[str, Any]:
    """Return point-in-time catalog of available empirical experiment datasets."""
    results_csv = _safe_read_csv(PATH_RESULTS_CSV)
    load_sum = _safe_read_json(PATH_LOAD_SUMMARY_JSON)
    ret_sum_s6 = _safe_read_json(PATH_RETRIEVAL_SUMMARY_S6_JSON)
    ret_sum_s8b2 = _safe_read_json(PATH_RETRIEVAL_SUMMARY_S8B2_JSON)

    return {
        "status": "available",
        "description": "Empirical characterization and evaluation datasets across Stages 4, 5, 6, and 8B.2.",
        "pricing_basis": {
            "prompt_tokens_per_million_usd": 0.15,
            "completion_tokens_per_million_usd": 0.60,
        },
        "datasets": {
            "load_testing": {
                "available": load_sum is not None,
                "total_records": len(results_csv) if results_csv else 0,
                "summary_available": load_sum is not None,
                "scenarios": [
                    {
                        "id": "real_baseline",
                        "name": "Real Groq Baseline",
                        "source": "real",
                        "provider": "groq (cloud)",
                        "model": "openai/gpt-oss-120b",
                        "total_requests": 20,
                    },
                    {
                        "id": "calibration_baseline",
                        "name": "Simulator Calibration Baseline",
                        "source": "simulator",
                        "provider": "custom-stand-in-simulator",
                        "model": "simulator/mock-model-v1",
                        "total_requests": 20,
                    },
                    {
                        "id": "scenario_a_steady",
                        "name": "Scenario A: Steady Load (15 RPM)",
                        "source": "simulator",
                        "total_requests": 15,
                    },
                    {
                        "id": "scenario_b_burst",
                        "name": "Scenario B: Burst Load (Concurrency 3)",
                        "source": "simulator",
                        "total_requests": 12,
                    },
                    {
                        "id": "scenario_c_overload",
                        "name": "Scenario C: Sustained Overload & Queue Recovery",
                        "source": "simulator",
                        "total_requests": 19,
                    },
                    {
                        "id": "scenario_d_halved_rpm",
                        "name": "Scenario D: Halved RPM Limit Throttling",
                        "source": "simulator",
                        "total_requests": 23,
                    },
                    {
                        "id": "scenario_e_daily_budget",
                        "name": "Scenario E: Daily Token/Request Budget Exhaustion",
                        "source": "simulator",
                        "total_requests": 10,
                    },
                ],
            },
            "retrieval_benchmarks": {
                "stage6": {
                    "stage": "Stage 6 Initial Evaluation",
                    "available": ret_sum_s6 is not None,
                    "date": "2026-11-12",
                    "questions_count": 32,
                    "answerable_count": 26,
                    "unanswerable_count": 6,
                    "configurations_count": len(ret_sum_s6.get("configurations", {}))
                    if ret_sum_s6
                    else 0,
                    "configurations": list(ret_sum_s6.get("configurations", {}).keys())
                    if ret_sum_s6
                    else [],
                },
                "stage8b2": {
                    "stage": "Stage 8B.2 Table Caption Preservation & Top-K Scaling",
                    "available": ret_sum_s8b2 is not None,
                    "date": "2026-11-12",
                    "questions_count": 32,
                    "answerable_count": 26,
                    "unanswerable_count": 6,
                    "configurations_count": len(ret_sum_s8b2.get("configurations", {}))
                    if ret_sum_s8b2
                    else 0,
                    "configurations": list(ret_sum_s8b2.get("configurations", {}).keys())
                    if ret_sum_s8b2
                    else [],
                },
            },
        },
    }


def get_load_experiments() -> Dict[str, Any]:
    """Return load testing results across the 5 traffic scenarios and calibration baselines."""
    load_sum = _safe_read_json(PATH_LOAD_SUMMARY_JSON)
    if not load_sum:
        return {
            "available": False,
            "error": "Load experiment summary file is unavailable or missing on disk.",
            "file": str(PATH_LOAD_SUMMARY_JSON),
        }

    raw_csv = _safe_read_csv(PATH_RESULTS_CSV) or []

    # Map scenario metadata
    scenario_metadata = {
        "real_baseline": {
            "display_name": "Real Groq Baseline",
            "source_type": "real",
            "provider": "Groq Cloud API (openai/gpt-oss-120b)",
            "description": "20 requests (10 non-streaming + 10 streaming) calibrated against real Groq infrastructure.",
            "traffic_pattern": "Sequential requests with 2.5s pacing, staying safely within 30 RPM limit.",
        },
        "calibration_baseline": {
            "display_name": "Simulator Calibration Baseline",
            "source_type": "simulator",
            "provider": "Local HTTP Stand-in Simulator",
            "description": "20 requests against simulator calibrated using exact lognormal equations.",
            "traffic_pattern": "Identical sequential pacing to evaluate simulator fidelity against real Groq.",
        },
        "scenario_a_steady": {
            "display_name": "Scenario A: Steady Load",
            "source_type": "simulator",
            "provider": "TrafficManager -> Simulator",
            "description": "15 requests offered at steady 15 RPM (1 request every 4 seconds) against 30 RPM limit.",
            "traffic_pattern": "Uniform inter-arrival interval (4.0s). Tests steady-state queue without contention.",
        },
        "scenario_b_burst": {
            "display_name": "Scenario B: Burst Traffic",
            "source_type": "simulator",
            "provider": "TrafficManager -> Simulator",
            "description": "12 concurrent requests injected simultaneously in a single burst wave.",
            "traffic_pattern": "Step burst of 12 requests. Tests FIFO queue serialization under max concurrency 3.",
        },
        "scenario_c_overload": {
            "display_name": "Scenario C: Sustained Overload",
            "source_type": "simulator",
            "provider": "TrafficManager -> Simulator",
            "description": "15 concurrent requests injected against max queue capacity 5 and 2s timeout, followed by 4 recovery probes.",
            "traffic_pattern": "15 concurrent flood requests (testing queue saturation and 504 timeouts) + 4 recovery probes.",
        },
        "scenario_d_halved_rpm": {
            "display_name": "Scenario D: Halved RPM Throttling",
            "source_type": "simulator",
            "provider": "TrafficManager -> Simulator",
            "description": "20 requests offered at 45 RPM into an artificially halved limit of 15 RPM (30s window), followed by 3 recovery probes.",
            "traffic_pattern": "Sustained offer rate of 45 RPM with 15 RPM ceiling. Tests 429 rate limit triggers and backoff retries.",
        },
        "scenario_e_daily_budget": {
            "display_name": "Scenario E: Daily Budget Exhaustion",
            "source_type": "simulator",
            "provider": "TrafficManager -> Simulator",
            "description": "10 requests with simulated daily budget cap of 5 RPD, followed by admin reset and recovery probes.",
            "traffic_pattern": "5 requests consume full daily budget; subsequent 3 requests trigger 429 quota exhaustion; 2 probes confirm recovery post-reset.",
        },
    }

    scenarios_data = []
    for sc_id, sc_stats in load_sum.get("scenarios", {}).items():
        meta = scenario_metadata.get(
            sc_id,
            {
                "display_name": sc_id.replace("_", " ").title(),
                "source_type": "simulator" if sc_id != "real_baseline" else "real",
                "provider": "Unknown",
                "description": "",
                "traffic_pattern": "",
            },
        )

        total_req = sc_stats.get("total_requests", 0)
        status_counts = sc_stats.get("status_counts", {})
        ok_count = status_counts.get("ok", 0)
        rate_limited_count = status_counts.get("rate_limited", 0)
        timeout_count = status_counts.get("timeout", 0)
        error_count = status_counts.get("error", 0)

        # Rate percentages
        rate_limited_pct = (
            round((rate_limited_count / total_req) * 100.0, 2) if total_req > 0 else 0.0
        )
        timeout_pct = round((timeout_count / total_req) * 100.0, 2) if total_req > 0 else 0.0
        error_pct = round((error_count / total_req) * 100.0, 2) if total_req > 0 else 0.0

        # Cost per 1k answers
        token_usage = sc_stats.get("token_usage", {})
        prompt_tokens = token_usage.get("total_prompt_tokens", 0)
        comp_tokens = token_usage.get("total_completion_tokens", 0)
        est_cost_usd = sc_stats.get("estimated_cost_usd", 0.0)
        cost_per_1000 = (
            round((est_cost_usd / ok_count) * 1000.0, 4) if ok_count > 0 else 0.0
        )

        tokens_per_answer = (
            round((prompt_tokens + comp_tokens) / ok_count, 1) if ok_count > 0 else 0.0
        )

        scenarios_data.append(
            {
                "scenario_id": sc_id,
                "name": meta["display_name"],
                "source": meta["source_type"],
                "provider": meta["provider"],
                "description": meta["description"],
                "traffic_pattern": meta["traffic_pattern"],
                "total_requests": total_req,
                "successful_requests": ok_count,
                "failed_requests": total_req - ok_count,
                "status_breakdown": {
                    "ok": ok_count,
                    "rate_limited_429": rate_limited_count,
                    "timeout_504": timeout_count,
                    "server_error_500": error_count,
                },
                "success_rate_pct": sc_stats.get("success_rate_pct", 0.0),
                "rate_limited_pct": rate_limited_pct,
                "timeout_pct": timeout_pct,
                "error_pct": error_pct,
                "total_retries": sc_stats.get("total_retries", 0),
                "avg_retries_per_request": sc_stats.get("avg_retries_per_request", 0.0),
                "total_latency_ms": sc_stats.get("total_latency_ms", {}),
                "ttft_ms": sc_stats.get("ttft_ms", {}),
                "all_turnaround_ms": sc_stats.get(
                    "all_requests_turnaround_latency", {}
                ).get("statistics", {}),
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": comp_tokens,
                    "total_tokens": token_usage.get("total_tokens", 0),
                    "tokens_per_answer": tokens_per_answer,
                },
                "estimated_cost_usd": est_cost_usd,
                "cost_per_1000_answers_usd": cost_per_1000,
            }
        )

    # Real vs Simulator Calibration Comparison
    comparison = None
    real_sc = next((s for s in scenarios_data if s["scenario_id"] == "real_baseline"), None)
    sim_sc = next(
        (s for s in scenarios_data if s["scenario_id"] == "calibration_baseline"), None
    )
    if real_sc and sim_sc:
        real_med = real_sc["total_latency_ms"].get("median", 0.0)
        sim_med = sim_sc["total_latency_ms"].get("median", 0.0)
        delta_pct = (
            round(abs(sim_med - real_med) / real_med * 100.0, 2) if real_med > 0 else 0.0
        )

        real_ttft = real_sc["ttft_ms"].get("median", 0.0)
        sim_ttft = sim_sc["ttft_ms"].get("median", 0.0)
        ttft_delta_pct = (
            round(abs(sim_ttft - real_ttft) / real_ttft * 100.0, 2) if real_ttft > 0 else 0.0
        )

        comparison = {
            "metric": "Latency Calibration Fidelity",
            "real_groq_median_ms": real_med,
            "simulator_median_ms": sim_med,
            "difference_ms": round(sim_med - real_med, 2),
            "difference_pct": delta_pct,
            "real_groq_ttft_median_ms": real_ttft,
            "simulator_ttft_median_ms": sim_ttft,
            "ttft_difference_ms": round(sim_ttft - real_ttft, 2),
            "ttft_difference_pct": ttft_delta_pct,
            "conclusion": (
                f"Simulator reproduces real Groq median non-streaming latency within {delta_pct}% "
                f"and streaming TTFT within {ttft_delta_pct}%."
            ),
        }

    return {
        "available": True,
        "total_records": len(raw_csv),
        "scenarios": scenarios_data,
        "calibration_comparison": comparison,
    }


def get_retrieval_experiments(version: Optional[str] = None) -> Dict[str, Any]:
    """Return retrieval benchmark evaluations across Stage 6 and Stage 8B.2."""
    sum_s6 = _safe_read_json(PATH_RETRIEVAL_SUMMARY_S6_JSON)
    sum_s8b2 = _safe_read_json(PATH_RETRIEVAL_SUMMARY_S8B2_JSON)

    if not sum_s6 and not sum_s8b2:
        return {
            "available": False,
            "error": "Retrieval experiment summary files are missing on disk.",
        }

    response: Dict[str, Any] = {
        "available": True,
        "methodology_note": (
            "Stage 6 evaluated initial chunking without caption/table context. Stage 8B.2 evaluated "
            "caption-preserved chunking and top-k expansion (k=5, 8, 10). Both evaluations tested "
            "the identical 32-question evaluation suite (26 answerable, 6 unanswerable) across the 3 target papers."
        ),
        "denominators": {
            "total_questions": 32,
            "answerable_questions": 26,
            "unanswerable_questions": 6,
            "recall_and_mrr_basis": "Answerable questions only (denominator: 26)",
            "accuracy_and_refusal_basis": "All questions (denominator: 32)",
        },
    }

    if version in (None, "all", "stage6") and sum_s6:
        response["stage6"] = {
            "stage_name": "Stage 6 Initial Retrieval Benchmark",
            "date": sum_s6.get("evaluation_timestamp", "2026-11-12"),
            "configurations": list(sum_s6.get("configurations", {}).values()),
        }

    if version in (None, "all", "stage8b2") and sum_s8b2:
        response["stage8b2"] = {
            "stage_name": "Stage 8B.2 Table Caption Preservation & Top-K Scaling",
            "metadata": sum_s8b2.get("metadata", {}),
            "configurations": list(sum_s8b2.get("configurations", {}).values()),
        }

    # Generate direct comparative matrix across matching configs
    if sum_s6 and sum_s8b2:
        cfg_s6 = sum_s6.get("configurations", {})
        cfg_s8b2 = sum_s8b2.get("configurations", {})

        comparisons = [
            {
                "configuration_name": "Dense-only (ChromaDB)",
                "k": 5,
                "stage6": {
                    "recall_at_5": cfg_s6.get("config_a_dense", {}).get("recall_at_5"),
                    "mrr": cfg_s6.get("config_a_dense", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s6.get("config_a_dense", {}).get(
                        "correct_and_cited_pct"
                    ),
                    "wrong_pct": cfg_s6.get("config_a_dense", {}).get("wrong_pct"),
                    "latency_mean_ms": cfg_s6.get("config_a_dense", {}).get(
                        "retrieval_latency_mean_ms"
                    ),
                    "cost_per_1000_usd": cfg_s6.get("config_a_dense", {}).get(
                        "cost_per_1000_answers_usd"
                    ),
                },
                "stage8b2": {
                    "recall_at_5": cfg_s8b2.get("config_a_dense_k5", {}).get("recall_at_5"),
                    "mrr": cfg_s8b2.get("config_a_dense_k5", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s8b2.get("config_a_dense_k5", {}).get(
                        "correct_and_cited_percentage"
                    ),
                    "wrong_pct": cfg_s8b2.get("config_a_dense_k5", {}).get(
                        "wrong_answer_percentage"
                    ),
                    "latency_mean_ms": cfg_s8b2.get("config_a_dense_k5", {}).get(
                        "avg_retrieval_latency_ms"
                    ),
                    "cost_per_1000_usd": cfg_s8b2.get("config_a_dense_k5", {}).get(
                        "cost_per_1000_queries_usd"
                    ),
                },
                "delta": {
                    "recall_at_5_improvement": round(
                        (
                            cfg_s8b2.get("config_a_dense_k5", {}).get("recall_at_5", 0)
                            - cfg_s6.get("config_a_dense", {}).get("recall_at_5", 0)
                        )
                        * 100.0,
                        2,
                    ),
                    "correct_and_cited_improvement_pct": round(
                        cfg_s8b2.get("config_a_dense_k5", {}).get(
                            "correct_and_cited_percentage", 0
                        )
                        - cfg_s6.get("config_a_dense", {}).get("correct_and_cited_pct", 0),
                        2,
                    ),
                },
            },
            {
                "configuration_name": "BM25-only (Rank-BM25)",
                "k": 5,
                "stage6": {
                    "recall_at_5": cfg_s6.get("config_b_bm25", {}).get("recall_at_5"),
                    "mrr": cfg_s6.get("config_b_bm25", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s6.get("config_b_bm25", {}).get(
                        "correct_and_cited_pct"
                    ),
                    "wrong_pct": cfg_s6.get("config_b_bm25", {}).get("wrong_pct"),
                    "latency_mean_ms": cfg_s6.get("config_b_bm25", {}).get(
                        "retrieval_latency_mean_ms"
                    ),
                    "cost_per_1000_usd": cfg_s6.get("config_b_bm25", {}).get(
                        "cost_per_1000_answers_usd"
                    ),
                },
                "stage8b2": {
                    "recall_at_5": cfg_s8b2.get("config_b_bm25_k5", {}).get("recall_at_5"),
                    "mrr": cfg_s8b2.get("config_b_bm25_k5", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s8b2.get("config_b_bm25_k5", {}).get(
                        "correct_and_cited_percentage"
                    ),
                    "wrong_pct": cfg_s8b2.get("config_b_bm25_k5", {}).get(
                        "wrong_answer_percentage"
                    ),
                    "latency_mean_ms": cfg_s8b2.get("config_b_bm25_k5", {}).get(
                        "avg_retrieval_latency_ms"
                    ),
                    "cost_per_1000_usd": cfg_s8b2.get("config_b_bm25_k5", {}).get(
                        "cost_per_1000_queries_usd"
                    ),
                },
                "delta": {
                    "recall_at_5_improvement": round(
                        (
                            cfg_s8b2.get("config_b_bm25_k5", {}).get("recall_at_5", 0)
                            - cfg_s6.get("config_b_bm25", {}).get("recall_at_5", 0)
                        )
                        * 100.0,
                        2,
                    ),
                    "correct_and_cited_improvement_pct": round(
                        cfg_s8b2.get("config_b_bm25_k5", {}).get(
                            "correct_and_cited_percentage", 0
                        )
                        - cfg_s6.get("config_b_bm25", {}).get("correct_and_cited_pct", 0),
                        2,
                    ),
                },
            },
            {
                "configuration_name": "Hybrid (Dense + BM25)",
                "k": 5,
                "stage6": {
                    "recall_at_5": cfg_s6.get("config_c_hybrid", {}).get("recall_at_5"),
                    "mrr": cfg_s6.get("config_c_hybrid", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s6.get("config_c_hybrid", {}).get(
                        "correct_and_cited_pct"
                    ),
                    "wrong_pct": cfg_s6.get("config_c_hybrid", {}).get("wrong_pct"),
                    "latency_mean_ms": cfg_s6.get("config_c_hybrid", {}).get(
                        "retrieval_latency_mean_ms"
                    ),
                    "cost_per_1000_usd": cfg_s6.get("config_c_hybrid", {}).get(
                        "cost_per_1000_answers_usd"
                    ),
                },
                "stage8b2": {
                    "recall_at_5": cfg_s8b2.get("config_c_hybrid_k5", {}).get("recall_at_5"),
                    "mrr": cfg_s8b2.get("config_c_hybrid_k5", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s8b2.get("config_c_hybrid_k5", {}).get(
                        "correct_and_cited_percentage"
                    ),
                    "wrong_pct": cfg_s8b2.get("config_c_hybrid_k5", {}).get(
                        "wrong_answer_percentage"
                    ),
                    "latency_mean_ms": cfg_s8b2.get("config_c_hybrid_k5", {}).get(
                        "avg_retrieval_latency_ms"
                    ),
                    "cost_per_1000_usd": cfg_s8b2.get("config_c_hybrid_k5", {}).get(
                        "cost_per_1000_queries_usd"
                    ),
                },
                "delta": {
                    "recall_at_5_improvement": round(
                        (
                            cfg_s8b2.get("config_c_hybrid_k5", {}).get("recall_at_5", 0)
                            - cfg_s6.get("config_c_hybrid", {}).get("recall_at_5", 0)
                        )
                        * 100.0,
                        2,
                    ),
                    "correct_and_cited_improvement_pct": round(
                        cfg_s8b2.get("config_c_hybrid_k5", {}).get(
                            "correct_and_cited_percentage", 0
                        )
                        - cfg_s6.get("config_c_hybrid", {}).get("correct_and_cited_pct", 0),
                        2,
                    ),
                },
            },
            {
                "configuration_name": "Full Hybrid (Dense + BM25 + FactStore)",
                "k": 5,
                "stage6": {
                    "recall_at_5": cfg_s6.get("config_d_full_hybrid", {}).get("recall_at_5"),
                    "mrr": cfg_s6.get("config_d_full_hybrid", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s6.get("config_d_full_hybrid", {}).get(
                        "correct_and_cited_pct"
                    ),
                    "wrong_pct": cfg_s6.get("config_d_full_hybrid", {}).get("wrong_pct"),
                    "latency_mean_ms": cfg_s6.get("config_d_full_hybrid", {}).get(
                        "retrieval_latency_mean_ms"
                    ),
                    "cost_per_1000_usd": cfg_s6.get("config_d_full_hybrid", {}).get(
                        "cost_per_1000_answers_usd"
                    ),
                },
                "stage8b2": {
                    "recall_at_5": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                        "recall_at_5"
                    ),
                    "mrr": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get("mrr"),
                    "correct_and_cited_pct": cfg_s8b2.get(
                        "config_d_full_hybrid_k5", {}
                    ).get("correct_and_cited_percentage"),
                    "wrong_pct": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                        "wrong_answer_percentage"
                    ),
                    "latency_mean_ms": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                        "avg_retrieval_latency_ms"
                    ),
                    "cost_per_1000_usd": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                        "cost_per_1000_queries_usd"
                    ),
                },
                "delta": {
                    "recall_at_5_improvement": round(
                        (
                            cfg_s8b2.get("config_d_full_hybrid_k5", {}).get("recall_at_5", 0)
                            - cfg_s6.get("config_d_full_hybrid", {}).get("recall_at_5", 0)
                        )
                        * 100.0,
                        2,
                    ),
                    "correct_and_cited_improvement_pct": round(
                        cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                            "correct_and_cited_percentage", 0
                        )
                        - cfg_s6.get("config_d_full_hybrid", {}).get(
                            "correct_and_cited_pct", 0
                        ),
                        2,
                    ),
                },
            },
        ]
        response["stage6_vs_stage8b2_comparison"] = comparisons

        # Top-k scaling summary in Stage 8B.2
        response["top_k_scaling_stage8b2"] = [
            {
                "k": 5,
                "recall": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get("recall_at_5"),
                "mrr": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get("mrr"),
                "correct_and_cited_pct": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                    "correct_and_cited_percentage"
                ),
                "wrong_pct": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                    "wrong_answer_percentage"
                ),
                "avg_context_tokens": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                    "avg_context_tokens"
                ),
                "cost_per_1000_usd": cfg_s8b2.get("config_d_full_hybrid_k5", {}).get(
                    "cost_per_1000_queries_usd"
                ),
            },
            {
                "k": 8,
                "recall": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get("recall_at_8"),
                "mrr": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get("mrr"),
                "correct_and_cited_pct": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get(
                    "correct_and_cited_percentage"
                ),
                "wrong_pct": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get(
                    "wrong_answer_percentage"
                ),
                "avg_context_tokens": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get(
                    "avg_context_tokens"
                ),
                "cost_per_1000_usd": cfg_s8b2.get("config_d_full_hybrid_k8", {}).get(
                    "cost_per_1000_queries_usd"
                ),
            },
            {
                "k": 10,
                "recall": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get("recall_at_10"),
                "mrr": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get("mrr"),
                "correct_and_cited_pct": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get(
                    "correct_and_cited_percentage"
                ),
                "wrong_pct": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get(
                    "wrong_answer_percentage"
                ),
                "avg_context_tokens": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get(
                    "avg_context_tokens"
                ),
                "cost_per_1000_usd": cfg_s8b2.get("config_d_full_hybrid_k10", {}).get(
                    "cost_per_1000_queries_usd"
                ),
            },
        ]

    return response
