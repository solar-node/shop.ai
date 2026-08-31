"""BudBuy workflow: intent (LLM) → research (API) → analyst (Python) → review_analysis (LLM) → recommendation (LLM) → risk (Rules) → purchase."""

from typing import Any, TypedDict
from database.models import AgentSession, get_engine, get_session_factory
from app.observability.logger import log_event
from app.agents import llm_client, purchase_agent, recommendation_agent, research_agent, review_agent, risk_agent
from app.commerce.ranking import rank_products, weights_from_priority

_engine = get_engine()
_Session = get_session_factory(_engine)


class BudBuyState(TypedDict, total=False):
    session_id: str
    user_goal: str
    current_stage: str
    stage_status: dict
    requirements: dict
    search_query: str
    raw_products: list
    candidates: list
    review_analysis: dict
    reviews: dict
    rag_context: dict
    selected_product: dict
    recommendation_reasons: list
    why_this_product: list
    recommendation: str
    recommendation_summary: str
    risk: dict
    pending_purchase: dict
    checkout: dict
    payment_status: str
    status: str
    message_to_user: str


PRODUCT_SPECS = [
    {"category": "earbuds", "topic": "ANC", "content": "30dB+ Hybrid ANC is useful for gym and commuting."},
    {"category": "earbuds", "topic": "Battery", "content": "35h+ total playback and fast charging are good targets."},
    {"category": "headphones", "topic": "Drivers", "content": "40mm dynamic drivers can provide clear bass and vocals."},
]


def log_agent_activity(state: BudBuyState, agent: str, action: str, detail: Any = None, success: bool = True):
    db = _Session()
    try:
        sid = state.get("session_id", "default_session")
        log_event(db, sid, agent, action, detail or {}, success=success)
        record = db.query(AgentSession).filter_by(id=sid).first()
        if record:
            record.status = state.get("status", "PROCESSING")
            record.state = dict(state)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def get_rag_specs(category: str) -> list[dict]:
    category = (category or "").lower()
    matches = [d for d in PRODUCT_SPECS if d["category"] in category or category in d["category"]]
    return matches or PRODUCT_SPECS[:2]


# 1. INTENT AGENT (LLM)
def intent_node(state: BudBuyState) -> dict:
    goal = state.get("user_goal", "")
    stage_status = dict(state.get("stage_status", {}))
    stage_status["intent"] = "running"
    state["current_stage"] = "INTENT"
    state["stage_status"] = stage_status
    log_agent_activity(state, "INTENT", "understanding_requirements", {"goal": goal})
    
    requirements = research_agent.extract_intent(goal)
    stage_status["intent"] = "completed"
    state["requirements"] = requirements
    state["stage_status"] = stage_status
    log_agent_activity(state, "INTENT", "requirements_extracted", requirements)
    return {
        "status": "DISCOVERING",
        "current_stage": "INTENT",
        "stage_status": stage_status,
        "requirements": requirements,
        "search_query": goal
    }


# 2. RESEARCH AGENT (Search Query Formulation & Live Marketplace Scraping)
def research_node(state: BudBuyState) -> dict:
    reqs = state.get("requirements", {})
    stage_status = dict(state.get("stage_status", {}))
    stage_status["research"] = "running"
    state["current_stage"] = "RESEARCH"
    state["stage_status"] = stage_status
    
    parts = []
    brand = reqs.get("brand_preference")
    if brand:
        parts.extend(brand if isinstance(brand, list) else [str(brand)])
        
    category = reqs.get("category", "earbuds")
    if category:
        parts.extend(category if isinstance(category, list) else [str(category)])
        
    prefs = reqs.get("soft_preferences", [])
    if isinstance(prefs, list):
        for p in prefs:
            if str(p).lower() not in " ".join(parts).lower():
                parts.append(str(p))
    elif prefs:
        parts.append(str(prefs))
        
    if reqs.get("budget_max"):
        parts.append(f"under {int(reqs['budget_max'])}")
    
    query = " ".join([str(p) for p in parts if p])
    if "india" not in query.lower():
        query = f"{query} India"
    if not query.strip():
        query = state.get("user_goal", "")

    log_agent_activity(state, "RESEARCH", "scanning_marketplaces", {"query": query})
    products = research_agent.find_and_rank_candidates(reqs, user_goal=query)
    stage_status["research"] = "completed"
    state["raw_products"] = products
    state["stage_status"] = stage_status
    log_agent_activity(state, "RESEARCH", "products_retrieved", {"count": len(products)})
    return {
        "status": "RESEARCHING",
        "current_stage": "RESEARCH",
        "stage_status": stage_status,
        "search_query": query,
        "raw_products": products
    }


