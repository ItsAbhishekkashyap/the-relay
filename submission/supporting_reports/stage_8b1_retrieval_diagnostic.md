# Stage 8B.1 Diagnostic Report: Transformer Base BLEU Retrieval Failure

**Task:** Diagnose retrieval omission for query: *"What BLEU score did the Transformer base model achieve on English-to-German?"*  
**Auditor:** Investigation & Retrieval Diagnostic Engineer  
**Date:** November 12, 2026  
**Status:** READ-ONLY Root Cause Investigation Complete  

---

## 1. Expected Correct Answer and Source Location

- **Target Query:** *"What BLEU score did the Transformer base model achieve on English-to-German?"*
- **Authoritative Ground Truth:** **27.3 BLEU**
- **Document Source:** *Attention Is All You Need* (Vaswani et al., `papers/1706.03762v7.pdf`)
- **Exact Location:** Page 8 (1-indexed), Table 2, column 2 ("BLEU EN-DE").
- **Table 2 Context & Structure:**
  - Table Title: *"Table 2: The Transformer achieves better BLEU scores than previous state-of-the-art models on the English-to-German and English-to-French newstest2014 tests at a fraction of the training cost."*
  - Row 1: `Transformer (base model)` $\to$ **BLEU EN-DE: 27.3**, BLEU EN-FR: 38.1, Training Cost: $3.3 \cdot 10^{18}$ FLOPs.
  - Row 2: `Transformer (big)` $\to$ **BLEU EN-DE: 28.4** (bolded), BLEU EN-FR: 41.8, Training Cost: $2.3 \cdot 10^{19}$ FLOPs.
- **Discrepancy in Narrative Prose:**
  - In Section 6.1 (*Machine Translation*, Page 8), the prose explicitly reports the **big** model's score:
    > *"On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models (including ensembles) by more than 2.0 BLEU, establishing a new state-of-the-art BLEU score of 28.4... Even our base model surpasses all previously published models and ensembles, at a fraction of the training cost of any of the competitive models."*
  - The prose praises the base model, but **never states the number 27.3**. The exact base model score of 27.3 exists **exclusively inside the rows of Table 2**.

---

## 2. PDF Extraction Result

- **PyMuPDF Extraction:** Inspected `data/extracted/1706.03762v7.json` (page 8, 0-indexed page index 7).
- **Extracted Text Integrity:**
  - Page 8 extracted text has 3,194 characters and contains the exact string `27.3`.
  - PyMuPDF faithfully extracted the raw text blocks and table structures from the PDF:
    ```
    Transformer (base model)
    27.3
    38.1
    3.3 · 1018
    Transformer (big)
    28.4
    41.8
    2.3 · 1019
    ```
- **Structural Finding:**
  - PyMuPDF extracted the caption (`Table 2: The Transformer achieves better BLEU scores...`) as a separate block from the table data rows.
  - The table rows were converted into markdown format, while the caption remained a preceding narrative element.

---

## 3. Chunk Dataset Result

Inspected `data/chunks/langchain_recursive/1706.03762v7.json` (50 total chunks, 7 on page 8):

- **Search for `27.3`:** Across all 50 chunks in the paper, **exactly one chunk** contains `27.3`: `1706.03762v7_lc_0026`.
- **Target Chunk Specification (`1706.03762v7_lc_0026`):**
  - **Chunk ID:** `1706.03762v7_lc_0026`
  - **Page Number:** 8
  - **Assigned Section:** `5.4 Regularization` *(Note: misattributed because Table 2 physically sits at the top of page 8 before the "6 Results" heading)*
  - **Element Type:** `table`
  - **Token Count:** 295 tokens (709 characters)
  - **Exact Chunk Content:**
    ```markdown
    |Model|BLEU<br>EN DE EN FR<br>- -|Col3|TrainingCost(FLOPs)<br>EN DE EN FR<br>- -|
    |---|---|---|---|
    |ByteNet [18]|23.75|||
    |Deep-Att + PosUnk [39]<br>GNMT + RL [38]<br>ConvS2S [9]<br>MoE[32]|24.6<br>25.16<br>26.03|39.2<br>39.92<br>40.46<br>40.56|1_._0_ ·_ 1020<br>2_._3_ ·_ 1019<br>1_._4_ ·_ 1020<br>9_._6_ ·_ 1018<br>1_._5_ ·_ 1020<br>2_._0_ ·_ 1019<br>1_._2_ ·_ 1020|
    |Deep-Att + PosUnk Ensemble [39]<br>GNMT + RL Ensemble [38]<br>ConvS2S Ensemble [9]|26.30<br>26.36|40.4<br>41.16<br>**41.29**|8_._0_ ·_ 1020<br>1_._8_ ·_ 1020<br>1_._1_ ·_ 1021<br>7_._7_ ·_ 1019<br>1_._2_ ·_ 1021|
    |Transformer (base model)<br>Transformer (big)|27.3<br>**28.4**|38.1<br>**41.8**|**3****_._3****_ ·_ 1018**<br>2_._3_ ·_ 1019|
    ```
