const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUTPUT_DIR = path.resolve(__dirname, '../reports/assets');

// ==============================================================================
// D.1 Overall System Architecture SVG
// ==============================================================================
const svgD1 = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 900" width="1400" height="900" style="background:#0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="gradHeader" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#4F46E5"/>
      <stop offset="100%" stop-color="#06B6D4"/>
    </linearGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1E293B"/>
      <stop offset="100%" stop-color="#0F172A"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.3"/>
    </filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#6366F1"/>
    </marker>
    <marker id="arrowCyan" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#06B6D4"/>
    </marker>
    <marker id="arrowEmerald" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#10B981"/>
    </marker>
  </defs>

  <!-- Title Banner -->
  <rect x="40" y="30" width="1320" height="70" rx="12" fill="#1E293B" stroke="#334155" stroke-width="1.5" filter="url(#shadow)"/>
  <text x="70" y="65" fill="#F8FAFC" font-size="22" font-weight="700">THE RELAY — SYSTEM ARCHITECTURE DIAGRAM (D.1)</text>
  <text x="70" y="86" fill="#94A3B8" font-size="13">Production-Aware AI Research Assistant • End-to-End Component Boundaries & Dataflow</text>
  <rect x="1140" y="47" width="190" height="34" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="1235" y="69" fill="#E0E7FF" font-size="12" font-weight="600" text-anchor="middle">Stage 8 Release Build</text>

  <!-- ========================================================================= -->
  <!-- 1. FRONTEND TIER (Vercel) -->
  <!-- ========================================================================= -->
  <rect x="40" y="130" width="360" height="730" rx="12" fill="url(#cardBg)" stroke="#3B82F6" stroke-width="2" filter="url(#shadow)"/>
  <path d="M 40 142 A 12 12 0 0 1 52 130 L 388 130 A 12 12 0 0 1 400 142 L 400 180 L 40 180 Z" fill="#1E3A8A"/>
  <text x="60" y="162" fill="#DBEAFE" font-size="16" font-weight="700">1. PRESENTATION TIER</text>
  <text x="320" y="162" fill="#93C5FD" font-size="11" font-family="monospace">Vercel (React 19)</text>

  <!-- Sub-components in Frontend -->
  <!-- Research Chat -->
  <rect x="60" y="200" width="320" height="100" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1"/>
  <text x="80" y="228" fill="#F8FAFC" font-size="14" font-weight="600">Research Chat View</text>
  <text x="80" y="248" fill="#94A3B8" font-size="12">• Query submission with paper filter</text>
  <text x="80" y="266" fill="#94A3B8" font-size="12">• Real-time loading & status badge</text>
  <text x="80" y="284" fill="#94A3B8" font-size="12">• Traceable citations & evidence drawer</text>

  <!-- System Overview -->
  <rect x="60" y="315" width="320" height="100" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1"/>
  <text x="80" y="343" fill="#F8FAFC" font-size="14" font-weight="600">System Overview & Telemetry</text>
  <text x="80" y="363" fill="#94A3B8" font-size="12">• Live gateway readiness & health poll</text>
  <text x="80" y="381" fill="#94A3B8" font-size="12">• FIFO queue depth & concurrency gauges</text>
  <text x="80" y="399" fill="#94A3B8" font-size="12">• Latency percentiles (p50, p95, p99)</text>

  <!-- Experiments Analytics -->
  <rect x="60" y="430" width="320" height="100" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1"/>
  <text x="80" y="458" fill="#F8FAFC" font-size="14" font-weight="600">Experiment Analytics Dashboard</text>
  <text x="80" y="478" fill="#94A3B8" font-size="12">• Groq vs Simulator calibration delta</text>
  <text x="80" y="496" fill="#94A3B8" font-size="12">• 5 load test stress scenarios</text>
  <text x="80" y="514" fill="#94A3B8" font-size="12">• RRF vs Dense vs BM25 quality benchmarks</text>

  <!-- Simulator Controls -->
  <rect x="60" y="545" width="320" height="100" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1"/>
  <text x="80" y="573" fill="#F8FAFC" font-size="14" font-weight="600">Simulator Control Center</text>
  <text x="80" y="593" fill="#94A3B8" font-size="12">• Base delay, jitter, TTFT adjustment</text>
  <text x="80" y="611" fill="#94A3B8" font-size="12">• Sliding RPM/TPM quota controls</text>
  <text x="80" y="629" fill="#94A3B8" font-size="12">• Fault injection & baseline reset</text>

  <!-- Frontend Client Service -->
  <rect x="60" y="660" width="320" height="175" rx="8" fill="#312E81" stroke="#6366F1" stroke-width="1.5"/>
  <text x="80" y="690" fill="#EEF2FF" font-size="14" font-weight="700">Unified Frontend API Client</text>
  <text x="80" y="712" fill="#C7D2FE" font-size="12 font-family="monospace">api.ts / env.ts (Vite BaseURL)</text>
  <text x="80" y="736" fill="#E0E7FF" font-size="12">• fetchWithTimeout + AbortController</text>
  <text x="80" y="756" fill="#E0E7FF" font-size="12">• Error taxonomy parsing (429, 503, 504)</text>
  <text x="80" y="776" fill="#E0E7FF" font-size="12">• Automatic retry & health state polling</text>
  <text x="80" y="796" fill="#E0E7FF" font-size="12">• 29 automated contract tests (pass 100%)</text>

  <!-- ========================================================================= -->
  <!-- 2. BACKEND API GATEWAY & WORKFLOW (Render) -->
  <!-- ========================================================================= -->
  <rect x="440" y="130" width="520" height="730" rx="12" fill="url(#cardBg)" stroke="#6366F1" stroke-width="2" filter="url(#shadow)"/>
  <path d="M 440 142 A 12 12 0 0 1 452 130 L 948 130 A 12 12 0 0 1 960 142 L 960 180 L 440 180 Z" fill="#312E81"/>
  <text x="460" y="162" fill="#EDE9FE" font-size="16" font-weight="700">2. APPLICATION & ORCHESTRATION TIER</text>
  <text x="830" y="162" fill="#C4B5FD" font-size="11" font-family="monospace">Render (FastAPI)</text>

  <!-- FastAPI Endpoints Box -->
  <rect x="460" y="200" width="480" height="120" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1"/>
  <text x="480" y="228" fill="#F8FAFC" font-size="14" font-weight="600">FastAPI Gateway Router (/v1)</text>
  <text x="480" y="250" fill="#A5B4FC" font-size="12 font-family="monospace">POST /v1/ask  •  GET /health  •  GET /ready  •  GET /v1/metrics</text>
  <text x="480" y="272" fill="#A5B4FC" font-size="12 font-family="monospace">GET /v1/experiments/*  •  GET/POST /simulator/* (In-Process Mounted)</text>
  <text x="480" y="296" fill="#94A3B8" font-size="12">• CORS Middleware (*) • Async lifespan • Port dynamic binding ($PORT)</text>

  <!-- LangGraph Workflow Box -->
  <rect x="460" y="335" width="480" height="235" rx="8" fill="#1E1B4B" stroke="#818CF8" stroke-width="1.5"/>
  <text x="480" y="365" fill="#EDE9FE" font-size="15" font-weight="700">LangGraph Research Assistant Workflow</text>
  <text x="480" y="385" fill="#C7D2FE" font-size="12 font-family="monospace">StateGraph: ResearchAssistantState (Structured Flow)</text>
  
  <rect x="480" y="405" width="130" height="50" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="545" y="428" fill="#FFFFFF" font-size="11" font-weight="600" text-anchor="middle">Input Validator</text>
  <text x="545" y="444" fill="#A5B4FC" font-size="10" text-anchor="middle">Filter Check</text>

  <rect x="635" y="405" width="140" height="50" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="705" y="428" fill="#FFFFFF" font-size="11" font-weight="600" text-anchor="middle">Hybrid Retriever</text>
  <text x="705" y="444" fill="#A5B4FC" font-size="10" text-anchor="middle">RRF-60 Rank Fusion</text>

  <rect x="795" y="405" width="130" height="50" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="860" y="428" fill="#FFFFFF" font-size="11" font-weight="600" text-anchor="middle">Evidence Gate</text>
  <text x="860" y="444" fill="#A5B4FC" font-size="10" text-anchor="middle">Sufficiency Check</text>

  <rect x="480" y="475" width="130" height="50" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="545" y="498" fill="#FFFFFF" font-size="11" font-weight="600" text-anchor="middle">Model Generator</text>
  <text x="545" y="514" fill="#A5B4FC" font-size="10" text-anchor="middle">via TrafficManager</text>

  <rect x="635" y="475" width="140" height="50" rx="6" fill="#312E81" stroke="#6366F1" stroke-width="1"/>
  <text x="705" y="498" fill="#FFFFFF" font-size="11" font-weight="600" text-anchor="middle">Citation Verifier</text>
  <text x="705" y="514" fill="#A5B4FC" font-size="10" text-anchor="middle">Provenance Match</text>

  <rect x="795" y="475" width="130" height="50" rx="6" fill="#065F46" stroke="#10B981" stroke-width="1"/>
  <text x="860" y="498" fill="#ECFDF5" font-size="11" font-weight="600" text-anchor="middle">Final Response</text>
  <text x="860" y="514" fill="#A7F3D0" font-size="10" text-anchor="middle">Answer + Citations</text>

  <text x="480" y="552" fill="#CBD5E1" font-size="11">• Grounded Refusal loop on insufficient evidence • Bounded 1-attempt Auto-Correction</text>

  <!-- TrafficManager Box -->
  <rect x="460" y="585" width="480" height="250" rx="8" fill="#0F172A" stroke="#06B6D4" stroke-width="1.5"/>
  <text x="480" y="615" fill="#CFFAFE" font-size="15" font-weight="700">TrafficManager & Resilience Engine</text>
  <text x="480" y="635" fill="#67E8F9" font-size="12 font-family="monospace">TrafficManager.ts / config.py (Concurrency & Rate Enforcer)</text>
  
  <rect x="480" y="650" width="220" height="70" rx="6" fill="#164E63" stroke="#0891B2" stroke-width="1"/>
  <text x="495" y="675" fill="#ECFEFF" font-size="12" font-weight="600">FIFO Queue & Concurrency</text>
  <text x="495" y="695" fill="#A5F3FC" font-size="11">• Max Queue Depth: 50–100</text>
  <text x="495" y="710" fill="#A5F3FC" font-size="11">• Max Concurrent Calls: 5 workers</text>

  <rect x="720" y="650" width="205" height="70" rx="6" fill="#164E63" stroke="#0891B2" stroke-width="1"/>
  <text x="735" y="675" fill="#ECFEFF" font-size="12" font-weight="600">Token Bucket Limiter</text>
  <text x="735" y="695" fill="#A5F3FC" font-size="11">• Sliding 60s Window: 30 RPM</text>
  <text x="735" y="710" fill="#A5F3FC" font-size="11">• Token Ceiling: 8,000 TPM</text>

  <rect x="480" y="730" width="220" height="70" rx="6" fill="#164E63" stroke="#0891B2" stroke-width="1"/>
  <text x="495" y="755" fill="#ECFEFF" font-size="12" font-weight="600">Circuit Breaker</text>
  <text x="495" y="775" fill="#A5F3FC" font-size="11">• Threshold: 5 failures</text>
  <text x="495" y="790" fill="#A5F3FC" font-size="11">• Reset Timeout: 30.0s</text>

  <rect x="720" y="730" width="205" height="70" rx="6" fill="#164E63" stroke="#0891B2" stroke-width="1"/>
  <text x="735" y="755" fill="#ECFEFF" font-size="12" font-weight="600">Backoff & Retries</text>
  <text x="735" y="775" fill="#A5F3FC" font-size="11">• Full Jitter Exponential</text>
  <text x="735" y="790" fill="#A5F3FC" font-size="11">• Max Retries: 3 attempts</text>

  <text x="480" y="822" fill="#94A3B8" font-size="11">Guarantees zero 429 rate limit violations across all 5 burst stress load scenarios.</text>

  <!-- ========================================================================= -->
  <!-- 3. RETRIEVAL & MODEL INFERENCE (Persistent Storage & Models) -->
  <!-- ========================================================================= -->
  <rect x="1000" y="130" width="360" height="730" rx="12" fill="url(#cardBg)" stroke="#10B981" stroke-width="2" filter="url(#shadow)"/>
  <path d="M 1000 142 A 12 12 0 0 1 1012 130 L 1348 130 A 12 12 0 0 1 1360 142 L 1360 180 L 1000 180 Z" fill="#064E3B"/>
  <text x="1020" y="162" fill="#D1FAE5" font-size="16" font-weight="700">3. RETRIEVAL & INFERENCE TIER</text>
  <text x="1270" y="162" fill="#A7F3D0" font-size="11" font-family="monospace">Data & Providers</text>

  <!-- Persistent Indexes -->
  <rect x="1020" y="200" width="320" height="255" rx="8" fill="#1E293B" stroke="#059669" stroke-width="1.5"/>
  <text x="1040" y="228" fill="#A7F3D0" font-size="15" font-weight="700">Persistent Retrieval Indexes</text>
  <text x="1040" y="246" fill="#6EE7B7" font-size="11 font-family="monospace">Pre-built on 3 arXiv Papers (402 chunks)</text>
  
  <rect x="1040" y="260" width="280" height="50" rx="6" fill="#064E3B" stroke="#10B981" stroke-width="1"/>
  <text x="1055" y="280" fill="#ECFDF5" font-size="12" font-weight="600">ChromaDB Vector Store (Dense)</text>
  <text x="1055" y="298" fill="#A7F3D0" font-size="10 font-family="monospace">all-MiniLM-L6-v2 (384d) • HNSW Cosine</text>

  <rect x="1040" y="320" width="280" height="50" rx="6" fill="#064E3B" stroke="#10B981" stroke-width="1"/>
  <text x="1055" y="340" fill="#ECFDF5" font-size="12" font-weight="600">BM25Okapi Index (Sparse Lexical)</text>
  <text x="1055" y="358" fill="#A7F3D0" font-size="10 font-family="monospace">bm25_index.json (k1=1.5, b=0.75)</text>

  <rect x="1040" y="380" width="280" height="50" rx="6" fill="#064E3B" stroke="#10B981" stroke-width="1"/>
  <text x="1055" y="400" fill="#ECFDF5" font-size="12" font-weight="600">SQLite Fact Store (Structured)</text>
  <text x="1055" y="418" fill="#A7F3D0" font-size="10 font-family="monospace">fact_store.db (tables, pages, sections)</text>

  <text x="1040" y="445" fill="#94A3B8" font-size="10">Fused at runtime via Reciprocal Rank Fusion: RRF-60</text>

  <!-- Model Providers -->
  <rect x="1020" y="475" width="320" height="360" rx="8" fill="#1E293B" stroke="#059669" stroke-width="1.5"/>
  <text x="1040" y="505" fill="#A7F3D0" font-size="15" font-weight="700">Dual Model Provider Strategy</text>
  
  <rect x="1040" y="525" width="280" height="135" rx="6" fill="#0F172A" stroke="#3B82F6" stroke-width="1.5"/>
  <text x="1055" y="550" fill="#93C5FD" font-size="13" font-weight="700">A. Hosted Groq Cloud (Primary)</text>
  <text x="1055" y="572" fill="#E2E8F0" font-size="11">• Model: openai/gpt-oss-120b</text>
  <text x="1055" y="590" fill="#E2E8F0" font-size="11">• Real ultra-fast LPU inference</text>
  <text x="1055" y="608" fill="#E2E8F0" font-size="11">• TTFT: 852.0ms | Turnaround: 1031.0ms</text>
  <text x="1055" y="626" fill="#E2E8F0" font-size="11">• Hardware: GroqCard LPU architecture</text>
  <text x="1055" y="644" fill="#93C5FD" font-size="10 font-family="monospace">GROQ_API_KEY environment binding</text>

  <rect x="1040" y="675" width="280" height="145" rx="6" fill="#0F172A" stroke="#8B5CF6" stroke-width="1.5"/>
  <text x="1055" y="700" fill="#C4B5FD" font-size="13" font-weight="700">B. Stand-in Simulator (Zero-Cost)</text>
  <text x="1055" y="722" fill="#E2E8F0" font-size="11">• In-Process ASGITransport (Memory)</text>
  <text x="1055" y="740" fill="#E2E8F0" font-size="11">• Calibrated Lognormal: 1033.8ms median</text>
  <text x="1055" y="758" fill="#E2E8F0" font-size="11">• 0.27% delta against real Groq</text>
  <text x="1055" y="776" fill="#E2E8F0" font-size="11">• Sliding window quota & fault injection</text>
  <text x="1055" y="794" fill="#C4B5FD" font-size="10 font-family="monospace">Zero-cost simulation & offline failover</text>

  <!-- Connectors -->
  <line x1="380" y1="740" x2="460" y2="260" stroke="#6366F1" stroke-width="2" stroke-dasharray="4,4" marker-end="url(#arrow)"/>
  <line x1="940" y1="430" x2="1040" y2="285" stroke="#10B981" stroke-width="2" marker-end="url(#arrowEmerald)"/>
  <line x1="940" y1="510" x2="1040" y2="580" stroke="#6366F1" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="940" y1="720" x2="1040" y2="740" stroke="#06B6D4" stroke-width="2" marker-end="url(#arrowCyan)"/>
