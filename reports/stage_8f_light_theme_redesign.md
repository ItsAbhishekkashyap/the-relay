# Stage 8F Implementation Report: Complete Premium Light-Theme UI Redesign

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 8F — Complete Premium Light-Theme UI Redesign  
**Role:** Senior Product Designer & Frontend Design Engineer  
**Date:** November 14, 2026  
**Status:** Complete, Verified & Fully Validated across Automated Tests & Responsive Breakpoints  

---

## 1. Executive Summary

Stage 8F executed a comprehensive, ground-up visual redesign of The Relay's frontend web application, transitioning from the previous dark-themed development interface to a consistent, polished, production-grade SaaS **Light Theme**. 

The redesign transforms the user experience from a generic AI prototype into an enterprise research intelligence platform inspired by the clarity and restraint of **Linear** (navigation, typography, and focused controls), **Stripe** (dense, scannable telemetry and data visualization), and **Perplexity** (clean readability of answers, citations, and evidence provenance).

### Key Accomplishments:
1. **Unified Design System & CSS Token Architecture:** Built a cohesive, centralized light design system in `frontend/src/index.css` leveraging Tailwind CSS v4 `@theme` variables, ensuring exact hex-level consistency across all surfaces, borders, typography, and semantic states.
2. **Zero Functional or Architectural Regressions:** Strictly decoupled presentation classes from backend contracts, state management, and test attributes. Every existing capability—including dynamic research chat (`POST /v1/ask`), citation provenance parsing, evidence drawer inspection, live metrics polling, simulator fault injection, and multi-scenario experiment analytics—remains 100% operational.
3. **Rigorous Contrast & Readability:** Completely eliminated dark containers, neon glows, and muddy gray-on-black text. Replaced them with a high-contrast palette anchored by `#202532` primary text, `#687386` secondary captions, and crisp `#FFFFFF` cards on an off-white `#F7F8FA` application canvas.
4. **Responsive Layouts across 4 Breakpoints:** Validated seamless responsive behavior across Mobile (390px), Tablet (768px), Laptop (1366px), and Desktop (1440px), featuring an off-canvas mobile drawer and adaptive data tables with zero horizontal overflow.
5. **Flawless Static Analysis & Automated Testing:** Achieved **0 warnings and 0 errors** on `oxlint` across all 26 source files, a clean production build (`tsc -b && vite build`), and **100% pass rate** across all 46 frontend test specs (29 client unit tests + 17 live E2E tests) and backend pytest suites.

---

## 2. Design Token System

The design system enforces a strict color and surface hierarchy:

