import React, { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught React Error in App:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: "100vh",
          width: "100vw",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#0B0F17",
          color: "#F3F5F8",
          fontFamily: "Inter, sans-serif",
          padding: "20px",
          textAlign: "center"
        }}>
          <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "10px", color: "#F43F5E" }}>
            Workspace encountered an issue
          </h2>
          <p style={{ color: "#8895A7", fontSize: "14px", maxWidth: "480px", marginBottom: "20px" }}>
            {this.state.error?.message || "An unexpected error occurred while rendering the agent pipeline."}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              padding: "10px 20px",
              background: "#00BAFF",
              color: "#000000",
              borderRadius: "8px",
              fontWeight: 600,
              cursor: "pointer",
              border: "none"
            }}
          >
            Reload Workspace
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