</svg>
`;

// ==============================================================================
// D.2 LangGraph Workflow SVG
// ==============================================================================
const svgD2 = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 900" width="1400" height="900" style="background:#0B0F19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="gradFlow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#4F46E5"/>
      <stop offset="100%" stop-color="#06B6D4"/>
    </linearGradient>
    <filter id="shadowD2" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.4"/>
    </filter>
    <marker id="arr" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#818CF8"/>
    </marker>
    <marker id="arrGreen" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#10B981"/>
    </marker>
    <marker id="arrAmber" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#F59E0B"/>
    </marker>
    <marker id="arrRose" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#F43F5E"/>
    </marker>
  </defs>

  <!-- Title Banner -->
  <rect x="50" y="30" width="1300" height="70" rx="12" fill="#1E293B" stroke="#334155" stroke-width="1.5" filter="url(#shadowD2)"/>
  <text x="80" y="65" fill="#F8FAFC" font-size="22" font-weight="700">RESEARCH QUESTION PROCESSING WORKFLOW (D.2)</text>
  <text x="80" y="86" fill="#94A3B8" font-size="13">LangGraph Deterministic StateGraph Flow • Evidence Checking, Citation Verification & Refusal Cycle</text>
  <rect x="1110" y="47" width="215" height="34" rx="6" fill="#1E1B4B" stroke="#6366F1" stroke-width="1"/>
  <text x="1217" y="69" fill="#E0E7FF" font-size="12" font-weight="600" text-anchor="middle">graph.py State Execution</text>

  <!-- MAIN FLOW NODES -->

  <!-- Node 0: Request Entry -->
  <rect x="60" y="150" width="220" height="120" rx="10" fill="#1E293B" stroke="#6366F1" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="170" y="185" fill="#EEF2FF" font-size="16" font-weight="700" text-anchor="middle">START: /v1/ask</text>
  <text x="170" y="208" fill="#94A3B8" font-size="12" text-anchor="middle">Incoming AskRequest</text>
  <text x="170" y="228" fill="#CBD5E1" font-size="11" text-anchor="middle">• User question string</text>
  <text x="170" y="246" fill="#CBD5E1" font-size="11" text-anchor="middle">• Optional paper_filter</text>

  <!-- Arrow 0 -> 1 -->
  <line x1="280" y1="210" x2="330" y2="210" stroke="#818CF8" stroke-width="2.5" marker-end="url(#arr)"/>

  <!-- Node 1: Input Validation -->
  <rect x="330" y="150" width="240" height="120" rx="10" fill="#1E293B" stroke="#6366F1" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="450" y="185" fill="#EEF2FF" font-size="16" font-weight="700" text-anchor="middle">1. Validate Input</text>
  <text x="450" y="208" fill="#94A3B8" font-size="12" text-anchor="middle">StateGraph Node: validate</text>
  <text x="450" y="228" fill="#CBD5E1" font-size="11" text-anchor="middle">• Verify non-empty query</text>
  <text x="450" y="246" fill="#CBD5E1" font-size="11" text-anchor="middle">• Validate paper ID against 3 PDFs</text>

  <!-- Arrow 1 -> 2 -->
  <line x1="570" y1="210" x2="620" y2="210" stroke="#818CF8" stroke-width="2.5" marker-end="url(#arr)"/>

  <!-- Node 2: Hybrid Retrieval -->
  <rect x="620" y="140" width="280" height="140" rx="10" fill="#1E1B4B" stroke="#818CF8" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="760" y="172" fill="#EDE9FE" font-size="16" font-weight="700" text-anchor="middle">2. Hybrid Retrieval</text>
  <text x="760" y="195" fill="#A5B4FC" font-size="12" text-anchor="middle">Parallel ChromaDB + BM25</text>
  <text x="760" y="218" fill="#CBD5E1" font-size="11" text-anchor="middle">• Dense: all-MiniLM-L6-v2 cosine (top 15)</text>
  <text x="760" y="236" fill="#CBD5E1" font-size="11" text-anchor="middle">• Sparse: BM25Okapi lexical matching (top 15)</text>
  <text x="760" y="254" fill="#CBD5E1" font-size="11" text-anchor="middle">• RRF-60 Rank Fusion: Score = sum(1/(60+r))</text>

  <!-- Arrow 2 -> 3 -->
  <line x1="900" y1="210" x2="950" y2="210" stroke="#818CF8" stroke-width="2.5" marker-end="url(#arr)"/>

  <!-- Node 3: Evidence Decision Diamond / Gate -->
  <polygon points="1070,140 1190,210 1070,280 950,210" fill="#1E293B" stroke="#F59E0B" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="1070" y="205" fill="#FEF3C7" font-size="13" font-weight="700" text-anchor="middle">Evidence Gate</text>
  <text x="1070" y="222" fill="#FCD34D" font-size="11" text-anchor="middle">Sufficient?</text>

  <!-- Refusal Branch (Down from Evidence Gate) -->
  <line x1="1070" y1="280" x2="1070" y2="360" stroke="#F43F5E" stroke-width="2.5" marker-end="url(#arrRose)"/>
  <rect x="940" y="360" width="260" height="100" rx="8" fill="#4C0519" stroke="#E11D48" stroke-width="1.5" filter="url(#shadowD2)"/>
  <text x="1070" y="388" fill="#FFE4E6" font-size="14" font-weight="700" text-anchor="middle">Grounded Refusal Path</text>
  <text x="1070" y="408" fill="#FDA4AF" font-size="11" text-anchor="middle">Out-of-domain / Insufficient chunks</text>
  <text x="1070" y="428" fill="#FECDD3" font-size="11" text-anchor="middle">Sets refusal_reason • Empty citations</text>
  <text x="1070" y="444" fill="#FECDD3" font-size="11" text-anchor="middle">Status: 'refused' (Honest Boundary)</text>

  <!-- Arrow Refusal -> Final -->
  <path d="M 1070 460 L 1070 790 L 780 790" fill="none" stroke="#F43F5E" stroke-width="2" marker-end="url(#arrRose)"/>

  <!-- Arrow Evidence Gate (Yes) -> Generation -->
  <path d="M 1190 210 L 1260 210 L 1260 520 L 760 520 L 760 550" fill="none" stroke="#10B981" stroke-width="2.5" marker-end="url(#arrGreen)"/>
  <text x="1215" y="198" fill="#10B981" font-size="12" font-weight="700">YES</text>

  <!-- Node 4: Generation via TrafficManager -->
  <rect x="620" y="550" width="280" height="130" rx="10" fill="#0F172A" stroke="#06B6D4" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="760" y="582" fill="#E0F2FE" font-size="16" font-weight="700" text-anchor="middle">4. Model Generation</text>
  <text x="760" y="604" fill="#38BDF8" font-size="12" text-anchor="middle">Dispatched via TrafficManager</text>
  <text x="760" y="626" fill="#CBD5E1" font-size="11" text-anchor="middle">• Groq (openai/gpt-oss-120b) or Simulator</text>
  <text x="760" y="644" fill="#CBD5E1" font-size="11" text-anchor="middle">• Strictly conditioned on retrieved chunks</text>
  <text x="760" y="662" fill="#CBD5E1" font-size="11" text-anchor="middle">• Strict bracketed citation syntax enforcement</text>

  <!-- Arrow 4 -> 5 -->
  <line x1="620" y1="615" x2="490" y2="615" stroke="#818CF8" stroke-width="2.5" marker-end="url(#arr)"/>

  <!-- Node 5: Citation Verification -->
  <rect x="230" y="540" width="260" height="150" rx="10" fill="#1E293B" stroke="#818CF8" stroke-width="2" filter="url(#shadowD2)"/>
  <text x="360" y="572" fill="#EDE9FE" font-size="16" font-weight="700" text-anchor="middle">5. Citation Verifier</text>
  <text x="360" y="594" fill="#A5B4FC" font-size="12" text-anchor="middle">Deterministic Provenance Check</text>
  <text x="360" y="618" fill="#CBD5E1" font-size="11" text-anchor="middle">• Regex parse: [Title, arXiv:ID, p.X, Sec Y]</text>
  <text x="360" y="636" fill="#CBD5E1" font-size="11" text-anchor="middle">• Exact match against retrieved passage IDs</text>
  <text x="360" y="654" fill="#CBD5E1" font-size="11" text-anchor="middle">• Verifies page, section, and paper title</text>
  <text x="360" y="672" fill="#CBD5E1" font-size="11" text-anchor="middle">• Detects ungrounded or hallucinated citations</text>

  <!-- Decision from Verification -->
  <!-- Case A: Verified -> Final -->
  <path d="M 360 690 L 360 790 L 520 790" fill="none" stroke="#10B981" stroke-width="2.5" marker-end="url(#arrGreen)"/>
  <text x="380" y="740" fill="#10B981" font-size="12" font-weight="700">100% VERIFIED</text>

  <!-- Case B: Unverified -> Auto-Correction Loop -->
  <path d="M 230 615 L 140 615 L 140 450 L 330 450" fill="none" stroke="#F59E0B" stroke-width="2" stroke-dasharray="5,5" marker-end="url(#arrAmber)"/>
  <rect x="180" y="420" width="220" height="65" rx="6" fill="#451A03" stroke="#D97706" stroke-width="1.5"/>
  <text x="290" y="445" fill="#FEF3C7" font-size="12" font-weight="700" text-anchor="middle">Bounded Auto-Correction</text>
  <text x="290" y="465" fill="#FDE68A" font-size="10" text-anchor="middle">Max 1 Revision Attempt</text>
  <line x1="400" y1="450" x2="620" y2="580" stroke="#F59E0B" stroke-width="2" stroke-dasharray="5,5" marker-end="url(#arrAmber)"/>

  <!-- Final Node: Assembled Response -->
  <rect x="520" y="745" width="260" height="90" rx="10" fill="#064E3B" stroke="#10B981" stroke-width="2.5" filter="url(#shadowD2)"/>
  <text x="650" y="778" fill="#ECFDF5" font-size="16" font-weight="700" text-anchor="middle">FINAL: AskResponse</text>
  <text x="650" y="800" fill="#A7F3D0" font-size="11" text-anchor="middle">answer • citations[] • retrieved_passages[]</text>
  <text x="650" y="818" fill="#A7F3D0" font-size="11 font-family="monospace">status: 'verified' | 'refused' | 'unverified'</text>
</svg>
`;

