from copy import deepcopy

from app.v2_hazard import HazardAssessment


def _normalize_text(
    request: str,
    clarification: str = "",
) -> str:
    return f"{request} {clarification}".lower().strip()


def _contains_any(
    text: str,
    phrases: list[str],
) -> bool:
    return any(
        phrase in text
        for phrase in phrases
    )


def validate_hazards(
    hazard: HazardAssessment,
    request: str,
    clarification: str = "",
) -> HazardAssessment:
    """
    Maintenance Autopilot V2.5
    Narrow deterministic hazard contrast validator.

    Purpose:
    - preserve the V2.4 semantic hazard assessor
    - correct only known ambiguous contrast classes
    - avoid broad re-interpretation of hazards
    - retain a conservative safety posture

    Current contrast classes:
    1. Water/electrical relationship validation
    2. Explicit negation of electrical proximity
    3. Partial electrical outage without dangerous manifestation
    4. Breaker/trip operation under ordinary load
    5. Unknown-source pooling without established uncontrolled flow
    6. Minor hinged fixture faults that are not structural fall risks
    """

    result = deepcopy(hazard)
    hazards = set(result.HazardConcepts)
    text = _normalize_text(request=request, clarification=clarification)

    smoke_or_fire = _contains_any(
        text,
        [
            "smoke",
            "smoking",
            "burning",
            "burnt smell",
            "burning smell",
            "on fire",
            "flame",
            "flames",
        ],
    )

    sparking = _contains_any(
        text,
        [
            "spark",
            "sparking",
            "sparks",
            "arcing",
            "electrical arc",
        ],
    )

    exposed_electrical = _contains_any(
        text,
        [
            "exposed wire",
            "exposed wiring",
            "bare wire",
            "bare wiring",
            "live wire",
            "live wiring",
        ],
    )

    abnormal_heat = _contains_any(
        text,
        [
            "hot socket",
            "hot outlet",
            "hot switch",
            "overheating",
            "overheated",
            "electrical burning smell",
        ],
    )

    explicit_no_electrical_proximity = _contains_any(
        text,
        [
            "no outlet nearby",
            "no outlets nearby",
            "no socket nearby",
            "no sockets nearby",
            "no electrical nearby",
            "no electrics nearby",
            "no electrical equipment nearby",
            "no electrical equipment near",
            "no electrical source nearby",
            "no electrical source near",
            "away from electrical",
            "away from electrics",
            "not near any outlet",
            "not near any outlets",
            "not near a socket",
            "not near any socket",
            "not near electrical",
            "not close to electrical",
            "nothing electrical nearby",
        ],
    )

    explicit_water_electrical_relation = _contains_any(
        text,
        [
            "water at the socket",
            "water near the socket",
            "water by the socket",
            "water toward the socket",
            "water towards the socket",
            "water reaching the socket",
            "water at the outlet",
            "water near the outlet",
            "water by the outlet",
            "water toward the outlet",
            "water towards the outlet",
            "water reaching the outlet",
            "water in the socket",
            "water in the outlet",
            "water in the electrical panel",
            "water at the electrical panel",
            "water through the electrical panel",
            "water from the electrical panel",
            "water through the light",
            "water from the light",
            "water through the ceiling light",
            "water from the ceiling light",
            "water through the light fitting",
            "water from the light fitting",
            "water through the light fixture",
            "water from the light fixture",
            "drip from the ceiling light",
            "dripping from the ceiling light",
            "leak from the ceiling light",
            "leaking from the ceiling light",
            "drip through the ceiling light",
            "dripping through the ceiling light",
            "leak through the ceiling light",
            "leaking through the ceiling light",
            "wet electrical panel",
            "wet socket",
            "wet outlet",
            "wet light fitting",
            "wet light fixture",
        ],
    )

    water_terms_present = _contains_any(
        text,
        [
            "water",
            "leak",
            "leaking",
            "drip",
            "dripping",
            "wet",
            "flood",
            "flooding",
        ],
    )

    protective_trip_present = _contains_any(
        text,
        [
            "breaker tripped",
            "breaker trip",
            "tripped the breaker",
            "trip switch went",
            "trip switch flipped",
            "tripped the circuit",
        ],
    )

    water_trip_relationship = water_terms_present and protective_trip_present

    positive_water_electrical_relation = (
        explicit_water_electrical_relation or water_trip_relationship
    )

    if (
        explicit_no_electrical_proximity
        and not explicit_water_electrical_relation
        and not water_trip_relationship
    ):
        positive_water_electrical_relation = False

    if positive_water_electrical_relation:
        hazards.add("WATER_ELECTRICAL_CONTACT")

    if (
        explicit_no_electrical_proximity
        and not positive_water_electrical_relation
    ):
        hazards.discard("WATER_ELECTRICAL_CONTACT")

    dangerous_electrical_manifestation = (
        smoke_or_fire
        or sparking
        or exposed_electrical
        or abnormal_heat
        or positive_water_electrical_relation
    )

    partial_outage = _contains_any(
        text,
        [
            "half the sockets",
            "half of the sockets",
            "half the outlets",
            "half of the outlets",
            "half the power",
            "half of the power",
            "some sockets are dead",
            "some sockets have gone dead",
            "some outlets are dead",
            "some outlets have gone dead",
            "part of the power",
            "part of the flat has no power",
            "part of the apartment has no power",
            "sockets have gone dead",
            "sockets are dead",
            "outlets have gone dead",
            "outlets are dead",
        ],
    )

    if partial_outage and not dangerous_electrical_manifestation:
        hazards.discard("ELECTRICAL_HAZARD")

    trip_language = _contains_any(
        text,
        [
            "trip switch",
            "breaker",
            "circuit breaker",
            "keeps tripping",
            "keeps flipping",
            "flipping off",
            "trips when",
            "trip when",
        ],
    )

    load_relationship = _contains_any(
        text,
        [
            "when we run",
            "when i run",
            "when using",
            "when both",
            "together",
            "at the same time",
            "under load",
            "when the kettle",
            "when the microwave",
        ],
    )

    trip_under_load = trip_language and load_relationship

    if trip_under_load and not dangerous_electrical_manifestation:
        hazards.discard("ELECTRICAL_HAZARD")

    unknown_source = _contains_any(
        text,
        [
            "can't work out where",
            "cannot work out where",
            "can't tell where",
            "cannot tell where",
            "don't know where",
            "do not know where",
            "not sure where",
            "not sure where it's coming from",
            "not sure where it is coming from",
            "unknown source",
        ],
    )

    pooling = _contains_any(
        text,
        [
            "pooling",
            "puddle",
            "water on the floor",
            "water on floor",
        ],
    )

    strong_ongoing_flow = _contains_any(
        text,
        [
            "pouring",
            "gushing",
            "actively flooding",
            "still flooding",
            "continuing to flood",
            "water everywhere",
            "won't stop flowing",
            "will not stop flowing",
            "cannot stop the water",
            "can't stop the water",
            "water keeps coming",
            "water is still coming",
        ],
    )

    unknown_source_pooling = unknown_source and pooling

    if unknown_source_pooling and not strong_ongoing_flow:
        hazards.discard("UNCONTROLLED_WATER")

    # =========================================================
    # HV05 — MINOR HINGED FIXTURE IS NOT AUTOMATICALLY A
    # STRUCTURAL FALL RISK
    # =========================================================

    minor_hinged_fixture = _contains_any(
        text,
        [
            "cupboard door",
            "cabinet door",
            "wardrobe door",
            "closet door",
        ],
    )

    hinge_fault = _contains_any(
        text,
        [
            "off its hinge",
            "off the hinge",
            "off a hinge",
            "come off its hinge",
            "came off its hinge",
            "come off the hinge",
            "came off the hinge",
            "hinge has come off",
            "hinge came off",
            "broken hinge",
            "hinge is broken",
            "hinge broke",
        ],
    )

    actual_fall_danger = _contains_any(
        text,
        [
            "about to fall on",
            "could fall on",
            "might fall on",
            "falling on someone",
            "could hit someone",
            "might hit someone",
            "hanging overhead",
            "danger of falling",
            "blocking the stairs",
            "blocking the staircase",
            "collapse",
            "collapsing",
        ],
    )

    if minor_hinged_fixture and hinge_fault and not actual_fall_danger:
        hazards.discard("STRUCTURAL_FALL_RISK")

    real_hazards = {
        value
        for value in hazards
        if value != "NO_ACTIVE_HAZARD"
    }

    if real_hazards:
        hazards.discard("NO_ACTIVE_HAZARD")

    if not hazards:
        hazards.add("NO_ACTIVE_HAZARD")

    hazard_order = [
        "GAS_HAZARD",
        "CO_HAZARD",
        "ACTIVE_FIRE_OR_SMOKE",
        "ELECTRICAL_HAZARD",
        "WATER_ELECTRICAL_CONTACT",
        "UNCONTROLLED_WATER",
        "SEWAGE_HAZARD",
        "STRUCTURAL_FALL_RISK",
        "SECURITY_EXPOSURE",
        "UNMAPPED_HAZARD",
        "NO_ACTIVE_HAZARD",
    ]

    result.HazardConcepts = [
        concept
        for concept in hazard_order
        if concept in hazards
    ]

    return result