# Stage 6: Retrieval Evaluation Dataset Report

## 1. Executive Summary

This report documents the design, structure, and manual verification of the 32-question evaluation dataset developed for **Stage 6 — Retrieval Quality vs Cost Evaluation** of *The Relay (Vaani Research ML Engineering Assignment)*.

The dataset serves as the rigorous empirical ground truth to benchmark four distinct retrieval configurations:
1. **Configuration A:** Dense-only (ChromaDB `all-MiniLM-L6-v2`)
2. **Configuration B:** BM25-only (Rank-BM25 Lexical Index)
3. **Configuration C:** Hybrid Dense + BM25 (Reciprocal Rank Fusion with $k=60$)
4. **Configuration D:** Full Hybrid (Dense + BM25 + Structured FactStore via RRF)

---

## 2. Corpus Overview and Scope

The target corpus consists of the three research papers ingested during Stages 1 and 2:
1. **Vaswani et al. (2017)** — *Attention Is All You Need* (`1706.03762v7`)
   - 15 pages extracted, 50 LangChain recursive chunks, 4 indexed tables/structured facts.
2. **Défossez et al. (2024)** — *Moshi: a speech-text foundation model for real-time dialogue* (`2410.00037v1`)
   - 66 pages extracted, 220 LangChain recursive chunks, 11 indexed tables/structured facts.
3. **Hwang, Wang, & Gu (2025)** — *Dynamic Chunking for End-to-End Hierarchical Sequence Modeling* (`2507.07955v2`)
   - 39 pages extracted, 132 LangChain recursive chunks, 27 indexed tables/structured facts.
4. **Out-of-Domain / Unanswerable queries**
   - 6 carefully chosen questions covering prominent machine learning topics not discussed in the 3 assigned papers (e.g., LLaMA-3, BERT MLM/NSP, DDPM diffusion, FlashAttention tiling, DeepSeek-R1, and AlphaFold protein folding).

**Total Corpus Chunks:** 402 chunks.  
**Total Structured FactStore Records:** 110 records.

---

## 3. Dataset Distribution & Typology

The 32 questions are distributed across the 3 target papers and refusal sets as follows:

| Paper / Domain | Paper ID | Question Count | Percentage |
| :--- | :--- | :---: | :---: |
| *Attention Is All You Need* (Vaswani et al., 2017) | `1706.03762v7` | 9 | 28.1% |
| *Moshi: Speech-Text Foundation Model* (Défossez et al., 2024) | `2410.00037v1` | 9 | 28.1% |
| *Dynamic Chunking* (Hwang et al., 2025) | `2507.07955v2` | 8 | 25.0% |
| Out-of-Domain Refusals (Unanswerable) | *None* | 6 | 18.8% |
| **Total** | — | **32** | **100.0%** |

### Question Categorization

To expose the respective strengths and failure modes of dense embeddings, sparse keyword matching, and structured fact tables, seven distinct question categories were authored:

1. **Conceptual (5 questions):** Evaluates dense semantic understanding where query terms may differ from passage phrasings (e.g., why dot products are scaled by $\frac{1}{\sqrt{d_k}}$, full-duplex modeling concept).
2. **Exact Terminology (3 questions):** Tests sparse keyword precision on exact technical phrases (e.g., "Masked Multi-Head Attention", "Mimi", "BPIC").
3. **Numerical & Factual (5 questions):** Tests precision on specific numerical constants and model dimensions (e.g., $d_{\text{model}}=512$, $N=6$, 160 ms theoretical latency, frame rates).
4. **Architectural (4 questions):** Evaluates multi-sentence retrieval describing sub-layers, residual pathways, and hierarchical encoders/decoders.
5. **Multi-Passage Evidence (3 questions):** Requires evidence from distinct sections of the same paper to synthesize a complete factual answer (e.g., combining mathematical definitions with experimental ablation results).
6. **Tabular & Structured Facts (6 questions):** Specifically evaluates the `FactStore` structured SQLite index against Markdown tables (e.g., Table 1 complexity, Table 2 BLEU scores, Table 1 hyperparameters).
7. **Refusal / Out-of-Domain (6 questions):** Tests the system's deterministic gatekeeper and refusal mechanisms to avoid hallucination on unanswerable topics.

---

## 4. Evaluation Question Master Table