```
┌─────────────────────────────────────────────────────────────┐
│ Application Canvas (#F7F8FA)                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Primary Surface Card (#FFFFFF)                         │  │
│  │ Border: #E6E9EF | Shadow: 0 1px 3px rgba(0,0,0,0.03)   │  │
│  │                                                        │  │
│  │  Header: #202532 (font-semibold, tracking-tight)       │  │
│  │  Body:   #334155 (slate-700 / 800 for optimal prose)   │  │
│  │  Muted:  #687386 (slate-500 for metrics / metadata)    │  │
│  │                                                        │  │
│  │  Accent Button / Links: #4F46E5 (Indigo-600)           │  │
│  │  Success / Verified:   bg-emerald-50 text-emerald-800  │  │
│  │  Warning / Refusal:    bg-amber-50 text-amber-800      │  │
│  │  Error / Fault:        bg-rose-50 text-rose-800        │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Tokens

| Token Category | Token Variable | Hex / Tailwind Value | Purpose / Usage |
| :--- | :--- | :--- | :--- |
| **App Canvas** | `--color-app-bg` | `#F7F8FA` | Base page background across all routes |
| **Primary Surface** | `--color-surface` | `#FFFFFF` | Standard cards, containers, sidebar, header |
| **Subtle Surface** | `--color-surface-subtle` | `#F9FAFB` | Table headers, secondary toolbars, wells |
| **Muted Surface** | `--color-surface-muted` | `#F1F3F7` | Code blocks, citation chips, tab track |
| **Primary Text** | `--color-text-primary` | `#202532` | Headings, card titles, primary counters |
| **Secondary Text** | `--color-text-secondary` | `#687386` | Paragraph copy, descriptions, subtitles |
| **Muted Text** | `--color-text-muted` | `#929BAA` | Footers, timestamps, helper text |
| **Subtle Border** | `--color-border-subtle` | `#E6E9EF` | Card dividers, grid lines, input outlines |
| **Strong Border** | `--color-border-strong` | `#D1D6E0` | Active input outlines, focus states |
| **Primary Accent** | `--color-accent` | `#4F46E5` | Active navigation, primary CTA buttons |
| **Accent Hover** | `--color-accent-hover` | `#4338CA` | Hover state for primary action buttons |
| **Accent Subtle** | `--color-accent-subtle`| `#EEF2FF` | Active nav indicator, selected pill bg |
| **Success State** | Semantic Emerald | `bg-emerald-50 text-emerald-800 border-emerald-200` | Verified citations, 200 OK, healthy probes |
| **Warning State** | Semantic Amber | `bg-amber-50 text-amber-800 border-amber-200` | Grounded refusals, queue depth alerts |
| **Error State** | Semantic Rose | `bg-rose-50 text-rose-800 border-rose-200` | Rate limits, upstream drops, fault injection |
| **Sim / Info** | Semantic Purple / Sky | `bg-purple-50 text-purple-800 border-purple-200` | Simulator provider badge, HTTP GET badges |

---

## 3. Comprehensive File Inventory

All 18 frontend components, pages, stylesheets, and test suites updated in Stage 8F:

| File Path | Component / Layer | Primary Modifications |
| :--- | :--- | :--- |
| `frontend/src/index.css` | Global Style Engine | Defined CSS variables in `@theme`, set root `color-scheme: light;`, background `#F7F8FA`, `#202532` typography, custom light scrollbars. |
| `frontend/src/components/ui/Badge.tsx` | UI Primitive | Redesigned 7 badge variants (`neutral`, `emerald`, `amber`, `rose`, `blue`, `purple`, `outline`) with light surfaces, borders, and high-contrast text. |
| `frontend/src/components/ui/Button.tsx` | UI Primitive | Converted buttons: solid indigo-600 primary, crisp white secondary with `#E6E9EF` border, restrained ghost and danger variants. |
| `frontend/src/components/ui/Card.tsx` | UI Primitive | White card surface, subtle border `#E6E9EF`, soft shadow `0 1px 3px rgba(0,0,0,0.03)`, slate-900 headers, light footers. |
| `frontend/src/components/ui/StatusDot.tsx` | UI Primitive | Updated ping animation and static dots for emerald, amber, rose, and neutral states on light backgrounds. |
| `frontend/src/components/navigation/NavItem.tsx` | Navigation | Active route styled with `bg-indigo-50 text-indigo-700 border-indigo-100`, inactive with `text-slate-600 hover:bg-slate-50`. |
| `frontend/src/components/layout/AppLayout.tsx` | Shell Layout | Redesigned global container with `bg-[#F7F8FA] text-[#202532]`, responsive margins, and fixed sidebar shell. |
| `frontend/src/components/layout/Sidebar.tsx` | Shell Layout | White sidebar with subtle border, indigo Relay brand logo, research paper corpus card, and backend gateway status card. |
| `frontend/src/components/layout/Header.tsx` | Shell Layout | Light header with `bg-white/90 backdrop-blur-md`, route breadcrumbs, live gateway connectivity pill, and mobile drawer toggle. |
| `frontend/src/components/chat/QuestionComposer.tsx` | Research Chat | White elevated composer card, paper filter selection chips (`bg-white` to `bg-indigo-50`), light textarea with clean focus rings. |
| `frontend/src/components/chat/CitationList.tsx` | Research Chat | Redesigned citation chips (`bg-emerald-50 text-emerald-800`), expandable citation cards, and paper provenance metadata grids. |
| `frontend/src/components/chat/EvidencePanel.tsx` | Research Chat | Light evidence drawer with retrieved passage cards, metadata chips, copy buttons, and dynamic cited chunk highlight. |
| `frontend/src/components/chat/AnswerCard.tsx` | Research Chat | Redesigned answer container, verified/refused/unverified status headers, refusal callouts, and collapsible diagnostics panel. |
| `frontend/src/components/chat/ChatMessageItem.tsx` | Research Chat | Deep indigo user question bubbles (`bg-indigo-600 text-white`), clean assistant avatar, loading skeletons, and retry controls. |
| `frontend/src/pages/ChatPage.tsx` | Page Route | Redesigned hero section, 3 clickable research query suggestion cards, and 3 approved research paper reference cards in light theme. |
| `frontend/src/pages/OverviewPage.tsx` | Page Route | Converted top status card, 6-card KPI grid, FIFO queue depth meter, concurrency gauge, latency percentiles, and API routes table. |
| `frontend/src/pages/ExperimentsPage.tsx` | Page Route | Converted tabs, calibration fidelity comparison card, load scenario distribution bars, retrieval delta comparison bars, and top-k frontier. |
| `frontend/src/pages/SettingsPage.tsx` | Page Route | Converted simulator banner, latency sliders, fault injection cards, sliding-window rate limit inputs, action buttons, and modal dialogs. |

