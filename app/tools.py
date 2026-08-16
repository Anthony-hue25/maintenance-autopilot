from strands import tool
import re


PROPERTIES = {
    "U1": {
        "authority_limit": 200,
        "equipment": "Split AC (3yr), gas water heater",
        "history": "AC serviced 6 months ago; no recent related faults",
        "preferred_vendor": "Comfort Air HVAC",
        "access": "Lockbox",
    },
    "U2": {
        "authority_limit": 200,
        "equipment": "Electric range, dishwasher",
        "history": "Kitchen faucet replaced 2 months ago",
        "preferred_vendor": "Rapid Plumbing",
        "access": "Tenant present evenings",
    },
    "U3": {
        "authority_limit": 150,
        "equipment": "Window AC, electric water heater",
        "history": "Same toilet clog reported twice in 6 weeks",
        "preferred_vendor": "HomeFix General",
        "access": "Lockbox",
    },
    "U4": {
        "authority_limit": 200,
        "equipment": "Central AC with condensate pump",
        "history": "AC condensate pump replaced 2 years ago",
        "preferred_vendor": "Comfort Air HVAC",
        "access": "Key with manager",
    },
    "U5": {
        "authority_limit": 300,
        "equipment": "Gas range, gas water heater",
        "history": "No recent issues",
        "preferred_vendor": "BrightSpark Electrical",
        "access": "Tenant coordinates",
    },
    "U6": {
        "authority_limit": 200,
        "equipment": "Electric range, garbage disposal",
        "history": "Disposal jammed once previously and was cleared",
        "preferred_vendor": "Rapid Plumbing",
        "access": "Lockbox",
    },
    "U7": {
        "authority_limit": 250,
        "equipment": "Split AC, washing machine",
        "history": "Ceiling stain noted at last inspection",
        "preferred_vendor": "HomeFix General",
        "access": "Tenant present",
    },
    "U8": {
        "authority_limit": 200,
        "equipment": "Window AC, electric range",
        "history": "Front door lock previously noted as sticky",
        "preferred_vendor": "BrightSpark / Locksmith",
        "access": "Lockbox",
    },
}


@tool
def get_property_details(unit_id: str) -> str:
    """
    Retrieve property context needed for an authorized maintenance decision.

    Args:
        unit_id: Rental unit identifier such as U1 or U4.
    """

    property_data = PROPERTIES.get(unit_id)

    if property_data is None:
        return "PROPERTY_NOT_FOUND"

    return (
        f"Unit: {unit_id}\n"
        f"Owner autonomous authority limit: ${property_data['authority_limit']}\n"
        f"Key equipment: {property_data['equipment']}\n"
        f"Relevant maintenance history: {property_data['history']}\n"
        f"Preferred vendor: {property_data['preferred_vendor']}\n"
        f"Access: {property_data['access']}"
    )


def screen_safety(request: str, clarification: str = "") -> dict:
    text = f"{request} {clarification}".lower()

    hazards = []

    gas_patterns = [
        r"\bsmell(?:ing)? gas\b",
        r"\bgas smell\b",
        r"\bstrong smell of gas\b",
        r"\bcarbon monoxide\b",
        r"\bco alarm\b",
    ]

    if any(re.search(pattern, text) for pattern in gas_patterns):
        hazards.append("GAS_OR_CO")

    electrical_fire_patterns = [
        r"\bsmoke\b",
        r"\bburning electrical\b",
        r"\belectrical smell\b",
        r"\bburning smell.*outlet\b",
        r"\bsparking\b",
        r"\bsparks\b",
        r"\bhanging by the wires\b",
        r"\bexposed wiring\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in electrical_fire_patterns
    ):
        hazards.append("ELECTRICAL_OR_FIRE")

    water_words = [
        "water",
        "dripping",
        "puddle",
        "leak",
        "leaking",
        "flood",
        "flooding",
    ]

    electrical_words = [
        "outlet",
        "socket",
        "electrical",
        "wire",
        "wiring",
        "breaker",
    ]

    explicit_no_electrical = any(
        phrase in text
        for phrase in [
            "no outlet near",
            "no outlets near",
            "not near an outlet",
            "away from the outlet",
            "no electrical nearby",
        ]
    )

    has_water = any(word in text for word in water_words)
    has_electrical = any(word in text for word in electrical_words)

    if has_water and has_electrical and not explicit_no_electrical:
        hazards.append("WATER_NEAR_ELECTRICAL")

    uncontrolled_water_patterns = [
        r"\bwater is pouring\b",
        r"\bwater pouring\b",
        r"\buncontrolled water\b",
        r"\bmajor flooding\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in uncontrolled_water_patterns
    ):
        hazards.append("UNCONTROLLED_WATER")

    security_patterns = [
        r"\bdoor (?:won't|will not|cannot) lock\b",
        r"\bwindow (?:won't|will not|cannot) lock\b",
        r"\bcannot secure\b",
        r"\bcan't secure\b",
        r"\bunsecured\b",
    ]

    if any(re.search(pattern, text) for pattern in security_patterns):
        hazards.append("SECURITY")

    structural_patterns = [
        r"\brailing.*loose\b",
        r"\bloose.*railing\b",
        r"\bceiling collapse\b",
        r"\bceiling.*falling\b",
    ]

    if any(re.search(pattern, text) for pattern in structural_patterns):
        hazards.append("STRUCTURAL_OR_FALL")

    return {
        "hazard_detected": len(hazards) > 0,
        "hazards": hazards,
    }