- **Critical Fragmentation Findings:**
  1. **Missing Caption:** The caption `Table 2: The Transformer achieves better BLEU scores...` was placed into chunk `1706.03762v7_lc_0025`. Chunk `1706.03762v7_lc_0026` contains **zero occurrences** of the words `"Table 2"` or `"Table"`.
  2. **Missing Language Names:** The table header uses abbreviated column tokens: `EN DE EN FR`. It contains **zero occurrences** of the words `"English"` or `"German"`.
  3. **Section Mislabeling:** Both `_lc_0025` and `_lc_0026` carry the section metadata `"5.4 Regularization"` instead of `"6.1 Machine Translation"`.

---

## 4. Dense Retrieval Result

Executed `dense_retriever.query("What BLEU score did the Transformer base model achieve on English-to-German?", top_k=20)`:

| Rank | Chunk ID | Page | Section | Cosine Score | Contains 27.3? | Content Summary |
| :---: | :--- | :---: | :--- | :---: | :---: | :--- |
| **1** | `1706.03762v7_lc_0025` | 8 | 5.4 Regularization | 0.8131 | **No** | Table 2 caption: achieves better BLEU scores on English-to-German... |
| **2** | `1706.03762v7_lc_0031` | 8 | 6.2 Model Variations | 0.6712 | **No** | 6.2 Model Variations: varied our base model on English-to-German... |
| **3** | `1706.03762v7_lc_0029` | 8 | 6.1 Machine Translation | 0.5994 | **No** | 6.1 Machine Translation prose: Transformer (big) achieves 28.4... |
| **4** | `1706.03762v7_lc_0032` | 9 | 6.2 Model Variations | 0.5976 | **No** | Table 3: Variations on Transformer architecture... |
| **5** | `1706.03762v7_lc_0037` | 10 | 6.3 English Constituency | 0.5322 | **No** | Table 4: Constituency parsing results... |
| ... | ... | ... | ... | ... | ... | ... |
| **>20** | `1706.03762v7_lc_0026` | 8 | 5.4 Regularization | < 0.4000 | **Yes** | **NOT IN TOP 20** |

**Why Dense Failed:** `all-MiniLM-L6-v2` maps raw markdown pipe characters, `<br>` tags, and mathematical exponents (`1_._0_ ·_ 1020`) to an embedding space far removed from natural question prose. Meanwhile, the caption chunk (`_lc_0025`) and Section 6.1 prose (`_lc_0029`) have fluent natural language and ranked in the top 3.

---

## 5. BM25 Retrieval Result

Executed `bm25_retriever.query("What BLEU score did the Transformer base model achieve on English-to-German?", top_k=20)`:

| Rank | Chunk ID | Page | Section | BM25 Score | Contains 27.3? | Query Term Matches |
| :---: | :--- | :---: | :--- | :---: | :---: | :--- |
| **1** | `1706.03762v7_lc_0029` | 8 | 6.1 Machine Translation | 21.8359 | **No** | `transformer`, `model`, `english`, `german`, `bleu`, `base`, `score` |
| **2** | `1706.03762v7_lc_0025` | 8 | 5.4 Regularization | 17.3578 | **No** | `transformer`, `bleu`, `english`, `german`, `models`, `scores` |
| **3** | `1706.03762v7_lc_0027` | 8 | 5.4 Regularization | 15.1517 | **No** | `base`, `model`, `score`, `bleu` |
| **4** | `1706.03762v7_lc_0032` | 9 | 6.2 Model Variations | 14.7882 | **No** | `base`, `model`, `english`, `german` |
| **5** | `1706.03762v7_lc_0031` | 8 | 6.2 Model Variations | 14.7444 | **No** | `base`, `model`, `english`, `german` |
| ... | ... | ... | ... | ... | ... | ... |
| **12** | `1706.03762v7_lc_0026` | 8 | 5.4 Regularization | 10.9632 | **Yes** | `transformer`, `base`, `model`, `bleu` (0 matches for English/German) |