| ID | Category | Target Paper | Target Pages | Key Expected Verification Evidence |
| :--- | :--- | :---: | :---: | :--- |
| `q01` | Conceptual | `1706.03762v7` | p. 4–5 | Scaling factor $\frac{1}{\sqrt{d_k}}$ counteracts vanishing softmax gradients for large dot-products. |
| `q02` | Exact Terminology | `1706.03762v7` | p. 3–4 | "Masked Multi-Head Attention" in decoder stack. |
| `q03` | Numerical / Factual | `1706.03762v7` | p. 3, 5, 9 | $d_{\text{model}}=512, N=6, h=8, d_{ff}=2048$. |
| `q04` | Architectural | `1706.03762v7` | p. 3 | Multi-head self-attention + position-wise FFN with residual and LayerNorm. |
| `q05` | Tabular / Structured | `1706.03762v7` | p. 6 | Table 1: Self-attention has $O(n^2 \cdot d)$ complexity, $O(1)$ sequential operations, $O(1)$ path length. |
| `q06` | Tabular / Structured | `1706.03762v7` | p. 8 | Table 2: Transformer (big) achieves 28.4 BLEU on EN-DE and 41.8 BLEU on EN-FR. |
| `q07` | Multi-Passage | `1706.03762v7` | p. 6, 9 | Section 3.5 sinusoidal formula vs Table 3 row (E) learned positional embedding (PPL 4.92, BLEU 25.7). |
| `q08` | Numerical / Factual | `1706.03762v7` | p. 7–8 | Learning rate schedule formula and 4,000 warmup steps. |
| `q09` | Conceptual | `1706.03762v7` | p. 8 | Label smoothing $\epsilon_{ls}=0.1$ hurts perplexity but improves BLEU score. |
| `q10` | Exact Terminology | `2410.00037v1` | p. 6, 7 | "Mimi" neural audio codec and "Helium" 7B text LLM. |
| `q11` | Conceptual | `2410.00037v1` | p. 3, 7 | Parallel joint modeling of user and Moshi speech/text streams without turn-taking cascades. |
| `q12` | Architectural | `2410.00037v1` | p. 7, 13 | Temporal Transformer across time vs Depth Transformer across RVQ codebooks. |
| `q13` | Numerical / Factual | `2410.00037v1` | p. 3, 7 | 160 ms theoretical latency (80 ms frame + 80 ms delay) and ~200 ms empirical latency on L4 GPU. |
| `q14` | Tabular / Structured | `2410.00037v1` | p. 8 | Table 1: Helium pre-training uses 500k steps, ~4M token batch size, cosine LR with peak 3e-4. |
| `q15` | Tabular / Structured | `2410.00037v1` | p. 22 | Table 2: Helium 7B scores MMLU 50.8, ARCe 79.1, ARCc 50.0. |
| `q16` | Conceptual | `2410.00037v1` | p. 7, 11 | Inner Monologue predicts text tokens before generating audio to stabilize speech modeling. |
| `q17` | Multi-Passage | `2410.00037v1` | p. 8, 12 | Table 1 acoustic delay parameter (2 frames / 160 ms) and Section 3.3 synchronization rationale. |
| `q18` | Numerical / Factual | `2410.00037v1` | p. 7, 10 | Mimi operates at 12.5 Hz frame rate with 8 generative RVQ codebooks. |
| `q19` | Conceptual | `2507.07955v2` | p. 1, 2 | End-to-end learned semantic boundary prediction vs static or space-delimiter heuristics. |
| `q20` | Architectural | `2507.07955v2` | p. 2, 4–5 | H-Net encoder E0, dynamic chunk boundary router, Level 1 main backbone M, and decoder D0. |
| `q21` | Exact Terminology | `2507.07955v2` | p. 11 | BPIC = "Bytes Per Inferred Chunk", defined as $L_S / L_0$. |
| `q22` | Tabular / Structured | `2507.07955v2` | p. 11 | Table 1: H-Net (2-stage) with (3,3)-DC uses byte input, achieves 7.0 BPIC, 870M parameters. |
| `q23` | Tabular / Structured | `2507.07955v2` | p. 13 | Table 2: H-Net (2-stage) achieves 0.771 bpb on FineWeb-Edu vs SpaceByte 0.791 bpb. |
| `q24` | Architectural | `2507.07955v2` | p. 5, 9 | Causal convolutions and attention guarantee no future byte lookahead in streaming inference. |
| `q25` | Multi-Passage | `2507.07955v2` | p. 11, 13 | Dynamic Chunking (BPIC 7.0, 0.771 bpb) vs MambaByte (BPIC 1.0) and SpaceByte (BPIC 6.0, 0.791 bpb). |
| `q26` | Numerical / Factual | `2507.07955v2` | p. 11 | Compression ratio formula $L_S / L_0$ (ratio of raw sequence to coarsened sequence). |
| `q27` | Refusal / Out-of-Domain | *None* | — | LLaMA-3 context length and attention heads (Out of Domain). |
| `q28` | Refusal / Out-of-Domain | *None* | — | BERT MLM and NSP pre-training objectives (Out of Domain). |
| `q29` | Refusal / Out-of-Domain | *None* | — | DDPM reverse Markov chain transitions for image synthesis (Out of Domain). |
| `q30` | Refusal / Out-of-Domain | *None* | — | FlashAttention SRAM tiling and online softmax rescaling (Out of Domain). |
| `q31` | Refusal / Out-of-Domain | *None* | — | DeepSeek-R1 reinforcement learning reward signals (Out of Domain). |
| `q32` | Refusal / Out-of-Domain | *None* | — | AlphaFold evoformer blocks and MSA protein folding (Out of Domain). |

---

## 5. Passage Matching Rules & Verification Standards

To prevent subjective or loose semantic evaluations, passage relevance is strictly determined by deterministic metadata verification:
1. **Primary Match Criterion:** A retrieved chunk is counted as relevant if its `chunk_id` is explicitly in the verified `expected_chunk_ids` set for that question.
2. **Secondary Match Criterion:** A retrieved chunk is counted as supporting evidence if:
   - `paper_id` matches the expected paper identifier.
   - `page_number` matches one of the `expected_pages`.
   - `section` matches one of the `expected_sections`.
   - The text span contains the factual answer or key figures specified in `expected_answer`.
3. **Refusal Criterion:** For out-of-domain questions (`q27` through `q32`), any retrieval resulting in refusal by the workflow sufficiency check or explicit refusal node is marked as a **Correct Refusal**. If any out-of-domain question produces a factual claim with purported evidence, it is graded as an **Incorrect Refusal / Hallucination**.

This dataset is stored in machine-readable format at `experiments/retrieval/evaluation_questions.json`.
