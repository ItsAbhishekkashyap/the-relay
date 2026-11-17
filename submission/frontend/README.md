# The Relay — Research Assistant Frontend & Chat Interface

A professional, responsive research assistant interface for **The Relay (Vaani Research ML Engineering Assignment)**, built with React 19, TypeScript, Vite, Tailwind CSS v4, and Lucide React icons.

Connected directly to the FastAPI backend supporting:
- Real-time service liveness (`GET /health`) and component readiness (`GET /ready`)
- Evidence-grounded research question answering (`POST /v1/ask`) across 3 arXiv papers
- Traceable citations verified against retrieved chunk metadata
- Collapsible retrieved evidence passages with RRF hybrid channel diagnostics
- Explicit grounded refusal banners and bounded auto-correction indicators

---

## 1. Discovered Backend API Contracts

The frontend integrates directly with the contracts declared in `app/api/schemas.py`, `app/api/routes.py`, and `app/workflow/schemas.py`.

### A. Health Endpoint (`GET /health`)

- **Method / Path:** `GET /health`
- **Tag:** `System`
- **Purpose:** Fast liveness check that verifies HTTP transport connectivity without invoking vector stores or LLM generation.
- **Success Status:** HTTP 200 OK
- **Response Schema (`HealthResponse`):**
```json
{
  "status": "ok",
  "service": "relay-research-assistant"
}
```

### B. Readiness Endpoint (`GET /ready`)

- **Method / Path:** `GET /ready`
- **Tag:** `System`
- **Purpose:** Deep operational health check verifying that the hybrid retriever, async TrafficManager, and LangGraph state graph are initialized and ready to serve traffic.
- **Success Status:** HTTP 200 OK
- **Response Schema (`ReadyResponse`):**
```json
{
  "status": "ready",
  "provider": "simulator",
  "model": "openai/gpt-oss-120b",
  "components": {
    "retriever": "initialized",
    "traffic_manager": "initialized",
    "workflow": "initialized"
  }
}
```
- **Not Ready Status:** HTTP 503 Service Unavailable
- **Failure Response Schema:**
```json
{
  "detail": {
    "status": "not_ready",
    "components": {
      "retriever": "initialized",
      "traffic_manager": "uninitialized",
      "workflow": "uninitialized"
    }
  }
}
```

### C. Question Answering Endpoint (`POST /v1/ask`)

- **Method / Path:** `POST /v1/ask`
- **Tag:** `Research`
- **Purpose:** Submits a natural language query to the 8-node LangGraph research assistant workflow. Answers are grounded exclusively in the 3 approved arXiv papers (`1706.03762v7`, `2410.00037v1`, `2507.07955v2`).
- **Request Schema (`AskRequest`):**
```json
{
  "question": "What BLEU score did the Transformer base model achieve on English-to-German?",
  "paper_filter": "1706.03762v7"
}
```
*(Note: `paper_filter` is optional; when 'All Papers' is selected in the UI, `paper_filter` is omitted or set to `null`)*

- **Success Status:** HTTP 200 OK
- **Response Schema (`AskResponse`):**
```json
{
  "request_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "question": "What BLEU score did the Transformer base model achieve on English-to-German?",
  "answer": "The Transformer base model achieves a BLEU score of 27.3 on the WMT 2014 English-to-German translation task [Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 5.1].",
  "status": "verified",
  "citations": [
    {
      "raw_text": "[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 5.1]",
      "paper_title": "Attention Is All You Need",
      "paper_id": "1706.03762v7",
      "page_number": 8,
      "section": "5.1",
      "is_verified": true,
      "verification_error": null
    }
  ],
  "retrieved_passages": [
    {
      "chunk_id": "1706.03762v7_p8_c0",
      "paper_id": "1706.03762v7",
      "paper_title": "Attention Is All You Need",
      "arxiv_id": "1706.03762",
      "paper_version": "v7",
      "page_number": 8,
      "page_numbers": [8],
      "section": "5.1",
      "content": "On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models...",
      "score": 0.033,
      "retrieval_channels": ["dense", "bm25"]
    }
  ],
  "provider": "simulator",
  "refusal_reason": null,
  "correction_occurred": false,
  "workflow_metadata": {}
}
```

---

## 2. Frontend Architecture (Stage 8B)

