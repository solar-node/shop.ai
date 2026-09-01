import React, { useState } from "react";

export default function CandidateProducts({
  candidates = [],
  selectedIndex = 0,
  onSelectCandidate,
  likedIds = [],
  onToggleLike,
  loading = false,
  budgetMax = 0,
}) {

  const activeIdx = typeof selectedIndex === "number" ? selectedIndex : 0;

  const handleSelect = (idx) => {
    if (onSelectCandidate && candidates[idx]) {
      onSelectCandidate(idx, candidates[idx]);
    }
  };


  const getStoreBadge = (source = "") => source || "Marketplace";

  const formatRupees = (val) => {
    if (!val && val !== 0) return "—";
    const num = typeof val === "number" ? val : parseFloat(String(val).replace(/[^0-9.]/g, ""));
    if (isNaN(num)) return val;
    return Math.round(num).toLocaleString("en-IN");
  };

  // Only render when candidates are evaluated and available
  if (!candidates || candidates.length === 0) {
    return null;
  }


  const listToRender = candidates.slice(0, 3);

  return (
    <section className="candidate-products-section candidate-products-full-width">
      <div className="section-header-row">
        <div>
          <h3 className="section-title">Candidate products & AI evaluation</h3>
          <p className="section-subtitle">
            Ranked from live marketplace evidence and agent research
          </p>
        </div>
        <div className="live-model-badge">
          <span className="verified-dot-green" />
          <span>Live candidates ({candidates.length} matches)</span>
        </div>
      </div>

      <div className="candidate-cards-grid candidate-cards-full-grid">
        {listToRender.map((c, idx) => {
          const isSelected = idx === activeIdx;
          const rawScore = Number(c.utility_score) || 0;

          const matchPct = Math.round(rawScore * 100);
          const storeBadge = getStoreBadge(c.source);
          const currentPrice = formatRupees(c.effective_price || c.price);
          const oldPrice = c.old_price ? formatRupees(c.old_price) : null;
          const isLiked = Array.isArray(likedIds) && likedIds.includes(c.product_id || c.name);
          const numRating = Number(c.rating);
          const ratingVal = !isNaN(numRating) && numRating > 0 ? numRating.toFixed(1) : "—";
          const reviewsCount = typeof c.review_count === "number" ? c.review_count.toLocaleString("en-IN") : "—";

          const sentimentLabel = c.sentiment_label || (
            numRating >= 4.4 ? "Very positive feedback" :
            numRating >= 4.0 ? "Mostly positive feedback" :
            numRating >= 3.4 ? "Mixed customer feedback" :
            "Some concerns in customer feedback"
          );

          const aiInsight = c.ai_insight || c.review_summary || (c.review_evidence?.evidence_summary || "Review evidence was not available.");

          const rawPrice = Number(c.effective_price || c.price) || 0;
          const budgetNum = Number(budgetMax) || 0;
          let budgetFitTag = null;
          if (budgetNum > 0 && rawPrice > 0) {
            if (rawPrice >= 0.85 * budgetNum && rawPrice <= budgetNum) {
              budgetFitTag = { text: "Optimal budget fit (85–100% target)", type: "optimal" };
            } else if (rawPrice < 0.85 * budgetNum) {
              const target85 = Math.round(0.85 * budgetNum).toLocaleString("en-IN");
              budgetFitTag = { text: `Below 85% target budget (< ₹${target85})`, type: "low" };
            } else {
              budgetFitTag = { text: `Exceeds ₹${budgetNum.toLocaleString("en-IN")} ceiling`, type: "high" };
            }
          }


          const matchedReqs = Array.isArray(c.matched_requirements) ? c.matched_requirements.slice(0, 4) : [];

          return (
            <div
              key={c.product_id || idx}
              className={`candidate-product-card candidate-card-large ${isSelected ? "card-selected-match" : ""}`}
              onClick={() => handleSelect(idx)}
            >
              {/* Product Image Banner (Upper part fully filled edge-to-edge) */}
              <div className="product-image-container product-image-container-full-bleed">
                <span className="match-rank-badge">#{idx + 1} match</span>

                <button
                  className={`card-heart-like-btn ${isLiked ? "liked" : ""}`}
                  title={isLiked ? "Remove product from likes" : "Save product"}
                  aria-label={isLiked ? "Remove product from likes" : "Save product"}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleLike && onToggleLike(c);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill={isLiked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                </button>

                {c.image_url ? (
                  <img
                    src={c.image_url}
                    alt={c.name}
                    className="product-card-img product-img-full-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="product-no-img-box">
                    <span>{c.name?.slice(0, 20)}</span>
                  </div>
                )}
              </div>

              {/* Product Info & Multi-Agent Details */}
              <div className="product-card-body">
                {/* Title & Store */}
                <div className="product-title-row">
                  <span className="product-title-text" title={c.name}>{c.name}</span>
                  <span className="store-pill-tag">{storeBadge}</span>
                </div>

                {/* Rating & Delivery Info */}
                <div className="product-rating-delivery-row">
                  <span className="star-rating-badge">★ {ratingVal}</span>
                  <span className="review-count-text">({reviewsCount}+ verified reviews)</span>
                  <span style={{ color: "var(--border)" }}>·</span>
                  <span className="delivery-tag-text">{c.delivery || "Delivery details unavailable"}</span>
                </div>

                {/* Product Fit Match Progress & Budget Range Fit */}
                <div className="bayesian-score-group">
                  <div className="bayesian-label-row">
                    <span>Product Fit (Bayesian Score)</span>
                    <span className="bayesian-pct">Score · {matchPct}%</span>
                  </div>
                  <div className="bayesian-bar-track">
                    <div className="bayesian-bar-fill" style={{ width: `${matchPct}%` }} />
                  </div>
                  {budgetFitTag && (
                    <div className={`budget-targeting-indicator ${budgetFitTag.type}`}>
                      <span>{budgetFitTag.text}</span>
                    </div>
                  )}
                </div>

                {/* Dynamic Extracted Feature Tags */}
                {matchedReqs.length > 0 && (
                  <div className="dynamic-specs-tag-row">
                    {matchedReqs.map((req, rIdx) => (
                      <span key={rIdx} className="spec-feature-pill">
                        ✓ {req}
                      </span>
                    ))}
                  </div>
                )}

                {/* Dynamic WHY THIS PRODUCT? Section */}

                {(() => {
                  const reasons = (Array.isArray(c.recommendation_reasons) && c.recommendation_reasons.length > 0 && c.recommendation_reasons) ||
                                  (Array.isArray(c.why_this_product) && c.why_this_product.length > 0 && c.why_this_product) ||
                                  [];
                  if (!reasons || reasons.length === 0) return null;

                  return (
                    <div className="why-product-box">
                      <div className="why-product-header">
                        <span className="why-product-title">WHY THIS PRODUCT?</span>
                      </div>
                      <ul className="why-product-list">
                        {reasons.slice(0, 4).map((reason, rIdx) => (
                          <li key={rIdx} className="why-product-item">
                            <svg className="why-check-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span className="why-reason-text">{reason}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })()}



                <div className="product-price-action-row">
                  <div className="price-stack">
                    {oldPrice && (
                      <span className="price-old-strike">₹{oldPrice}</span>
                    )}
                    <span className="price-current-bold price-rupees-bold">₹{currentPrice}</span>
                  </div>

                  <button
                    className={`select-candidate-btn ${isSelected ? "btn-selected" : "btn-unselected"}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelect(idx);
                    }}
                  >
                    {isSelected ? "Selected ✓" : "Select Product"}
                  </button>
                </div>

                {/* Direct Store Link if available */}
                {c.flipkart_url && (
                  <div style={{ marginTop: "4px", textAlign: "right" }}>
                    <a
                      href={c.flipkart_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="store-direct-link"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View live listing on {storeBadge} ↗
                    </a>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
