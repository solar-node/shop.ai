# BudBuy — Autonomous Multi-Agent Shopping Assistant

> AI-native shopping assistant built with **LangGraph**, **FastAPI**, **React**, and **Razorpay**. Researches live marketplace products, performs Bayesian volume-weighted ranking, synthesizes evidence-grounded recommendations, enforces deterministic policy risk gates, and completes Razorpay test checkouts.

---

## 🏛️ System Architecture (LangGraph)

```
                            USER SHOPPING GOAL
                                    │
                                    ▼
       1. Intent Agent              (Gemini NLP requirements extraction + regex fallback)
                                    │
                                    ▼
       2. Research Agent            (SerpAPI Google Shopping & Amazon India live scraper)
                                    │
                                    ▼
       3. Product Analyst           (Deterministic Bayesian rating & review-volume ranking)
                                    │
                                    ▼
       4. Evaluation & Rec.         (Feature extraction, review confidence & dynamic reasons)
                                    │
                                    ▼
       5. Risk Guard                (Deterministic budget, merchant trust & stock policy gate)
                                    │
                       ┌────────────┴────────────┐
                       ▼                         ▼
                 approval_node             purchase_node
             (Human-in-the-loop)       (Auto-checkout authorized)
                       │                         │
                       ▼ (User Confirms)         ▼
                 purchase_node                  END
                       │
                       ▼ (Razorpay Checkout & HMAC Verification)
                      END
```

---

## 💡 Core Engineering Principles

1. **Deterministic vs LLM Separation**:
   - **LLMs** are used where natural language understanding and evidence synthesis add value (intent parsing, review sentiment summarization, hardware feature extraction).
   - **Deterministic Algorithms** are strictly enforced for product rankings (`_bayesian_quality_score`), pricing calculations, risk policy checks, and Razorpay HMAC signature verification. The LLM is never allowed to arbitrarily pick a winner or bypass financial limits.
2. **Volume-Weighted Bayesian Ranking**:
   - Incorporates Bayesian mean prior shrinkage ($m=150.0, C=3.8$) and logarithmic review volume scaling so battle-tested products ($4.0★$ with 12,000 reviews) reliably outrank early products ($4.3★$ with 400 reviews) while penalizing low-sample noise.
3. **Resilient Two-Tier Fallbacks**:
   - All external LLM calls implement exponential backoff on HTTP 429 quota exhaustion with deterministic regex/heuristic fallbacks to ensure uninterrupted execution.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Lucide SVG Icons, JetBrains Mono |
| **Backend API** | FastAPI, Uvicorn, Python 3.11 |
| **Agent Framework** | **LangGraph** (`StateGraph`, TypedDict State, Checkpointing) |
| **LLM Reasoning** | **Google Gemini** (`google-genai`) |
| **Marketplace Scraper** | SerpAPI (Google Shopping India) |
| **Merchant Protocol** | Model Context Protocol (MCP stdio client/server) |
| **Database** | SQLite + SQLAlchemy |
| **Payment Gateway** | Razorpay Test API + HMAC-SHA256 Signature Verification |

---

## 🚀 Setup & Installation

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/your-username/budbuy.git
cd budbuy

# Create and activate virtual environment (or use conda)
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
```
Edit `.env` with your API keys:
- `GEMINI_API_KEY`: Google AI Studio Gemini API Key
- `RAZORPAY_KEY_ID`: Razorpay Test Mode Key ID
- `RAZORPAY_KEY_SECRET`: Razorpay Test Mode Key Secret
- `SERPAPI_KEY`: SerpAPI Google Shopping search key

### 3. Initialize Database
```bash
python3 scripts/seed_database.py
```

### 4. Run Automated Test Suite
```bash
python3 tests/test_pipeline.py
```

### 5. Start Backend & Frontend

**Terminal 1 — FastAPI Backend:**
```bash
uvicorn app.api.main:app --reload --port 8000
```

**Terminal 2 — React Frontend:**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
# → Open http://localhost:5173
```

---

## 🧪 Testing Realistic Shopping Queries

1. Open `http://localhost:5173`.
2. Try a realistic multi-constraint query:
   - *"Find ANC earbuds under ₹3000 for gym"*
   - *"Best wireless earbuds with deep bass under ₹2500"*
3. Watch the sequential multi-agent execution pipeline illuminate stage-by-stage as live candidates are ranked and verified.
4. Click **Select** on candidate cards to sync Risk Guard verification and complete payment in Razorpay Test Mode.

---

## 📂 Project Structure

```
budbuy/
├── app/
│   ├── agents/           orchestrator.py, research_agent.py, review_agent.py, recommendation_agent.py, risk_agent.py, purchase_agent.py
│   ├── api/              FastAPI REST routes (main.py)
│   ├── commerce/         ranking.py (Bayesian scoring), policies.py (Risk Guard)
│   ├── inventory/        reservation.py (Concurrency-safe inventory reservation)
│   ├── mcp/              merchant_server.py + client.py (Model Context Protocol)
│   ├── payments/         razorpay_client.py, idempotency.py
│   └── observability/    logger.py (Decision Ledger)
├── database/             models.py (SQLAlchemy schema)
├── frontend/             React 18 + Vite SPA
│   └── src/              App.jsx, components/, hooks/, api/
├── tests/                test_pipeline.py (Integration & unit test suite)
├── scripts/              seed_database.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
