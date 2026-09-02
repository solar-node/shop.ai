"""LangGraph orchestration for Shop.ai's category-agnostic autonomous shopping flow."""
import os
from typing import Any, TypedDict
from dotenv import load_dotenv

load_dotenv()

# Ensure LangSmith tracing environment flags are active
if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

from database.models import AgentSession, get_engine, get_session_factory
from app.observability.logger import log_event
from app.agents import research_agent, product_info_agent, review_trust_agent, evidence_agent, recommendation_agent, risk_agent, purchase_agent
from app.commerce.ranking import rank_products, weights_from_priority


_engine = get_engine()
_Session = get_session_factory(_engine)


class ShopAIState(TypedDict, total=False):

    session_id: str
    user_goal: str
    current_stage: str
    stage_status: dict
    requirements: dict
    search_query: str
    marketplace_data: list
    product_info_data: dict
    review_trust_data: dict
    normalized_evidence: list
    candidates: list
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


BudBuyState = ShopAIState


def log_agent_activity(state: ShopAIState, agent: str, action: str, detail: Any = None, success: bool = True):
    db = _Session()
    try:
        sid = state.get("session_id", "default")
        log_event(db, sid, agent, action, detail or {}, success=success)
        record = db.query(AgentSession).filter_by(id=sid).first()
        if not record:
            record = AgentSession(id=sid, user_goal=state.get("user_goal", ""))
            db.add(record)
        record.status = state.get("status", "PROCESSING")
        record.state = dict(state)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def _set_stage(state, stage: str, status: str):
    stages = dict(state.get("stage_status", {}))
    stages[stage] = status
    return stages


def intent_node(state: BudBuyState) -> dict:
    goal = state.get("user_goal", "")
    reqs = research_agent.extract_intent(goal)
    query = research_agent.build_search_query(reqs, goal)
    stages = _set_stage(state, "intent", "completed")
    stages["research"] = "running"
    updates = {"requirements": reqs, "search_query": query, "stage_status": stages, "current_stage": "RESEARCH", "status": "DISCOVERING"}
    state.update(updates)
    log_agent_activity(state, "INTENT", "intent_extracted", reqs)
    return updates


def marketplace_research_node(state: BudBuyState) -> dict:
    reqs = state.get("requirements", {})
    stages = _set_stage(state, "research", "running")
    products = research_agent.find_candidates(reqs, state.get("user_goal", ""))
    updates = {"marketplace_data": products, "stage_status": stages, "current_stage": "RESEARCH"}
    state.update(updates)
    log_agent_activity(state, "MARKETPLACE_RESEARCH", "products_retrieved", {"count": len(products)})
    return updates


def product_info_research_node(state: BudBuyState) -> dict:
    result = product_info_agent.research_product_attributes(state.get("requirements", {}), state.get("user_goal", ""))
    updates = {"product_info_data": result}
    state.update(updates)
    log_agent_activity(state, "PRODUCT_INFO_RESEARCH", "attribute_plan_created", result)
    return updates


def review_trust_research_node(state: BudBuyState) -> dict:
    result = review_trust_agent.research_review_trust(state.get("requirements", {}))
    updates = {"review_trust_data": result}
    state.update(updates)
    log_agent_activity(state, "REVIEW_TRUST_RESEARCH", "review_model_prepared", result)
    return updates


def evidence_synthesis_node(state: BudBuyState) -> dict:
    marketplace = state.get("marketplace_data", [])
    normalized = evidence_agent.synthesize_evidence(
        marketplace,
        state.get("product_info_data", {}),
        state.get("review_trust_data", {}),
        state.get("requirements", {}),
        state.get("user_goal", ""),
    )
    stages = _set_stage(state, "research", "completed")
    stages["analyst"] = "running"
    updates = {"normalized_evidence": normalized, "stage_status": stages, "current_stage": "ANALYST", "status": "RESEARCHING"}
    state.update(updates)
    log_agent_activity(state, "EVIDENCE_SYNTHESIS", "evidence_fused", {"count": len(normalized)})
    return updates


def analyst_node(state: BudBuyState) -> dict:
    reqs = state.get("requirements", {})
    evidence = state.get("normalized_evidence", [])
    ranked = rank_products(
        evidence,
        budget_max=float(reqs.get("budget_max") or 0),
        requirements=reqs,
        weights=weights_from_priority(reqs.get("priority_order"), reqs, state.get("user_goal", "")),
        user_goal=state.get("user_goal", ""),
    )

    lookup = {str(x.get("product_id")): x for x in evidence}
    candidates = []
    for i, item in enumerate(ranked, 1):
        raw = lookup.get(str(item.product_id), {})
        candidates.append({**raw, "utility_score": item.utility_score, "rank": i, "components": item.components})
    stages = _set_stage(state, "analyst", "completed")
    stages["evaluation"] = "running"
    updates = {"candidates": candidates, "stage_status": stages, "current_stage": "EVALUATION", "status": "ANALYZING"}
    state.update(updates)
    log_agent_activity(state, "ANALYST", "products_ranked", {"count": len(candidates), "top": candidates[0].get("name") if candidates else None})
    return updates


