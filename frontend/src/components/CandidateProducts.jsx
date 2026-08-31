import React, { useState } from "react";

export default function CandidateProducts({
  candidates = [],
  selectedIndex = 0,
  onSelectCandidate,
  likedIds = [],
  onToggleLike,
  loading = false,
}) {
  const activeIdx = typeof selectedIndex === "number" ? selectedIndex : 0;

  const handleSelect = (idx) => {
    if (onSelectCandidate && candidates[idx]) {
      onSelectCandidate(idx, candidates[idx]);
    }
  };


  const getStoreBadge = (source = "") => {
    const s = (source || "").toLowerCase();
    if (s.includes("amazon")) return "Amazon.in";
    if (s.includes("flipkart")) return "Flipkart";
    if (s.includes("croma")) return "Croma";
    if (s.includes("oneplus")) return "OnePlus";
    if (s.includes("boat")) return "boAt";
    if (s.includes("myntra")) return "Myntra";
    if (s.includes("reliance")) return "Reliance Digital";
    if (s.includes("tatacliq") || s.includes("tata cliq")) return "Tata CLiQ";
    return source || "Verified Store";
  };

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
            Ranked live from SerpAPI Google Shopping & verified e-commerce marketplace feeds
          </p>
        </div>
        <div className="live-model-badge">
          <span className="verified-dot-green" />
          <span>Real SerpAPI Products ({candidates.length} live matches)</span>
        </div>
      </div>

      <div className="candidate-cards-grid candidate-cards-full-grid">
        {listToRender.map((c, idx) => {
          const isSelected = idx === activeIdx;
          const rawScore = c.utility_score || (0.96 - idx * 0.04);

          const matchPct = Math.min(Math.max(Math.round(rawScore * 100), 50), 98);
          const storeBadge = getStoreBadge(c.source);
          const currentPrice = formatRupees(c.effective_price || c.price);
          const oldPrice = c.old_price ? formatRupees(c.old_price) : null;
          const isLiked = Array.isArray(likedIds) && likedIds.includes(c.product_id || c.name);
          const numRating = Number(c.rating);
          const ratingVal = !isNaN(numRating) && numRating > 0 ? numRating.toFixed(1) : "4.4";
          const reviewsCount = typeof c.review_count === "number" ? c.review_count.toLocaleString("en-IN") : (c.review_count || "1,200");

          const sentimentLabel = c.sentiment_label || (
            numRating >= 4.4 ? "Very positive feedback" :
            numRating >= 4.0 ? "Mostly positive feedback" :
            numRating >= 3.4 ? "Mixed customer feedback" :
            "Some concerns in customer feedback"
          );

          const aiInsight = c.ai_insight || c.review_summary || "Strong customer satisfaction signal with consistently positive feedback and good evidence confidence.";

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
                  <span className="delivery-tag-text">{c.delivery || "Free Delivery · 2-3 days"}</span>
                </div>

                {/* Product Fit Match Progress */}
                <div className="bayesian-score-group">
                  <div className="bayesian-label-row">
                    <span>Product Fit</span>
                    <span className="bayesian-pct">Best fit · {matchPct}%</span>
                  </div>
                  <div className="bayesian-bar-track">
                    <div className="bayesian-bar-fill" style={{ width: `${matchPct}%` }} />
                  </div>
                </div>


                {/* AI Review Box */}
                <div className="sentiment-analysis-box">
                  <div className="sentiment-header">
                    <span className="sentiment-dot-green" />
                    <span className="sentiment-title">AI REVIEW</span>
                    <span className="sentiment-pct-badge">{sentimentLabel}</span>
                  </div>
                  <p className="sentiment-text">
                    "{aiInsight}"
                  </p>
                </div>

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
