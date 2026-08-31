import React, { useState, useEffect } from "react";

export default function NeuralPipeline({ stateStatus, events = [], activeState = {} }) {
  const isCompleted = stateStatus === "COMPLETED" || activeState?.status === "COMPLETED";
  const stageStatus = activeState?.stage_status || {};
  const currentStage = activeState?.current_stage || "";

  // Determine current active stage index (0..5) strictly from backend state
  let targetIdx = 0;
  if (isCompleted) {
    targetIdx = 5;
  } else if (
    currentStage === "PURCHASE" ||
    activeState?.status === "AWAITING_PAYMENT" ||
    activeState?.status === "AWAITING_APPROVAL"
  ) {
    targetIdx = 4;
  } else if (
    currentStage === "RISK" ||
    activeState?.status === "RISK_RUNNING" ||
    stageStatus.risk === "running"
  ) {
    targetIdx = 4;
  } else if (
    currentStage === "EVALUATION" ||
    activeState?.status === "RECOMMENDING" ||
    stageStatus.evaluation === "running"
  ) {
    targetIdx = 3;
  } else if (
    currentStage === "ANALYST" ||
    activeState?.status === "ANALYZING" ||
    stageStatus.analyst === "running"
  ) {
    targetIdx = 2;
  } else if (
    currentStage === "RESEARCH" ||
    activeState?.status === "RESEARCHING" ||
    stageStatus.research === "running"
  ) {
    targetIdx = 1;
  } else {
    targetIdx = 0;
  }

  // Smooth animated progression index tracking actual backend stage
  const [displayedIdx, setDisplayedIdx] = useState(targetIdx);

  useEffect(() => {
    setDisplayedIdx(targetIdx);
  }, [targetIdx]);

  // A stage is DONE only if its backend execution has genuinely completed
  const isStageDone = (idx) => {
    if (isCompleted) return true;
    if (idx === 0) return stageStatus.intent === "completed" || targetIdx > 0;
    if (idx === 1) return stageStatus.research === "completed" || targetIdx > 1;
    if (idx === 2) return stageStatus.analyst === "completed" || targetIdx > 2;
    if (idx === 3) return stageStatus.evaluation === "completed" || targetIdx > 3;
    if (idx === 4) return stageStatus.risk === "completed" || activeState?.status === "AWAITING_APPROVAL" || activeState?.status === "AWAITING_PAYMENT";
    if (idx === 5) return isCompleted;
    return false;
  };

  const stages = [
    {
      id: "INTENT",
      num: "1",
      name: "Intent Agent",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
        </svg>
      ),
    },
    {
      id: "RESEARCH",
      num: "2",
      name: "Research Agent",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
    },
    {
      id: "ANALYST",
      num: "3",
      name: "Product Analyst",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
    {
      id: "EVALUATION",
      num: "4",
      name: "Evaluation & Recommendation",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      ),
    },
    {
      id: "RISK",
      num: "5",
      name: "Risk Guard",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      ),
    },
    {
      id: "PURCHASE",
      num: "6",
      name: "Purchase / Pay",
      icon: (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
          <line x1="1" y1="10" x2="23" y2="10" />
        </svg>
      ),
    },
  ];

  return (
    <section className="pipeline-stepper-container">
      <div className="section-header-row">
        <h3 className="section-title">Agent Execution Pipeline</h3>
        <div className="streaming-indicator-pill">
          <span className="streaming-pulse-dot" />
          <span>{isCompleted ? "COMPLETED" : "STREAMING PIPELINE"}</span>
        </div>
      </div>

      <div className="pipeline-stepper-wrapper">
        <div className="pipeline-stepper-flow">
          {stages.map((st, idx) => {
            const isDone = isStageDone(idx);
            const isCurrent = idx === targetIdx && !isDone && !isCompleted;
            const isQueued = !isDone && !isCurrent;

            // Connector line segment connects stage idx to stage idx + 1
            // Advances ONLY after stage idx genuinely completes
            const isSegmentDone = isStageDone(idx);

            return (
              <React.Fragment key={st.id}>
                {/* Node Circle Anchor */}
                <div
                  className={`flow-node-anchor ${isDone ? "item-done" : isCurrent ? "item-current" : "item-queued"}`}
                >
                  <div className="flow-node-circle">
                    {isDone ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="check-pop-anim">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      st.icon
                    )}
                  </div>
                  {isCurrent && <div className="flow-pulse-ring" />}

                  {/* Centered label block underneath circle */}
                  <div className="flow-label-group">
                    <div className="flow-name-line">
                      <span className="flow-num">{st.num}.</span>
                      <span className="flow-name">{st.name}</span>
                    </div>
                    <div className="flow-meta-line">
                      <span className={`flow-status-tag ${isDone ? "status-done" : isCurrent ? "status-current" : "status-queued"}`}>
                        {isDone ? "DONE" : isCurrent ? "RUNNING" : "WAITING"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Edge-touching connector line behind the circles */}
                {idx < stages.length - 1 && (
                  <div className={`flow-connector-line ${isSegmentDone ? "segment-done" : "segment-queued"}`}>
                    <div className={`flow-connector-fill ${isSegmentDone ? "fill-done" : ""}`} />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </section>
  );
}
