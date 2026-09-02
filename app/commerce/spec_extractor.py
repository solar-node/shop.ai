"""Category-agnostic specification extraction and 3-state requirement matching engine.
Performs deterministic, evidence-grounded matching against product text, snippets, and metadata
without hardcoded product names, categories, or expected results.
"""
import re
from typing import Any, Dict, List, Tuple

STOP_WORDS = {
    "with", "for", "and", "the", "a", "an", "in", "of", "to", "under", "below",
    "within", "good", "great", "strong", "best", "high", "top", "easy", "features",
    "specs", "support", "regular", "daily", "preferred", "preference", "need", "want"
}


def stem(word: str) -> str:
    """Minimal language-agnostic English stemmer for root matching."""
    w = word.lower().strip()
    for suffix in ("ing", "tion", "sion", "ment", "ness", "able", "ible", "ed", "es", "s", "er", "or", "ive", "ity", "y"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[:-len(suffix)]
    return w


def matches_token(token: str, text: str) -> bool:
    """Checks if token or its root stem is present in text."""
    t_low = token.lower().strip()
    if len(t_low) <= 1:
        return False
    if t_low in text:
        return True
    st = stem(t_low)
    if len(st) >= 3 and st in text:
        return True
    return False


def extract_product_specs(text: str, snippet: str = "", category: str = "", badge: str = "") -> Dict[str, Any]:
    """Category-agnostic numerical and unit specification extraction from listing text."""
    specs = {}
    full_text = f" {text} {snippet} {badge} "

    # 1. Capacity & Memory (GB, TB, MB, mAh)
    for m in re.finditer(r"\b(\d{1,5})\s*(GB|TB|MB|mAh|L|ml|kg|g)\b", full_text, re.I):
        val, unit = m.group(1), m.group(2).upper()
        if unit in ("GB", "TB", "MB"):
            if "RAM" in full_text[m.start()-5:m.end()+10].upper() or "DDR" in full_text[m.start()-5:m.end()+10].upper():
                specs["ram"] = f"{val}{unit}"
            elif "SSD" in full_text[m.start()-5:m.end()+10].upper() or "STORAGE" in full_text[m.start()-5:m.end()+10].upper() or "ROM" in full_text[m.start()-5:m.end()+10].upper():
                specs["storage"] = f"{val}{unit}"
            elif "ram" not in specs:
                specs["ram"] = f"{val}{unit}"
            elif "storage" not in specs and f"{val}{unit}" != specs.get("ram"):
                specs["storage"] = f"{val}{unit}"
        elif unit == "MAH":
            specs["battery_capacity"] = f"{val}mAh"
        else:
            specs[unit.lower()] = f"{val} {unit}"

    # 2. Frequencies & Power (Hz, W, bar, RPM)
    for m in re.finditer(r"\b(\d{1,4})\s*(Hz|W|bar|RPM|V|kW)\b", full_text, re.I):
        val, unit = m.group(1), m.group(2)
        specs[unit.lower()] = f"{val}{unit}"

    # 3. Sizes & Dimensions (inch, ", cm, mm)
    size_match = re.search(r"(\b\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|\"|cm|\-inch)\b", full_text, re.I)
    if size_match:
        specs["screen_size"] = f"{size_match.group(1)} inch"

    # 4. Camera & Optical (MP, 4K, 1080p, 1440p, QHD, FHD)
    cam_match = re.search(r"(\b\d{2,3}\s*MP)\b", full_text, re.I)
    if cam_match:
        specs["camera"] = cam_match.group(1).replace(" ", "")
    res_match = re.search(r"\b(1440p|1080p|2K|4K|QHD|WQHD|FHD|UHD|Retina|AMOLED|OLED|IPS)\b", full_text, re.I)
    if res_match:
        specs["resolution"] = res_match.group(1).upper()

    # 5. Generic Entity Extraction (terms in parentheses or separated by commas/dashes)
    entities = [x.strip() for x in re.split(r"[,/|()]", text) if len(x.strip()) > 3 and len(x.strip()) < 40]
    if entities:
        specs["features"] = entities[:5]

    return specs


def _clean_and_dedup_requirements(req_list: List[str]) -> List[str]:
    """Cleans and deduplicates requirements while preserving order."""
    cleaned = []
    for r in req_list:
        r_str = str(r).strip()
        if not r_str:
            continue
        r_low = r_str.lower()
        if any(r_low == c.lower() or (r_low in c.lower() and len(r_low) < len(c.lower())) for c in cleaned):
            continue
        cleaned.append(r_str)
    return cleaned


def evaluate_requirement_3state(
    req: str,
    evidence_text: str,
    specs: Dict[str, Any],
    price: float,
    budget_max: float,
) -> str:
    """Evaluates a single requirement against product evidence into 3 states:
    - TRUE: verified match supported by evidence
    - FALSE: contradicted by evidence (e.g. price > budget or spec < requirement)
    - UNKNOWN: evidence unavailable / unmentioned in listing
    """
    r_low = req.lower().strip()
    e_low = (evidence_text + " " + " ".join(str(v) for v in specs.values())).lower()

    # 1. Price constraint check
    if "price" in r_low or "<=" in r_low or "under" in r_low or "below" in r_low:
        digits = re.findall(r"\d+", r_low)
        if digits:
            target_max = float(digits[0])
            if price > 0:
                return "TRUE" if price <= target_max else "FALSE"
        return "UNKNOWN"

    # 2. Check numerical spec requirements
    # RAM
    ram_req = re.search(r"(\d+)\s*gb\s*ram", r_low)
    if ram_req:
        target_ram = int(ram_req.group(1))
        prod_ram = re.search(r"(\d+)\s*gb\s*(?:ram|ddr|lpddr)?", e_low)
        if prod_ram:
            return "TRUE" if int(prod_ram.group(1)) >= target_ram else "FALSE"
        return "UNKNOWN"

    # Storage / SSD
    ssd_req = re.search(r"(\d+)\s*(?:gb|tb)\s*ssd", r_low)
    if ssd_req:
        target_ssd = int(ssd_req.group(1))
        prod_ssd = re.search(r"(\d+)\s*(?:gb|tb)\s*ssd", e_low)
        if prod_ssd:
            return "TRUE" if int(prod_ssd.group(1)) >= target_ssd else "FALSE"
        return "UNKNOWN"

    # Refresh Rate
    hz_req = re.search(r"(\d+)\s*hz", r_low)
    if hz_req:
        target_hz = int(hz_req.group(1))
        prod_hz = re.search(r"(\d+)\s*hz", e_low)
        if prod_hz:
            return "TRUE" if int(prod_hz.group(1)) >= target_hz else "FALSE"
        return "UNKNOWN"

    # Screen Size
    inch_req = re.search(r"(\d+(?:\.\d+)?)\s*(?:inch|\"|\-inch)", r_low)
    if inch_req:
        target_inch = float(inch_req.group(1))
        prod_inch = re.search(r"(\d+(?:\.\d+)?)\s*(?:inch|\"|\-inch)", e_low)
        if prod_inch:
            return "TRUE" if abs(float(prod_inch.group(1)) - target_inch) <= 0.5 else "FALSE"
        return "UNKNOWN"

    # 3. Direct substring match
    if r_low in e_low:
        return "TRUE"

    # 4. Token & Semantic Stem matching
    words = re.findall(r"[a-zA-Z0-9]+", r_low)
    meaningful_tokens = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    if not meaningful_tokens:
        return "UNKNOWN"

    matched_tokens = [t for t in meaningful_tokens if matches_token(t, e_low)]
    
    if len(meaningful_tokens) == 1:
        return "TRUE" if len(matched_tokens) == 1 else "UNKNOWN"
    
    # If >= 50% of core tokens match the evidence
    if len(matched_tokens) >= max(1, len(meaningful_tokens) * 0.5):
        return "TRUE"

    return "UNKNOWN"


def match_requirements_against_product(
    product: Dict[str, Any],
    requirements: Dict[str, Any],
    user_goal: str = "",
) -> Tuple[List[str], List[str], List[str], float]:
    """Matches user requirements against actual product evidence using 3-state evaluation.

    Returns:
        (matched_requirements, contradicted_requirements, unknown_requirements, feature_match_score)
    """
    specs = product.get("specs") or {}
    name = str(product.get("name") or "")
    snippet = str(product.get("snippet") or "")
    badge = str(product.get("badge") or "")
    source = str(product.get("source") or product.get("seller") or "")
    price = float(product.get("price") or product.get("effective_price") or 0)
    budget_max = float(requirements.get("budget_max") or 0)

    raw_matched = [str(x).strip().lower() for x in product.get("matched_requirements", []) if str(x).strip()]
    raw_missing = [str(x).strip().lower() for x in product.get("missing_requirements", []) if str(x).strip()]

    evidence_text = f" {name} {snippet} {badge} {source} " + " ".join(str(v) for v in specs.values()) + " " + " ".join(raw_matched)
    evidence_lower = evidence_text.lower()

    hard_constraints = _clean_and_dedup_requirements(requirements.get("hard_constraints", []))
    soft_preferences = _clean_and_dedup_requirements(requirements.get("soft_preferences", []))
    priority_order = _clean_and_dedup_requirements(requirements.get("priority_order", []))
    brand_pref = str(requirements.get("brand_preference") or "").strip().lower()

    all_reqs = _clean_and_dedup_requirements(hard_constraints + priority_order + soft_preferences)

    if not all_reqs and not brand_pref:
        return (list(product.get("matched_requirements", [])), [], [], 0.85)

    matched = []
    contradicted = []
    unknown = []
    hard_violations = 0

    # 1. Hard Constraints Evaluation
    for hc in hard_constraints:
        state = evaluate_requirement_3state(hc, evidence_lower, specs, price, budget_max)
        if state == "TRUE":
            matched.append(hc)
        elif state == "FALSE":
            contradicted.append(hc)
            hard_violations += 1
        else:
            unknown.append(hc)

    # 2. Soft Preferences & Priorities Evaluation
    for req in all_reqs:
        if req in hard_constraints:
            continue
        state = evaluate_requirement_3state(req, evidence_lower, specs, price, budget_max)
        if state == "TRUE":
            matched.append(req)
        elif state == "FALSE":
            contradicted.append(req)
        else:
            unknown.append(req)

    # 3. Brand Preference Evaluation
    brand_bonus = 0.0
    if brand_pref:
        if brand_pref in evidence_lower:
            brand_bonus = 0.10
            matched.append(f"Brand: {brand_pref.title()}")
        else:
            unknown.append(f"Brand: {brand_pref.title()}")

    # 4. Priority-Weighted Score Calculation
    total_weights = 0.0
    matched_weights = 0.0

    for i, req in enumerate(all_reqs):
        # Decreasing positional weight for earlier items in priority list
        weight = max(1.0, 3.0 - (i * 0.40))
        total_weights += weight
        if req in matched:
            matched_weights += weight

    raw_score = (matched_weights / total_weights) if total_weights > 0 else 0.85
    score = raw_score + brand_bonus

    # Apply strict hard constraint penalty
    if hard_violations > 0:
        score = 0.0 if any(hc in contradicted for hc in hard_constraints if "price" in hc.lower()) else (score * (0.25 ** hard_violations))

    return (matched, contradicted, unknown, round(min(max(score, 0.0), 1.0), 4))