```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── AnswerCard.tsx        # Verification status, answer text, refusal banner & diagnostics
│   │   │   ├── CitationList.tsx      # Traceable citation chips and expandable metadata inspector
│   │   │   ├── EvidencePanel.tsx     # Collapsible retrieved passage viewer with copy actions
│   │   │   ├── ChatMessageItem.tsx   # User question, honest processing indicator, error with retry
│   │   │   └── QuestionComposer.tsx  # Controlled textarea, paper filter pills, Enter-to-submit
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx         # Responsive container with fixed sidebar & mobile drawer
│   │   │   ├── Header.tsx            # Sticky header with connectivity pill, latency & refresh
│   │   │   └── Sidebar.tsx           # Brand header, navigation links, corpus info & backend status
│   │   ├── navigation/
│   │   │   └── NavItem.tsx           # Keyboard-accessible sidebar navigation items
│   │   └── ui/
│   │       ├── Badge.tsx             # Semantic badge component with native title tooltip support
│   │       ├── Button.tsx            # Button with loading spinner, variants, and disabled states
│   │       ├── Card.tsx              # Minimal charcoal card container with header/footer slots
│   │       └── StatusDot.tsx         # Live status dot with pulse animation
│   ├── config/
│   │   └── env.ts                    # Safe frontend environment configuration and timeouts
│   ├── hooks/
│   │   └── useBackendHealth.ts       # Parallel health & readiness hook with auto-polling
│   ├── pages/
│   │   ├── ChatPage.tsx              # Functional research chat orchestrator & session feed
│   │   ├── OverviewPage.tsx          # Real FastAPI health, readiness, endpoint matrix & pipeline
│   │   ├── ExperimentsPage.tsx       # Scenarios A–E & Configs A–D completed experiment records
│   │   └── SettingsPage.tsx          # Read-only runtime parameter inspector & zero-credential notice
│   ├── services/
│   │   └── api.ts                    # Reusable API client (getHealth, getReady, askQuestion)
│   ├── types/
│   │   └── api.ts                    # TypeScript types matching FastAPI Pydantic models & chat turns
│   ├── App.tsx                       # Root view orchestrator managing active tab and layout
│   ├── index.css                     # Tailwind CSS v4 directives and dark theme baseline
│   └── main.tsx                      # React 19 entry point
├── tests/
│   └── client.test.ts                # 13 automated tests covering API contracts and error handling
├── index.html                        # Application entry point with dark canvas defaults
├── package.json                      # Locked dependencies and scripts (dev, build, lint, test)
├── tsconfig.json                     # TypeScript strict configuration
├── vite.config.ts                    # Vite 8 config with development proxy for FastAPI
└── .env.example                      # Frontend environment template
```

---

## 3. How the Research Chat Works

1. **Question Input & Paper Filter:**
   - The user types a question and optionally selects a paper filter:
     - `All 3 Papers`: `paper_filter` is omitted or `null`.
     - `1706.03762v7 (Attention)`: mapped to `"1706.03762v7"`.
     - `2410.00037v1 (Moshi)`: mapped to `"2410.00037v1"`.
     - `2507.07955v2 (Chunking)`: mapped to `"2507.07955v2"`.
2. **Honest Loading State:**
   - Because `/v1/ask` returns a complete JSON response rather than token SSE, the UI presents an honest progress state indicating that hybrid retrieval and LangGraph citation verification are active.
3. **Verified Answers:**
   - Renders with an emerald status badge (`Verified Provenance`), provider indicator, request ID with click-to-copy, and citation badges.
4. **Grounded Refusals:**
   - If the research assistant determines that evidence is insufficient or out-of-domain, it is visibly rendered in an amber alert box explaining the refusal with `refusal_reason`.
5. **Traceable Citations:**
   - Collapsible citation cards display paper title, arXiv ID, page number, section name, verification state, and raw text.
6. **Retrieved Evidence Chunks:**
   - Collapsible evidence panel displays every chunk retrieved by the hybrid engine with its channels (`dense`, `bm25`, `fact_store`), score, and full text.
7. **Session History:**
   - Preserves conversation turns in frontend memory for the active browser session, with a "Clear Session" option.

---

## 4. Setup, Execution & Testing

### Installation
From the repository root:
```powershell
cd frontend
npm install
```

### Running the Development Server
```powershell
npm run dev
```
Launches on `http://localhost:5173`. Vite automatically proxies `/health`, `/ready`, and `/v1` to `http://127.0.0.1:8000`.

### Running Automated Frontend Tests
```powershell
npm test
```
Executes 13 unit tests via Node.js native test runner verifying:
- `GET /health` and `GET /ready` contract compliance
- `POST /v1/ask` payload formation and paper filter mapping
- Parsing of `verified`, `refused`, and `unverified` states
- Citation extraction and retrieved document extraction
- HTTP 429 (rate limit), 503 (queue full), 504 (timeout), and 400 (bad request) handling
- User request cancellation via `AbortSignal`
- Network failure when backend is unreachable

### Production Build
```powershell
npm run build
```
Executes `tsc -b` for strict type-checking, followed by `vite build` producing a minified production bundle in `dist/`.

### Linting
```powershell
npm run lint
```
Executes `oxlint` with 0 warnings and 0 errors.
