from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class PricingInconsistency:
    key1: str
    key2: str
    inconsistency_type: str

# parses the price key to extract product, variant, and deductible information for easier comparison in the next steps.
def parse_price_key(key: str) -> Dict[str, str | int]:
    if key == "mtpl":
        return {"product": "mtpl", "variant": None, "deductible": None}
    
    VALID_VARIANTS = {"compact", "basic", "comfort", "premium"}
    
    for variant in VALID_VARIANTS:
        if variant in key:
            parts = key.split(variant)
            product = parts[0].rstrip("_")          # Remove trailing underscore 
            deductible = int(parts[1].lstrip("_"))  # Remove leading underscore 
            
            return {"product": product, "variant": variant, "deductible": deductible}
    
    return {"product": None, "variant": None, "deductible": None}


# This function aims to fill a violations map with all the inconsistencies found in the prices based on the business rules.
# each key in the violations map will have a list of all the violations it has with other keys, including the type of 
# violation, the key it violates with, and the neighbor price for reference.  
def validate_and_report(prices: Dict[str, int]) -> Tuple[bool, Dict[str, List[Dict]]]:
    
    violations_map = {}
    product_order = ["mtpl", "limited_casco", "casco"]
    variant_order = ["compact", "basic", "comfort", "premium"]
    deductible_order = [100, 200, 500]
    
    # Compare each price against every other price to find violations
    for key in prices.keys():
        parsed = parse_price_key(key)
        
        #sanity check for unrecognized keys
        if parsed["product"] is None or parsed["variant"] is None or parsed["deductible"] is None :
            print(f"Warning: Unrecognized price key format '{key}'. Skipping validation for this key.")
            continue
        
        price = prices[key]
        violations_map[key] = []
        
        for other_key in prices.keys():
            if key == other_key:
                continue
            
            other_parsed = parse_price_key(other_key)
            
            #sanity check for unrecognized keys
            if other_parsed["product"] is None:
                continue
            
            other_price = prices[other_key]
            
            #compare based on deductible for same variant, and product 
            if (parsed["product"] == other_parsed["product"] and
                parsed["variant"] == other_parsed["variant"] and
                parsed["deductible"] != other_parsed["deductible"]):
                
                deductible_idx = deductible_order.index(parsed["deductible"])
                other_deductible_idx = deductible_order.index(other_parsed["deductible"])
                
                # If current deductible is lower than the other, flag it as too low
                if deductible_idx < other_deductible_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "deductible_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
                # If current deductible is higher than the other, flag it as too high
                elif deductible_idx > other_deductible_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "deductible_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })

            #compare based on variant for same deductible, and product 
            elif (parsed["product"] == other_parsed["product"] and
                  parsed["deductible"] == other_parsed["deductible"] and
                  parsed["variant"] != other_parsed["variant"]):
                
                variant_idx = variant_order.index(parsed["variant"])
                other_variant_idx = variant_order.index(other_parsed["variant"])
                
                # If current variant is lower than the other, flag it as too low
                if variant_idx < other_variant_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "variant_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })
                
                # If current variant is higher than the other, flag it as too high
                elif variant_idx > other_variant_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "variant_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
            
            #compare based on product for same variant, and deductible
            elif (parsed["product"] != other_parsed["product"] and
                  parsed["variant"] == other_parsed["variant"] and
                  parsed["deductible"] == other_parsed["deductible"]):
                
                product_idx = product_order.index(parsed["product"])
                other_product_idx = product_order.index(other_parsed["product"])
                
                # If current product is lower than the other, flag it as too low
                if product_idx < other_product_idx and price >= other_price:
                    violations_map[key].append({
                        "type": "product_violation",
                        "violates_with": other_key,
                        "direction": "too_high",
                        "neighbor_price": other_price
                    })

                # If current product is higher than the other, flag it as too high
                elif product_idx > other_product_idx and price <= other_price:
                    violations_map[key].append({
                        "type": "product_violation",
                        "violates_with": other_key,
                        "direction": "too_low",
                        "neighbor_price": other_price
                    })
        
        # if no violations found for this key, remove it from the map to keep it clean
        if not violations_map[key]:
            del violations_map[key]
    
    valid = len(violations_map) == 0    # no violations means all prices are valid
    return valid, violations_map