// ==============================================================================
// D.3 Document Ingestion & Hybrid Retrieval Pipeline SVG
// ==============================================================================
const svgD3 = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 900" width="1400" height="900" style="background:#0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <defs>
    <filter id="shadowD3" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.3"/>
    </filter>
    <marker id="arrD3" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#38BDF8"/>
    </marker>
    <marker id="arrPurp" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 8 5 L 0 9 z" fill="#A855F7"/>
    </marker>
  </defs>

  <!-- Title Banner -->
  <rect x="40" y="30" width="1320" height="70" rx="12" fill="#1E293B" stroke="#334155" stroke-width="1.5" filter="url(#shadowD3)"/>
  <text x="70" y="65" fill="#F8FAFC" font-size="22" font-weight="700">INGESTION & HYBRID RETRIEVAL PIPELINE (D.3)</text>
  <text x="70" y="86" fill="#94A3B8" font-size="13">120 Pages • Layout-Aware Extraction • LangChain Chunking • Triple Multi-Modal Indexing & RRF Fusion</text>
  <rect x="1140" y="47" width="190" height="34" rx="6" fill="#064E3B" stroke="#10B981" stroke-width="1"/>
  <text x="1235" y="69" fill="#ECFDF5" font-size="12" font-weight="600" text-anchor="middle">402 Production Chunks</text>

  <!-- PHASE 1: SOURCE PAPERS -->
  <rect x="40" y="130" width="260" height="730" rx="12" fill="#1E293B" stroke="#475569" stroke-width="1.5" filter="url(#shadowD3)"/>
  <text x="60" y="165" fill="#F8FAFC" font-size="16" font-weight="700">1. SOURCE CORPUS</text>
  <text x="60" y="185" fill="#94A3B8" font-size="12">3 Exact arXiv Research PDFs</text>

  <rect x="60" y="210" width="220" height="180" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="75" y="238" fill="#38BDF8" font-size="13" font-weight="700">Paper 1: Attention</text>
  <text x="75" y="258" fill="#E2E8F0" font-size="11">arXiv:1706.03762v7</text>
  <text x="75" y="278" fill="#94A3B8" font-size="11">• 15 pages total</text>
  <text x="75" y="296" fill="#94A3B8" font-size="11">• Vaswani et al. (Google Brain)</text>
  <text x="75" y="314" fill="#94A3B8" font-size="11">• Key: Table 2 (BLEU 27.3/28.4)</text>
  <text x="75" y="332" fill="#94A3B8" font-size="11">• Multi-head self-attention</text>
  <text x="75" y="350" fill="#94A3B8" font-size="11">• Section 6.1 Translation</text>
  <text x="75" y="372" fill="#A5B4FC" font-size="11 font-family="monospace">53 Chunks Generated</text>

  <rect x="60" y="410" width="220" height="190" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="75" y="438" fill="#38BDF8" font-size="13" font-weight="700">Paper 2: Moshi</text>
  <text x="75" y="458" fill="#E2E8F0" font-size="11">arXiv:2410.00037v1</text>
  <text x="75" y="478" fill="#94A3B8" font-size="11">• 66 pages total</text>
  <text x="75" y="496" fill="#94A3B8" font-size="11">• Défossez et al. (Kyutai)</text>
  <text x="75" y="514" fill="#94A3B8" font-size="11">• Full-duplex speech-text</text>
  <text x="75" y="532" fill="#94A3B8" font-size="11">• Mimi neural audio codec</text>
  <text x="75" y="550" fill="#94A3B8" font-size="11">• 12.5 Hz streaming frame rate</text>
  <text x="75" y="568" fill="#94A3B8" font-size="11">• Helium 7B LLM backbone</text>
  <text x="75" y="588" fill="#A5B4FC" font-size="11 font-family="monospace">221 Chunks Generated</text>

  <rect x="60" y="620" width="220" height="190" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="75" y="648" fill="#38BDF8" font-size="13" font-weight="700">Paper 3: Dynamic Chunking</text>
  <text x="75" y="668" fill="#E2E8F0" font-size="11">arXiv:2507.07955v2</text>
  <text x="75" y="688" fill="#94A3B8" font-size="11">• 39 pages total</text>
  <text x="75" y="706" fill="#94A3B8" font-size="11">• Research Team</text>
  <text x="75" y="724" fill="#94A3B8" font-size="11">• Variable boundary chunking</text>
  <text x="75" y="742" fill="#94A3B8" font-size="11">• Semantic document partitioning</text>
  <text x="75" y="760" fill="#94A3B8" font-size="11">• Long-context RAG evaluation</text>
  <text x="75" y="778" fill="#94A3B8" font-size="11">• Multi-hop retrieval frontier</text>
  <text x="75" y="798" fill="#A5B4FC" font-size="11 font-family="monospace">128 Chunks Generated</text>

  <!-- Arrow Phase 1 -> Phase 2 -->
  <line x1="300" y1="490" x2="350" y2="490" stroke="#38BDF8" stroke-width="2.5" marker-end="url(#arrD3)"/>

  <!-- PHASE 2: EXTRACTION & CHUNKING -->
  <rect x="350" y="130" width="290" height="730" rx="12" fill="#1E293B" stroke="#475569" stroke-width="1.5" filter="url(#shadowD3)"/>
  <text x="370" y="165" fill="#F8FAFC" font-size="16" font-weight="700">2. INGESTION & CHUNKING</text>
  <text x="370" y="185" fill="#94A3B8" font-size="12">Document Ingestion Pipeline</text>

  <!-- Step A: PyMuPDF Extraction -->
  <rect x="370" y="210" width="250" height="180" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="390" y="240" fill="#A78BFA" font-size="14" font-weight="700">PyMuPDF (fitz) Extraction</text>
  <text x="390" y="262" fill="#CBD5E1" font-size="12">• Native C-speed parser</text>
  <text x="390" y="282" fill="#CBD5E1" font-size="12">• Preserves bounding boxes</text>
  <text x="390" y="302" fill="#CBD5E1" font-size="12">• Extracts section hierarchies</text>
  <text x="390" y="322" fill="#CBD5E1" font-size="12">• Captures complex markdown tables</text>
  <text x="390" y="342" fill="#CBD5E1" font-size="12">• Preserves mathematical formulas</text>
  <text x="390" y="365" fill="#818CF8" font-size="11 font-family="monospace">data/extracted/*.json</text>

  <!-- Arrow -->
  <line x1="495" y1="390" x2="495" y2="440" stroke="#A78BFA" stroke-width="2.5" marker-end="url(#arrPurp)"/>

  <!-- Step B: LangChain Recursive Chunking -->
  <rect x="370" y="440" width="250" height="230" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="390" y="470" fill="#A78BFA" font-size="14" font-weight="700">LangChain Chunking</text>
  <text x="390" y="492" fill="#C4B5FD" font-size="12 font-family="monospace">RecursiveCharacterTextSplitter</text>
  <text x="390" y="520" fill="#CBD5E1" font-size="12">• chunk_size = 500 chars</text>
  <text x="390" y="540" fill="#CBD5E1" font-size="12">• chunk_overlap = 100 chars</text>
  <text x="390" y="560" fill="#CBD5E1" font-size="12">• Natural markdown boundary splits</text>
  <text x="390" y="580" fill="#CBD5E1" font-size="12">• Retains paper_id, page, section</text>
  <text x="390" y="600" fill="#CBD5E1" font-size="12">• Table preservation logic</text>
  <text x="390" y="620" fill="#CBD5E1" font-size="12">• 402 chunks across 120 pages</text>
  <text x="390" y="645" fill="#818CF8" font-size="11 font-family="monospace">data/chunks/langchain_chunks.json</text>

  <!-- Summary badge -->
  <rect x="370" y="690" width="250" height="120" rx="8" fill="#1E1B4B" stroke="#6366F1" stroke-width="1"/>
  <text x="390" y="720" fill="#EEF2FF" font-size="13" font-weight="700">Chunk Density Distribution:</text>
  <text x="390" y="742" fill="#C7D2FE" font-size="11">• Attention: 3.53 chunks/page</text>
  <text x="390" y="760" fill="#C7D2FE" font-size="11">• Moshi: 3.35 chunks/page</text>
  <text x="390" y="778" fill="#C7D2FE" font-size="11">• Dynamic Chunking: 3.28 chunks/p</text>
  <text x="390" y="798" fill="#C7D2FE" font-size="11 font-weight="600">Total: 402 verified chunks</text>

  <!-- Arrow Phase 2 -> Phase 3 -->
  <line x1="640" y1="490" x2="690" y2="490" stroke="#38BDF8" stroke-width="2.5" marker-end="url(#arrD3)"/>

  <!-- PHASE 3: PERSISTENT TRIPLE INDEX -->
  <rect x="690" y="130" width="330" height="730" rx="12" fill="#1E293B" stroke="#475569" stroke-width="1.5" filter="url(#shadowD3)"/>
  <text x="710" y="165" fill="#F8FAFC" font-size="16" font-weight="700">3. TRIPLE INDEX ARCHITECTURE</text>
  <text x="710" y="185" fill="#94A3B8" font-size="12">Persistent Multi-Modal Vector & Relational Storage</text>

  <!-- Dense Index -->
  <rect x="710" y="210" width="290" height="175" rx="8" fill="#0F172A" stroke="#10B981" stroke-width="1.5"/>
  <text x="730" y="238" fill="#34D399" font-size="14" font-weight="700">A. Dense Vector Index (ChromaDB)</text>
  <text x="730" y="260" fill="#A7F3D0" font-size="11 font-family="monospace">all-MiniLM-L6-v2 (384 dimensions)</text>
  <text x="730" y="282" fill="#CBD5E1" font-size="12">• Space: HNSW Cosine Distance</text>
  <text x="730" y="300" fill="#CBD5E1" font-size="12">• L2-normalized dense embeddings</text>
  <text x="730" y="318" fill="#CBD5E1" font-size="12">• Semantic similarity for conceptual matching</text>
  <text x="730" y="336" fill="#CBD5E1" font-size="12">• Metadata: paper_id, page, section</text>
  <text x="730" y="360" fill="#6EE7B7" font-size="11 font-family="monospace">data/indexes/chroma/chroma.sqlite3</text>

  <!-- Sparse Index -->
  <rect x="710" y="405" width="290" height="175" rx="8" fill="#0F172A" stroke="#38BDF8" stroke-width="1.5"/>
  <text x="730" y="433" fill="#38BDF8" font-size="14" font-weight="700">B. Sparse Lexical Index (BM25Okapi)</text>
  <text x="730" y="455" fill="#BAE6FD" font-size="11 font-family="monospace">rank-bm25 Python implementation</text>
  <text x="730" y="477" fill="#CBD5E1" font-size="12">• Exact keyword matching (BLEU, Mimi)</text>
  <text x="730" y="495" fill="#CBD5E1" font-size="12">• k1 = 1.5, b = 0.75 tuning parameters</text>
  <text x="730" y="513" fill="#CBD5E1" font-size="12">• Tokenized corpus with word boundaries</text>
  <text x="730" y="531" fill="#CBD5E1" font-size="12">• Zero semantic drift on exact numbers/IDs</text>
  <text x="730" y="555" fill="#7DD3FC" font-size="11 font-family="monospace">data/indexes/bm25/bm25_index.json</text>

  <!-- FactStore Index -->
  <rect x="710" y="600" width="290" height="175" rx="8" fill="#0F172A" stroke="#F59E0B" stroke-width="1.5"/>
  <text x="730" y="628" fill="#FBBF24" font-size="14" font-weight="700">C. Structured Fact Store (SQLite)</text>
  <text x="730" y="650" fill="#FDE68A" font-size="11 font-family="monospace">Structured Relational Schema</text>
  <text x="730" y="672" fill="#CBD5E1" font-size="12">• Relational metadata lookup table</text>
  <text x="730" y="690" fill="#CBD5E1" font-size="12">• Markdown tables & figure extraction</text>
  <text x="730" y="708" fill="#CBD5E1" font-size="12">• Exact filter by paper_id & section</text>
  <text x="730" y="726" fill="#CBD5E1" font-size="12">• Provenance verification ground-truth</text>
  <text x="730" y="750" fill="#FCD34D" font-size="11 font-family="monospace">data/indexes/fact_store.db</text>

  <text x="710" y="805" fill="#94A3B8" font-size="11">Pre-built and committed for zero-downtime deployment</text>

  <!-- Arrow Phase 3 -> Phase 4 -->
  <line x1="1020" y1="490" x2="1070" y2="490" stroke="#38BDF8" stroke-width="2.5" marker-end="url(#arrD3)"/>

  <!-- PHASE 4: QUERY TIME RRF FUSION -->
  <rect x="1070" y="130" width="290" height="730" rx="12" fill="#1E293B" stroke="#6366F1" stroke-width="2" filter="url(#shadowD3)"/>
  <text x="1090" y="165" fill="#EDE9FE" font-size="16" font-weight="700">4. RRF HYBRID FUSION</text>
  <text x="1090" y="185" fill="#C7D2FE" font-size="12">Query Execution Engine</text>

  <!-- Query Box -->
  <rect x="1090" y="210" width="250" height="90" rx="8" fill="#1E1B4B" stroke="#6366F1" stroke-width="1"/>
  <text x="1105" y="238" fill="#EEF2FF" font-size="13" font-weight="700">User Technical Query</text>
  <text x="1105" y="258" fill="#CBD5E1" font-size="11 font-family="monospace">q = "What is the BLEU score..."</text>
  <text x="1105" y="278" fill="#A5B4FC" font-size="11">Dispatched simultaneously to both</text>

  <!-- Parallel Branch -->
  <rect x="1090" y="320" width="250" height="150" rx="8" fill="#0F172A" stroke="#334155" stroke-width="1"/>
  <text x="1105" y="348" fill="#F8FAFC" font-size="13" font-weight="700">Parallel Top-K Retrieval</text>
  <text x="1105" y="372" fill="#34D399" font-size="12">• Dense Chroma: Top-15 ranks</text>
  <text x="1105" y="392" fill="#38BDF8" font-size="12">• Sparse BM25: Top-15 ranks</text>
  <text x="1105" y="416" fill="#CBD5E1" font-size="11">Paper Filter applied at query time:</text>
  <text x="1105" y="434" fill="#A5B4FC" font-size="11 font-family="monospace">where={"paper_id": "1706.03762v7"}</text>

  <!-- RRF Math Formula Card -->
  <rect x="1090" y="490" width="250" height="180" rx="8" fill="#312E81" stroke="#818CF8" stroke-width="1.5"/>
  <text x="1105" y="520" fill="#EEF2FF" font-size="14" font-weight="700">Reciprocal Rank Fusion</text>
  <text x="1105" y="545" fill="#E0E7FF" font-size="12 font-family="monospace">RRF Score Formula (k = 60):</text>
  
  <rect x="1105" y="560" width="220" height="40" rx="6" fill="#1E1B4B" stroke="#6366F1" stroke-width="1"/>
  <text x="1215" y="585" fill="#38BDF8" font-size="12" font-family="monospace" font-weight="700" text-anchor="middle">RRF(d) = Σ [ 1 / (60 + r_m) ]</text>

  <text x="1105" y="620" fill="#C7D2FE" font-size="11">• Eliminates score scaling artifacts</text>
  <text x="1105" y="638" fill="#C7D2FE" font-size="11">• Rewards passages present in both</text>
  <text x="1105" y="656" fill="#C7D2FE" font-size="11">• Top 5 fused passages returned</text>

  <!-- Output Box -->
  <rect x="1090" y="690" width="250" height="140" rx="8" fill="#064E3B" stroke="#10B981" stroke-width="1.5"/>
  <text x="1105" y="720" fill="#ECFDF5" font-size="14" font-weight="700">Reranked Context Chunks</text>
  <text x="1105" y="744" fill="#A7F3D0" font-size="11">• Top 5 most relevant passages</text>
  <text x="1105" y="764" fill="#A7F3D0" font-size="11">• Injected into LangGraph context</text>
  <text x="1105" y="784" fill="#A7F3D0" font-size="11">• Provenance verified metadata</text>
  <text x="1105" y="808" fill="#6EE7B7" font-size="11 font-weight="600">Retrieval Quality: Hit@5 = 100%</text>