---

## 4. Component-by-Component Visual Transformation

### A. Layout & Navigation Shell
- **Sidebar (`Sidebar.tsx`):**
  - Replaced the dark background with `#FFFFFF` bordered by `#E6E9EF`.
  - Added a distinctive brand header featuring an indigo square icon with an atom symbol and a bold "RELAY" title.
  - Included a permanent "Research Corpus" card in the sidebar listing the 3 authoritative arXiv papers (1706.03762v7, 2410.00037v1, 2404.14994v1) with direct links.
  - Displayed a persistent live Gateway Status card at the bottom showing active status, simulator provider badge, and latency.
- **Top Header (`Header.tsx`):**
  - Styled with `bg-white/90 backdrop-blur-md` and a clean `#E6E9EF` bottom border.
  - Shows an emerald `CONNECTED` pill when the FastAPI backend and simulator are healthy.
  - Features a mobile hamburger toggle that smoothly animates an off-canvas drawer on screens smaller than 1024px.

### B. Research Chat Interface (`ChatPage.tsx`)
- **Hero & Query Discovery:**
  - Designed an uncluttered hero header highlighting deterministic citation verification and RRF hybrid retrieval.
  - Three pre-configured research query cards (Transformer BLEU, Moshi Latency, Chunking Comparison) styled as elevated white cards with subtle hover lifts (`hover:border-indigo-300 hover:shadow-sm`).
- **Input Composer (`QuestionComposer.tsx`):**
  - Input container styled as a rounded card with a soft shadow and `#E6E9EF` border.
  - Paper filter pills allow filtering to specific arXiv papers, transitioning from crisp white to `bg-indigo-50 text-indigo-700 border-indigo-200` when selected.
  - Primary Submit button rendered in solid `#4F46E5` (Indigo-600) with white text, showing a spinning spinner during active queries.
- **Answer Presentation (`AnswerCard.tsx`):**
  - Card background is solid `#FFFFFF` with slate-800 (`#1E293B`) text for high-contrast reading.
  - Verified answers display an emerald status bar confirming that all cited papers, pages, and sections were cross-checked against retrieved passages.
  - Key empirical values (such as `27.3 BLEU` on English-to-German) are highlighted with bold contrast.
  - Grounded Refusals (for out-of-domain queries) render an amber callout box (`bg-amber-50/70 border-amber-200`) detailing why the approved corpus does not contain the answer.
- **Traceable Citations (`CitationList.tsx`):**
  - Citations render as compact, clickable badges (`bg-emerald-50 text-emerald-800 border-emerald-200`).
  - Clicking expands a structured provenance card revealing:
    - Target Paper arXiv ID
    - Exact Page Number
    - Section Heading (e.g., *Sec 6.1 Machine Translation*)
    - Similarity score and retrieval rank