def screen_information_state(request: str, clarification: str = "") -> dict:
    clarification_text = clarification.strip().lower()

    if not clarification_text:
        return {
            "clarification_provided": False,
            "insufficient_after_ask": False,
            "no_response_after_ask": False,
            "signals": [],
        }

    no_response_phrases = [
        "no response",
        "no reply",
        "tenant did not respond",
        "tenant didn't respond",
        "no response to clarification",
        "no response to:",
    ]

    no_response = any(
        phrase in clarification_text
        for phrase in no_response_phrases
    )

    if no_response:
        return {
            "clarification_provided": True,
            "insufficient_after_ask": False,
            "no_response_after_ask": True,
            "signals": ["NO_RESPONSE"],
        }

    weak_clarification_phrases = [
        "i don't know",
        "not sure",
        "can't see",
        "cannot see",
        "maybe",
        "it was maybe",
        "not really sure",
    ]

    weak_hits = [
        phrase
        for phrase in weak_clarification_phrases
        if phrase in clarification_text
    ]

    return {
        "clarification_provided": True,
        "insufficient_after_ask": len(weak_hits) > 0,
        "no_response_after_ask": False,
        "signals": weak_hits,
    }


def screen_scope_change(request: str, clarification: str = "") -> dict:
    text = f"{request} {clarification}".lower()

    scope_signals = []

    patterns = {
        "SOFT_BUILDING_MATERIAL": [
            "soft wall",
            "wall feels soft",
            "soft ceiling",
            "ceiling feels soft",
            "soft floor",
        ],
        "STAINING_OR_DISCOLORATION": [
            "dark staining",
            "dark stain",
            "brown stain",
            "staining",
        ],
        "SPREADING_DAMP": [
            "damp patch",
            "spreading damp",
            "getting bigger",
            "seems bigger",
        ],
        "VISIBLE_PROPERTY_DAMAGE": [
            "floor is swelling",
            "floor swelling",
            "laminate floor is swelling",
            "cabinet swelling",
        ],
        "MUSTY_MOISTURE_SIGNAL": [
            "musty smell",
            "musty odor",
        ],
    }

    for signal_name, phrases in patterns.items():
        if any(phrase in text for phrase in phrases):
            scope_signals.append(signal_name)

    direct_damage = any(
        signal in scope_signals
        for signal in [
            "SOFT_BUILDING_MATERIAL",
            "VISIBLE_PROPERTY_DAMAGE",
        ]
    )

    multiple_moisture_signals = len(scope_signals) >= 2

    scope_change_detected = (
        direct_damage or multiple_moisture_signals
    )

    return {
        "scope_change_detected": scope_change_detected,
        "signals": scope_signals,
    }


def screen_security_information(
    request: str,
    clarification: str = "",
) -> dict:
    request_text = request.lower()
    clarification_text = clarification.lower().strip()

    security_terms = [
        "door lock",
        "door won't lock",
        "door wont lock",
        "lock is being weird",
        "lock being weird",
        "window won't lock",
        "window wont lock",
        "window doesn't latch",
        "window doesnt latch",
        "window won't latch",
        "window wont latch",
        "lock is sticky",
        "sticky lock",
    ]

    security_issue = any(
        term in request_text
        for term in security_terms
    )

    if not security_issue:
        return {
            "security_issue": False,
            "needs_clarification": False,
            "safety_silence": False,
            "security_known": False,
        }

    no_response_after_ask = any(
        phrase in clarification_text
        for phrase in [
            "no response",
            "no reply",
            "tenant did not respond",
            "tenant didn't respond",
        ]
    )

    secure_status_known = any(
        phrase in request_text
        for phrase in [
            "door still locks",
            "still locks",
            "still secure",
            "can still lock",
            "cannot secure",
            "can't secure",
        ]
    )

    external_access_known = any(
        phrase in request_text
        for phrase in [
            "ground floor",
            "facing the street",
            "accessible from outside",
            "balcony",
            "fire escape",
        ]
    )

    if no_response_after_ask:
        return {
            "security_issue": True,
            "needs_clarification": False,
            "safety_silence": True,
            "security_known": False,
        }

    if secure_status_known or external_access_known:
        return {
            "security_issue": True,
            "needs_clarification": False,
            "safety_silence": False,
            "security_known": True,
        }

    return {
        "security_issue": True,
        "needs_clarification": True,
        "safety_silence": False,
        "security_known": False,
    }


def screen_resolution_state(
    request: str,
    clarification: str = "",
) -> dict:
    text = f"{request} {clarification}".lower()

    resolved_signals = [
        "no active source",
        "no active water source",
        "it's fine now",
        "its fine now",
        "started working again",
        "stopped after",
        "already resolved",
        "never mind",
        "mopped it",
    ]

    outstanding_signals = [
        "still leaking",
        "still broken",
        "still not working",
        "still dripping",
        "still won't",
        "still wont",
        "getting worse",
        "keeps happening",
    ]

    resolved = any(
        phrase in text
        for phrase in resolved_signals
    )

    outstanding = any(
        phrase in text
        for phrase in outstanding_signals
    )

    return {
        "resolved_signal": resolved,
        "outstanding_signal": outstanding,
        "close_candidate": resolved and not outstanding,
    }