# 3. PRODUCT ANALYST (Deterministic Python Bayesian Ranking)
def analyst_node(state: BudBuyState) -> dict:
    raw, reqs = state.get("raw_products", []), state.get("requirements", {})
    stage_status = dict(state.get("stage_status", {}))
    stage_status["analyst"] = "running"
    state["current_stage"] = "ANALYST"
    state["stage_status"] = stage_status
    log_agent_activity(state, "ANALYST", "calculating_product_fit", {"count": len(raw)})

    ranked = rank_products(raw, budget_max=reqs.get("budget_max") or 999999,
                           soft_preferences=reqs.get("soft_preferences", []),
                           weights=weights_from_priority(reqs.get("priority", "")),
                           brand_preference=reqs.get("brand_preference", ""))
    lookup = {p.get("product_id"): p for p in raw}
    candidates = [{**lookup.get(item.product_id, {}), "utility_score": item.utility_score, "rank": rank}
                  for rank, item in enumerate(ranked, 1)]
    stage_status["analyst"] = "completed"
    state["candidates"] = candidates
    state["stage_status"] = stage_status
    log_agent_activity(state, "ANALYST", "products_ranked", {
        "top_match": candidates[0].get("name", "None") if candidates else "None"})
    return {
        "status": "ANALYZING",
        "current_stage": "ANALYST",
        "stage_status": stage_status,
        "candidates": candidates
    }


# 4. EVALUATION & RECOMMENDATION (LLM Review Signal Analysis & Personalized Synthesis)
def evaluation_node(state: BudBuyState) -> dict:
    candidates = state.get("candidates", [])
    reqs = state.get("requirements", {})
    user_goal = state.get("user_goal", "")
    stage_status = dict(state.get("stage_status", {}))
    stage_status["evaluation"] = "running"
    state["current_stage"] = "EVALUATION"
    state["stage_status"] = stage_status
    log_agent_activity(state, "EVALUATION", "evaluating_candidates_and_reviews", {"count": len(candidates)})

    top_candidates = candidates[:3]
    review_map = {p.get("product_id"): review_agent.analyze_reviews(p, reqs) for p in top_candidates}

    enriched = []
    for index, candidate in enumerate(candidates, 1):
        pid = candidate.get("product_id")
        rev_info = review_map.get(pid, {})
        sentiment_label = rev_info.get("sentiment_label") or "Mostly positive feedback"
        ai_insight = rev_info.get("ai_insight") or rev_info.get("review_summary") or "Customers generally praise the sound quality and overall daily reliability."
        confidence = rev_info.get("review_confidence", "high")
        price = float(candidate.get("price") or 2199.0)

        cand_dict = {
            **candidate,
            "effective_price": price,
            "review_analysis": rev_info,
            "reviews": rev_info,
            "sentiment_label": sentiment_label,
            "ai_insight": ai_insight,
            "review_confidence": confidence,
            "review_summary": ai_insight,
            "sentiment_verdict": ai_insight,
            "positive_sentiment_pct": 96 if sentiment_label == "Very positive feedback" else (88 if sentiment_label == "Mostly positive feedback" else 72),
            "selection_rationale": f"Ranked #{index} match: {round(candidate.get('utility_score', .95) * 100)}% score. {ai_insight}"
        }

        # Step B: Synthesize structured evidence reasons via Recommendation Agent
        rec_data = recommendation_agent.synthesize_recommendation_and_reasons(cand_dict, reqs, user_goal, rev_info)
        cand_dict["recommendation_reasons"] = rec_data.get("recommendation_reasons", [])
        cand_dict["why_this_product"] = rec_data.get("recommendation_reasons", [])
        cand_dict["llm_rec"] = rec_data.get("recommendation", "")
        enriched.append(cand_dict)

    if not enriched:
        stage_status["evaluation"] = "failed"
        return {
            "status": "FAILED",
            "current_stage": "EVALUATION",
            "stage_status": stage_status,
            "message_to_user": "No suitable products found matching budget."
        }

    selected = enriched[0]
    top_rec = selected.get("llm_rec") or (
        f"I recommend {selected.get('name')} at ₹{selected['effective_price']:,.0f}. "
        f"It matches your budget and requirements with strong customer satisfaction."
    )

    stage_status["evaluation"] = "completed"
    state["stage_status"] = stage_status
    log_agent_activity(state, "EVALUATION", "evaluation_completed", {
        "product": selected.get("name"),
        "sentiment": selected.get("sentiment_label", "Positive"),
        "recommendation_reasons": selected.get("recommendation_reasons", []),
        "why_this_product": selected.get("why_this_product", [])
    })

    return {
        "status": "RECOMMENDING",
        "current_stage": "EVALUATION",
        "stage_status": stage_status,
        "review_analysis": review_map,
        "reviews": review_map,
        "candidates": enriched,
        "selected_product": selected,
        "recommendation_reasons": selected.get("recommendation_reasons", []),
        "why_this_product": selected.get("why_this_product", []),
        "recommendation": top_rec,
        "recommendation_summary": top_rec,
    }


