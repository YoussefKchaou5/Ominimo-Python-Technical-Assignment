from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class PricingInconsistency:
    key1: str
    key2: str
    inconsistency_type: str


def parse_price_key(key: str) -> Dict[str, str | int]:
    if key == "mtpl":
        return {"product": "mtpl", "variant": None, "deductible": None}
    
    VALID_VARIANTS = {"compact", "basic", "comfort", "premium"}
    
    for variant in VALID_VARIANTS:
        if variant in key:
            parts = key.split(variant)
            product = parts[0].rstrip("_")
            deductible = int(parts[1].lstrip("_"))
            
            return {"product": product, "variant": variant, "deductible": deductible}
    
    return {"product": None, "variant": None, "deductible": None}


def validate_and_report(prices: Dict[str, int]) -> Tuple[bool, Dict[str, List[Dict]]]:
    violations_map = {}
    
    product_order = ["mtpl", "limited_casco", "casco"]
    variant_order = ["compact", "basic", "comfort", "premium"]
    deductible_order = [100, 200, 500]
    
    for key in prices.keys():
        parsed = parse_price_key(key)
        
        if parsed["product"] is None:
            continue
        
        price = prices[key]
        violations_map[key] = []
        
        for other_key in prices.keys():
            if key == other_key:
                continue
            
            other_parsed = parse_price_key(other_key)
            
            if other_parsed["product"] is None:
                continue
            
            other_price = prices[other_key]
            
            if (parsed["product"] == other_parsed["product"] and
                parsed["variant"] == other_parsed["variant"] and
                parsed["deductible"] != other_parsed["deductible"]):
                
                deductible_idx = deductible_order.index(parsed["deductible"])
                other_deductible_idx = deductible_order.index(other_parsed["deductible"])
                
                if deductible_idx < other_deductible_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "deductible_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
                elif deductible_idx > other_deductible_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "deductible_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })
            
            elif (parsed["product"] == other_parsed["product"] and
                  parsed["deductible"] == other_parsed["deductible"] and
                  parsed["variant"] != other_parsed["variant"]):
                
                variant_idx = variant_order.index(parsed["variant"])
                other_variant_idx = variant_order.index(other_parsed["variant"])
                
                if variant_idx < other_variant_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "variant_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })
                elif variant_idx > other_variant_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "variant_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
            
            elif (parsed["product"] != other_parsed["product"] and
                  parsed["variant"] == other_parsed["variant"] and
                  parsed["deductible"] == other_parsed["deductible"]):
                
                product_idx = product_order.index(parsed["product"])
                other_product_idx = product_order.index(other_parsed["product"])
                
                if product_idx < other_product_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "product_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })
                elif product_idx > other_product_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "product_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
        
        if not violations_map[key]:
            del violations_map[key]
    
    valid = len(violations_map) == 0
    return valid, violations_map


def fix_and_explain(prices: Dict[str, int], violations_map: Dict[str, List[Dict]]) -> Tuple[Dict[str, int], str]:
    corrected_prices = prices.copy()
    explanation_lines = []
    
    for key in violations_map.keys():
        parsed = parse_price_key(key)
        violations = violations_map[key]
        
        total_adjustment = 0
        adjustment_details = []
        
        for violation in violations:
            neighbor_price = violation["neighbor_price"]
            current_price = corrected_prices[key]
            
            if violation["type"] == "deductible_violation":
                if violation["direction"] == "too_low":
                    adjustment = neighbor_price - current_price + 1
                    adjustment_details.append(f"deductible too low (vs {violation['violates_with']}): +{adjustment}")
                else:
                    adjustment = neighbor_price - current_price - 1
                    adjustment_details.append(f"deductible too high (vs {violation['violates_with']}): {adjustment}")
                
                total_adjustment += adjustment
            
            elif violation["type"] == "variant_violation":
                if violation["direction"] == "too_high":
                    adjustment = neighbor_price - current_price - 1
                    adjustment_details.append(f"variant too high (vs {violation['violates_with']}): {adjustment}")
                else:
                    adjustment = neighbor_price - current_price + 1
                    adjustment_details.append(f"variant too low (vs {violation['violates_with']}): +{adjustment}")
                
                total_adjustment += adjustment
            
            elif violation["type"] == "product_violation":
                if violation["direction"] == "too_high":
                    adjustment = neighbor_price - current_price - 1
                    adjustment_details.append(f"product too high (vs {violation['violates_with']}): {adjustment}")
                else:
                    adjustment = neighbor_price - current_price + 1
                    adjustment_details.append(f"product too low (vs {violation['violates_with']}): +{adjustment}")
                
                total_adjustment += adjustment
        
        if total_adjustment != 0:
            old_price = corrected_prices[key]
            new_price = max(1, old_price + total_adjustment)
            corrected_prices[key] = new_price
            
            explanation_lines.append(
                f"{key}: {old_price} to {new_price} (adjustments: {', '.join(adjustment_details)})"
            )
    
    explanation = "\n".join(explanation_lines) if explanation_lines else "No adjustments needed."
    
    return corrected_prices, explanation


