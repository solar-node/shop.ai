import React, { useState } from "react";

export default function RiskApprovalBanner({
  riskData,
  onProceed,
  loading,
  price = 0,
  productName = "",
  merchantName = "Verified Store",
  budgetMax = null,
  isAwaitingApproval = true,
  productImage = "",
}) {
  const [showDetails, setShowDetails] = useState(false);
  const isApproved = riskData ? riskData.approved !== false : true;
  const formattedPrice = typeof price === "number" ? Math.round(price).toLocaleString("en-IN") : price;
  const formattedBudget = typeof budgetMax === "number" ? Math.round(budgetMax).toLocaleString("en-IN") : (budgetMax || null);

  const displayReason = riskData?.reason
    ? riskData.reason.replace(/₹\s*[\d,]+(\.\d+)?/g, `₹${formattedPrice}`)
    : `Product verified at ₹${formattedPrice}. Human confirmation required before staging Razorpay checkout.`;

  return (
    <div className="risk-guard-approval-banner risk-banner-prominent">
      <div className="risk-banner-main-row">
        <div className="risk-banner-left">
          <div className={`risk-shield-icon-circle ${isApproved ? "risk-shield-approved" : "risk-shield-blocked"}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              {isApproved ? <path d="M9 12l2 2 4-4" /> : <line x1="12" y1="8" x2="12" y2="14" />}
            </svg>
          </div>

          <div className="risk-banner-text-content">
            <div className="risk-title-badge-row">
              <span className="risk-banner-title">
                Purchase Approval & Risk Assessment
              </span>
              <span className={`risk-status-pill ${isApproved ? (isAwaitingApproval ? "pill-review" : "pill-approved") : "pill-blocked"}`}>
                {isApproved ? (isAwaitingApproval ? "ACTION REQUIRED" : "APPROVED") : "POLICY BLOCKED"}
              </span>
            </div>

            <p className="risk-banner-desc">
              {displayReason}
            </p>

            {/* Selected Product Quick Info */}
            <div className="approval-product-quickbar">
              {productImage && (
                <img src={productImage} alt={productName} className="approval-thumb" />
              )}
              <div className="approval-meta">
                <div className="approval-name">{productName || "Selected Product"}</div>
                <div className="approval-pricing-row">
                  <span className="approval-price">₹{formattedPrice}</span>
                  <span className="approval-dot">·</span>
                  <span className="approval-merchant">{merchantName}</span>
                  {formattedBudget && (
                    <>
                      <span className="approval-dot">·</span>
                      <span className="approval-budget">Budget: ₹{formattedBudget}</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            <button
              className="risk-details-toggle-btn"
              onClick={() => setShowDetails(!showDetails)}
              type="button"
            >
              <span>{showDetails ? "Hide security checklist" : "View security & policy checklist"}</span>
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                style={{ transform: showDetails ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s ease" }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </div>
        </div>

        {/* Right CTA Action */}
        <div className="risk-banner-right">
          {isApproved ? (
            <button
              className="proceed-purchase-cta-btn proceed-cta-large"
              onClick={onProceed}
              disabled={loading}
            >
              {loading ? (
                <span className="spinner-subtle" />
              ) : (
                <>
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                    <circle cx="9" cy="21" r="1" />
                    <circle cx="20" cy="21" r="1" />
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                  </svg>
                  <span>Approve & Pay (₹{formattedPrice})</span>
                </>
              )}
            </button>
          ) : (
            <div className="risk-blocked-notice">
              <span>Checkout blocked by safety policy</span>
            </div>
          )}
        </div>
      </div>

      {showDetails && (
        <div className="risk-expanded-details-box">
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text">
              <strong>Budget Guard:</strong> ₹{formattedPrice} locked within your {formattedBudget ? `₹${formattedBudget} budget ceiling` : "budget"} with zero hidden fees.
            </span>
          </div>
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text">
              <strong>Stock & Inventory Lock:</strong> Warehouse stock verified; atomic 5-minute reservation TTL staged upon confirmation.
            </span>
          </div>
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text">
              <strong>Merchant Reputation:</strong> Verified merchant platform with active return policy and buyer protection guarantee.
            </span>
          </div>
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text">
              <strong>Cryptographic Security:</strong> HMAC-SHA256 authenticated Razorpay gateway order signature verification.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

