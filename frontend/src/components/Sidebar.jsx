import React from "react";

export default function Sidebar({
  currentTab,
  onSelectTab,
  backendOnline,
  ordersCount = 1,
  likesCount = 0,
  conversations = [],
  activeConversationId = null,
  onSelectConversation = null,
}) {
  const defaultConversations = [
    { id: "c1", title: "Find noise-cancelling headphones" },
    { id: "c2", title: "Compare travel laptops" },
    { id: "c3", title: "Find products within my budget" },
  ];

  const threadList = conversations.length > 0 ? conversations : defaultConversations;

  return (
    <aside className="app-sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-logo-icon">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <rect x="3" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" />
          </svg>
        </div>
        <span className="brand-name">budbuy</span>
        <span className="brand-badge-beta">BETA</span>
      </div>

      {/* Navigation & Conversations */}
      <div className="sidebar-nav-container">
        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-nav">
          <button
            className={`nav-item ${currentTab === "workspace" ? "nav-item-active" : ""}`}
            onClick={() => onSelectTab && onSelectTab("workspace")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
            </svg>
            <span>Workspace</span>
          </button>

          <button
            className={`nav-item ${currentTab === "orders" ? "nav-item-active" : ""}`}
            onClick={() => onSelectTab && onSelectTab("orders")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
            </svg>
            <span>Orders</span>
            {ordersCount > 0 && <span className="nav-badge-count">{ordersCount}</span>}
          </button>

          <button
            className={`nav-item ${currentTab === "likes" ? "nav-item-active" : ""}`}
            onClick={() => onSelectTab && onSelectTab("likes")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <span>Likes</span>
            {likesCount > 0 && <span className="nav-badge-count">{likesCount}</span>}
          </button>
        </nav>

        {/* Conversation History */}
        <div style={{ marginTop: "16px" }}>
          <div className="sidebar-section-label">CONVERSATIONS</div>
          <div className="conversations-history-list">
            {threadList.map((t) => (
              <button
                key={t.id}
                className={`conversation-thread-btn ${activeConversationId === t.id ? "active" : ""}`}
                onClick={() => onSelectConversation && onSelectConversation(t)}
                title={t.title}
              >
                {t.title}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* System Status Footer */}
      <div className="sidebar-bottom-status">
        <div className="status-indicator-row">
          <span className={`status-pulse-dot ${backendOnline === false ? "offline" : ""}`} />
          <span className="status-title-text">All systems operational</span>
        </div>
        <div className="status-sub-text">
          Agents are monitoring your active session.
        </div>
      </div>
    </aside>
  );
}