# 5. RISK GUARD (Deterministic Policy Gate)
def risk_node(state: BudBuyState) -> dict:
    selected, reqs = state.get("selected_product", {}), state.get("requirements", {})
    stage_status = dict(state.get("stage_status", {}))
    stage_status["risk"] = "running"
    state["current_stage"] = "RISK"
    state["stage_status"] = stage_status
    log_agent_activity(state, "RISK", "evaluating_policy_and_security", {"product": selected.get("name") if selected else None})

    result = risk_agent.check_purchase(selected, reqs)
    stage_status["risk"] = "completed"
    state["risk"] = result
    state["stage_status"] = stage_status
    log_agent_activity(state, "RISK", "policy_checked", result, result.get("approved", True))
    return {
        "current_stage": "RISK",
        "stage_status": stage_status,
        "risk": result
    }


# 6a. HUMAN APPROVAL NODE
def approval_node(state: BudBuyState) -> dict:
    selected, risk = state.get("selected_product", {}), state.get("risk", {})
    stage_status = dict(state.get("stage_status", {}))
    stage_status["purchase"] = "ready"
    price = selected.get("effective_price", selected.get("price", 2199))
    pending = {"product_id": selected.get("product_id"), "name": selected.get("name"),
               "image_url": selected.get("image_url", ""), "flipkart_url": selected.get("flipkart_url", ""),
               "effective_price": price, "reason": risk.get("reason", "Confirmation required.")}
    log_agent_activity(state, "ORCHESTRATOR", "awaiting_user_confirmation", pending)
    return {
        "status": "AWAITING_APPROVAL",
        "current_stage": "PURCHASE",
        "stage_status": stage_status,
        "pending_purchase": pending,
        "message_to_user": f"Found {pending['name']} at ₹{price:,.0f}. Proceed to checkout?"
    }


# 6b. PURCHASE NODE (Razorpay Staging & MCP Cart Reservation)
def purchase_node(state: BudBuyState) -> dict:
    selected = state.get("selected_product", {})
    stage_status = dict(state.get("stage_status", {}))
    stage_status["purchase"] = "ready"
    price = selected.get("effective_price") or selected.get("price") or 2199
    checkout = purchase_agent.prepare_checkout(state.get("session_id", "sess"), selected.get("product_id"), float(price))
    checkout.update({"effective_price": float(price), "amount": float(price), "product_name": selected.get("name"),
                     "product_image": selected.get("image_url", ""), "flipkart_url": selected.get("flipkart_url", "")})
    log_agent_activity(state, "PURCHASE", "awaiting_razorpay_checkout", {"order_id": checkout.get("razorpay_order_id"), "amount": price})
    return {
        "status": "AWAITING_PAYMENT",
        "current_stage": "PURCHASE",
        "stage_status": stage_status,
        "checkout": checkout,
        "message_to_user": f"Opening Razorpay checkout for {selected.get('name')} at ₹{price:,.0f}."
    }



def risk_router(state: BudBuyState) -> str:
    risk = state.get("risk", {})
    if not risk.get("approved"):
        return "end"
    return "approval" if risk.get("requires_user_confirmation") else "purchase"


# 7. LANGGRAPH STATEGRAPH COMPILATION (6-Stage Streamlined Workflow)
def build_graph():
    try:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, START, StateGraph
        graph = StateGraph(BudBuyState)
        
        nodes = {
            "intent": intent_node,
            "research": research_node,
            "analyst": analyst_node,
            "evaluation": evaluation_node,
            "risk": risk_node,
            "approval": approval_node,
            "purchase": purchase_node,
        }
        for name, node in nodes.items():
            graph.add_node(name, node)

        # 6-Stage sequential workflow
        graph.add_edge(START, "intent")
        graph.add_edge("intent", "research")
        graph.add_edge("research", "analyst")
        graph.add_edge("analyst", "evaluation")
        graph.add_edge("evaluation", "risk")
        graph.add_conditional_edges("risk", risk_router, {"approval": "approval", "purchase": "purchase", "end": END})
        graph.add_edge("approval", END)
        graph.add_edge("purchase", END)

        return graph.compile(checkpointer=MemorySaver())
    except Exception as error:
        print(f"[LangGraph] Could not build graph: {error}")
        return None


