"""Category-aware specification extraction and evidence-grounded requirement matching engine.
Extracts verified specifications and attributes from marketplace listing text, snippets,
and badges without hardcoding product-specific values.
"""
import re
from typing import Any, Dict, List, Tuple


def extract_product_specs(text: str, snippet: str = "", category: str = "", badge: str = "") -> Dict[str, Any]:
    """Category-aware specification extraction from listing text and snippet."""
    specs = {}
    full_text = f" {text} {snippet} {badge} "
    cat = (category or "").lower()

    # 1. RAM / Memory (e.g. 16GB RAM, 8 GB DDR5, 32GB)
    ram_match = re.search(r"\b(\d{1,3}\s*GB)\s*(?:RAM|DDR\d*|LPDDR\d*|Unified\s*Memory)?\b", full_text, re.I)
    if ram_match:
        specs["ram"] = ram_match.group(1).upper().replace(" ", "")

    # 2. Storage / SSD / ROM (e.g. 512GB SSD, 1TB SSD, 256GB Storage)
    ssd_match = re.search(r"\b(\d{1,3}\s*(?:GB|TB))\s*(?:SSD|NVMe|PCIe|ROM|Storage|UFS\s*[\d.]*)\b", full_text, re.I)
    if ssd_match:
        specs["storage"] = ssd_match.group(1).upper().replace(" ", "") + " SSD"
    else:
        all_gb = re.findall(r"\b(\d{2,4}\s*(?:GB|TB))\b", full_text, re.I)
        if len(all_gb) >= 2 and (specs.get("ram") is None or all_gb[1].upper().replace(" ", "") != specs.get("ram")):
            specs["storage"] = all_gb[1].upper().replace(" ", "") + " Storage"

    # 3. Processors / CPU / Chipset
    cpu_match = re.search(
        r"\b((?:Intel\s+(?:Core\s+)?)?i[3579]-?\d{4,5}\w*|Intel\s+Core\s+i[3579]|AMD\s+Ryzen\s+[3579][\w\s-]*|Apple\s+M[1234][\w\s]*|Snapdragon\s+[\w\s+]+|Dimensity\s+\d+[\w+]*|MediaTek\s+[\w\s+]+|Exynos\s+\d+|Google\s+Tensor\s+G\d*)\b",
        full_text,
        re.I,
    )
    if cpu_match:
        specs["processor"] = cpu_match.group(1).strip()

    # 4. Dedicated / Integrated GPU
    gpu_match = re.search(r"\b(RTX\s*\d{4}[\w\s]*|GTX\s*\d{4}[\w\s]*|Radeon\s*[\w\s]+|Iris\s*X[ee]|GeForce\s*[\w\s]+)\b", full_text, re.I)
    if gpu_match:
        specs["gpu"] = gpu_match.group(1).strip()

    # 5. Refresh Rate & Display (Monitors / Laptops / Phones)
    hz_match = re.search(r"\b(\d{2,3}\s*Hz)\b", full_text, re.I)
    if hz_match:
        specs["refresh_rate"] = hz_match.group(1).replace(" ", "").upper()

    res_match = re.search(r"\b(1440p|1080p|2K|4K|QHD|WQHD|FHD|UHD|Retina|AMOLED|OLED|IPS)\b", full_text, re.I)
    if res_match:
        specs["resolution"] = res_match.group(1).upper()

    size_match = re.search(r"\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|\"|cm|\-inch)\b", full_text, re.I)
    if size_match:
        specs["screen_size"] = f"{size_match.group(1)} inch"

    # 6. Audio / Headphones: ANC / Battery / Drivers
    if re.search(r"\b(?:active\s+noise\s+cancel\w*|anc|enc|noise\s+isolat\w*)\b", full_text, re.I):
        specs["noise_cancellation"] = "Active Noise Cancellation (ANC)"

    bat_hrs = re.search(r"\b(\d{1,3}\s*(?:Hours?|Hrs?|H))\s*(?:Playtime|Battery|Playback)?\b", full_text, re.I)
    if bat_hrs:
        specs["battery_life"] = bat_hrs.group(1).strip()

    driver_match = re.search(r"\b(\d{1,2}\s*mm)\s*(?:Drivers?|dynamic\s*drivers?)?\b", full_text, re.I)
    if driver_match:
        specs["driver_size"] = driver_match.group(1).replace(" ", "")

    # 7. Smartphone Camera / Battery / Fast Charging
    cam_match = re.search(r"\b(\d{2,3}\s*MP)\s*(?:Camera|OIS|Triple|Quad|Dual)?\b", full_text, re.I)
    if cam_match:
        specs["camera"] = cam_match.group(1).replace(" ", "") + (" OIS" if "ois" in full_text.lower() else " Camera")

    charge_match = re.search(r"\b(\d{2,3}\s*W)\s*(?:Fast\s+Charging|Charging|FlashCharge|SuperVOOC)?\b", full_text, re.I)
    if charge_match:
        specs["fast_charging"] = charge_match.group(1).replace(" ", "") + " Fast Charging"

    bat_mah = re.search(r"\b(\d{4,5}\s*mAh)\b", full_text, re.I)
    if bat_mah:
        specs["battery_capacity"] = bat_mah.group(1).replace(" ", "")

    # 8. Monitor Ergonomics & Stand
    if re.search(r"\b(Height\s*Adjustable|Adjustable\s*Stand|Pivot|Swivel|Tilt)\b", full_text, re.I):
        specs["stand"] = "Height Adjustable Stand"

    # 9. Footwear & Shoes
    cushion = re.search(r"\b(Air\s*Zoom|Gel|Boost|Nitro|Cloud|Floatride|EVA|React|FlyteFoam|Fresh\s*Foam)\b", full_text, re.I)
    if cushion:
        specs["cushioning"] = cushion.group(1).title() + " Cushioning"
    if re.search(r"\b(Road\s*Running|Trail\s*Running|Walking|Racing|Training)\b", full_text, re.I):
        specs["usage"] = re.search(r"\b(Road\s*Running|Trail\s*Running|Walking|Racing|Training)\b", full_text, re.I).group(1).title()
    if re.search(r"\b(Wide\s*(?:Fit|Toe)?|Extra\s*Wide)\b", full_text, re.I):
        specs["fit"] = "Wide Fit"

    return specs


