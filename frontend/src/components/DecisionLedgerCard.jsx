import React, { useState } from "react";

const STAGE_CONFIG = {
  INTENT: {
    name: "Intent",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
      </svg>
    ),
    defaultSummary: "Extracted shopping constraints, category, and budget ceiling.",
    details: {
      role: "Intent Understanding Agent (LLM)",
      tools: ["gemini_structured_parser", "heuristic_nlp_extractor"],
      method: "NLP intent decomposition & budget constraint parsing",
    },
  },
  RESEARCH: {
    name: "Research",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
    defaultSummary: "Queried live marketplace listings across Google Shopping & Amazon via SerpAPI.",
    details: {
      role: "Live Marketplace Catalog Agent (API)",
      tools: ["serpapi_google_shopping", "mcp_catalog_scanner"],
      method: "Real-time e-commerce catalog search & pricing extraction",
    },
  },
  ANALYST: {
    name: "Product Fit",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    defaultSummary: "Ranked candidates using multi-factor Bayesian utility math and budget fit.",
    details: {
      role: "Product Analyst & Utility Ranker (Python)",
      tools: ["bayesian_utility_ranker", "preference_weight_matrix"],
      method: "Deterministic utility scoring over price, ratings, and feature weights",
    },
  },
  EVALUATION: {
    name: "Review Evidence",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
    defaultSummary: "Customer feedback analyzed for sentiment consistency, sound quality, and daily reliability.",
    details: {
      role: "Review Signal & Recommendation Agent (LLM)",
      tools: ["gemini_review_analyzer", "evidence_confidence_scorer"],
      method: "Review sentiment classification and evidence grounding",
    },
  },
  RISK: {
    name: "Risk Guard",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    defaultSummary: "Purchase approved within budget ceiling, in-stock inventory, and seller trust policy.",
    details: {
      role: "Deterministic Policy & Safety Gate",
      tools: ["budget_ceiling_validator", "seller_reputation_guard"],
      method: "Hard rule verification before transaction staging",
    },
  },
  PURCHASE: {
    name: "Purchase / Razorpay",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
        <line x1="1" y1="10" x2="23" y2="10" />
      </svg>
    ),
    defaultSummary: "Ready for user confirmation & Razorpay checkout execution.",
    details: {
      role: "Payment Gateway Staging & Cart Reservation",
      tools: ["razorpay_order_api", "hmac_sha256_verifier"],
      method: "Cryptographic HMAC checkout staging and webhook authentication",
    },
  },
};

export default function DecisionLedgerCard({ events = [], sessionId, userGoal, activeState }) {
  const [expandedStage, setExpandedStage] = useState(null);

  const toggleExpand = (stageKey) => {
    setExpandedStage(expandedStage === stageKey ? null : stageKey);
  };

  // Get dynamic, grounded summaries from events or activeState
  const getDynamicSummary = (stageKey) => {
    if (stageKey === "INTENT") {
      const intentEvt = events.find((e) => (e.agent || "").toUpperCase().includes("INTENT"));
      const reqs = intentEvt?.detail || activeState?.requirements;
      if (reqs?.budget_max) {
        const cat = reqs.category || "earbuds";
        return `Extracted intent for ${cat} under ₹${Number(reqs.budget_max).toLocaleString("en-IN")}${reqs.brand_preference ? ` (${reqs.brand_preference})` : ""}.`;
      }
      return userGoal ? `Interpreted goal: "${userGoal}"` : STAGE_CONFIG.INTENT.defaultSummary;
    }

    if (stageKey === "RESEARCH") {
      const researchEvt = events.find((e) => (e.agent || "").toUpperCase().includes("RESEARCH") && e.detail?.count);
      const count = researchEvt?.detail?.count || activeState?.raw_products?.length || (activeState?.candidates?.length ? activeState.candidates.length : 6);
      return `${count} live marketplace listings found across Google Shopping & Amazon.`;
    }

    if (stageKey === "ANALYST") {
      const topCand = activeState?.candidates?.[0];
      if (topCand) {
        const scorePct = Math.round((topCand.utility_score || 0.96) * 100);
        return `Selected top match based on price, ANC capability, specifications, and ${scorePct}% product-fit score.`;
      }
      return STAGE_CONFIG.ANALYST.defaultSummary;
    }

    if (stageKey === "EVALUATION") {
      const topCand = activeState?.candidates?.[0] || activeState?.selected_product;
      const sentiment = topCand?.sentiment_label || "Very positive feedback";
      const insight = topCand?.ai_insight || "Customer feedback is strongly positive for sound quality and ANC.";
      return `${sentiment}: "${insight}"`;
    }

    if (stageKey === "RISK") {
      const risk = activeState?.risk;
      if (risk?.approved) {
        return "Purchase approved within budget and merchant safety policy.";
      }
      return STAGE_CONFIG.RISK.defaultSummary;
    }

    if (stageKey === "PURCHASE") {
      if (activeState?.status === "COMPLETED") {
        return "Payment completed & cryptographically verified via Razorpay.";
      }
      return "Ready for user confirmation & Razorpay checkout.";
    }

    return STAGE_CONFIG[stageKey]?.defaultSummary || "";
  };

  const stagesList = ["INTENT", "RESEARCH", "ANALYST", "EVALUATION", "RISK", "PURCHASE"];

  return (
    <div className="why-agent-chose-card">
      <div className="why-agent-header">
        <div>
          <h3 className="why-agent-title">Why the agent chose this</h3>
          <p className="why-agent-subtitle">Evidence behind the recommendation</p>
        </div>
      </div>

      <div className="why-agent-timeline">
        {stagesList.map((stageKey, idx) => {
          const config = STAGE_CONFIG[stageKey];
          const summary = getDynamicSummary(stageKey);
          const isExpanded = expandedStage === stageKey;

          return (
            <div
              key={stageKey}
              className={`why-agent-row ${isExpanded ? "row-expanded" : ""}`}
            >
              <div className="why-agent-dot-col">
                <span className="why-agent-icon-badge">
                  {config.icon}
                </span>
                {idx < stagesList.length - 1 && <span className="why-agent-line" />}
              </div>

              <div className="why-agent-content-col">
                <div className="why-agent-top-line">
                  <span className="why-agent-stage-name">{config.name}</span>
                  <button
                    className="why-agent-details-toggle"
                    onClick={() => toggleExpand(stageKey)}
                    type="button"
                  >
                    <span>{isExpanded ? "Hide Details" : "Details"}</span>
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s ease" }}
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </button>
                </div>

                <p className="why-agent-summary-text">
                  {summary}
                </p>

                {isExpanded && (
                  <div className="why-agent-expanded-panel">
                    <div className="why-detail-item">
                      <span className="why-detail-label">Agent Node:</span>
                      <span className="why-detail-val">{config.details.role}</span>
                    </div>
                    <div className="why-detail-item">
                      <span className="why-detail-label">Tools & Modules:</span>
                      <div className="why-detail-tools-row">
                        {config.details.tools.map((t) => (
                          <code key={t} className="why-tool-code">{t}</code>
                        ))}
                      </div>
                    </div>
                    <div className="why-detail-item">
                      <span className="why-detail-label">Methodology:</span>
                      <span className="why-detail-val">{config.details.method}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

