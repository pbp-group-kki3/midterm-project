# SpoonFeed's products grading algorithm

# score mapping details
NUTRI_POINTS = {"a": 100, "b": 75, "c": 50, "d": 25, "e": 0}
GREEN_POINTS = {"a-plus": 100, "a": 85, "b": 70, "c": 50, "d": 30, "e": 15, "f": 0}
NOVA_POINTS = {1: 100, 2: 75, 3: 40, 4: 0} # NOVA points in numbers because that's how the API sends them

# each parameter's weight details
WEIGHTS = {"nutrition": 0.50, "environment": 0.35, "processing": 0.15}

# spoonfeed grade scoring metric
def spoonfeed_grade(product):
    parts={} # each parameter grade we have, stored here

    nutri = (product.get("nutriscore_grade") or "").lower()
    if nutri in NUTRI_POINTS:
        parts["nutrition"] = NUTRI_POINTS[nutri]

    eco_score = product.get("ecoscore_score")
    eco_grade = (product.get("ecoscore_grade") or "").lower()
    if isinstance(eco_score, (int, float)):
        parts["environment"] = max(0, min(100, eco_score))
    elif eco_grade in GREEN_POINTS:                           
        parts["environment"] = GREEN_POINTS[eco_grade]

    nova = product.get("nova_group")
    if nova in NOVA_POINTS:
        parts["processing"] = NOVA_POINTS[nova]

    # return unknown only when all three parameters are missing
    if not parts:
        return {"score":None, "grade":"?", "parts": {}}
    
    # total weighted average - also anticipating for missing values
    total_weight = sum(WEIGHTS[k] for k in parts)             # e.g. 0.50 + 0.35 + 0.15 = 1.0, or 0.85 if NOVA is missing
    score = sum(parts[k] * WEIGHTS[k] for k in parts) / total_weight   # keeps the result on the 0–100 scale

    # give grade 
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "E"

    return {"score": round(score, 1), "grade": grade, "parts": parts}

# helper function - to get the value easily
def grade_value(value, valid): # value - actual grade of product, valid - dict of real grades
    if isinstance(value, str): # is value a string = returns boolean
        value = value.lower()
    if value not in valid:
        return "?"
    return str(value).upper().replace("-PLUS","+") # if it has -PLUS, switch that with +