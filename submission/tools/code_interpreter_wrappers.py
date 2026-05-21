import re
from typing import Dict, Any, Tuple

def validate_positioning(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates positioning and ICP docs. Check for target audience, problem, solution, value proposition.
    """
    results = {
        "checks": {},
        "score": 0,
        "feedback": []
    }
    
    # Required keys in positioning artifact
    required_keys = ["target_audience", "core_problem", "value_proposition", "primary_benefit"]
    for key in required_keys:
        val = data.get(key, "")
        if val and isinstance(val, str) and len(val.strip()) > 10:
            results["checks"][f"has_{key}"] = True
            results["score"] += 25
        else:
            results["checks"][f"has_{key}"] = False
            results["feedback"].append(f"Attribute '{key}' is too short or missing. It should contain detailed description.")
            
    success = results["score"] >= 75
    return success, results

def validate_landing_page(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates landing page structure. Expecting a title, a CTA, features, and optionally a mock HTTP status check.
    """
    results = {
        "checks": {},
        "score": 0,
        "feedback": []
    }
    
    # Check landing page structure
    hero_headline = data.get("hero_headline", "")
    if len(hero_headline.strip()) >= 15:
        results["checks"]["hero_headline_valid"] = True
        results["score"] += 30
    else:
        results["checks"]["hero_headline_valid"] = False
        results["feedback"].append("Hero headline must be strong and at least 15 characters.")

    cta = data.get("cta_text", "")
    if len(cta.strip()) >= 3:
        results["checks"]["cta_valid"] = True
        results["score"] += 20
    else:
        results["checks"]["cta_valid"] = False
        results["feedback"].append("landing page needs a clear, active Call To Action (CTA).")

    # Mocking a deployed URL check
    url = data.get("url", "")
    if url:
        # Simple regex for URL formatting
        url_regex = re.compile(
            r'^(?:http)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
            r'localhost|' #localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if re.match(url_regex, url):
            results["checks"]["url_format_valid"] = True
            results["score"] += 30
            # Simulating deterministic HTTP status success for demo
            results["checks"]["http_status_200"] = True
            results["score"] += 20
        else:
            results["checks"]["url_format_valid"] = False
            results["checks"]["http_status_200"] = False
            results["feedback"].append("Deployed Landing page URL format is invalid.")
    else:
        results["checks"]["url_format_valid"] = False
        results["checks"]["http_status_200"] = False
        results["feedback"].append("No landing page deploy URL was specified.")

    success = results["score"] >= 70
    return success, results

def validate_marketing_email(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates email subject line and body copy. Check copy length and CTA parameters.
    """
    results = {
        "checks": {},
        "score": 0,
        "feedback": []
    }
    
    subject = data.get("subject", "")
    if len(subject.strip()) >= 10:
        results["checks"]["subject_length_valid"] = True
        results["score"] += 30
    else:
        results["checks"]["subject_length_valid"] = False
        results["feedback"].append("Subject line is too short. It should grab the customer's attention.")

    body = data.get("body", "")
    if len(body.strip()) >= 100:
        results["checks"]["body_length_valid"] = True
        results["score"] += 40
    else:
        results["checks"]["body_length_valid"] = False
        results["feedback"].append("Body copy is too brief. You need a narrative arc and detailed value pitch.")

    # CTA presence check within the email body
    if "[CTA]" in body or "[link]" in body or "http" in body or "Click here" in body or "Sign up" in body:
        results["checks"]["body_cta_included"] = True
        results["score"] += 30
    else:
        results["checks"]["body_cta_included"] = False
        results["feedback"].append("Email body copy is missing an explicit clickable action or link placeholder (e.g. '[CTA]').")

    success = results["score"] >= 70
    return success, results
