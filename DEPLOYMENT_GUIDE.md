# The Relay — Production Deployment Guide (Render & Vercel)

This guide provides end-to-end instructions for deploying **The Relay — Production-Aware AI Research Assistant**:
* **Backend:** Deployed as a web service on **Render** (FastAPI + LangGraph + Hybrid Retrieval + Stand-in Simulator)
* **Frontend:** Deployed as a high-performance web application on **Vercel** (React 19 + TypeScript + Vite + Tailwind CSS v4)

---

## 1. Project Directory Layout

The repository is now structured into dedicated, decoupled directories for backend and frontend deployment:

```
RELAY ASSIGNMENT/
├── backend/                        # Dedicated backend directory for RENDER
│   ├── app/                        # FastAPI application, LangGraph workflow, Hybrid retriever
│   ├── simulator/                  # Calibrated stand-in model simulator (mounted at /simulator)
│   ├── data/                       # Pre-built ChromaDB, BM25, and FactStore SQLite indexes
│   ├── papers/                     # 3 original research PDFs (120 pages total)
│   ├── experiments/                # Empirical benchmarks, load scenario logs, results.csv
│   ├── scripts/                    # Automation scripts
│   ├── tests/                      # Automated test suites
│   ├── requirements.txt            # Pinned production Python dependencies
│   ├── pyproject.toml              # Python project configuration
│   ├── uv.lock                     # Dependency lockfile
│   ├── Dockerfile                  # Production container definition for Render
│   ├── .dockerignore               # Docker build exclusions
│   ├── render.yaml                 # Render Blueprint configuration
│   ├── .env.example                # Template for Render environment variables
│   ├── run.py                      # Standalone startup runner (honors Render $PORT)
│   └── README.md                   # Backend service documentation
│
├── frontend/                       # Dedicated frontend directory for VERCEL
│   ├── src/                        # React 19 source code (Pages, Components, Services)
│   ├── public/                     # Static assets
│   ├── package.json                # Frontend dependencies & build scripts
│   ├── tsconfig.json               # TypeScript configuration
│   ├── vite.config.ts              # Vite bundler configuration
│   ├── vercel.json                 # Vercel SPA routing configuration (rewrites to /index.html)
│   ├── .env.example                # Template for Vercel environment variables
│   ├── .env.production             # Production environment template
│   └── README.md                   # Frontend web application documentation
│
├── render.yaml                     # Root-level Render Blueprint (points rootDir to backend)
├── vercel.json                     # Root-level Vercel routing configuration
└── DEPLOYMENT_GUIDE.md             # This comprehensive master guide
```

---

## 2. Environment Variables (.env) Cheat Sheet

### A. Environment Variables to Attach on **RENDER** (Backend)

In your Render Dashboard, go to your Web Service > **Environment** tab, and add:

