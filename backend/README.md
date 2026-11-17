# The Relay — Backend Service (Render Deployment Guide)

FastAPI backend for **The Relay: Production-Aware AI Research Assistant**, featuring LangGraph agentic reasoning, multi-channel hybrid retrieval (ChromaDB + BM25 + FactStore), asynchronous traffic governance, and unified simulator observability.

---

## 1. Quick Deploy to Render

### Option A: Deploy via Docker (Recommended)

1. **Log in to Render:** Go to [dashboard.render.com](https://dashboard.render.com/).
2. **Create New Web Service:** Click **New +** > **Web Service**.
3. **Connect Repository:** Connect your GitHub repository containing this project.
4. **Configure Service Settings:**
   * **Name:** `the-relay-backend` (or any chosen name)
   * **Region:** Choose the region nearest to you (e.g., `Oregon (US West)` or `Frankfurt (EU)`)
   * **Root Directory:** `backend` *(Crucial: set this so Render builds inside the backend directory)*
   * **Runtime:** `Docker`
   * **Instance Type:** `Free` (or higher)
5. **Set Environment Variables:**
   Under **Environment Variables**, add:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `MODEL_PROVIDER` | `groq` (or `simulator`) | Set to `groq` for live LLM, or `simulator` for zero-cost mode |
   | `GROQ_API_KEY` | `gsk_your_key_here` | Required if `MODEL_PROVIDER=groq` |
   | `GROQ_MODEL` | `openai/gpt-oss-120b` | Model identifier |
   | `CORS_ORIGINS` | `*` | Or specify your Vercel frontend URL: `https://your-frontend.vercel.app` |
6. **Click Create Web Service:** Render will build the Docker container and start the service. Your backend URL will be:
   `https://the-relay-backend.onrender.com`

---

### Option B: Deploy via Native Python (Alternative)

If you prefer deploying with Render's native Python runtime instead of Docker:
* **Root Directory:** `backend`
* **Runtime:** `Python 3`
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* **Environment Variables:** Same as Option A above.

---

## 2. API Endpoints Available on Render

Once deployed, your service exposes:
* **Health Check:** `GET /health` (`{"status": "ok", "ready": true}`)
* **Readiness Probe:** `GET /ready` (Validates retriever, provider, traffic manager)
* **Research Assistant Ask:** `POST /v1/ask` (`{"question": "..."}`)
* **Live System Metrics:** `GET /v1/metrics`
* **Experiment Analytics:** `GET /v1/experiments/overview`, `/load`, `/retrieval`
* **Simulator Observability:** `GET /simulator/status`, `GET /simulator/admin/config`
* **Interactive OpenAPI Docs:** `GET /docs`

---

## 3. Local Development in `backend/`

```bash
# Navigate to backend directory
cd backend

# Install dependencies with uv
uv sync

# Copy environment template
cp .env.example .env

# Run FastAPI backend locally
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
