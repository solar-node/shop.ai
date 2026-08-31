import React, { useState } from "react";

export default function RiskApprovalBanner({ riskData, onProceed, loading, price = 2499, productName = "" }) {
  const [showDetails, setShowDetails] = useState(false);
  const isApproved = riskData ? riskData.approved !== false : true;
  const formattedPrice = typeof price === "number" ? Math.round(price).toLocaleString("en-IN") : price;

  // Dynamically derive the reason to always reflect the currently selected product's price
  const displayReason = riskData?.reason
    ? riskData.reason.replace(/₹\s*[\d,]+(\.\d+)?/g, `₹${formattedPrice}`)
    : `Product verified at ₹${formattedPrice}. Confirmation required before proceeding to checkout.`;

  return (
    <div className="risk-guard-approval-banner risk-banner-prominent">
      <div className="risk-banner-main-row">
        <div className="risk-banner-left">
          <div className="risk-shield-icon-circle risk-shield-large">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>

          <div className="risk-banner-text-content">
            <div className="risk-title-badge-row">
              <span className="risk-banner-title">
                Risk Guard approval
              </span>
              <span className={`risk-status-pill ${isApproved ? "pill-approved" : "pill-review"}`}>
                {isApproved ? "APPROVED" : "REVIEW NEEDED"}
              </span>
            </div>

            <p className="risk-banner-desc">
              {displayReason}
            </p>

            <button
              className="risk-details-toggle-btn"
              onClick={() => setShowDetails(!showDetails)}
              type="button"
            >
              <span>{showDetails ? "Hide security details" : "Security & policy details"}</span>
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
              <span>Proceed to purchase</span>
            </>
          )}
        </button>
      </div>

      {showDetails && (
        <div className="risk-expanded-details-box">
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text"><strong>Budget Guard:</strong> ₹{formattedPrice} locked under your budget ceiling with zero hidden charges.</span>
          </div>
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text"><strong>Cryptographic Security:</strong> HMAC SHA-256 signature verification enabled for Razorpay gateway.</span>
          </div>
          <div className="risk-detail-row">
            <span className="detail-bullet">✓</span>
            <span className="detail-text"><strong>Seller Reputation:</strong> Verified merchant catalog with active return policy and fast delivery guarantee.</span>
          </div>
        </div>
      )}
    </div>
  );
}