def main(prices: Dict[str, int]) -> Tuple[Dict[str, int], str, int]:
    current_prices = prices.copy()
    iteration = 0
    max_iterations = 10
    all_explanations = []
    
    while iteration < max_iterations:
        valid, violations_map = validate_and_report(current_prices)
        
        if valid:
            all_explanations.append(f"\n=== ITERATION {iteration} ===\nAll prices are consistent with business rules.")
            final_explanation = "\n".join(all_explanations)
            return current_prices, final_explanation, iteration
        
        current_prices, fix_explanation = fix_and_explain(current_prices, violations_map)
        all_explanations.append(f"\n=== ITERATION {iteration} ===\n{fix_explanation}")
        iteration += 1
    
    all_explanations.append(f"\n=== ITERATION {iteration} ===\nMax iterations reached. Some inconsistencies may remain.")
    final_explanation = "\n".join(all_explanations)
    return current_prices, final_explanation, iteration


def read_prices_from_file(filename: str) -> Dict[str, int]:
    prices = {}
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(",") :
                key, value = line.split(":")[0].strip("\"") , line.split(":")[1][:-1]
            else: 
                key, value = line.split(":")[0].strip("\"") , line.split(":")[1]
            prices[key.strip()] = int(value.strip())
    return prices


def write_output_to_file(filename: str, corrected_prices: Dict[str, int], explanation: str, iterations: int) -> None:
    with open(filename, "w") as f:
        f.write("=== FINAL CORRECTED PRICES ===\n")
        for key in corrected_prices.keys():
            f.write(f"{key}: {corrected_prices[key]}\n")
        f.write(f"\n=== CORRECTION PROCESS ===\n{explanation}\n")
        f.write(f"\n=== TOTAL ITERATIONS ===\n{iterations}\n")


example_prices_to_correct = {
    "mtpl": 400,
    "limited_casco_compact_100": 820,
    "limited_casco_compact_200": 760,
    "limited_casco_compact_500": 650,
    "limited_casco_basic_100": 900,
    "limited_casco_basic_200": 780,
    "limited_casco_basic_500": 600,
    "limited_casco_comfort_100": 950,
    "limited_casco_comfort_200": 870,
    "limited_casco_comfort_500": 720,
    "limited_casco_premium_100": 1100,
    "limited_casco_premium_200": 980,
    "limited_casco_premium_500": 800,
    "casco_compact_100": 750,
    "casco_compact_200": 700,
    "casco_compact_500": 620,
    "casco_basic_100": 830,
    "casco_basic_200": 760,
    "casco_basic_500": 650,
    "casco_comfort_100": 900,
    "casco_comfort_200": 820,
    "casco_comfort_500": 720,
    "casco_premium_100": 1050,
    "casco_premium_200": 950,
    "casco_premium_500": 780
}


if __name__ == "__main__":
    input_prices = read_prices_from_file("Input.txt")
    corrected_prices, explanation, iterations = main(input_prices)
    write_output_to_file("output.txt", corrected_prices, explanation, iterations)
