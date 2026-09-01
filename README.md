# shop.ai — Autonomous Shopping Agent

shop.ai is an AI-native shopping agent that turns a natural-language shopping goal into a researched, evidence-backed and policy-checked purchase.


The architecture is intentionally **category-extensible**: the LLM decides what the user wants and which attributes matter instead of maintaining a growing list of product categories and specifications in Python.

## Architecture

```text
                         USER SHOPPING GOAL
                                  │
                                  ▼
                    ┌────────────────────────┐
                    │ Intent / Shopping      │
                    │ Planner — LLM          │
                    └────────────┬───────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
        Marketplace         Product Info      Review / Trust
        Research            Research           Research
        Tool/API            LLM                Python
                 └───────────────┬───────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │ Evidence Synthesis      │
                    │ LLM                     │
                    └────────────┬───────────┘
                                 ▼
                    ┌────────────────────────┐
                    │ Product Analyst         │
                    │ Deterministic Python    │
                    │ Bayesian Ranking        │
                    └────────────┬───────────┘
                                 ▼
                    ┌────────────────────────┐
                    │ Recommendation LLM      │
                    │ WHY THIS PRODUCT?       │
                    └────────────┬───────────┘
                                 ▼
                    ┌────────────────────────┐
                    │ Risk Guard              │
                    │ Deterministic Python    │
                    └────────────┬───────────┘
                                 ▼
                              Approval?
                             /         \
                           YES          AUTO
                            │             │
                            └──────┬──────┘
                                   ▼
                            Purchase Agent
                                   │
                                Razorpay
```

### Why this split?

- **LLMs** handle natural language, category understanding, attribute discovery, evidence synthesis and explanations.
- **Python** handles arithmetic, ranking, inventory, financial policy and payment verification.
- The LLM is never allowed to change the deterministic ranking or bypass the Risk Guard.

### Parallel research

After intent extraction, three independent branches execute concurrently in LangGraph:

1. **Marketplace Research** — retrieves live listings and factual marketplace fields.
2. **Product Info Research** — an LLM determines which attributes are important for the current request.
3. **Review/Trust Research** — prepares the statistical review-evidence model.

The branches join at **Evidence Synthesis**, where an LLM combines their outputs into normalized product evidence.

## Ranking

The Product Analyst uses deterministic Bayesian review evidence rather than asking an LLM to choose the winner.

For rating `R` and review count `v`:

```text
Adjusted rating = (v × R + m × C) / (v + m)
```

where `m = 150` and `C = 3.8`.

Review-volume confidence is logarithmically scaled so evidence volume matters strongly without allowing review count alone to dominate product fit.

The final utility combines:

```text
45% quality/evidence
35% requirement match
10% price fit
10% availability
```

Requirement matching is based on the **LLM-normalized evidence** rather than category-specific Python rules.

## Grounded recommendations

The Recommendation Agent receives the ranked candidate plus the evidence used to evaluate it. It produces:

- personalized recommendation
- 3–4 **WHY THIS PRODUCT?** reasons
- tradeoffs

Reasons must be supported by supplied evidence. The system does not fabricate specifications or customer stories.

## Purchase safety

The Risk Guard is deliberately not an LLM.

It checks:

- verified budget ceiling
- verified product price
- merchant trust evidence
- confirmed stock
- optional autonomous purchase limit

Normal purchases require confirmation. Auto-buy can proceed only when the user's explicit auto-purchase limit permits it.

Razorpay payment completion is accepted only after backend signature verification.

## Project Structure

```text
shop.ai/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── research_agent.py
│   │   ├── product_info_agent.py
│   │   ├── review_trust_agent.py
│   │   ├── evidence_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── risk_agent.py
│   │   ├── purchase_agent.py
│   │   └── llm_client.py
│   ├── commerce/
│   │   ├── ranking.py
│   │   └── policies.py
│   ├── integrations/
│   │   └── product_scraper.py
│   ├── mcp/
│   ├── payments/
│   ├── inventory/
│   ├── observability/
│   └── api/
├── database/
├── frontend/
├── tests/
├── scripts/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup

### Backend

```bash
conda create -n shopai python=3.11
conda activate shopai
pip install -r requirements.txt
cp .env.example .env
```


Set the required values in `.env`:

```text
GEMINI_API_KEY=...
SERPAPI_KEY=...
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

`SCRAPERAPI_KEY` is optional.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Start the API

From the repository root:

```bash
uvicorn app.api.main:app --reload
```

Then open the frontend URL shown by Vite.

## Testing

Backend syntax / unit checks:

```bash
python -m pytest tests/test_pipeline.py
```

Frontend production build:

```bash
cd frontend
npm run build
```

## Security

Never commit `.env`, database files, API keys or generated frontend artifacts. Use `.env.example` as the configuration template.

Razorpay credentials remain backend-only. The frontend receives only the public Razorpay key ID required by Checkout.
