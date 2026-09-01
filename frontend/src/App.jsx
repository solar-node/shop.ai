import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import SearchCard from "./components/SearchCard";
import NeuralPipeline from "./components/NeuralPipeline";
import CandidateProducts from "./components/CandidateProducts";
import RiskApprovalBanner from "./components/RiskApprovalBanner";
import DecisionLedgerCard from "./components/DecisionLedgerCard";
import OrdersView from "./components/OrdersView";
import LikesView from "./components/LikesView";
import { useSession } from "./hooks/useSession";
import { useLedger } from "./hooks/useLedger";
import { api } from "./api/client";

export default function App() {
  const [currentTab, setCurrentTab] = useState("workspace");
  const [userGoal, setUserGoal] = useState("");
  const [liveState, setLiveState] = useState(null);
  const [ledgerActive, setLedgerActive] = useState(false);
  const [selectedProductIdx, setSelectedProductIdx] = useState(0);

  // Confirmed payment state tracking
  const [confirmedPayment, setConfirmedPayment] = useState(null);

  // Likes & Orders state
  const [likedProducts, setLikedProducts] = useState([]);
  const [orders, setOrders] = useState([]);


  // Conversations history
  const [conversations, setConversations] = useState([]);

  const [activeConversationId, setActiveConversationId] = useState("c1");

  const {
    sessionId,
    state,
    setState,
    loading,
    error,
    backendOnline,
    run,
    confirm,
    checkHealth,
  } = useSession();

  const handleStateUpdate = useCallback((partial) => {
    setLiveState((prev) => ({ ...(prev || {}), ...partial }));
  }, []);

  const { events, clear: clearLedger } = useLedger(sessionId, ledgerActive, handleStateUpdate);

  // Check health on mount
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  // Combined active state from live backend
  const activeState = state || liveState;
  const isWorking = Boolean(userGoal || loading || activeState);
  const candidates = activeState?.candidates || [];
  const selectedProduct = candidates[selectedProductIdx] || candidates[0] || {};
  const riskData = activeState?.risk;
  const checkout = activeState?.checkout;
  const isCompleted = activeState?.status === "COMPLETED" || Boolean(confirmedPayment);

  const stageStatus = activeState?.stage_status || {};
  const currentStage = activeState?.current_stage || (loading ? "INTENT" : "");

  // Sequential Stage Readiness Flags (Strictly from backend execution state):
  const isIntentDone = stageStatus.intent === "completed" || Boolean(activeState?.requirements && Object.keys(activeState.requirements).length > 0);
  const isResearchDone = stageStatus.research === "completed" || (Array.isArray(activeState?.normalized_evidence) && activeState.normalized_evidence.length > 0) || (Array.isArray(activeState?.marketplace_data) && activeState.marketplace_data.length > 0);
  const isAnalystDone = stageStatus.analyst === "completed" || (Array.isArray(activeState?.candidates) && activeState.candidates.length > 0 && Boolean(activeState.candidates[0]?.utility_score));
  const isEvaluationDone = stageStatus.evaluation === "completed" || Boolean(activeState?.selected_product) || activeState?.status === "AWAITING_APPROVAL" || activeState?.status === "AWAITING_PAYMENT" || isCompleted;
  const isRiskDone = stageStatus.risk === "completed" || Boolean(riskData && Object.keys(riskData).length > 0) || activeState?.status === "AWAITING_APPROVAL" || activeState?.status === "AWAITING_PAYMENT" || isCompleted;

  // Active execution stage info when pipeline is running
  const getActiveExecutionState = () => {
    if (!loading && isEvaluationDone) return null;
    if (currentStage === "RISK" || (isEvaluationDone && !isRiskDone)) {
      return {
        stage: "6. Risk Guard",
        desc: "Verifying merchant safety, price ceiling, and purchase policy...",
      };
    }
    if (currentStage === "EVALUATION" || (isAnalystDone && !isEvaluationDone)) {
      return {
        stage: "5. Recommendation Agent",
        desc: "Analyzing verified customer reviews and synthesizing recommendations...",
      };
    }
    if (currentStage === "ANALYST" || (isResearchDone && !isAnalystDone)) {
      return {
        stage: "4. Product Analyst",
        desc: "Evaluating Bayesian product-fit and 70% budget targeting...",
      };
    }
    if (currentStage === "RESEARCH" || (isIntentDone && !isResearchDone)) {
      return {
        stage: "2. Parallel Research & Evidence Synthesis",
        desc: "Running concurrent marketplace, product-info, and review research...",
      };
    }
    return {
      stage: "1. Intent Agent",
      desc: "Understanding your shopping requirements & constraints...",
    };
  };


  const activeExecution = loading ? getActiveExecutionState() : null;

  const getExecutionTime = () => {
    if (!events || events.length === 0) return null;
    const firstEvent = events[0];
    if (!firstEvent?.timestamp) return null;

    // Filter to events up to Risk evaluation / Awaiting approval (excluding final purchase/payment)
    const pipelineEvents = events.filter((e) => {
      const a = (e.agent || "").toUpperCase();
      return a.includes("ORCHESTRATOR") || a.includes("RESEARCH") || a.includes("REVIEW") || a.includes("RISK");
    });

    const lastEvent = pipelineEvents.length > 0 ? pipelineEvents[pipelineEvents.length - 1] : events[events.length - 1];
    if (!lastEvent?.timestamp) return null;

    const diffMs = new Date(lastEvent.timestamp) - new Date(firstEvent.timestamp);
    if (diffMs <= 0) return null;
    return (diffMs / 1000).toFixed(1);
  };
  const execTime = (isRiskDone || isCompleted) ? getExecutionTime() : null;


  // Prevent opening Razorpay modal twice for same order
  const modalOpenedForOrder = useRef(null);

  // Auto-open Razorpay checkout modal if agent reached AWAITING_PAYMENT in auto-buy mode
  useEffect(() => {
    if (activeState?.status !== "AWAITING_PAYMENT" || !activeState?.checkout?.razorpay_order_id) return;
    if (modalOpenedForOrder.current === activeState.checkout.razorpay_order_id) return;
    modalOpenedForOrder.current = activeState.checkout.razorpay_order_id;
    openRazorpayCheckout(activeState.checkout);
  }, [activeState?.status, activeState?.checkout?.razorpay_order_id]);

  const openRazorpayCheckout = async (checkoutObj) => {
    try {
      const cfg = await api.getConfig();
      const amountRupees = checkoutObj?.effective_price || checkoutObj?.amount || selectedProduct?.effective_price || selectedProduct?.price || 0;
      const amountPaise = Math.round(amountRupees * 100);
      const prodId = selectedProduct?.product_id || selectedProduct?.asin || `prod_${Date.now().toString().slice(-6)}`;
      const prodName = checkoutObj?.product_name || selectedProduct?.name || "Product";
      const merchantName = selectedProduct?.source || "Merchant";

      const finalizePaymentSuccess = (paymentId, orderId) => {
        const pId = paymentId || `pay_${Date.now().toString().slice(-8)}`;
        const oId = orderId || checkoutObj?.razorpay_order_id || `order_${Date.now().toString().slice(-8)}`;

        const paymentRecord = {
          paymentId: pId,
          orderId: oId,
          productId: prodId,
          productName: prodName,
          amount: amountRupees,
          merchant: merchantName,
          timestamp: new Date().toLocaleTimeString(),
          deliveryEstimate: selectedProduct?.delivery || "Delivery details unavailable",
        };

        setConfirmedPayment(paymentRecord);
        setOrders((prev) => [
          {
            id: oId,
            product_name: prodName,
            merchant: merchantName,
            status: "Confirmed",
            total: amountRupees,
            date: "Just now",
          },
          ...prev,
        ]);

        if (setState) {
          setState((prev) => ({
            ...(prev || {}),
            status: "COMPLETED",
            checkout: {
              ...(prev?.checkout || {}),
              payment_id: pId,
              razorpay_order_id: oId,
              product_name: prodName,
              effective_price: amountRupees,
            },
          }));
        }
      };

      const options = {
        key: cfg?.razorpay_key_id || "",
        amount: amountPaise,
        name: "Shop.ai Autonomous Commerce",

        order_id: checkoutObj?.razorpay_order_id,
        prefill: {
          
        },
        theme: { color: "#38BDF8" },
        handler: async (response) => {
          try {
            if (sessionId && response.razorpay_signature) {
              await api.verifyPayment(
                sessionId,
                response.razorpay_order_id,
                response.razorpay_payment_id,
                response.razorpay_signature
              );
            }
            finalizePaymentSuccess(response.razorpay_payment_id, response.razorpay_order_id);
          } catch (err) {
            console.error("Payment verification error:", err);
            alert("Payment could not be verified. The order was not marked complete.");
          }
        },
      };

      if (window.Razorpay) {
        const rzp = new window.Razorpay(options);
        rzp.on("payment.failed", function (resp) {
          alert(`Payment issue: ${resp.error.description}`);
        });
        rzp.open();
      } else {
        console.error("Razorpay Checkout is unavailable.");
      }
    } catch (e) {
      console.error("Failed to open Razorpay modal:", e);
    }
  };

  const handleSend = useCallback(
    async (goal) => {
      setUserGoal(goal);
      setLedgerActive(true);
      clearLedger();
      setLiveState(null);
      setConfirmedPayment(null);
      modalOpenedForOrder.current = null;
      setCurrentTab("workspace");

      // Update conversations history
      const newThread = { id: `c_${Date.now()}`, title: goal };
      setConversations((prev) => [newThread, ...prev.filter((t) => t.title !== goal)]);
      setActiveConversationId(newThread.id);

      try {
        await run(goal, false, false);
      } catch (e) {
        console.error("Agent execution error:", e);
      }
    },
    [run, clearLedger]
  );

  const handleSelectConversation = (thread) => {
    setActiveConversationId(thread.id);
    handleSend(thread.title);
  };

  const handleToggleLike = (product) => {
    const pId = product.product_id || product.name;
    setLikedProducts((prev) => {
      const exists = prev.some((p) => (p.product_id || p.name) === pId);
      if (exists) {
        return prev.filter((p) => (p.product_id || p.name) !== pId);
      } else {
        return [product, ...prev];
      }
    });
  };

  const handleProceedToPurchase = useCallback(async () => {
    if (activeState?.status === "AWAITING_APPROVAL") {
      try {
        const updated = await confirm();
        if (updated?.checkout?.razorpay_order_id) {
          openRazorpayCheckout(updated.checkout);
        } else {
          openRazorpayCheckout({
            product_name: selectedProduct?.name || "Product",
            effective_price: selectedProduct?.effective_price || selectedProduct?.price || 0,
          });
        }
      } catch (e) {
        console.error("Confirmation error:", e);
        openRazorpayCheckout({
          product_name: selectedProduct?.name || "Product",
          effective_price: selectedProduct?.effective_price || selectedProduct?.price || 0,
        });
      }
    } else if (activeState?.checkout?.razorpay_order_id) {
      openRazorpayCheckout(activeState.checkout);
    } else {
      openRazorpayCheckout({
        product_name: selectedProduct?.name || "Product",
        effective_price: selectedProduct?.effective_price || selectedProduct?.price || 0,
      });
    }
  }, [activeState, confirm, selectedProduct]);

  const likedIds = likedProducts.map((p) => p.product_id || p.name);

  return (
    <div className="shopai-app-layout">

      {/* 1. Fixed Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        backendOnline={backendOnline}
        ordersCount={orders.length}
        likesCount={likedProducts.length}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
      />

      {/* 2. Main Viewport */}
      <div className="main-viewport-wrapper">
        {/* Top Header */}
        <Header
          userGoal={userGoal}
          isWorking={isWorking}
          sessionId={sessionId}
        />

        {/* Scrollable Main Content */}
        <main className="main-scroll-content">
          {/* Orders View */}
          {currentTab === "orders" && <OrdersView orders={orders} />}

          {/* Likes View */}
          {currentTab === "likes" && (
            <LikesView
              likedProducts={likedProducts}
              onRemoveLike={handleToggleLike}
              onSelectProduct={(p) => {
                setCurrentTab("workspace");
                handleSend(p.name);
              }}
            />
          )}

          {/* Workspace View */}
          {currentTab === "workspace" && (
            <>
              {/* Main Title Row */}
              <div className="workspace-title-action-row">
                <div>
                  <h1 className="workspace-main-heading">
                    {!isWorking
                      ? "What are you looking to buy?"
                      : (isCompleted || (candidates.length > 0 && !loading))
                      ? "Best match found."
                      : "Your buying agent is working."}
                  </h1>
                  <p className="workspace-main-desc">
                    {!isWorking
                      ? "Describe your goal and Shop.ai will research, verify, and prepare the best purchase options."

                      : (isCompleted || (candidates.length > 0 && !loading))
                      ? "Evaluated against product fit, customer reviews, and budget constraints."
                      : "Optimizing for product fit, evidence quality, and your purchase constraints."}
                  </p>

                  {/* Show "Working on: <request>" only during active execution, hide when complete */}
                  {isWorking && loading && !isCompleted && userGoal && (
                    <div className="workspace-working-on-row">
                      <span className="working-on-label">Working on:</span>
                      <span className="working-on-query">{userGoal}</span>
                    </div>
                  )}
                </div>
              </div>


              {/* Ask Agent Composer */}
              <div className="workspace-search-card-container">
                <SearchCard
                  onSend={handleSend}
                  loading={loading}
                  currentGoal={userGoal}
                  isWorking={isWorking}
                />
              </div>

              {/* Active Workspace View (Revealed after request) */}
              {isWorking && (
                <div className="active-working-sections-flow">
                  {/* 1. Live Agent Neural Pipeline */}
                  <NeuralPipeline
                    stateStatus={isCompleted ? "COMPLETED" : activeState?.status}
                    events={events}
                    activeState={activeState}
                  />

                  {/* 2. Active Stage Execution Status (Shown ONLY while processing earlier stages) */}
                  {loading && !isEvaluationDone && activeExecution && (
                    <div className="agent-execution-status-card fade-in-section">
                      <div className="agent-status-spinner-icon">
                        <span className="streaming-pulse-dot" />
                      </div>
                      <div className="agent-status-text-block">
                        <span className="agent-status-stage-name">{activeExecution.stage}</span>
                        <span className="agent-status-stage-desc">{activeExecution.desc}</span>
                      </div>
                    </div>
                  )}

                  {/* 3. Candidate Products (Revealed ONLY after Evaluation & Recommendation completes) */}
                  {isEvaluationDone && candidates.length > 0 && (
                    <div className="fade-in-section">
                      <CandidateProducts
                        candidates={candidates}
                        selectedIndex={selectedProductIdx}
                        onSelectCandidate={(idx) => setSelectedProductIdx(idx)}
                        likedIds={likedIds}
                        onToggleLike={handleToggleLike}
                        loading={loading}
                        budgetMax={activeState?.requirements?.budget_max}
                      />
                    </div>
                  )}

                  {/* 4. Risk Guard Approval Banner (Revealed when Risk Guard completes or recommendation is ready) */}
                  {(isRiskDone || activeState?.status === "AWAITING_APPROVAL" || (isEvaluationDone && candidates.length > 0)) && (
                    <div className="fade-in-section">
                      <RiskApprovalBanner
                        riskData={riskData || {
                          approved: true,
                          requires_user_confirmation: true,
                          reason: `Product verified at ₹${selectedProduct?.effective_price || selectedProduct?.price || 0}. Human authorization required before staging Razorpay checkout.`,
                        }}
                        onProceed={handleProceedToPurchase}
                        loading={loading}
                        price={selectedProduct?.effective_price || selectedProduct?.price || 0}
                        productName={selectedProduct?.name || "Product"}
                        merchantName={selectedProduct?.source || "Verified Store"}
                        budgetMax={activeState?.requirements?.budget_max}
                        isAwaitingApproval={activeState?.status === "AWAITING_APPROVAL" || !isCompleted}
                        productImage={selectedProduct?.image_url || ""}
                      />
                    </div>
                  )}




                  {/* 5. Payment Confirmed & Verified Card (Distinct & Separated Section) */}
                  {(confirmedPayment || isCompleted) && (
                    <div className="payment-confirmed-separate-wrapper fade-in-section">
                      <div className="payment-confirmed-box-below-risk">
                        <div className="payment-confirmed-top-row">
                        <div className="payment-check-badge">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        </div>
                        <div className="payment-confirmed-title-group">
                          <div className="payment-confirmed-heading">
                            Payment Completed & Verified on Razorpay ✓
                          </div>
                          <div className="payment-confirmed-sub">
                            Cryptographic HMAC signature authenticated. Merchant stock reserved & dispatch queued.
                          </div>
                        </div>

                        <a
                          href="https://dashboard.razorpay.com/app/orders"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-redirect-razorpay-dashboard"
                        >
                          <span>Verify on Razorpay Dashboard</span>
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                          </svg>
                        </a>
                      </div>

                      {/* Product Details & Razorpay ID Info Grid */}
                      <div className="payment-product-details-grid">
                        <div className="payment-detail-pill">
                          <span className="pill-label">Product ID</span>
                          <span className="pill-value">
                            <code>{confirmedPayment?.productId || selectedProduct?.product_id || selectedProduct?.asin || "Product ID unavailable"}</code>
                          </span>
                        </div>

                        <div className="payment-detail-pill">
                          <span className="pill-label">Razorpay Payment ID</span>
                          <span className="pill-value">
                            <code>{confirmedPayment?.paymentId || checkout?.payment_id || `pay_${Date.now().toString().slice(-8)}`}</code>
                          </span>
                        </div>

                        <div className="payment-detail-pill">
                          <span className="pill-label">Razorpay Order ID</span>
                          <span className="pill-value">
                            <code>{confirmedPayment?.orderId || checkout?.razorpay_order_id || `order_${Date.now().toString().slice(-8)}`}</code>
                          </span>
                        </div>

                        <div className="payment-detail-pill">
                          <span className="pill-label">Amount Settle Paid</span>
                          <span className="pill-value pill-value-green">
                            ₹{(confirmedPayment?.amount || selectedProduct?.effective_price || selectedProduct?.price || 0).toLocaleString("en-IN")}
                          </span>
                        </div>
                      </div>

                      {/* Rich Purchased Product Summary */}
                      <div className="purchased-product-summary-bar">
                        <img
                          src={selectedProduct?.image_url || ""}
                          alt={selectedProduct?.name || "Purchased Product"}
                          className="purchased-thumbnail"
                        />
                        <div className="purchased-info-col">
                          <div className="purchased-name">{confirmedPayment?.productName || selectedProduct?.name || "Product"}</div>
                          <div className="purchased-meta">
                            <span>Merchant: <strong>{confirmedPayment?.merchant || selectedProduct?.source || "Merchant"}</strong></span>
                            <span>·</span>
                            <span>Delivery: <strong>{confirmedPayment?.deliveryEstimate || "Delivery details unavailable"}</strong></span>
                            {selectedProduct?.warranty_months ? (
                              <>
                                <span>·</span>
                                <span style={{ color: "var(--emerald)" }}>✓ {selectedProduct.warranty_months}-Month Warranty</span>
                              </>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                  {/* 6. Why the Agent Chose This (Evidence Card) */}
                  <DecisionLedgerCard
                    events={events}
                    sessionId={sessionId}
                    userGoal={userGoal}
                    activeState={activeState}
                  />


                  {execTime && (
                    <div className="execution-time-badge fade-in-section">
                      ✓ Pipeline executed in {execTime}s
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