def _clean_and_dedup_requirements(req_list: List[str]) -> List[str]:
    """Cleans and deduplicates requirement phrases semantically."""
    cleaned = []
    for r in req_list:
        r_str = str(r).strip()
        if not r_str or r_str.lower().startswith("price"):
            continue
        r_low = r_str.lower()
        if any(r_low == c.lower() or (r_low in c.lower() and len(r_low) < len(c.lower())) for c in cleaned):
            continue
        cleaned.append(r_str)
    return cleaned


def match_requirements_against_product(
    product: Dict[str, Any],
    requirements: Dict[str, Any],
    user_goal: str = "",
) -> Tuple[List[str], List[str], float]:
    """Matches extracted user requirements against verified product evidence.

    Returns:
        (matched_requirements, missing_requirements, feature_match_score)
    """
    specs = product.get("specs") or {}
    name = str(product.get("name") or "")
    snippet = str(product.get("snippet") or "")
    badge = str(product.get("badge") or "")
    source = str(product.get("source") or product.get("seller") or "")
    
    raw_matched = [str(x).strip().lower() for x in product.get("matched_requirements", []) if str(x).strip()]
    raw_missing = [str(x).strip().lower() for x in product.get("missing_requirements", []) if str(x).strip()]

    # Combined textual evidence
    evidence_text = f" {name} {snippet} {badge} {source} " + " ".join(str(v) for v in specs.values()) + " " + " ".join(raw_matched)
    evidence_lower = evidence_text.lower()

    hard_constraints = _clean_and_dedup_requirements(requirements.get("hard_constraints", []))
    soft_preferences = _clean_and_dedup_requirements(requirements.get("soft_preferences", []))
    priority_order = _clean_and_dedup_requirements(requirements.get("priority_order", []))
    brand_pref = str(requirements.get("brand_preference") or "").strip().lower()

    all_reqs = _clean_and_dedup_requirements(hard_constraints + priority_order + soft_preferences)

    if not all_reqs and not brand_pref:
        return (list(product.get("matched_requirements", [])), list(product.get("missing_requirements", [])), 0.85)

    matched = []
    missing = []
    hard_violations = 0

    def _is_matched(req: str) -> bool:
        r_low = req.lower()

        # Check pre-labeled raw_matched / raw_missing
        if any(r_low == m or r_low in m or m in r_low for m in raw_matched):
            return True
        if any(r_low == m or r_low in m or m in r_low for m in raw_missing):
            return False

        if r_low in evidence_lower:
            return True

        # Numerical spec matching
        digits = re.findall(r"\d+", r_low)
        if digits:
            num = digits[0]
            if "gb" in r_low and "ram" in r_low:
                spec_ram = specs.get("ram", "")
                return bool(spec_ram and num in spec_ram)
            if "gb" in r_low or "ssd" in r_low or "tb" in r_low:
                spec_storage = specs.get("storage", "")
                return bool(spec_storage and num in spec_storage)
            if "hz" in r_low:
                spec_hz = specs.get("refresh_rate", "")
                return bool(spec_hz and num in spec_hz)
            if "inch" in r_low or '"' in r_low:
                spec_size = specs.get("screen_size", "")
                return bool(spec_size and num in spec_size)
            if "mp" in r_low:
                spec_cam = specs.get("camera", "")
                return bool(spec_cam and num in spec_cam)
            if "w" in r_low and "charging" in r_low:
                spec_charge = specs.get("fast_charging", "")
                return bool(spec_charge and num in spec_charge)

        # Keyword concept matching using word boundaries
        if re.search(r"\b(?:anc|enc|noise\s*cancel\w*)\b", r_low):
            return bool("noise_cancellation" in specs or re.search(r"\b(?:anc|enc|noise\s*cancel\w*)\b", evidence_lower))
        if re.search(r"\b(?:cushion\w*|comfort\w*)\b", r_low):
            return bool("cushioning" in specs or re.search(r"\b(?:cushion\w*|zoom|gel|boost|nitro|comfort|soft)\b", evidence_lower))
        if re.search(r"\b(?:processor|cpu|performance|fast|compute|coding|work)\b", r_low):
            return bool("processor" in specs or any(w in evidence_lower for w in ("intel", "core", "ryzen", "m2", "m3", "snapdragon", "dimensity", "octa-core", "processor", "cpu", "performance")))
        if re.search(r"\b(?:adjustable|stand|ergonomic|pivot|swivel|height)\b", r_low):
            return bool("stand" in specs or re.search(r"\b(?:adjustable|height|pivot|swivel)\b", evidence_lower))
        if re.search(r"\b(?:battery|battery\s*life|backup)\b", r_low):
            return bool("battery_life" in specs or "battery_capacity" in specs or "battery" in evidence_lower)
        if re.search(r"\b(?:camera|photography|low-light|photo)\b", r_low):
            return bool("camera" in specs or re.search(r"\b(?:camera|mp|ois|lens|photo)\b", evidence_lower))
        if re.search(r"\b(?:road|road\s*run\w*)\b", r_low):
            return bool(specs.get("usage") == "Road Running" or "road" in evidence_lower)
        if re.search(r"\b(?:wide|wide\s*fit)\b", r_low):
            return bool("fit" in specs or "wide" in evidence_lower)

        return False

    for hc in hard_constraints:
        if _is_matched(hc):
            matched.append(hc)
        else:
            missing.append(hc)
            hard_violations += 1

    for req in all_reqs:
        if req in hard_constraints:
            continue
        if _is_matched(req):
            matched.append(req)
        else:
            missing.append(req)

    brand_bonus = 0.0
    if brand_pref:
        if brand_pref in evidence_lower:
            brand_bonus = 0.10
            matched.append(f"Brand: {brand_pref.title()}")
        else:
            missing.append(f"Brand: {brand_pref.title()}")

    total_weights = 0.0
    matched_weights = 0.0

    for i, req in enumerate(all_reqs):
        weight = max(1.0, 2.5 - (i * 0.35))
        total_weights += weight
        if req in matched:
            matched_weights += weight

    raw_score = (matched_weights / total_weights) if total_weights > 0 else 0.85
    score = raw_score + brand_bonus

    if hard_violations > 0:
        score = score * (0.35 ** hard_violations)

    return (matched, missing, round(min(max(score, 0.0), 1.0), 4))