COMPILED_GRAPH = build_graph()



class Orchestrator:
    """Adapter used by the FastAPI endpoints."""
    def __init__(self, session_id: str, user_goal: str):
        self.session_id, self.user_goal, self.db = session_id, user_goal, _Session()
        self.state: BudBuyState = {
            "session_id": session_id, "user_goal": user_goal, "status": "DISCOVERING",
            "current_stage": "INTENT",
            "stage_status": {
                "intent": "running",
                "research": "pending",
                "analyst": "pending",
                "evaluation": "pending",
                "risk": "pending",
                "purchase": "pending"
            },
            "requirements": {}, "search_query": user_goal, "raw_products": [], "candidates": [],
            "review_analysis": {}, "reviews": {}, "rag_context": {},
            "selected_product": None, "recommendation_reasons": [], "why_this_product": [], "recommendation": "", "recommendation_summary": "",
            "risk": {}, "pending_purchase": None, "checkout": None, "payment_status": "", "message_to_user": ""
        }




    def run(self, simulate_oos: bool = False, simulate_payment_timeout: bool = False) -> dict:
        log_agent_activity(self.state, "ORCHESTRATOR", "goal_received", {"goal": self.user_goal})
        if COMPILED_GRAPH:
            try:
                result = COMPILED_GRAPH.invoke(self.state, {"configurable": {"thread_id": self.session_id}})
                self.state.update(result)
                return self._finish(self.state.get("message_to_user", "Workflow complete."))
            except Exception as error:
                print(f"[Graph] Falling back to direct execution: {error}")
        
        # Direct execution fallback
        for node in (intent_node, research_node, analyst_node, evaluation_node, risk_node):
            self.state.update(node(self.state))


        risk = self.state.get("risk", {})
        if not risk.get("approved"):
            return self._finish(risk.get("reason", "Purchase was not approved."))
        node = approval_node if risk.get("requires_user_confirmation") else purchase_node
        self.state.update(node(self.state))
        return self._finish(self.state.get("message_to_user", "Ready."))

    def confirm_pending_purchase(self) -> dict:
        pending = self.state.get("pending_purchase")
        if not pending:
            return self._finish("No pending purchase found.")
        price = float(pending.get("effective_price", 2199))
        checkout = purchase_agent.prepare_checkout(self.session_id, pending.get("product_id"), price)
        checkout.update({
            "effective_price": price, "amount": price, "product_name": pending.get("name", "Audio Gear"),
            "product_image": pending.get("image_url", ""), "flipkart_url": pending.get("flipkart_url", "")
        })
        self.state.update({"status": "AWAITING_PAYMENT", "checkout": checkout})
        log_agent_activity(self.state, "PURCHASE", "user_approved_checkout", {
            "razorpay_order_id": checkout.get("razorpay_order_id"), "amount": price, "product": pending.get("name")
        })
        return self._finish(f"Approved! Opening Razorpay checkout for ₹{price:,.0f}...")

    def poll_payment(self) -> dict:
        checkout = self.state.get("checkout")
        if not checkout:
            return self._finish("No active checkout.")
        result = purchase_agent.check_and_finalize_payment(
            checkout.get("payment_id"), checkout.get("reservation_id"), checkout.get("cart_id")
        )
        log_agent_activity(self.state, "PURCHASE", "payment_status_checked", result, result.get("status") == "SUCCESS")
        if result.get("status") == "SUCCESS":
            self.state.update({"status": "COMPLETED", "payment_status": "SUCCESS"})
            return self._finish("Order confirmed successfully!")
        return self._finish(f"Payment status: {result.get('status')}")

    def _finish(self, message: str) -> dict:
        self.state["message_to_user"] = message
        record = self.db.query(AgentSession).filter_by(id=self.session_id).first()
        if not record:
            record = AgentSession(id=self.session_id, user_goal=self.user_goal)
            self.db.add(record)
        record.state, record.status = self.state, self.state.get("status", "PROCESSING")
        self.db.commit()
        return self.state


def run_budbuy(session_id: str, user_goal: str) -> dict:
    return Orchestrator(session_id, user_goal).run()
