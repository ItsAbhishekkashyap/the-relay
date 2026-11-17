# Stage 8B Implementation Report: Research Chat UI Integration

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 8B — Research Chat UI Integration  
**Role:** Frontend Implementation Engineer  
**Date:** November 12, 2026  
**Status:** Complete & Fully Validated against Local Simulator  

---

## 1. Executive Summary

Stage 8B connects the React/Vite/TypeScript frontend to the live FastAPI research assistant backend (`POST /v1/ask`), supporting grounded scientific question answering across the 3 target arXiv preprints (*Attention Is All You Need*, *Moshi: Speech-Text Foundation Model*, and *Dynamic Chunking for Retrieval*).

All development and end-to-end verification were executed **strictly against the local stand-in model simulator (`MODEL_PROVIDER=simulator`)** on `http://127.0.0.1:8001`, ensuring **zero Groq API requests** and zero financial or rate-limit expenditure.

---

## 2. Files Created and Modified

| File | Status | Description |
| :--- | :--- | :--- |
| `.env` | Modified | Configured `MODEL_PROVIDER=simulator` to enforce simulator routing across all services. |
| `frontend/src/components/chat/EvidencePanel.tsx` | Modified | Added `citations` prop and `isPassageCited()` matching logic; renders distinct `Cited Passage` (emerald) vs `Retrieved Context` (neutral) badges and highlight borders. |
| `frontend/src/components/chat/CitationList.tsx` | Modified | Added `parsePaperIdAndVersion()` for structured arXiv ID and version `(v7)` breakdown; added paper title resolution and explicit provenance status badges. |
| `frontend/src/components/chat/AnswerCard.tsx` | Modified | Wired citations into `EvidencePanel`; added dedicated Provenance Validation banner clarifying that metadata validation does not assert automated semantic proof. |
| `frontend/src/components/chat/ChatMessageItem.tsx` | Modified | Added contextual error diagnosis (`getErrorHint()`) providing actionable guidance for connection drops, rate limits (429), timeouts (504), and validation errors (400/422). |
| `frontend/src/pages/ChatPage.tsx` | Modified | Added in-memory session state notice to the conversation header, clarifying backend statelessness. |
| `frontend/package.json` | Modified | Updated test scripts: `"test": "node --experimental-strip-types tests/client.test.ts && node --experimental-strip-types tests/e2e_live_stack.test.ts"`. |
| `frontend/tests/client.test.ts` | Modified | Added Tests 14–16 validating citation metadata parsing, refusal reason preservation, and unverified error tracking. |
| `frontend/tests/e2e_live_stack.test.ts` | Created | Automated end-to-end test suite testing live Vite proxy (`:5173`) $\to$ FastAPI (`:8000`) $\to$ Simulator (`:8001`). |
| `reports/stage_8b_chat_integration.md` | Created | This deliverable implementation report. |

---

## 3. Chat Features Implemented

### A. Question Submission
- **Controlled Textarea:** Full two-way state binding with auto-focus on load.
- **Dual Submission Controls:** Submits via `Enter` key (without Shift) and the dedicated `"Ask Question"` button.
- **Empty & Whitespace Prevention:** Buttons and Enter key disabled when input is empty or whitespace-only.
- **In-Flight Concurrency Lock:** Prevents duplicate submissions while a query is running (`isSubmitting` disables input, paper pills, and submit button).
- **Paper Filtering Support:** Supports optional corpus filtering across `"all"`, `"1706.03762v7"`, `"2410.00037v1"`, and `"2507.07955v2"`.
- **Request Cancellation:** Integrates `AbortController` linked to user navigation or component unmount.

### B. Conversation Display & Session State
- **Session State Management:** Retains question history and assistant responses in React state (`messages`).
- **Honest Statelessness Notification:** Header explicitly indicates: `Session History: N turn(s) • In-memory session state (stateless backend)`.
- **Session Reset / New Chat:** Clear session button with trash icon resets local conversation history.
- **Visual Distinction:** User turns styled with right alignment and dark indigo bubbles; assistant turns formatted with emerald Sparkles icon and structured multi-section cards.

### C. Answer Status & Provenance Semantics
- **Three Strict Statuses Rendered:**
  - `verified` $\to$ **Verified Provenance** (Emerald shield badge).
  - `refused` $\to$ **Grounded Refusal** (Amber alert triangle badge).
  - `unverified` $\to$ **Unverified Citation** (Zinc help-circle badge).
