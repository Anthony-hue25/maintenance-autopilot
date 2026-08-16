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
    """Retrieve property context needed for a maintenance decision."""

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


@tool
def check_repair_authority(
    unit_id: str,
    quoted_cost: float,
) -> str:
    """Check quoted repair cost against unit-specific authority."""

    property_data = PROPERTIES.get(unit_id)

    if property_data is None:
        return "PROPERTY_NOT_FOUND"

    limit = property_data["authority_limit"]
    within = quoted_cost <= limit

    result = (
        "WITHIN_AUTHORITY"
        if within
        else "EXCEEDS_AUTHORITY"
    )

    return (
        f"Unit: {unit_id}\n"
        f"Authority limit: ${limit:.2f}\n"
        f"Quoted cost: ${quoted_cost:.2f}\n"
        f"Authority result: {result}\n"
        f"Within authority: {within}"
    )


def screen_identity(unit_id: str) -> dict:
    """
    Determine whether the reported unit has a known authority context.
    """

    known = unit_id in PROPERTIES

    return {
        "unit_known": known,
        "identity_problem": not known,
    }


def screen_safety(
    request: str,
    clarification: str = "",
) -> dict:
    text = f"{request} {clarification}".lower()

    hazards = []

    # Gas / CO including credible unsafe gas connection findings.
    gas_patterns = [
        r"\bsmell(?:ing)? gas\b",
        r"\bgas smell\b",
        r"\bstrong smell of gas\b",
        r"\bcarbon monoxide\b",
        r"\bco alarm\b",
        r"\bgas connection.*unsafe\b",
        r"\bunsafe gas connection\b",
        r"\bgas fitting.*unsafe\b",
        r"\bunsafe gas fitting\b",
        r"\bgas line.*unsafe\b",
    ]

    if any(re.search(pattern, text) for pattern in gas_patterns):
        hazards.append("GAS_OR_CO")

    # Electrical / fire.
    # Generic "smoke" is intentionally avoided so a chirping
    # smoke alarm does not become an emergency.
    fire_patterns = [
        r"\bsmoke coming\b",
        r"\bvisible smoke\b",
        r"\bthere(?:'s| is) smoke\b",
        r"\bsmoke from\b",
        r"\bstrong burning electrical smell\b",
        r"\bburning electrical\b",
        r"\belectrical burning smell\b",
        r"\bburning smell.*outlet\b",
        r"\bsparking\b",
        r"\bsparks\b",
        r"\bhanging by the wires\b",
        r"\bexposed wiring\b",
    ]

    if any(re.search(pattern, text) for pattern in fire_patterns):
        hazards.append("ELECTRICAL_OR_FIRE")

    # Water + electrical proximity.
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

    if (
        any(word in text for word in water_words)
        and any(word in text for word in electrical_words)
        and not explicit_no_electrical
    ):
        hazards.append("WATER_NEAR_ELECTRICAL")

    # Truly uncontrolled water.
    uncontrolled_patterns = [
        r"\bwater is pouring\b",
        r"\bwater pouring\b",
        r"\buncontrolled water\b",
        r"\bmajor flooding\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in uncontrolled_patterns
    ):
        hazards.append("UNCONTROLLED_WATER")

    # Explicit current security exposure.
    security_patterns = [
        r"\bdoor (?:won't|will not|cannot) lock\b",
        r"\bwindow (?:won't|will not|cannot) lock\b",
        r"\bcannot secure\b",
        r"\bcan't secure\b",
        r"\bunsecured\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in security_patterns
    ):
        hazards.append("SECURITY")

    # Structural / fall hazards.
    structural_patterns = [
        r"\brailing.*loose\b",
        r"\bloose.*railing\b",
        r"\bceiling collapse\b",
        r"\bceiling.*falling\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in structural_patterns
    ):
        hazards.append("STRUCTURAL_OR_FALL")

    return {
        "hazard_detected": bool(hazards),
        "hazards": hazards,
    }