def recommendation_node(state: BudBuyState) -> dict:
    candidates = state.get("candidates", [])
    reqs = state.get("requirements", {})
    if not candidates:
        return {"status": "FAILED", "current_stage": "EVALUATION", "message_to_user": "No suitable products were found."}
    
    batch_res = recommendation_agent.synthesize_all_candidate_reasons(candidates, reqs, state.get("user_goal", ""))
    reasons_map = batch_res.get("candidates_reasons", {})
    overall_rec = batch_res.get("overall_recommendation", "")

    enriched = []
    for i, candidate in enumerate(candidates):
        p_id = str(candidate.get("product_id") or f"prod_{i}")
        reasons = reasons_map.get(p_id) or reasons_map.get(candidate.get("name")) or []
        if not reasons:
            reasons = recommendation_agent._differentiated_fallback_reasons(candidate, reqs, state.get("user_goal", ""), rank=i + 1)
        enriched.append({
            **candidate,
            "recommendation_reasons": reasons,
            "why_this_product": reasons,
            "llm_rec": overall_rec if i == 0 else "",
            "tradeoffs": "",
        })
    selected = enriched[0]
    stages = _set_stage(state, "evaluation", "completed")
    stages["risk"] = "running"
    updates = {
        "candidates": enriched, "selected_product": selected,
        "recommendation_reasons": selected.get("recommendation_reasons", []),
        "why_this_product": selected.get("why_this_product", []),
        "recommendation": overall_rec,
        "recommendation_summary": overall_rec,
        "stage_status": stages, "current_stage": "RISK", "status": "RECOMMENDING"
    }
    state.update(updates)
    log_agent_activity(state, "RECOMMENDATION", "recommendation_completed", {"product": selected.get("name")})
    return updates


def risk_node(state: BudBuyState) -> dict:
    selected = state.get("selected_product") or {}
    result = risk_agent.check_purchase(selected, state.get("requirements", {}), user_goal=state.get("user_goal", ""))
    stages = _set_stage(state, "risk", "completed")
    stages["purchase"] = "ready"
    updates = {"risk": result, "stage_status": stages, "current_stage": "PURCHASE"}
    state.update(updates)
    log_agent_activity(state, "RISK", "policy_decision", result, result.get("approved", False))
    return updates



def approval_node(state: BudBuyState) -> dict:
    selected = state.get("selected_product") or {}
    risk = state.get("risk") or {}
    price = selected.get("effective_price", selected.get("price"))
    pending = {"product_id": selected.get("product_id"), "name": selected.get("name"), "image_url": selected.get("image_url", ""), "flipkart_url": selected.get("flipkart_url", ""), "effective_price": price, "reason": risk.get("reason", "Confirmation required.")}
    stages = _set_stage(state, "purchase", "ready")
    return {"status": "AWAITING_APPROVAL", "current_stage": "PURCHASE", "stage_status": stages, "pending_purchase": pending, "message_to_user": f"Found {pending['name']} at ₹{price:,.0f}. Proceed to checkout?"}


def purchase_node(state: BudBuyState) -> dict:
    selected = state.get("selected_product") or {}
    price = selected.get("effective_price", selected.get("price"))
    if price is None:
        return {"status": "FAILED", "message_to_user": "Product price is unavailable."}
    checkout = purchase_agent.prepare_checkout(state.get("session_id", "session"), selected.get("product_id"), float(price))
    checkout.update({"effective_price": float(price), "amount": float(price), "product_name": selected.get("name"), "product_image": selected.get("image_url", ""), "flipkart_url": selected.get("flipkart_url", "")})
    stages = _set_stage(state, "purchase", "ready")
    return {"status": "AWAITING_PAYMENT", "current_stage": "PURCHASE", "stage_status": stages, "checkout": checkout, "message_to_user": f"Opening checkout for {selected.get('name')} at ₹{price:,.0f}."}


def risk_router(state: BudBuyState) -> str:
    risk = state.get("risk", {})
    if not risk.get("approved") or not state.get("selected_product"):
        return "end"
    return "approval" if risk.get("requires_user_confirmation") else "purchase"


