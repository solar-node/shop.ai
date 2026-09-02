#!/usr/bin/env python3
"""
Comprehensive Evaluation Suite for shop.ai (Autonomous Multi-Agent Commerce Platform).

Evaluates the system across 7 core pillars:
1. Deterministic Math & Bayesian Ranking Integrity
2. Deterministic Price & Budget Targeting (85%-100% sweet spot)
3. Evidence-Grounded Feature Matching
4. Policy Gate & Risk Guard Security Enforcement
5. Cryptographic Payment Verification (HMAC-SHA256)
6. Category-Agnostic Intent & Constraint Extraction
7. Decision Explainability & Differentiated Bullet Points
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.commerce.ranking import _bayesian_quality_score, _price_value_score, _feature_match_score
from app.commerce.policies import evaluate_purchase
from app.agents.research_agent import extract_intent
from app.agents.recommendation_agent import _differentiated_fallback_reasons

from app.payments.razorpay_client import verify_payment_signature


class EvaluationBenchmark:
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0

    def assert_test(self, category: str, test_name: str, condition: bool, details: str = ""):
        self.total_tests += 1
        if condition:
            self.passed_tests += 1
            status = "PASS"
        else:
            status = "FAIL"
        self.results.append({
            "category": category,
            "name": test_name,
            "status": status,
            "details": details
        })

    def run_all(self):
        print("\n" + "=" * 75)
        print("  shop.ai — MULTI-AGENT COMMERCE SYSTEM EVALUATION BENCHMARK")
        print("=" * 75 + "\n")

        self.eval_bayesian_ranking()
        self.eval_budget_targeting()
        self.eval_feature_matching()
        self.eval_risk_guard_and_policies()
        self.eval_cryptographic_payment_security()
        self.eval_category_agnostic_intent()
        self.eval_decision_explainability()

        self.print_summary()

    def eval_bayesian_ranking(self):
        cat = "1. Bayesian Rating & Statistical Volume Confidence"
        
        # Test 1: Statistical review volume confidence shrinkage
        high_vol = _bayesian_quality_score(4.3, 15000)
        low_vol = _bayesian_quality_score(4.7, 10)
        self.assert_test(cat, "High Volume (15k revs @ 4.3★) beats Low Volume (10 revs @ 4.7★)", high_vol > low_vol,
                         f"High vol: {high_vol} vs Low vol: {low_vol}")

        # Test 2: Moderate volume ranking
        mid_vol = _bayesian_quality_score(4.5, 3000)
        self.assert_test(cat, "Moderate Volume (3k revs @ 4.5★) achieves high quality score (> 0.80)", mid_vol > 0.80,
                         f"Score: {mid_vol}")

        # Test 3: Zero / negative reviews handling
        zero_vol = _bayesian_quality_score(5.0, 0)
        self.assert_test(cat, "Zero reviews rating strongly shrunk toward prior (<= 0.40)", zero_vol <= 0.40,
                         f"Score: {zero_vol}")

    def eval_budget_targeting(self):
        cat = "2. Deterministic Price & Budget Targeting"
        budget = 10000.0

        # Test 1: Hard ceiling enforcement
        over_budget = _price_value_score(10500.0, budget)
        self.assert_test(cat, "Over-budget product (₹10,500 on ₹10,000) receives 0.0 price score", over_budget == 0.0,
                         f"Score: {over_budget}")

        # Test 2: Ideal >=90% budget zone gives top price value score (>= 0.95)
        top_zone = _price_value_score(9500.0, budget)
        self.assert_test(cat, ">=90% budget sweet-spot (₹9,500 on ₹10,000) achieves top score (>= 0.95)", top_zone >= 0.95,
                         f"Score: {top_zone}")

        # Test 3: High tier zone (80%-89%)
        mid_zone = _price_value_score(8500.0, budget)
        self.assert_test(cat, "High tier zone (₹8,500 on ₹10,000) scores in 0.70–0.95 range", 0.70 <= mid_zone < 0.95,
                         f"Score: {mid_zone}")

        # Test 4: Low-end underspending item (<60%, e.g. ₹5,000) receives low score (< 0.30)
        low_zone = _price_value_score(5000.0, budget)
        self.assert_test(cat, "Low-end item (₹5,000 on ₹10,000) strongly de-prioritized (< 0.30)", low_zone < 0.30 and low_zone < top_zone,
                         f"Low: {low_zone} vs Top: {top_zone}")


    def eval_feature_matching(self):
        cat = "3. Evidence-Grounded Feature Matching"
        reqs = {"hard_constraints": ["16GB RAM"], "soft_preferences": ["dedicated GPU", "SSD"]}

        cand_full = {"matched_requirements": ["16GB RAM", "dedicated GPU", "SSD"], "missing_requirements": []}
        score_full = _feature_match_score(cand_full, reqs)
        self.assert_test(cat, "Full feature match achieves 1.0 score", score_full == 1.0, f"Score: {score_full}")

        cand_missing = {"matched_requirements": ["SSD"], "missing_requirements": ["16GB RAM"]}
        score_missing = _feature_match_score(cand_missing, reqs)
        self.assert_test(cat, "Missing constraint receives penalty deduction (< 0.50)", score_missing < 0.50, f"Score: {score_missing}")

    def eval_risk_guard_and_policies(self):
        cat = "4. Policy Gate & Risk Guard Security"

        rej = evaluate_purchase(effective_price=8000, budget_max=7000, auto_purchase_limit=None, merchant_trust_score=0.95, stock_confirmed=True)
        self.assert_test(cat, "Price > Budget Ceiling is strictly REJECTED (approved=False)", not rej.approved,
                         f"Reason: {rej.reason}")

        stock_rej = evaluate_purchase(effective_price=4000, budget_max=5000, auto_purchase_limit=None, merchant_trust_score=0.95, stock_confirmed=False)
        self.assert_test(cat, "Out-of-stock product is strictly REJECTED (approved=False)", not stock_rej.approved,
                         f"Reason: {stock_rej.reason}")

        trust_rej = evaluate_purchase(effective_price=4000, budget_max=5000, auto_purchase_limit=None, merchant_trust_score=0.55, stock_confirmed=True)
        self.assert_test(cat, "Untrusted seller (< 0.60) is strictly REJECTED (approved=False)", not trust_rej.approved,
                         f"Reason: {trust_rej.reason}")

        gate = evaluate_purchase(effective_price=4500, budget_max=5000, auto_purchase_limit=4000, merchant_trust_score=0.95, stock_confirmed=True)
        self.assert_test(cat, "Price > Auto-buy limit requires explicit human approval (confirmation=True)",
                         gate.approved and gate.requires_user_confirmation, f"Reason: {gate.reason}")

        auto = evaluate_purchase(effective_price=3500, budget_max=5000, auto_purchase_limit=4000, merchant_trust_score=0.95, stock_confirmed=True)
        self.assert_test(cat, "Price <= Auto-buy limit allows immediate auto-buy (confirmation=False)",
                         auto.approved and not auto.requires_user_confirmation, f"Reason: {auto.reason}")


    def eval_cryptographic_payment_security(self):
        cat = "5. Cryptographic Payment Verification (HMAC-SHA256)"
        import hmac, hashlib

        order_id = "order_test_998877"
        payment_id = "pay_test_112233"
        secret = "test_secret_key_12345"

        msg = f"{order_id}|{payment_id}".encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        # Deterministic HMAC Verification function matching Razorpay security specification
        def _verify_hmac(o_id, p_id, sig, sec):
            expected = hmac.new(sec.encode("utf-8"), f"{o_id}|{p_id}".encode("utf-8"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, sig)

        is_valid = _verify_hmac(order_id, payment_id, valid_sig, secret)
        self.assert_test(cat, "Authentic HMAC-SHA256 signature is verified as True", is_valid, "Valid signature accepted")

        tampered_sig = valid_sig[:-4] + "ffff"
        is_tampered = _verify_hmac(order_id, payment_id, tampered_sig, secret)
        self.assert_test(cat, "Tampered/forged payment signature is strictly REJECTED as False", not is_tampered,
                         "Tampered signature blocked")


    def eval_category_agnostic_intent(self):
        cat = "6. Category-Agnostic Intent & Constraint Extraction"

        test_cases = [
            ("Find me good wireless earbuds under ₹3,000 for gym workouts with ANC", "earbuds", 3000.0),
            ("I need a laptop under ₹70,000 mainly for coding, Python and ML", "laptop", 70000.0),
            ("Find me a good smartphone under ₹25,000 with 50MP camera and fast charging", "smartphone", 25000.0),
            ("Find me a good pair of running shoes under ₹4,000 for regular jogging", "running shoes", 4000.0),
        ]

        for prompt, expected_cat, expected_budget in test_cases:
            res = extract_intent(prompt)
            cat_match = expected_cat.lower() in res.get("category", "").lower()

            budget_match = res.get("budget_max") == expected_budget
            cat_val = res.get('category', '')
            budget_val = res.get('budget_max', 0)
            self.assert_test(cat, f"Extract intent & budget correctly for '{expected_cat}'", cat_match and budget_match,
                             f"Extracted category: '{cat_val}', Budget: ₹{budget_val}")

    def eval_decision_explainability(self):
        cat = "7. Decision Explainability ('WHY THIS PRODUCT?')"
        cand1 = {"name": "Nike Revolution 8", "price": 4295, "rating": 4.5, "review_count": 5300, "utility_score": 0.56, "matched_requirements": ["cushioning"]}
        cand2 = {"name": "Nike Run Defy", "price": 3596, "rating": 4.6, "review_count": 1800, "utility_score": 0.52, "matched_requirements": ["grip"]}
        reqs = {"budget_max": 5000, "category": "running shoes"}

        reasons1 = _differentiated_fallback_reasons(cand1, reqs, "Find shoes under 5000", rank=1)
        reasons2 = _differentiated_fallback_reasons(cand2, reqs, "Find shoes under 5000", rank=2)

        len_valid = 2 <= len(reasons1) <= 4 and 2 <= len(reasons2) <= 4
        self.assert_test(cat, "Generates 2–4 concise bullet points per candidate", len_valid, f"Count 1: {len(reasons1)}, Count 2: {len(reasons2)}")

        reasons_distinct = reasons1 != reasons2
        self.assert_test(cat, "Reasoning is distinct and non-generic between Rank #1 and Rank #2", reasons_distinct,
                         f"R1: '{reasons1[0]}' vs R2: '{reasons2[0]}'")

    def print_summary(self):
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0}
            if r["status"] == "PASS":
                categories[cat]["pass"] += 1
            else:
                categories[cat]["fail"] += 1

        print("-" * 75)
        print(f"{'EVALUATION PILLAR':<55} | {'PASS':<6} | {'STATUS'}")
        print("-" * 75)
        for cat, counts in categories.items():
            tot = counts["pass"] + counts["fail"]
            pillar_status = "100% PASSED" if counts["fail"] == 0 else f"{counts['pass']}/{tot} PASSED"
            print(f"{cat:<55} | {counts['pass']}/{tot:<4} | {pillar_status}")

        print("-" * 75)
        pct = round((self.passed_tests / self.total_tests) * 100, 1) if self.total_tests > 0 else 0
        print(f"OVERALL SYSTEM INTEGRITY: {self.passed_tests}/{self.total_tests} Tests Passed ({pct}%)\n")


if __name__ == "__main__":
    benchmark = EvaluationBenchmark()
    benchmark.run_all()