def screen_information_state(
    request: str,
    clarification: str = "",
) -> dict:
    request_text = request.strip().lower()
    clarification_text = clarification.strip().lower()

    # Initial reports where the missing fact directly changes
    # the next decision.
    initial_ambiguity_phrases = [
        "i think there's a leak somewhere",
        "i think there is a leak somewhere",
        "can't see anything",
        "cannot see anything",
        "not sure where",
        "don't know where",
        "dont know where",
        "not sure where it's coming from",
        "not sure where its coming from",
        "i'm not sure where it's coming from",
        "im not sure where its coming from",
    ]

    needs_initial_clarification = (
        not clarification_text
        and any(
            phrase in request_text
            for phrase in initial_ambiguity_phrases
        )
    )

    if not clarification_text:
        return {
            "clarification_provided": False,
            "needs_initial_clarification": (
                needs_initial_clarification
            ),
            "insufficient_after_ask": False,
            "no_response_after_ask": False,
            "signals": (
                ["INITIAL_DECISION_AMBIGUITY"]
                if needs_initial_clarification
                else []
            ),
        }

    no_response_phrases = [
        "no response",
        "no reply",
        "tenant did not respond",
        "tenant didn't respond",
        "no response to clarification",
        "no response to:",
    ]

    if any(
        phrase in clarification_text
        for phrase in no_response_phrases
    ):
        return {
            "clarification_provided": True,
            "needs_initial_clarification": False,
            "insufficient_after_ask": False,
            "no_response_after_ask": True,
            "signals": ["NO_RESPONSE"],
        }

    weak_phrases = [
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
        for phrase in weak_phrases
        if phrase in clarification_text
    ]

    return {
        "clarification_provided": True,
        "needs_initial_clarification": False,
        "insufficient_after_ask": bool(weak_hits),
        "no_response_after_ask": False,
        "signals": weak_hits,
    }

def screen_scope_change(
    request: str,
    clarification: str = "",
) -> dict:
    """
    Detect hidden building-material damage, consequential property
    damage, and spreading mold/moisture scope.

    Uses regex for phrases where descriptive words may occur
    between the material and the condition, e.g.
    'wall under the sink feels soft'.
    """

    text = f"{request} {clarification}".lower()

    signals = []

    # -------------------------------------------------
    # HIDDEN MATERIAL DAMAGE
    # Examples:
    # "soft wall"
    # "wall feels soft"
    # "wall under the sink feels soft"
    # "ceiling near the vent feels soft"
    # -------------------------------------------------

    hidden_damage_patterns = [
        r"\bsoft\s+wall\b",
        r"\bwall\b.{0,60}\b(?:feels?|is)\s+soft\b",
        r"\bsoft\s+ceiling\b",
        r"\bceiling\b.{0,60}\b(?:feels?|is)\s+soft\b",
        r"\bsoft\s+floor\b",
        r"\bfloor\b.{0,60}\b(?:feels?|is)\s+soft\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in hidden_damage_patterns
    ):
        signals.append("HIDDEN_MATERIAL_DAMAGE")

    # -------------------------------------------------
    # CONSEQUENTIAL PROPERTY DAMAGE
    # -------------------------------------------------

    property_damage_patterns = [
        r"\bfloor\b.{0,50}\bswelling\b",
        r"\blaminate\b.{0,50}\bswelling\b",
        r"\bcabinet\b.{0,50}\bswelling\b",
        r"\bsoaked\b.{0,30}\bcabinet\b",
        r"\bsoaked\b.{0,30}\bfloor\b",
        r"\bwater damage\b.{0,30}\bfloor\b",
        r"\bwater damage\b.{0,30}\bcabinet\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in property_damage_patterns
    ):
        signals.append("PROPERTY_DAMAGE")

    # -------------------------------------------------
    # MOISTURE EVIDENCE
    # -------------------------------------------------

    moisture_patterns = [
        r"\bmusty smell\b",
        r"\bmusty odor\b",
        r"\bdark staining\b",
        r"\bdark stain\b",
        r"\bbrown staining\b",
        r"\bbrown stain\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in moisture_patterns
    ):
        signals.append("MOISTURE_EVIDENCE")

    # -------------------------------------------------
    # MOLD
    # -------------------------------------------------

    mold_present = bool(
        re.search(r"\bmou?ld\b", text)
    )

    mold_spreading = (
        mold_present
        and "spreading" in text
    )

    if mold_present:
        signals.append("MOLD")

    if mold_spreading:
        signals.append("SPREADING_MOLD")

    hidden_damage_detected = (
        "HIDDEN_MATERIAL_DAMAGE" in signals
    )

    property_damage_detected = (
        "PROPERTY_DAMAGE" in signals
    )

    scope_change_detected = (
        hidden_damage_detected
        or mold_spreading
    )

    return {
        "scope_change_detected": scope_change_detected,
        "property_damage_detected": property_damage_detected,
        "mold_scope_detected": mold_spreading,
        "signals": signals,
    }