- **Provenance Validation Notice:** Explicitly labels that citation verification confirms paper, page, and section metadata presence in retrieved passages, and does **not** assert automated proof of semantic entailment.
- **Execution Diagnostics:** Displays request correlation ID (with one-click clipboard copy), provider name badge (`simulator`), auto-correction badge (`Auto-Corrected`), and total response duration in seconds.

### D. Traceable Citations & Evidence Panel
- **Traceable Citations List (`CitationList.tsx`):**
  - Displays paper title, arXiv ID, and version (e.g. `1706.03762 (v7)`).
  - Displays page number and section heading.
  - Collapsible detail cards showing raw citation text and verification errors.
- **Collapsible Evidence Panel (`EvidencePanel.tsx`):**
  - Renders all retrieved passages with chunk IDs, retrieval channels (`DENSE + BM25`), page numbers, and RRF scores.
  - **Cited vs Non-Cited Discrimination:** Passages matching response citations are dynamically flagged with `Cited Passage` badge and emerald highlight; other passages are labeled `Retrieved Context`.
  - One-click copy button for individual passage texts.

### E. Error Handling & Recovery
- Handles backend offline status, HTTP 400/422 validation errors, HTTP 429 rate limits, HTTP 503 queue capacity, and HTTP 504 timeouts.
- **Contextual Troubleshooting Hints:** Automatically detects error categories and advises user (e.g. suggesting specific paper filters for timeouts, or waiting briefly for rate limits).
- **Actionable Retry:** Retries the specific failed question with its original filter settings.

---

## 4. API Integration Details

### Contract Endpoint: `POST /v1/ask`

#### Request Payload:
```json
{
  "question": "What BLEU score did the Transformer base model achieve on English-to-German?",
  "paper_filter": null
}
```

#### Response Handling:
```json
{
  "request_id": "ff776a94-ca35-4a03-9a7a-ab035b4f3a83",
  "question": "What BLEU score did the Transformer base model achieve on English-to-German?",
  "answer": "According to Table 2, the Transformer (base model) achieved a BLEU score of 27.3 on the WMT 2014 English-to-German translation task [Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 6.1 Machine Translation]. (By comparison, the Transformer (big) achieved a BLEU score of 28.4).",
  "status": "verified",
  "citations": [
    {
      "raw_text": "[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 6.1 Machine Translation]",
      "paper_title": "Attention Is All You Need",
      "paper_id": "1706.03762v7",
      "page_number": 8,
      "section": "6.1 Machine Translation",
      "is_verified": true,
      "verification_error": null
    }
  ],
  "retrieved_passages": [
    {
      "chunk_id": "1706.03762v7_lc_0026",
      "paper_id": "1706.03762v7",
      "paper_title": "Attention Is All You Need",
      "arxiv_id": "1706.03762",
      "paper_version": "v7",
      "page_number": 8,
      "page_numbers": [8],
      "section": "6.1 Machine Translation",
      "content": "[Paper: Attention Is All You Need (1706.03762v7) | Page 8 | Section: 6.1 Machine Translation]\nTable 2: The Transformer achieves better BLEU scores...\n|Transformer (base model)|27.3|...",
      "score": 0.032258,
      "retrieval_channels": ["dense", "bm25"]
    }
  ],
  "provider": "simulator",
  "refusal_reason": null,
  "correction_occurred": false,
  "workflow_metadata": { ... }
}
```

---

## 5. Critical End-to-End Validation (Simulator Only)

### Provider Confirmation
Before executing tests, `MODEL_PROVIDER=simulator` was set in `.env`.
Inspection of `GET http://localhost:5173/ready`:
```json
{
  "status": "ready",
  "provider": "simulator",
  "model": "simulator/mock-model-v1",
  "components": {
    "retriever": "initialized",
    "traffic_manager": "initialized",
    "workflow": "initialized"
  }
}
```
**Zero requests were sent to the Groq API.**

---

### Test Question 1: Target In-Domain Query
> **Query:** *"What BLEU score did the Transformer base model achieve on English-to-German?"*

- **Result:**
  - **Answer:** Successfully returned **27.3 BLEU** from Table 2.
  - **Citation:** `[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 6.1 Machine Translation]`.
  - **Status:** `verified` (`is_verified: true`).
  - **Retrieved Evidence:** Chunk `1706.03762v7_lc_0026` correctly retrieved at Rank 2 and highlighted with `Cited Passage` badge in the UI evidence panel.

---

### Test Question 2: Target Out-of-Domain Query
> **Query:** *"What was the quantum volume of the Sycamore processor in 2019?"*