def build_graph():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    graph = StateGraph(BudBuyState)
    for name, node in {
        "intent": intent_node,
        "marketplace_research": marketplace_research_node,
        "product_info_research": product_info_research_node,
        "review_trust_research": review_trust_research_node,
        "evidence_synthesis": evidence_synthesis_node,
        "analyst": analyst_node,
        "recommendation": recommendation_node,
        "risk": risk_node,
        "approval": approval_node,
        "purchase": purchase_node,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "intent")
    graph.add_edge("intent", "marketplace_research")
    graph.add_edge("intent", "product_info_research")
    graph.add_edge("intent", "review_trust_research")
    graph.add_edge("marketplace_research", "evidence_synthesis")
    graph.add_edge("product_info_research", "evidence_synthesis")
    graph.add_edge("review_trust_research", "evidence_synthesis")
    graph.add_edge("evidence_synthesis", "analyst")
    graph.add_edge("analyst", "recommendation")
    graph.add_edge("recommendation", "risk")
    graph.add_conditional_edges("risk", risk_router, {"approval": "approval", "purchase": "purchase", "end": END})
    graph.add_edge("approval", END)
    graph.add_edge("purchase", END)
    return graph.compile(checkpointer=MemorySaver())


COMPILED_GRAPH = build_graph()


class Orchestrator:
    def __init__(self, session_id: str, user_goal: str):
        self.session_id, self.user_goal, self.db = session_id, user_goal, _Session()
        self.state: BudBuyState = {
            "session_id": session_id, "user_goal": user_goal, "status": "DISCOVERING", "current_stage": "INTENT",
            "stage_status": {"intent":"running","research":"pending","analyst":"pending","evaluation":"pending","risk":"pending","purchase":"pending"},
            "requirements": {}, "search_query": user_goal, "marketplace_data": [], "product_info_data": {}, "review_trust_data": {},
            "normalized_evidence": [], "candidates": [], "selected_product": None, "recommendation_reasons": [], "why_this_product": [],
            "recommendation": "", "recommendation_summary": "", "risk": {}, "pending_purchase": None, "checkout": None,
            "payment_status": "", "message_to_user": ""
        }

    @traceable(run_type="chain", name="Shop.ai Autonomous Pipeline")
    def run(self, user_goal: str = None, simulate_oos=False, simulate_payment_timeout=False):
        if user_goal:
            self.user_goal = user_goal
            self.state["user_goal"] = user_goal
        else:
            user_goal = self.user_goal

        log_agent_activity(self.state, "ORCHESTRATOR", "goal_received", {"goal": self.user_goal})

        try:
            result = COMPILED_GRAPH.invoke(self.state, {"configurable": {"thread_id": self.session_id}})
            self.state.update(result)
        except Exception as exc:
            print(f"[Graph] {exc}; using direct fallback")
            for node in (intent_node, marketplace_research_node, product_info_research_node, review_trust_research_node, evidence_synthesis_node, analyst_node, recommendation_node, risk_node):
                self.state.update(node(self.state))
            risk = self.state.get("risk", {})
            if risk.get("approved"):
                self.state.update(approval_node(self.state) if risk.get("requires_user_confirmation") else purchase_node(self.state))
            else:
                self.state["status"] = "FAILED"
                self.state["message_to_user"] = risk.get("reason", "Purchase was not approved.")
        return self._finish(self.state.get("message_to_user", "Workflow complete."))

    def confirm_pending_purchase(self):
        pending = self.state.get("pending_purchase")
        if not pending:
            return self._finish("No pending purchase found.")
        price = pending.get("effective_price")
        checkout = purchase_agent.prepare_checkout(self.session_id, pending.get("product_id"), float(price))
        checkout.update({"effective_price": float(price), "amount": float(price), "product_name": pending.get("name"), "product_image": pending.get("image_url", ""), "flipkart_url": pending.get("flipkart_url", "")})
        self.state.update({"status":"AWAITING_PAYMENT","current_stage":"PURCHASE","checkout":checkout})
        return self._finish("Approved. Opening checkout...")

    def poll_payment(self):
        checkout = self.state.get("checkout")
        if not checkout:
            return self._finish("No active checkout.")
        result = purchase_agent.check_and_finalize_payment(checkout.get("payment_id"), checkout.get("reservation_id"), checkout.get("cart_id"))
        if result.get("status") == "SUCCESS":
            self.state.update({"status":"COMPLETED","payment_status":"SUCCESS"})
        return self._finish(f"Payment status: {result.get('status')}")

    def _finish(self, message):
        self.state["message_to_user"] = message
        record = self.db.query(AgentSession).filter_by(id=self.session_id).first()
        if not record:
            record = AgentSession(id=self.session_id, user_goal=self.user_goal)
            self.db.add(record)
        record.state, record.status = self.state, self.state.get("status", "PROCESSING")
        self.db.commit()
        return self.state


@traceable(run_type="chain", name="Shop.ai Shopping Execution")
def run_shopai(session_id: str, user_goal: str, simulate_oos: bool = False, simulate_payment_timeout: bool = False):
    return Orchestrator(session_id, user_goal).run(
        user_goal=user_goal,
        simulate_oos=simulate_oos,
        simulate_payment_timeout=simulate_payment_timeout,
    )


run_budbuy = run_shopai