def screen_replacement_upgrade(
    request: str,
    clarification: str = "",
) -> dict:
    text = f"{request} {clarification}".lower()

    patterns = [
        "replacement recommended",
        "replacement is recommended",
        "recommend replacement",
        "full replacement",
        "replace the unit",
        "replace it with",
        "upgrade",
        "smart thermostat",
        "smart one",
        "prefer the better one",
    ]

    hits = [
        phrase
        for phrase in patterns
        if phrase in text
    ]

    return {
        "replacement_or_upgrade": bool(hits),
        "signals": hits,
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


def screen_repeat_failure(
    request: str,
    clarification: str = "",
    history: str = "",
) -> dict:
    """
    Detect recurrence of the SAME or materially-related failure mode.

    Deliberately avoids treating an unrelated problem on the same
    fixture as a repeat failure.
    """

    request_text = request.lower()
    clarification_text = clarification.lower()
    history_text = history.lower()

    combined = (
        f"{request_text} "
        f"{clarification_text} "
        f"{history_text}"
    )

    signals = []

    # Strong explicit recurrence language.
    explicit_again = "again" in request_text

    # Drain / clog family.
    drain_terms = [
        "clog",
        "clogged",
        "backed up",
        "slow drain",
        "sink's a bit slow",
        "sink is a bit slow",
    ]

    current_drain_fault = any(
        term in request_text
        for term in drain_terms
    )

    historical_drain_fault = any(
        term in clarification_text
        or term in history_text
        or f"history: {term}" in request_text
        for term in drain_terms
    )

    # If current text explicitly says "again" with a drain/clog
    # fault, that is sufficient recurrence evidence.
    drain_repeat = (
        current_drain_fault
        and (
            explicit_again
            or historical_drain_fault
        )
    )

    # Special protection against false recurrence:
    # clog history followed by running/fill fault is NOT repeat.
    running_toilet_terms = [
        "running constantly",
        "running toilet",
        "won't stop filling",
        "wont stop filling",
        "keeps filling",
    ]

    current_running_fault = any(
        term in request_text
        for term in running_toilet_terms
    )

    if current_running_fault:
        drain_repeat = False

    if drain_repeat:
        signals.append("RELATED_DRAIN_OR_CLOG_FAILURE")

    return {
        "repeat_failure_detected": bool(signals),
        "signals": signals,
    }
def screen_authority(
    unit_id: str,
    request: str,
    clarification: str = "",
) -> dict:
    """
    Deterministically identify quoted repair costs and compare them
    with the unit-specific autonomous authority limit.

    A known authority breach forces ESCALATE. A within-authority
    result does not force ACT because other overrides may still apply.
    """

    property_data = PROPERTIES.get(unit_id)

    if property_data is None:
        return {
            "authority_known": False,
            "authority_limit": None,
            "quoted_costs": [],
            "authority_exceeded": False,
        }

    text = f"{request} {clarification}"

    # Capture values such as:
    # $201
    # $285.00
    # ~$1,200
    money_matches = re.findall(
        r"[$]\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
    )

    quoted_costs = []

    for match in money_matches:
        try:
            quoted_costs.append(
                float(match.replace(",", ""))
            )
        except ValueError:
            pass

    authority_limit = float(
        property_data["authority_limit"]
    )

    authority_exceeded = any(
        cost > authority_limit
        for cost in quoted_costs
    )

    return {
        "authority_known": True,
        "authority_limit": authority_limit,
        "quoted_costs": quoted_costs,
        "authority_exceeded": authority_exceeded,
    }