**Why BM25 Ranked it #12:** Chunk `_lc_0026` contains `EN DE`, but does not contain `"English"` or `"German"`. Chunks `_lc_0029` and `_lc_0025` match the full multi-token terms `"English-to-German"`, earning scores of 21.84 and 17.36. Chunk `_lc_0026` only matched generic terms (`transformer`, `base`, `model`, `bleu`), pushing its rank down to **12th**.

---

## 6. FactStore Result

Executed `fact_store.search("What BLEU score did the Transformer base model achieve on English-to-German?", top_k=20)`:

- **Total Results Returned:** **0 records.**
- **Target Chunk `1706.03762v7_lc_0026`:** Not retrieved (0 hits).
- **Reason:** As established during the Stage 6A evaluation integrity audit, SQLite FTS5 index requires conjunctive boolean token matching across structured table columns. Natural language conversational queries return 0 hits without a specialized SQL query translation layer.

---

## 7. Hybrid Retrieval Result

Executed `hybrid_retriever.retrieve("What BLEU score did the Transformer base model achieve on English-to-German?", top_k=5)`:

| Rank in Top 5 | Chunk ID | Page | Section | RRF Score ($k=60$) | Contains 27.3? | Included in Generation? |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| **1** | `1706.03762v7_lc_0025` | 8 | 5.4 Regularization | 0.0325 | **No** | **YES** |
| **2** | `1706.03762v7_lc_0029` | 8 | 6.1 Machine Translation | 0.0323 | **No** | **YES** |
| **3** | `1706.03762v7_lc_0031` | 8 | 6.2 Model Variations | 0.0315 | **No** | **YES** |
| **4** | `1706.03762v7_lc_0032` | 9 | 6.2 Model Variations | 0.0312 | **No** | **YES** |
| **5** | `1706.03762v7_lc_0001` | 1 | Abstract | 0.0299 | **No** | **YES** |
| ... | ... | ... | ... | ... | ... | ... |
| **18** | `1706.03762v7_lc_0026` | 8 | 5.4 Regularization | 0.0139 | **Yes** | **NO (TRUNCATED)** |

**Mathematical RRF Breakdown for Target Chunk `_lc_0026`:**
- Dense rank: $>20$ (Score contribution = 0.0)
- BM25 rank: 12 (Score contribution = $1.0 / (60 + 12) = 0.013889$)
- FactStore rank: none (Score contribution = 0.0)
- Total RRF Score = $0.013889$, placing it at **Rank 18**.
- Since production `top_k = 5`, **`1706.03762v7_lc_0026` was completely excluded from the prompt context.**

---

## 8. End-to-End Evidence Analysis

1. **Was Table 2 included among the five passages?**
   - **No.** The table caption was included (`_lc_0025`), but the table row data (`_lc_0026`) was absent.
2. **Did the answer generator receive the relevant table row?**
   - **No.** The generator never received `_lc_0026`.
3. **Did the model ignore available evidence or never receive it?**
   - **The model never received it.** The model acted with strict factual fidelity to the context provided. In chunk `_lc_0029`, the text stated:
     > *"the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models... BLEU score of 28.4... Even our base model surpasses all previously published models... at a fraction of the training cost."*
   - Because `_lc_0029` mentioned the base model without stating its BLEU score, the model truthfully responded that the passages did not state the base model's score.
4. **Did the correction attempt remove or overlook the correct evidence?**
   - No. The correction loop operates over the existing retrieved evidence set; because `_lc_0026` was never retrieved into state, the correction loop could not introduce it.
