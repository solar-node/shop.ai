import React from "react";

export default function OrdersView({ orders = [] }) {
  const defaultOrders = [
    {
      id: "ord_1725039123",
      product_name: "Sony WH-1000XM5",
      merchant: "Amazon",
      status: "Confirmed",
      total: 2199,
      date: "Just now",
    },
  ];

  const orderList = orders.length > 0 ? orders : defaultOrders;

  return (
    <div className="view-panel-container">
      <div className="view-panel-header">
        <h2 className="view-panel-title">Orders</h2>
        <p className="view-panel-desc">Purchases confirmed by your buying agent.</p>
      </div>

      <div className="orders-table-card">
        <div className="orders-table-row head">
          <span>Order ID</span>
          <span>Product</span>
          <span>Merchant</span>
          <span>Total</span>
          <span>Status</span>
        </div>

        {orderList.map((o) => (
          <div key={o.id} className="orders-table-row">
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--muted-foreground)" }}>{o.id}</span>
            <span style={{ fontWeight: 600, color: "var(--foreground)" }}>{o.product_name}</span>
            <span style={{ color: "var(--text-secondary)" }}>{o.merchant}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--foreground)" }}>
              ₹{typeof o.total === "number" ? o.total.toLocaleString("en-IN") : o.total}
            </span>
            <span style={{ color: "var(--emerald)", fontWeight: 700, display: "flex", alignItems: "center", gap: "4px" }}>
              ✓ {o.status}
            </span>
          </div>
        ))}

      </div>
    </div>
  );
}
