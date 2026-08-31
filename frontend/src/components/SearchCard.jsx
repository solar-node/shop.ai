import React, { useState, useRef, useEffect } from "react";

const STARTER_PROMPTS = [
  "Find ANC earbuds under ₹3000 for gym",
  "Compare top noise-cancelling headphones under ₹5000",
  "Best wireless earbuds with 40h+ battery under ₹2000",
  "Auto-buy boAt or OnePlus earbuds under ₹2500",
];

export default function SearchCard({ onSend, loading, currentGoal, isWorking }) {
  const [inputVal, setInputVal] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);

  // Initialize SpeechRecognition if supported
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-IN";

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setInputVal(transcript);
        }
        setIsRecording(false);
      };

      recognition.onerror = () => {
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  const toggleVoiceInput = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in this browser. Please type your request.");
      return;
    }
    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsRecording(true);
      } catch (err) {
        setIsRecording(false);
      }
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!inputVal.trim() || loading) return;
    onSend(inputVal.trim());
  };

  const handleChipClick = (chipText) => {
    setInputVal(chipText);
    onSend(chipText);
  };

  return (
    <div className="search-agent-card">
      {/* Top Header Row */}
      <div className="search-card-top-row">
        <div className="search-card-left-header">
          <div className="search-sparkle-icon-circle">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          </div>
          <div>
            <div className="search-title-text">Ask your autonomous buying agent</div>
            <div className="search-subtitle-text">
              Describe what you want to buy, your budget in ₹, or tell the agent to auto-buy.
            </div>
          </div>
        </div>

        <span className="badge-natural-language">AUTONOMOUS AGENT</span>
      </div>

      {/* Starter Prompts Row (4 prompts in 2 lines) */}
      {!isWorking && (
        <div className="search-chips-container-two-lines">
          <span className="chips-label">Try asking:</span>
          <div className="search-chips-2x2-grid">
            {STARTER_PROMPTS.map((prompt, i) => (
              <button
                key={i}
                className="suggestion-chip-btn suggestion-chip-compact"
                onClick={() => handleChipClick(prompt)}
                disabled={loading}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Row */}
      <form onSubmit={handleSubmit} className="search-input-form-row">
        <div className="search-input-wrapper">
          <input
            type="text"
            className="search-main-input"
            placeholder="e.g. Find ANC earbuds under ₹3000 with long battery life..."
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            disabled={loading}
          />
          <button
            type="button"
            className={`mic-icon-btn ${isRecording ? "recording" : ""}`}
            title={isRecording ? "Stop voice input" : "Tap to speak"}
            aria-label={isRecording ? "Stop voice input" : "Tap to speak"}
            onClick={toggleVoiceInput}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
        </div>

        <button
          type="submit"
          className="ask-agent-submit-btn"
          disabled={loading || !inputVal.trim()}
        >
          {loading ? (
            <span className="spinner-subtle" />
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              <span>Ask agent</span>
            </>
          )}
        </button>
      </form>

      {/* Active working on indicator */}
      {isWorking && currentGoal && (
        <div className="working-on-indicator-row">
          <span className="working-dot-cyan" />
          <span>Working on: <strong style={{ color: "var(--foreground)" }}>{currentGoal}</strong></span>
        </div>
      )}
    </div>
  );
}