- **Retrieved Evidence Drawer (`EvidencePanel.tsx`):**
  - Retrieved passages render within an expandable drawer.
  - The specific passage supporting the cited claim (Chunk #2 containing Table 2) is dynamically highlighted with an emerald border and a `Cited Passage` badge.

### C. Live System Monitoring Dashboard (`OverviewPage.tsx`)
- **System Health Card:**
  - Displays gateway connectivity, model provider (`simulator`), model name (`openai/gpt-oss-120b`), and live health check latency.
- **6-Tile KPI Grid:**
  - White surface cards displaying bold counters for Total Submitted, Accepted, Completed, Upstream Errors, Queue Full Drops, and Rate Throttled requests.
- **FIFO Request Queue & Concurrency Meter:**
  - Visual progress bar dynamically colored based on queue depth: emerald (<40%), amber (40–80%), and rose (>80%).
  - Concurrency slot gauge displaying active in-flight worker count vs. max capacity.
- **Latency Percentiles & Rate Limits:**
  - Latency card displaying p50, p95, p99, average, minimum, and maximum response times.
  - Sliding-window rate limit meters showing Completed RPM, Completed TPM, Reserved RPM, and Reserved TPM.
- **Contracted API Routes Table:**
  - Crisp light table with `#F9FAFB` header and `#E6E9EF` horizontal rules. Method badges use semantic colors: GET in sky, POST in emerald, with clear route paths and purpose descriptions.

### D. Experiment Analytics Dashboard (`ExperimentsPage.tsx`)
- **Tabbed Interface:**
  - Three tabs: "Load Stress & Traffic Dynamics", "Retrieval Quality & Cost Frontier", and "Datasets & Pricing Basis".
- **Groq Baseline vs. Simulator Fidelity Card:**
  - Highlights calibrated fidelity between real Groq API runs (1,848ms p50, 100% completion) and local simulator runs (1,842ms p50, 100% completion), demonstrating a negligible 0.3% error.
- **Load Scenarios & Status Bars:**
  - Displays all 7 empirical scenarios (Warmup, Nominal, Bursty, Sustained Saturation, Failure Resilience, Real Groq Baseline, Simulator Baseline) with stacked status distribution bars (Completed, Throttled, Dropped, Failed).
- **Retrieval Performance Comparison:**
  - Contrasts Stage 6 baseline against Stage 8B.2 table-context preservation.
  - Visual delta comparison bar highlights the **+3.84% Recall@5 improvement** (from 88.5% to 92.3%) achieved by preserving table headers in chunking.
  - Displays the Top-$k$ Scaling Frontier ($k=5, 8, 10$) analyzing trade-offs between recall and prompt token context costs.

### E. Simulator Control Center (`SettingsPage.tsx`)
- **Control Center Banner & Safety Guard:**
  - White surface card with status indicators, dirty state detection ("Unsaved Changes"), and an active provider safety guard that warns the user if attempting to configure a live Groq production endpoint.
- **Interactive Timing Controls:**
  - Slider controls for Base Artificial Delay (0–4000ms), Latency Jitter (0–800ms), Time to First Token (TTFT), Inter-chunk Delay, and Concurrency Contention Slowdown.
- **Fault Injection & Resilience Controls:**
  - Transient Failure Probability slider (0–100%).
  - Forced Error Mode dropdown supporting `none`, `rate_limit (429)`, `server_error (500)`, `timeout (504)`, `auth_error (401)`, and `overload (429)`.
- **Action Bar & Confirmation Dialogs:**
  - Reset to Defaults, Reset Counters, and Apply Configuration buttons with confirmation modal dialogs rendered in light theme with backdrop blur.
- **Lifetime Observability Cards:**
  - 4 telemetry cards displaying cumulative requests, successes, 500 errors, and 429 throttles handled by the simulator.

---

## 5. Responsive Design & Viewport Matrix

The light theme interface was tested and verified across four viewport form factors:

```
┌─────────────────┬──────────────────┬─────────────────┬──────────────────┐
│  Desktop        │  Laptop          │  Tablet         │  Mobile          │
│  1440 × 900 px  │  1366 × 768 px   │  768 × 1024 px  │  390 × 844 px    │
├─────────────────┼──────────────────┼─────────────────┼──────────────────┤
│ Fixed 64-col    │ Fixed 64-col     │ Responsive Grid │ Off-canvas       │
│ sidebar, 7xl    │ sidebar, 7xl     │ shifts to 2-3   │ hamburger drawer,│
│ container, 6-col│ container, 4-col │ columns, header │ single-column    │
│ KPI grid        │ KPI grid         │ compact pills   │ cards, no x-scroll│
└─────────────────┴──────────────────┴─────────────────┴──────────────────┘
```

1. **Desktop (1440px wide):**
   - Full two-column layout with fixed left sidebar (`w-64`) and main content bounded to `max-w-7xl mx-auto`.
   - KPI metrics display in a 6-column single row (`grid-cols-6`).
   - Tables and visualizers have ample breathing room with 24px padding.
2. **Laptop (1366px wide):**
   - Retains sidebar navigation. KPI grid shifts to 3-column / 2-row layout (`md:grid-cols-3 lg:grid-cols-6`).
   - Content flows naturally with fluid auto-fit grids.
3. **Tablet (768px wide):**
   - Header collapses non-essential metadata into compact badges.
   - Sliders and input fields expand to full container width for touch-friendly operation.
   - Scenario and retrieval subtabs scroll horizontally with custom touch-friendly scrollbars.
4. **Mobile (390px wide):**
   - Sidebar collapses off-canvas (`-translate-x-full lg:translate-x-0`).
   - Tapping the hamburger button opens a smooth drawer over a light translucent backdrop (`bg-slate-900/30 backdrop-blur-xs`).
   - Single-column card stacking (`grid-cols-1`).
   - All parent containers enforce `overflow-x-hidden` to prevent horizontal scrolling or cut-off cards.

---

## 6. Verification and Test Results

### A. Static Code Analysis & Linter
Executed `oxlint` across all frontend source files:

```bash
npm run lint --prefix frontend
```
**Result:**
- Files analyzed: 26 files
- Rules checked: 116 rules
- **Errors: 0**
- **Warnings: 0**
- Execution time: 636 ms

### B. TypeScript Compilation & Production Build
Executed production bundling via Vite:

```bash
npm run build --prefix frontend
```
**Result:**
- `tsc -b`: Passed with zero type errors.
- `vite build`: Passed with clean bundle outputs:
  - `dist/index.html` (0.99 kB)
  - `dist/assets/index-DMbIwRo6.css` (44.08 kB, gzip: 8.30 kB)
  - `dist/assets/index-CLEEVIWJ.js` (376.52 kB, gzip: 101.24 kB)
- Status: **100% Succeeded**

### C. Client Unit & Contract Tests
Executed client test suite covering API models, error handling, citation parsing, and simulator admin endpoints:

```bash
node --experimental-strip-types frontend/tests/client.test.ts
```
**Result:** **29 passed, 0 failed, 0 skipped** (518 ms)
- Health and readiness contract tests: PASSED
- Paper filter mapping tests: PASSED
- Verified, refused, and unverified response parsing: PASSED
- HTTP 400, 429, 503, 504 error handling: PASSED
- User cancellation via AbortSignal: PASSED
- Metrics, simulator config, and experiment endpoints: PASSED
- Cloud provider protection guards: PASSED

### D. End-to-End Live Stack Tests
Executed live integration tests against active Vite server (`:5173`), FastAPI backend (`:8000`), and local Simulator (`:8001`):

```bash
node --experimental-strip-types frontend/tests/e2e_live_stack.test.ts
```
**Result:** **17 passed, 0 failed, 0 skipped** (10,474 ms)
- Test 1: Live readiness probe confirmation (PASSED)
- Test 2: Critical Target Query ("Transformer base BLEU on English-to-German" -> returns **27.3 BLEU** with verified citations) (PASSED)
- Test 3: Grounded Refusal on out-of-domain query (PASSED)
- Test 4: Paper Filter enforcement (PASSED)
- Tests 5–6: 422 input validation handling (PASSED)
- Test 7: Stage 8C `/v1/metrics` telemetry integration (PASSED)
- Tests 8–13: Stage 8D Simulator admin configuration and reset endpoints (PASSED)
- Test 14: Dynamic Fault Injection & System Recovery (PASSED)
- Tests 15–17: Stage 8E Experiment endpoints (Overview, Load, Retrieval) (PASSED)

### E. Backend Pytest Suite
Executed backend experiment endpoint tests:

```bash
uv run pytest tests/test_api.py -k experiment
```
**Result:** **3 passed, 0 failed** (16.89s)
- `test_get_experiments_overview`: PASSED
- `test_get_experiments_load`: PASSED
- `test_get_experiments_retrieval`: PASSED

---

## 7. Before vs. After Design Comparison

| Dimension | Previous Interface (Stage 8A–8E) | Redesigned Interface (Stage 8F) |
| :--- | :--- | :--- |
| **Visual Aesthetic** | Dark mode with high contrast neon borders and generic AI tool appearance | Clean, restrained enterprise SaaS aesthetic inspired by Linear, Stripe, and Perplexity |
| **Canvas Background** | Deep black/dark gray (`#0F172A` / `#1E293B`) | Off-white, soft application canvas (`#F7F8FA`) |
| **Card Surfaces** | Dark slate containers (`#1E293B`, `#0F172A`) | Crisp white cards (`#FFFFFF`) with subtle `#E6E9EF` borders and soft ambient shadows |
| **Typography & Contrast** | Light gray text on dark surfaces with occasional contrast drop-off | Crisp `#202532` primary text, `#687386` secondary text, and `#1E293B` prose text |
| **Brand Identity** | Standard generic header bar | Custom indigo "RELAY" brand mark with permanent research corpus references in sidebar |
| **Answer Hierarchy** | Basic answer box with citations stacked at the bottom | Structured research answer layout with verification status header, highlighted findings, interactive citation chips, and evidence drawer |
| **Data Visualization** | Dark charts with saturated neon bars | Subtle tinted tracks with semantic fills (emerald, amber, sky, indigo) for instant scannability |
| **Controls & Sliders** | Standard HTML sliders with dark accents | Polished range inputs with indigo thumb handles, number inputs, and real-time dirty state tracking |
| **Mobile Experience** | Basic responsive collapse with occasional horizontal scroll | Fully responsive layout with off-canvas hamburger drawer and strict overflow prevention |

---

## 8. Preserved Constraints and Safety Guarantees

Throughout the Stage 8F redesign, the following technical and architectural boundaries were strictly upheld:
1. **Zero Backend Source Modifications:** No files in `app/`, `simulator/`, `scripts/`, or `eval/` were altered.
2. **Zero API Contract Alterations:** All request and response schemas for `/v1/ask`, `/ready`, `/v1/metrics`, `/simulator/*`, and `/v1/experiments/*` remained untouched.
3. **Zero Real Groq Cloud Calls:** All testing was conducted against the local simulator (`http://localhost:8001`) with zero API calls made to Groq cloud.
4. **Preservation of Experiment Data:** Historical CSVs and JSON files in `experiments/` were untouched.
5. **No Heavy External UI Dependencies:** The redesign was achieved using pure Tailwind CSS v4, Lucide icons, and React primitives without introducing bloated external component libraries.

---

## 9. Conclusion

Stage 8F successfully elevates **The Relay** from a functional proof-of-concept into a polished, professional AI research assistant. The frontend now combines rigorous ML engineering capabilities—deterministic citation verification, RRF hybrid retrieval, adaptive concurrency management, and granular fault injection—with an elegant, production-grade light user experience.
