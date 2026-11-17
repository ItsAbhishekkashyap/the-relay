# The Relay — Frontend UI (Vercel Deployment Guide)

Modern SaaS light-theme interface for **The Relay: Production-Aware AI Research Assistant**, built with React 19, TypeScript, Vite, and Tailwind CSS v4.

---

## 1. Quick Deploy to Vercel

1. **Log in to Vercel:** Go to [vercel.com](https://vercel.com/) and sign in with GitHub.
2. **Add New Project:** Click **Add New...** > **Project**.
3. **Import Repository:** Select your GitHub repository.
4. **Configure Project Settings:**
   * **Framework Preset:** `Vite` (automatically detected)
   * **Root Directory:** Click **Edit** and select **`frontend`** *(Crucial: set to `frontend`)*
   * **Build Command:** `npm run build` (or `tsc -b && vite build`)
   * **Output Directory:** `dist`
   * **Install Command:** `npm install`
5. **Set Environment Variables on Vercel:**
   Under **Environment Variables**, add:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `VITE_API_BASE_URL` | `https://the-relay-backend.onrender.com` | **Required:** The URL of your deployed Render backend (NO trailing slash) |
   | `VITE_REQUEST_TIMEOUT_MS` | `10000` | Optional probe timeout in ms |
   | `VITE_ASK_TIMEOUT_MS` | `60000` | Optional inference timeout in ms |
   | `VITE_POLL_INTERVAL_MS` | `15000` | Optional live monitoring poll interval |
6. **Click Deploy:** Vercel will build and deploy your frontend in ~30 seconds. Your frontend URL will be:
   `https://the-relay-frontend.vercel.app`

---

## 2. Features Included

* **Research Chat:** Interactive question-answering with bracketed citations, evidence drawer, and grounded refusal handling.
* **System Overview:** Live health probes, queue depth gauge, active concurrency monitoring ($N/4$), and sliding-window RPM/TPM gauges.
* **Experiment Analytics:** Interactive scenario inspection (Scenarios A–E), latency percentile charts, and Stage 8B.2 retrieval comparison matrix.
* **Simulator Control Center:** Real-time simulator status and dynamic configuration controls.
* **Client Routing:** Fully configured with `vercel.json` for client-side SPA route rewrites.

---

## 3. Local Development in `frontend/`

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server with local proxy to localhost:8000
npm run dev

# Run automated test suites (54 tests)
npm test

# Run linter
npm run lint

# Build production bundle
npm run build
```