def fix_and_explain(prices: Dict[str, int], violations_map: Dict[str, List[Dict]]) -> Tuple[Dict[str, int], str]:
    corrected_prices = prices.copy()
    explanation_lines = []

    product_order = ["mtpl", "limited_casco", "casco"]
    variant_order = ["compact", "basic", "comfort", "premium"]
    deductible_order = [100, 200, 500]
    
    deductible_adjustment_rate = 0.10
    variant_adjustment_rate = 0.07

    # First pass: fix product violations (neighbor-based)
    for key in violations_map.keys():
        parsed = parse_price_key(key)
        
        #sanity check for unrecognized keys
        if parsed["product"] is None or parsed["variant"] is None or parsed["deductible"] is None:
            continue
        
        violations = violations_map[key]
        product_violations = [v for v in violations if v["type"] == "product_violation"]
        
        if product_violations:
            total_adjustment = 0
            adjustment_details = []
            
            for violation in product_violations:
                neighbor_price = violation["neighbor_price"]
                current_price = corrected_prices[key]
                
                # For product violations, we will adjust the price to be 1€ above or below the neighbor price depending on 
                # the direction of the violation, to ensure we fix the inconsistency (Subject to change upon more business info).
                if violation["direction"] == "too_high":
                    adjustment = neighbor_price - current_price - 1
                    adjustment_details.append(f"product too high (vs {violation['violates_with']}): {adjustment}")
                else:
                    adjustment = neighbor_price - current_price + 1
                    adjustment_details.append(f"product too low (vs {violation['violates_with']}): +{adjustment}")
                
                total_adjustment += adjustment
            
            # Apply the total adjustment for this key, ensuring we don't go below 1€ and log the explanation
            if total_adjustment != 0:
                old_price = corrected_prices[key]
                new_price = max(1, old_price + total_adjustment)
                corrected_prices[key] = new_price
                
                explanation_lines.append(
                    f"{key}: {old_price} to {new_price} (adjustments: {', '.join(adjustment_details)})"
                )

    # Second pass: fix deductible violations using 10% per step rule
    for key in violations_map.keys():
        parsed = parse_price_key(key)
        
        #sanity check for unrecognized keys
        if parsed["product"] is None or parsed["variant"] is None or parsed["deductible"] is None:
            continue
        
        violations = violations_map[key]
        deductible_violations = [v for v in violations if v["type"] == "deductible_violation"]
        
        if deductible_violations:
            deductible_idx = deductible_order.index(parsed["deductible"])
            product = parsed["product"]
            variant = parsed["variant"]
            
            # Find the €100 deductible for this product/variant as base reference
            base_key = f"{product}_{variant}_{deductible_order[0]}" if product != "mtpl" else "mtpl"
            base_price = corrected_prices.get(base_key, corrected_prices[key])
            
            # Calculate expected price based on deductible percentage rule
            deductible_multiplier = 1 - (deductible_adjustment_rate * deductible_idx)
            expected_price = int(base_price * deductible_multiplier)
            
            # Apply the adjustment if needed and log the explanation
            old_price = corrected_prices[key]
            if old_price != expected_price:
                corrected_prices[key] = expected_price
                adjustment = expected_price - old_price
                discount_percent = deductible_adjustment_rate * 100 * deductible_idx
                explanation_lines.append(
                    f"{key}: {old_price} to {expected_price} (deductible adjustment: {adjustment}€, {discount_percent:.0f}% discount from €100)"
                )

    # Third pass: fix variant violations using 7% per step rule
    for key in violations_map.keys():
        parsed = parse_price_key(key)

        #sanity check for unrecognized keys, and also skip if variant or deductible is missing since 
        # we need both to apply the variant adjustment rule (MTPL case)
        if parsed["product"] is None or parsed["variant"] is None or parsed["deductible"] is None:
            continue
        
        violations = violations_map[key]
        variant_violations = [v for v in violations if v["type"] == "variant_violation"]
        
        if variant_violations:
            variant_idx = variant_order.index(parsed["variant"])
            product = parsed["product"]
            deductible = parsed["deductible"]
            
            # Find the compact/basic for this product/deductible as base reference
            base_key = f"{product}_compact_{deductible}" if product != "mtpl" else "mtpl"
            base_price = corrected_prices.get(base_key)
            
            # If compact price is not available, fallback to the basic to avoid missing reference
            if base_price is None:
                base_key = f"{product}_basic_{deductible}"
                base_price = corrected_prices.get(base_key, corrected_prices[key])
            
            # Calculate expected price based on variant percentage rule
            variant_multiplier = 1 + (variant_adjustment_rate * variant_idx)
            expected_price = int(base_price * variant_multiplier)
            
            # Apply the adjustment if needed and log the explanation
            old_price = corrected_prices[key]
            if old_price != expected_price:
                corrected_prices[key] = expected_price
                adjustment = expected_price - old_price
                increase_percent = variant_adjustment_rate * 100 * variant_idx
                explanation_lines.append(
                    f"{key}: {old_price} to {expected_price} (variant adjustment: {adjustment}€, {increase_percent:.0f}% increase from compact/basic)"
                )
    
    explanation = "\n".join(explanation_lines) if explanation_lines else "No adjustments needed."
    
    return corrected_prices, explanation


def main(prices: Dict[str, int]) -> Tuple[Dict[str, int], str, int]:
    current_prices = prices.copy()
    iteration = 0
    max_iterations = 10
    all_explanations = []
    
    # We will iterate through the validation and fixing process until we either have no violations or 
    # reach the maximum number of iterations to prevent infinite loops in case of complex inconsistencies.

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

# Utility functions to read input from a file and write output to a file, 
# handling the expected format and ensuring the results are saved for review.
def read_prices_from_file(filename: str) -> Dict[str, int]:
    prices = {}
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(",") :
                key, value = line.split(":")[0].strip("\""), line.split(":")[1][:-1]
            else: 
                key, value = line.split(":")[0].strip("\""), line.split(":")[1]
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
    input_prices = read_prices_from_file("input.txt")
    # input_prices = example_prices_to_correct
    
    corrected_prices, explanation, iterations = main(input_prices)
    write_output_to_file("output.txt", corrected_prices, explanation, iterations)
    
    # print("Corrected Prices:", corrected_prices)
    # print("Explanation:", explanation)    