</svg>
`;

async function renderDiagrams() {
  console.log('Rendering SVG architecture and workflow diagrams...');
  
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: {
      width: 1400,
      height: 900,
      deviceScaleFactor: 2,
    }
  });

  const page = await browser.newPage();

  try {
    // 1. Render D.1 Overall System Architecture
    await page.setContent(svgD1, { waitUntil: 'load' });
    const d1Path = path.join(OUTPUT_DIR, 'D1_overall_system_architecture.png');
    await page.screenshot({ path: d1Path });
    console.log('Saved D.1 to:', d1Path);

    // 2. Render D.2 Research Question Processing Workflow
    await page.setContent(svgD2, { waitUntil: 'load' });
    const d2Path = path.join(OUTPUT_DIR, 'D2_research_question_workflow.png');
    await page.screenshot({ path: d2Path });
    console.log('Saved D.2 to:', d2Path);

    // 3. Render D.3 Ingestion & Hybrid Retrieval Pipeline
    await page.setContent(svgD3, { waitUntil: 'load' });
    const d3Path = path.join(OUTPUT_DIR, 'D3_ingestion_hybrid_retrieval.png');
    await page.screenshot({ path: d3Path });
    console.log('Saved D.3 to:', d3Path);

    console.log('ALL 3 ARCHITECTURE DIAGRAMS RENDERED SUCCESSFULLY!');
  } finally {
    await browser.close();
  }
}

renderDiagrams().catch(err => {
  console.error('Error rendering diagrams:', err);
  process.exit(1);
});