| Variable Name | Recommended Value | Required? | Description |
| :--- | :--- | :---: | :--- |
| `MODEL_PROVIDER` | `groq` *(or `simulator`)* | **Yes** | Set to `groq` to use real Groq LPU inference, or `simulator` for zero-cost stand-in testing. |
| `GROQ_API_KEY` | `gsk_your_actual_key_here` | **Yes (if groq)** | Your Groq Cloud API key from [console.groq.com/keys](https://console.groq.com/keys). |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Optional | Upstream Groq model identifier (defaults to `openai/gpt-oss-120b`). |
| `CORS_ORIGINS` | `*` *(or your Vercel URL)* | **Yes** | Comma-separated list of allowed frontend domains. Use `*` or `https://the-relay-frontend.vercel.app`. |
| `PORT` | `8000` | Optional | Automatically injected by Render. Our backend reads `$PORT` dynamically. |

> **Pro-Tip for Zero Spend:** If you want to deploy and test the entire system without spending anything on Groq API keys, set `MODEL_PROVIDER=simulator`. The calibrated stand-in simulator will run in-process and generate realistic responses!

---

### B. Environment Variables to Attach on **VERCEL** (Frontend)

In your Vercel Project Dashboard, go to **Settings** > **Environment Variables**, and add:

| Variable Name | Recommended Value | Required? | Description |
| :--- | :--- | :---: | :--- |
| `VITE_API_BASE_URL` | `https://the-relay-backend.onrender.com` | **Yes** | **The public URL of your deployed Render backend.** <br>⚠️ **DO NOT include a trailing slash.** |
| `VITE_REQUEST_TIMEOUT_MS` | `10000` | Optional | Timeout for status and health check probes (10 seconds). |
| `VITE_ASK_TIMEOUT_MS` | `60000` | Optional | Timeout for research question answering inference (60 seconds). |
| `VITE_POLL_INTERVAL_MS` | `15000` | Optional | Interval for live system monitoring refresh (15 seconds). |

---

## 3. Step-by-Step Deployment Instructions

### STEP 1: Deploy Backend to RENDER

1. **Sign in to Render:** Navigate to [dashboard.render.com](https://dashboard.render.com/).
2. **Create a Web Service:**
   * Click the **New +** button in the top right.
   * Select **Web Service**.
   * Choose **Build and deploy from a Git repository** and connect your GitHub repository.
3. **Configure Service Details:**
   * **Name:** `the-relay-backend` (or any unique name you choose).
   * **Region:** Select the region closest to your users (e.g., `Oregon (US West)` or `Frankfurt (EU)`).
   * **Branch:** `main` (or your active branch).
   * **Root Directory:** Type `backend` *(⚠️ Critical step: this tells Render to run inside the `backend/` folder)*.
   * **Runtime:** You can choose either **`Python`** *(Native)* or **`Docker`**:
     * **If choosing `Python` (Native):**
       * **Build Command:** `pip install -r requirements.txt && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"`
       * **Start Command:** `python run.py`
     * **If choosing `Docker`:**
       * Render automatically uses `backend/Dockerfile` with all pre-cached dependencies.
   * **Instance Type:** Select **Free** (512MB RAM).
4. **Add Environment Variables:**
   Scroll down to the **Environment Variables** section and add:
   * `MODEL_PROVIDER` = `groq` *(or `simulator`)*
   * `GROQ_API_KEY` = `gsk_your_groq_api_key_here` *(if using `groq`)*
   * `GROQ_MODEL` = `openai/gpt-oss-120b`
   * `CORS_ORIGINS` = `*`
   * `PYTHON_VERSION` = `3.11.10`
   * `MALLOC_ARENA_MAX` = `2` *(limits memory fragmentation to strictly stay within 512MB)*
   * `WEB_CONCURRENCY` = `1`
5. **Deploy:**
   * Click **Create Web Service**.
   * Render will build the container (takes ~2–3 minutes on first build).
   * Once live, copy your backend URL:
     `https://the-relay-backend.onrender.com`

#### Verify Render Backend:
Open your browser and test these endpoints:
* `https://the-relay-backend.onrender.com/health` $\rightarrow$ Returns `{"status":"ok","ready":true}`
* `https://the-relay-backend.onrender.com/ready` $\rightarrow$ Returns component initialization status
* `https://the-relay-backend.onrender.com/docs` $\rightarrow$ Interactive Swagger UI

---

### STEP 2: Deploy Frontend to VERCEL

1. **Sign in to Vercel:** Navigate to [vercel.com](https://vercel.com/) and log in with GitHub.
2. **Add New Project:**
   * Click **Add New...** > **Project**.
   * Find your repository and click **Import**.
3. **Configure Project Settings:**
   * **Project Name:** `the-relay-frontend` (or any name you choose).
   * **Framework Preset:** `Vite` *(Automatically detected)*.
   * **Root Directory:** Click **Edit** and choose `frontend` *(⚠️ Critical step)*.
   * **Build Command:** `npm run build` *(Default)*.
   * **Output Directory:** `dist` *(Default)*.
   * **Install Command:** `npm install` *(Default)*.
4. **Add Environment Variables on Vercel:**
   Expand the **Environment Variables** section:
   * **Key:** `VITE_API_BASE_URL`
   * **Value:** `https://the-relay-backend.onrender.com` *(Paste your actual Render URL from Step 1 with NO trailing slash)*.
5. **Deploy:**
   * Click **Deploy**.
   * Vercel will bundle and deploy the app in ~30–45 seconds.
   * Once deployed, your frontend URL will be:
     `https://the-relay-frontend.vercel.app`

---

## 4. End-to-End Verification Checklist

Once both services are deployed, perform this 2-minute verification:

1. **Open Frontend:** Navigate to your Vercel URL `https://the-relay-frontend.vercel.app`.
2. **Check System Overview Tab:**
   * The top status badge should display **System Ready** (green).
   * Concurrency should display `0/4` and Queue Depth `0/50`.
   * Sliding-window RPM and TPM gauges should show live readings.
3. **Test Research Chat (Grounded Query):**
   * Submit: *"What BLEU score did the Transformer base model achieve on English-to-German?"*
   * Expected answer: **27.3 BLEU**.
   * Citation badge: `[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 6.1 Machine Translation]`.
   * Click **View Evidence** to inspect the table snippet.
4. **Test Out-of-Domain Refusal:**
   * Submit: *"What is the capital of France?"*
   * Expected answer: Polite grounded refusal with **0 citations**.
5. **Check Experiment Analytics Tab:**
   * Select Scenarios A through E to view latency and reliability charts.
6. **Check Simulator Controls Tab:**
   * View live simulator status and calibrated distribution parameters.

---

## 5. Troubleshooting & FAQs

### Q1: I get a CORS error in the browser console.
* **Fix:** In your Render dashboard, check that `CORS_ORIGINS` is set to `*` or includes your exact Vercel frontend URL (e.g. `https://the-relay-frontend.vercel.app`).

### Q2: Render Free Tier "Cold Start" delay.
* **Explanation:** Render's free tier spins down web services after 15 minutes of inactivity. When you send your first request, it may take 30–50 seconds to wake up.
* **Fix:** Once awake, responses will be fast (~1s). Our frontend has a 60-second inference timeout (`VITE_ASK_TIMEOUT_MS=60000`) specifically configured to tolerate cold starts.

### Q3: My Vercel frontend shows "Failed to fetch" or "Network Error".
* **Check 1:** Ensure `VITE_API_BASE_URL` on Vercel does **NOT** have a trailing slash (e.g., use `https://my-app.onrender.com`, NOT `https://my-app.onrender.com/`).
* **Check 2:** Check that your Render backend is finished deploying and returns `{"status":"ok"}` when visiting `https://your-backend.onrender.com/health` directly.

### Q4: Can I run this with zero cloud spend?
* **Yes!** Set `MODEL_PROVIDER=simulator` on Render. The backend will run entirely against the local calibrated simulator, providing 100% of features with $0 spend.