- **Result:**
  - **Status:** `refused`.
  - **Answer:** *"I am unable to answer this research question from the three target papers.\nReason: Retrieved evidence passages do not contain terms matching the research query. The query appears to be out-of-domain for the 3 target papers."*
  - **Refusal Reason:** Explicitly captured and rendered in the amber refusal banner.
  - **Citations:** Empty array (`0` citations displayed).

---

## 6. Automated Test Commands and Results

### A. Frontend Linting
```bash
npm run lint --prefix frontend
```
**Output:**
```text
> frontend@0.0.0 lint
> oxlint

Found 0 warnings and 0 errors.
Finished in 75ms on 26 files with 116 rules using 12 threads.
```

### B. Production Build
```bash
npm run build --prefix frontend
```
**Output:**
```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.8 building client environment for production...
✓ 2103 modules transformed.
rendering chunks...
dist/index.html                   0.99 kB │ gzip:  0.55 kB
dist/assets/index-DzhHN2ot.css   43.02 kB │ gzip:  7.97 kB
dist/assets/index-MZYTAQpX.js   301.35 kB │ gzip: 89.18 kB
✓ built in 750ms
```

### C. Full Automated Test Suite (Client + Live E2E)
```bash
npm test --prefix frontend
```
**Output:**
```text
> frontend@0.0.0 test
> node --experimental-strip-types tests/client.test.ts && node --experimental-strip-types tests/e2e_live_stack.test.ts

▶ Frontend API Client & Contract Tests
  ✔ 1. Validates GET /health response contract (18.0526ms)
  ✔ 2. Validates GET /ready response contract and components (4.0161ms)
  ✔ 3. Paper filter mapping: correctly includes paper_filter when specified (7.5853ms)
  ✔ 4. Paper filter mapping: omits paper_filter when null or undefined (2.6542ms)
  ✔ 5. Verified response correctly parses citations and retrieved passages (2.6039ms)
  ✔ 6. Refused response correctly parses refusal_reason and empty citations (4.3726ms)
  ✔ 7. Unverified response parses verification failure metadata (1.9745ms)
  ✔ 8. Handles HTTP 429 rate limit error gracefully (3.1822ms)
  ✔ 9. Handles HTTP 503 queue capacity error gracefully (1.8959ms)
  ✔ 10. Handles HTTP 504 processing timeout gracefully (2.9922ms)
  ✔ 11. Handles HTTP 400 bad request error gracefully (1.7637ms)
  ✔ 12. User cancellation via AbortSignal raises 499 canceled (0.6414ms)
  ✔ 13. Network failure when endpoint is unreachable raises connection error (4.0926ms)
  ✔ 14. Validates retrieved passages carry provenance metadata for citation matching (1.6409ms)
  ✔ 15. Validates out-of-domain refusal retains refusal_reason and empty citations (1.3475ms)
  ✔ 16. Validates unverified response flags correction and verification error details (2.592ms)
✔ Frontend API Client & Contract Tests (83.8907ms)

▶ Stage 8B Live Stack E2E Validation (Vite -> FastAPI -> Simulator)
  ✔ 1. Live readiness probe confirms simulator provider and initialized components (27.9186ms)
  ✔ 2. Critical Target Query: Transformer base BLEU on English-to-German (1056.8332ms)
  ✔ 3. Out-of-Domain Query: Grounded refusal verification (49.7634ms)
  ✔ 4. Paper Filter Validation: Supported filter works as expected (2309.8564ms)
  ✔ 5. Error Handling: Rejects empty question with 422 (9.1359ms)
  ✔ 6. Error Handling: Rejects invalid paper filter with 422 (6.7111ms)
✔ Stage 8B Live Stack E2E Validation (Vite -> FastAPI -> Simulator) (3494.6591ms)

Total Tests: 22 passed (0 failed, 0 skipped)
```

---

## 7. Remaining Limitations

1. **Client-Side Session Persistence:** Conversation history is stored in React memory (`useState`). Refreshing the browser clears the conversation by design, as the backend API is intentionally stateless without persistent user session tables.
2. **Provenance vs Semantic Verification:** The verification badge validates provenance metadata against retrieved evidence passages. It does not perform automated natural language inference (NLI) or semantic entailment checking on generated mathematical assertions.
3. **TrafficManager Throttling Under Rapid Repetition:** When executing consecutive automated test runs, the simulator's calibrated 8,000 TPM limit requires occasional counter resets via `POST /admin/reset` to prevent artificial 429 backoff during burst testing.
