import React from "react";

export default function Header({ userGoal, isWorking, sessionId }) {
  const [isLight, setIsLight] = React.useState(false);

  const toggleTheme = () => {
    const next = !isLight;
    setIsLight(next);
    if (next) {
      document.documentElement.classList.add("light-theme");
      document.body.classList.add("light-theme");
    } else {
      document.documentElement.classList.remove("light-theme");
      document.body.classList.remove("light-theme");
    }
  };

  return (
    <header className="main-top-header">
      <div className="header-left-title-group">
        <span className="header-eyebrow">
          {isWorking ? "ACTIVE WORKSPACE" : "BUDBUY AGENT"}
        </span>
        <h2 className="header-main-query">
          {userGoal ? userGoal : "New buying request"}
        </h2>
      </div>

      <div className="header-right-actions">
        <div className="header-search-pill">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span className="search-text">Search</span>
          <kbd className="search-kbd">⌘ K</kbd>
        </div>

        <button className="header-icon-btn" title={isLight ? "Switch to Dark Mode" : "Switch to Light Mode"} onClick={toggleTheme}>
          {isLight ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
          )}
        </button>

        <button className="header-icon-btn" title="Notifications">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>

        <div className="header-avatar-circle" title="User Profile">
          JD
        </div>
      </div>
    </header>
  );
}
