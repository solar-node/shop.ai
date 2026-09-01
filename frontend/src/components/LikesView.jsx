import React from "react";

export default function LikesView({ likedProducts = [], onRemoveLike, onSelectProduct }) {
  return (
    <div className="view-panel-container">
      <div className="view-panel-header">
        <h2 className="view-panel-title">Liked products</h2>
        <p className="view-panel-desc">Products saved for later review.</p>
      </div>

      {likedProducts.length === 0 ? (
        <div className="orders-table-card">
          <div className="likes-empty-state">
            No liked products yet. Save products from your workspace.
          </div>
        </div>
      ) : (
        <div className="candidate-cards-grid">
          {likedProducts.map((p, idx) => (
            <div key={p.product_id || idx} className="candidate-product-card">
              <div className="product-image-container" style={{ background: p.bg_style || "var(--input-background)" }}>
                <button
                  className="card-heart-like-btn liked"
                  title="Remove product from likes"
                  onClick={() => onRemoveLike && onRemoveLike(p)}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                </button>
                <img src={p.image_url} alt={p.name} className="product-card-img" />
              </div>
              <div className="product-card-body">
                <div className="product-title-row">
                  <span className="product-title-text">{p.name}</span>
                  <span className="store-pill-tag">{p.source || "Amazon"}</span>
                </div>
                <div className="product-price-action-row">
                  <span className="price-current-bold">₹{typeof p.price === "number" ? Math.round(p.price).toLocaleString("en-IN") : p.price}</span>

                  <button
                    className="select-candidate-btn btn-selected"
                    onClick={() => onSelectProduct && onSelectProduct(p)}
                  >
                    View in workspace
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