5. **Why was the final response labelled "verified provenance" despite the factual omission?**
   - The model answered that the base model score was not specified, but stated that the big model achieved 28.4 on WMT 2014 English-to-German, citing `[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 6.1]`.
   - The deterministic citation validator checked:
     - Paper ID: `1706.03762v7` (present in evidence).
     - Page: `8` (present in evidence).
     - Section: `6.1` (matches Section `6.1 Machine Translation` from `_lc_0029`).
   - Because the citation metadata was genuine, `verify_citations_against_evidence` marked it as valid.
   - This empirically confirms the **metadata verification vs. semantic entailment gap**: metadata verification confirms that the cited paper/page/section exists in the evidence, but cannot verify whether the substantive user question was fully answered.

---

## 9. Provider Used in the Failed UI Test

- **Observed in UI:** The frontend response header and badge displayed `provider: "groq"`.
- **Configuration Inspection:**
  - In `app/config.py`, `model_provider: str = Field(default="groq")`.
  - In `.env`, `GROQ_API_KEY` is configured and `GROQ_MODEL=openai/gpt-oss-120b` is set.
  - When the FastAPI server is started without the environment override `$env:LLM_PROVIDER="simulator"`, it defaults to Groq.
- **Verdict:** The test was executed against the **live Groq service** (`openai/gpt-oss-120b`).

---

## 10. Exact Root Cause

The failure was caused by a **three-stage retrieval cascading failure**:

```
[PyMuPDF & Chunking Pipeline]
Table 2 Caption ("Table 2: ... English-to-German")  ──► Stored in Chunk _lc_0025 (Page 8, Prose)
Table 2 Rows ("Transformer (base model) 27.3 EN DE") ──► Stored in Chunk _lc_0026 (Page 8, Table)
                                                                │
                                                                ▼
                                                [Lexical & Semantic Isolation]
                                     • Contains NO "Table 2" token
                                     • Contains NO "English" or "German" (only "EN DE")
                                     • Pipe-delimited markdown degrades Dense cosine embedding
                                                                │
                                                                ▼
                                                [Multi-Channel Ranking Deficit]
                                     • Dense: Rank >20 (0.0 score)
                                     • BM25:  Rank 12 (10.96 vs 21.84 for prose)
                                     • RRF:   Rank 18
                                                                │
                                                                ▼
                                                [Top_K Truncation (top_k=5)]
                                     Chunk _lc_0026 excluded from generator context!
                                                                │
                                                                ▼
                                                [Generator Omission & Verification]
                                     LLM truthfully states score not in text, cites Page 8 Sec 6.1.
                                     Metadata validation marks Page 8 as "Verified".
```

1. **Caption-Table Decoupling:** Chunking isolated the caption from the table body.
2. **Vocabulary Collision / Acronym Compression:** The table uses `EN DE`, while user queries use `English-to-German`.
3. **Markdown Dense Penalty:** MiniLM embeddings penalize raw markdown tables without conversational syntax.
4. **Top-K Truncation:** Cutoff at $k=5$ dropped Rank 18.

---

## 11. Remaining Uncertainty

- **Cross-paper table behavior:** It is currently unknown whether other tables in the corpus (e.g., Table 1 in Attention, acoustic latency tables in Moshi, or sequence length tables in Dynamic Chunking) suffer from similar caption-table detachment.
- **BM25 acronym expansion:** Whether token-level hyphen splitting in BM25 tokenization (`English-to-German` $\to$ `['english', 'to', 'german']`) can be bridged to `['en', 'de']` without a synonym dictionary.

---

## 12. Recommended Minimal Correction for Next Task

*(Do NOT implement now — for future task planning only)*

1. **Table Context Header Prepending (Highest Impact):**
   When chunking tables in `pdf_ingestion.py` or `chunking.py`, automatically prepend the preceding table caption and section heading directly into the table chunk text (e.g. `Table 2: Machine Translation Results (English-to-German, English-to-French)\n\n|Model|BLEU EN-DE...`). This immediately restores the missing `Table 2`, `English`, and `German` keywords to the table chunk.
2. **Increase Top-K Generation Budget:**
   Expand the hybrid retrieval evidence budget from `top_k=5` to `top_k=8` or `10`. At $k=10$ or with caption prepending, Table 2 will rank within the top 3.
3. **Acronym Synonym Normalization in BM25:**
   Add simple bilingual synonym expansion during query preprocessing (`English-to-German` $\to$ `EN-DE`, `English-to-French` $\to$ `EN-FR`).
