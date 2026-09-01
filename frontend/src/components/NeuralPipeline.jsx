import React from "react";

export default function NeuralPipeline({ stateStatus, events = [], activeState = {} }) {
  const isCompleted = stateStatus === "COMPLETED" || activeState?.status === "COMPLETED";
  const stageStatus = activeState?.stage_status || {};
  const currentStage = activeState?.current_stage || "";

  // 1. Intent Node Status
  const isIntentDone = stageStatus.intent === "completed" || Boolean(activeState?.requirements && Object.keys(activeState.requirements).length > 0);
  const isIntentRunning = !isIntentDone && (currentStage === "INTENT" || activeState?.status === "DISCOVERING");

  // 2. Parallel Research Nodes Statuses
  const isMarketplaceDone = Boolean(activeState?.marketplace_data && activeState.marketplace_data.length > 0) || stageStatus.research === "completed" || isCompleted;
  const isProductInfoDone = Boolean(activeState?.product_info_data && Object.keys(activeState.product_info_data).length > 0) || stageStatus.research === "completed" || isCompleted;
  const isReviewTrustDone = Boolean(activeState?.review_trust_data && Object.keys(activeState.review_trust_data).length > 0) || stageStatus.research === "completed" || isCompleted;

  const isResearchRunning = isIntentDone && !isMarketplaceDone && (currentStage === "RESEARCH" || activeState?.status === "RESEARCHING");

  // 3. Evidence Synthesis Status
  const isEvidenceDone = stageStatus.research === "completed" || Boolean(activeState?.normalized_evidence && activeState.normalized_evidence.length > 0) || isCompleted;
  const isEvidenceRunning = isMarketplaceDone && !isEvidenceDone;

  // 4. Product Analyst (Bayesian Ranking) Status
  const isAnalystDone = stageStatus.analyst === "completed" || (Array.isArray(activeState?.candidates) && activeState.candidates.length > 0 && Boolean(activeState.candidates[0]?.utility_score)) || isCompleted;
  const isAnalystRunning = isEvidenceDone && !isAnalystDone && (currentStage === "ANALYST" || activeState?.status === "ANALYZING");

  // 5. Recommendation Agent Status
  const isRecDone = stageStatus.evaluation === "completed" || Boolean(activeState?.selected_product?.recommendation_reasons?.length) || activeState?.status === "AWAITING_APPROVAL" || activeState?.status === "AWAITING_PAYMENT" || isCompleted;
  const isRecRunning = isAnalystDone && !isRecDone && (currentStage === "EVALUATION" || activeState?.status === "RECOMMENDING");

  // 6. Risk Guard Status
  const isRiskDone = stageStatus.risk === "completed" || Boolean(activeState?.risk && Object.keys(activeState.risk).length > 0) || activeState?.status === "AWAITING_APPROVAL" || activeState?.status === "AWAITING_PAYMENT" || isCompleted;
  const isRiskRunning = isRecDone && !isRiskDone && (currentStage === "RISK" || activeState?.status === "RISK_RUNNING");

  // 7. Human Approval Gate
  const isAwaitingApproval = activeState?.status === "AWAITING_APPROVAL";
  const isApprovalPassed = isCompleted || activeState?.status === "AWAITING_PAYMENT";

  // 8. Purchase & Razorpay Status
  const isPurchaseStaged = activeState?.status === "AWAITING_PAYMENT";
  const isPaymentCompleted = isCompleted;

  const getBadgeClass = (isDone, isRunning) => {
    if (isDone) return "flow-badge-done";
    if (isRunning) return "flow-badge-running";
    return "flow-badge-waiting";
  };

  const getBadgeText = (isDone, isRunning) => {
    if (isDone) return "DONE";
    if (isRunning) return "RUNNING";
    return "WAITING";
  };

  return (
    <section className="pipeline-stepper-container">
      <div className="section-header-row">
        <div>
          <h3 className="section-title">LangGraph Multi-Agent Architecture</h3>
          <p className="section-subtitle">
            Parallel research fan-out with deterministic ranking & risk-gated execution
          </p>
        </div>
        <div className="streaming-indicator-pill">
          <span className="streaming-pulse-dot" />
          <span>{isCompleted ? "GRAPH COMPLETED" : "STATEGRAPH EXECUTING"}</span>
        </div>
      </div>

      <div className="graph-architecture-layout">
        {/* Stage 1: Intent Understanding */}
        <div className="graph-level-block">
          <div className={`graph-node-card ${isIntentDone ? "node-done" : isIntentRunning ? "node-running" : "node-waiting"}`}>
            <div className="graph-node-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
              </svg>
            </div>
            <div className="graph-node-info">
              <div className="graph-node-title">1. Intent Planner (LLM)</div>
              <div className="graph-node-meta">NLP constraint & budget decomposition</div>
            </div>
            <span className={`graph-node-badge ${getBadgeClass(isIntentDone, isIntentRunning)}`}>
              {getBadgeText(isIntentDone, isIntentRunning)}
            </span>
          </div>
        </div>

        {/* Fan-Out Branch Connector */}
        <div className="graph-branch-wires">
          <div className="wire-vertical-stem" />
          <div className="wire-horizontal-fork" />
        </div>

        {/* Stage 2: Parallel Research Fan-Out (3 Concurrent Nodes) */}
        <div className="graph-parallel-row">
          {/* 2A: Marketplace Research */}
          <div className={`graph-subnode-card ${isMarketplaceDone ? "node-done" : isResearchRunning ? "node-running" : "node-waiting"}`}>
            <div className="graph-subnode-header">
              <span className="subnode-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </span>
              <span className="subnode-title">2A. Marketplace Research</span>
            </div>
            <div className="subnode-desc">Live SerpAPI & ScraperAPI search</div>
            <div className="subnode-footer">
              <span className="parallel-tag">PARALLEL</span>
              <span className={`graph-node-badge ${getBadgeClass(isMarketplaceDone, isResearchRunning)}`}>
                {getBadgeText(isMarketplaceDone, isResearchRunning)}
              </span>
            </div>
          </div>

          {/* 2B: Product Spec Research */}
          <div className={`graph-subnode-card ${isProductInfoDone ? "node-done" : isResearchRunning ? "node-running" : "node-waiting"}`}>
            <div className="graph-subnode-header">
              <span className="subnode-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              </span>
              <span className="subnode-title">2B. Product Spec Spec</span>
            </div>
            <div className="subnode-desc">Category attribute planning</div>
            <div className="subnode-footer">
              <span className="parallel-tag">PARALLEL</span>
              <span className={`graph-node-badge ${getBadgeClass(isProductInfoDone, isResearchRunning)}`}>
                {getBadgeText(isProductInfoDone, isResearchRunning)}
              </span>
            </div>
          </div>

          {/* 2C: Review & Trust Stats */}
          <div className={`graph-subnode-card ${isReviewTrustDone ? "node-done" : isResearchRunning ? "node-running" : "node-waiting"}`}>
            <div className="graph-subnode-header">
              <span className="subnode-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </span>
              <span className="subnode-title">2C. Review & Trust Stats</span>
            </div>
            <div className="subnode-desc">Statistical volume confidence</div>
            <div className="subnode-footer">
              <span className="parallel-tag">PARALLEL</span>
              <span className={`graph-node-badge ${getBadgeClass(isReviewTrustDone, isResearchRunning)}`}>
                {getBadgeText(isReviewTrustDone, isResearchRunning)}
              </span>
            </div>
          </div>
        </div>

        {/* Fan-In Join Connector */}
        <div className="graph-branch-wires reverse">
          <div className="wire-horizontal-fork" />
          <div className="wire-vertical-stem" />
        </div>

        {/* Stage 3: Evidence Synthesis Join */}
        <div className="graph-level-block">
          <div className={`graph-node-card ${isEvidenceDone ? "node-done" : isEvidenceRunning ? "node-running" : "node-waiting"}`}>
            <div className="graph-node-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <div className="graph-node-info">
              <div className="graph-node-title">3. Evidence Synthesis (LLM Join)</div>
              <div className="graph-node-meta">Unified normalization across 3 parallel research streams</div>
            </div>
            <span className={`graph-node-badge ${getBadgeClass(isEvidenceDone, isEvidenceRunning)}`}>
              {getBadgeText(isEvidenceDone, isEvidenceRunning)}
            </span>
          </div>
        </div>

        {/* Downstream Sequential Pipeline Grid (4..7) */}
        <div className="graph-sequential-grid">
          {/* Stage 4: Product Analyst */}
          <div className={`graph-seq-card ${isAnalystDone ? "node-done" : isAnalystRunning ? "node-running" : "node-waiting"}`}>
            <div className="seq-card-num">4</div>
            <div className="seq-card-content">
              <div className="seq-card-title">Product Analyst (Python)</div>
              <div className="seq-card-desc">Bayesian utility ranking & 85% budget targeting</div>

            </div>
            <span className={`graph-node-badge ${getBadgeClass(isAnalystDone, isAnalystRunning)}`}>
              {getBadgeText(isAnalystDone, isAnalystRunning)}
            </span>
          </div>

          {/* Stage 5: Recommendation Agent */}
          <div className={`graph-seq-card ${isRecDone ? "node-done" : isRecRunning ? "node-running" : "node-waiting"}`}>
            <div className="seq-card-num">5</div>
            <div className="seq-card-content">
              <div className="seq-card-title">Recommendation Agent</div>
              <div className="seq-card-desc">Grounded "WHY THIS PRODUCT?" reasoning</div>
            </div>
            <span className={`graph-node-badge ${getBadgeClass(isRecDone, isRecRunning)}`}>
              {getBadgeText(isRecDone, isRecRunning)}
            </span>
          </div>

          {/* Stage 6: Risk Guard */}
          <div className={`graph-seq-card ${isRiskDone ? "node-done" : isRiskRunning ? "node-running" : "node-waiting"}`}>
            <div className="seq-card-num">6</div>
            <div className="seq-card-content">
              <div className="seq-card-title">Risk Guard (Policy Gate)</div>
              <div className="seq-card-desc">Budget ceiling, stock lock & seller trust check</div>
            </div>
            <span className={`graph-node-badge ${getBadgeClass(isRiskDone, isRiskRunning)}`}>
              {getBadgeText(isRiskDone, isRiskRunning)}
            </span>
          </div>

          {/* Stage 7: Human Approval & Razorpay */}
          <div className={`graph-seq-card ${isPaymentCompleted ? "node-done" : isAwaitingApproval ? "node-waiting-approval" : isPurchaseStaged ? "node-running" : "node-waiting"}`}>
            <div className="seq-card-num">7</div>
            <div className="seq-card-content">
              <div className="seq-card-title">Human Approval & Razorpay</div>
              <div className="seq-card-desc">
                {isPaymentCompleted
                  ? "HMAC verified & payment completed"
                  : isAwaitingApproval
                  ? "User authorization required"
                  : "Staged for payment"}
              </div>
            </div>
            <span className={`graph-node-badge ${isPaymentCompleted ? "flow-badge-done" : isAwaitingApproval ? "flow-badge-approval" : isPurchaseStaged ? "flow-badge-running" : "flow-badge-waiting"}`}>
              {isPaymentCompleted ? "PAID ✓" : isAwaitingApproval ? "ACTION REQUIRED" : isPurchaseStaged ? "CHECKOUT" : "WAITING"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

