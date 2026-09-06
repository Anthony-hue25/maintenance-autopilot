from copy import deepcopy

from app.v2_case import CaseAssessment


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


def validate_case(
    case: CaseAssessment,
    request: str,
    clarification: str = "",
) -> CaseAssessment:
    """
    Maintenance Autopilot V2.5
    Narrow deterministic case contrast validator.

    Purpose:
    - preserve the semantic Case Assessor
    - correct known unstable information-state contrasts
    - recognize a narrow progressive-scope contrast
    - operate on the ORIGINAL full case after issue merging
    - never decide the final workflow outcome

    Current contrast classes:
    CV01 - Explicit no response after clarification
    CV02 - Preserve insufficient-after-ask
    CV03 - Unknown-source water pooling before clarification
    CV04 - Abnormal/discoloured tap water before clarification
    CV05 - Progressive abnormal moisture / biological-type scope

    This validator does NOT:
    - decide ACT / ASK / ESCALATE
    - diagnose mold
    - infer repeat failure
    - assess active safety hazards
    """

    result = deepcopy(
        case
    )

    text = _normalize_text(
        request=request,
        clarification=clarification,
    )

    clarification_text = (
        clarification
        .lower()
        .strip()
    )

    # =========================================================
    # CLARIFICATION STATE
    # =========================================================

    no_response_markers = [
        "no response",
        "no reply",
        "no answer",
        "did not respond",
        "didn't respond",
    ]

    explicit_no_response = _contains_any(
        clarification_text,
        no_response_markers,
    )

    clarification_present = bool(
        clarification_text
    )

    substantive_clarification = (
        clarification_present
        and not explicit_no_response
    )

    # =========================================================
    # CV01 — EXPLICIT NO RESPONSE
    #
    # Example:
    #
    # "Asked whether it is fully off or just hanging: no reply."
    #
    # ->
    # NO_RESPONSE_AFTER_ASK
    # =========================================================

    if explicit_no_response:
        result.InformationState = (
            "NO_RESPONSE_AFTER_ASK"
        )

        return result

    # =========================================================
    # CV02 — PRESERVE INSUFFICIENT AFTER ASK
    #
    # If a meaningful clarification round already happened and
    # the semantic assessor correctly recognized that the reply
    # remained materially inconclusive, do not turn the case
    # back into NEEDS_CLARIFICATION.
    # =========================================================

    if (
        substantive_clarification
        and result.InformationState
        == "INSUFFICIENT_AFTER_ASK"
    ):
        return result

    # =========================================================
    # CV03 — UNKNOWN-SOURCE WATER POOLING
    #
    # A visible puddle establishes that something is wrong.
    #
    # But if the source/current behavior is still unknown and
    # no clarification round has occurred, decision-changing
    # information is still missing.
    #
    # Example:
    #
    # "I can't work out where it's coming from but there's water
    # pooling on the bathroom floor."
    #
    # ->
    # NEEDS_CLARIFICATION
    #
    # This does NOT classify the water as an emergency.
    # =========================================================

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

    pooling_or_floor_water = _contains_any(
        text,
        [
            "water pooling",
            "pooling on",
            "pooling in",
            "puddle",
            "water on the floor",
            "water on floor",
        ],
    )

    if (
        unknown_source
        and pooling_or_floor_water
        and not clarification_present
    ):
        result.InformationState = (
            "NEEDS_CLARIFICATION"
        )

    # =========================================================
    # CV04 — ABNORMAL / DISCOLOURED TAP WATER
    #
    # Abnormal supply-water colour may require one focused
    # clarification before selecting the appropriate route.
    #
    # Example:
    #
    # "The tap water's coming out a funny brown colour this
    # morning."
    #
    # ->
    # NEEDS_CLARIFICATION
    # =========================================================

    abnormal_water_quality = _contains_any(
        text,
        [
            "brown water",
            "brown colour",
            "brown color",
            "brown coloured",
            "brown colored",
            "discoloured water",
            "discolored water",
            "funny brown colour",
            "funny brown color",
            "rusty water",
            "orange water",
            "yellow water",
        ],
    )

    tap_or_supply_context = _contains_any(
        text,
        [
            "tap water",
            "water's coming out",
            "water is coming out",
            "coming out the tap",
            "coming from the tap",
            "faucet water",
        ],
    )

    if (
        abnormal_water_quality
        and tap_or_supply_context
        and not clarification_present
    ):
        result.InformationState = (
            "NEEDS_CLARIFICATION"
        )

    # =========================================================
    # CV05 — PROGRESSIVE ABNORMAL MOISTURE / BIOLOGICAL SCOPE
    #
    # IMPORTANT:
    #
    # This does NOT diagnose mold.
    #
    # It recognizes a narrower scope boundary:
    #
    # abnormal spotting / growth-like surface evidence
    # +
    # explicit progression over time
    # +
    # building surface / material context
    #
    # ALL THREE dimensions must be present.
    #
    # Example:
    #
    # "There's black spotting spreading across the bathroom
    # ceiling, getting worse each week."
    #
    # ->
    # PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE
    #
    # Contrast:
    #
    # "There's a brown stain spreading on the ceiling."
    #
    # ->
    # MOISTURE_PRESENT only.
    #
    # Contrast:
    #
    # "There's a small dark spot on the ceiling."
    #
    # ->
    # Does not qualify because explicit progression is missing.
    # =========================================================

    abnormal_surface_evidence = _contains_any(
        text,
        [
            "black spotting",
            "dark spotting",
            "black spots",
            "dark spots",
            "growth-like",
            "growth like",
            "fuzzy patch",
            "fuzzy patches",
            "fuzzy area",
            "fuzzy areas",
            "mildew-like",
            "mildew like",
        ],
    )

    explicit_progression = _contains_any(
        text,
        [
            "spreading",
            "getting worse",
            "growing",
            "expanding",
            "increasing",
            "worsening",
            "worse each week",
            "worsening each week",
            "bigger each week",
            "larger each week",
            "getting bigger",
        ],
    )

    building_surface = _contains_any(
        text,
        [
            "ceiling",
            "wall",
            "walls",
            "drywall",
            "plaster",
            "plasterboard",
            "building finish",
            "building finishes",
        ],
    )

    progressive_scope = (
        abnormal_surface_evidence
        and explicit_progression
        and building_surface
    )

    if progressive_scope:

        if (
            "ACTIVE_MAINTENANCE_NEED"
            not in result.ConditionConcepts
        ):
            result.ConditionConcepts.append(
                "ACTIVE_MAINTENANCE_NEED"
            )

        if (
            "MOISTURE_PRESENT"
            not in result.ConditionConcepts
        ):
            result.ConditionConcepts.append(
                "MOISTURE_PRESENT"
            )

        if (
            "PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE"
            not in result.ConditionConcepts
        ):
            result.ConditionConcepts.append(
                "PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE"
            )

    return result