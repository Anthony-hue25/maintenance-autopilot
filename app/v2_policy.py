import re
from dataclasses import dataclass
from typing import Literal, Optional

from app.tools import PROPERTIES
from app.v2_hazard import HazardAssessment
from app.v2_case import CaseAssessment


Outcome = Literal[
    "ACT",
    "ESCALATE",
    "AWAITING",
    "CLOSE",
    "ASK",
    "ACT+ESCALATE",
]


@dataclass
class WorkflowFacts:
    UnitKnown: bool
    AuthorityLimit: Optional[float]
    QuotedCosts: list[float]
    ExplicitNoResponseAfterAsk: bool
    PrimaryEntranceUnsecured: bool


@dataclass
class PolicyDecision:
    Outcome: Outcome
    Rule: str
    Reason: str
    FailSafeType: str = "NONE"
    ProtectiveActionRequired: bool = False


CRITICAL_HAZARDS = {
    "GAS_HAZARD",
    "CO_HAZARD",
    "ACTIVE_FIRE_OR_SMOKE",
    "ELECTRICAL_HAZARD",
    "WATER_ELECTRICAL_CONTACT",
    "UNCONTROLLED_WATER",
    "SEWAGE_HAZARD",
    "STRUCTURAL_FALL_RISK",
}


def _contains_any(
    text: str,
    phrases: list[str],
) -> bool:
    return any(
        phrase in text
        for phrase in phrases
    )


def build_workflow_facts(
    unit: str,
    request: str,
    clarification: str,
) -> WorkflowFacts:

    property_data = PROPERTIES.get(
        unit
    )

    if property_data:
        known = True
        authority = float(
            property_data["authority_limit"]
        )
    else:
        known = False
        authority = None

    # =========================================================
    # ORIGINAL TEXT
    #
    # Deterministic workflow facts must always be derived from
    # the original tenant report / clarification rather than
    # decomposed or model-generated paraphrases.
    # =========================================================

    text = f"{request} {clarification}"

    lower = (
        text
        .lower()
        .strip()
    )

    # =========================================================
    # QUOTED COSTS
    # =========================================================

    matches = re.findall(
        r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
    )

    costs = []

    for value in matches:
        try:
            costs.append(
                float(
                    value.replace(
                        ",",
                        "",
                    )
                )
            )

        except ValueError:
            pass

    # =========================================================
    # EXPLICIT NO RESPONSE
    # =========================================================

    no_response = _contains_any(
        lower,
        [
            "no response",
            "no reply",
            "did not respond",
            "didn't respond",
            "no answer",
        ],
    )

    # =========================================================
    # PRIMARY ENTRANCE UNSECURED
    #
    # This fact is deliberately narrow.
    #
    # It requires:
    #
    # 1. a PRIMARY dwelling entrance
    # AND
    # 2. explicit evidence that the entrance cannot currently
    #    be secured.
    #
    # Examples that qualify:
    #
    # "Front door won't latch and I can't lock it."
    #
    # "Main entrance door cannot be secured."
    #
    # Examples that DO NOT qualify:
    #
    # "Front door lock is being weird."
    #
    # because whether it can still be secured is unknown.
    #
    # "Ground floor window won't lock."
    #
    # because this is not the primary dwelling entrance.
    #
    # "Back door handle is floppy but still locks."
    #
    # because it remains securable.
    # =========================================================

    primary_entrance = _contains_any(
        lower,
        [
            "front door",
            "main door",
            "main entrance",
            "entrance door",
            "entry door",
            "primary entrance",
            "primary door",
        ],
    )

    confirmed_cannot_secure = _contains_any(
        lower,
        [
            "can't lock it",
            "cannot lock it",
            "can't lock",
            "cannot lock",
            "won't lock",
            "will not lock",
            "doesn't lock",
            "does not lock",
            "not locking",
            "can't secure",
            "cannot secure",
            "won't secure",
            "will not secure",
            "cannot be secured",
            "can't be secured",
            "won't latch",
            "will not latch",
            "not latching",
            "doesn't latch",
            "does not latch",
            "won't pull shut",
            "will not pull shut",
            "won't close properly",
            "will not close properly",
        ],
    )

    # Explicit evidence that the door IS still securable should
    # defeat the new fact.
    explicitly_still_secure = _contains_any(
        lower,
        [
            "still locks",
            "still lock",
            "door still locks",
            "still locks with the key",
            "can still lock",
            "can lock it",
            "still secure",
            "still secured",
            "remains secure",
            "remains securable",
        ],
    )

    primary_entrance_unsecured = (
        primary_entrance
        and confirmed_cannot_secure
        and not explicitly_still_secure
    )

    return WorkflowFacts(
        UnitKnown=known,
        AuthorityLimit=authority,
        QuotedCosts=costs,
        ExplicitNoResponseAfterAsk=no_response,
        PrimaryEntranceUnsecured=(
            primary_entrance_unsecured
        ),
    )


def apply_policy(
    hazard: HazardAssessment,
    case: CaseAssessment,
    facts: WorkflowFacts,
) -> PolicyDecision:

    hazards = set(
        hazard.HazardConcepts
    )

    conditions = set(
        case.ConditionConcepts
    )

    critical = hazards.intersection(
        CRITICAL_HAZARDS
    )

    # =========================================================
    # P00H — UNMAPPED HAZARD
    # =========================================================

    if (
        hazard.UnmappedHazard
        or "UNMAPPED_HAZARD" in hazards
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P00H_UNMAPPED_HAZARD",
            Reason=(
                "Unmapped potential safety hazard requires "
                "protective escalation."
            ),
            FailSafeType="PROTECTIVE",
            ProtectiveActionRequired=True,
        )

    # =========================================================
    # P01 / P02 — UNKNOWN PROPERTY
    # =========================================================

    if not facts.UnitKnown:

        if critical:
            return PolicyDecision(
                Outcome="ACT+ESCALATE",
                Rule="P01_UNKNOWN_UNIT_CRITICAL",
                Reason=(
                    "Critical mitigation cannot wait for "
                    "property identification."
                ),
                ProtectiveActionRequired=True,
            )

        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P02_UNKNOWN_UNIT",
            Reason=(
                "Property authority context is unavailable."
            ),
        )

    # =========================================================
    # P03 — ACTIVE CRITICAL HAZARD
    # =========================================================

    if critical:
        return PolicyDecision(
            Outcome="ACT+ESCALATE",
            Rule="P03_CRITICAL_HAZARD",
            Reason=(
                "Recognized active critical hazard requires "
                "protective action and escalation."
            ),
            ProtectiveActionRequired=True,
        )

    # =========================================================
    # P03S — CONFIRMED SECURITY EXPOSURE
    #
    # A confirmed security exposure always warrants immediate
    # protective action.
    #
    # A confirmed UNSECURED PRIMARY DWELLING ENTRANCE additionally
    # warrants owner notification/escalation.
    #
    # This preserves:
    #
    # accessible unsecured window
    # -> ACT
    #
    # while distinguishing:
    #
    # front/main entrance cannot latch or lock
    # -> ACT+ESCALATE
    # =========================================================

    if "SECURITY_EXPOSURE" in hazards:

        if facts.PrimaryEntranceUnsecured:
            return PolicyDecision(
                Outcome="ACT+ESCALATE",
                Rule=(
                    "P03S_PRIMARY_ENTRANCE_SECURITY_EXPOSURE"
                ),
                Reason=(
                    "The primary dwelling entrance cannot be "
                    "secured; take protective action and notify "
                    "the owner."
                ),
                ProtectiveActionRequired=True,
            )

        return PolicyDecision(
            Outcome="ACT",
            Rule="P03S_SECURITY_EXPOSURE",
            Reason=(
                "Confirmed security exposure requires "
                "prompt protective action."
            ),
            ProtectiveActionRequired=True,
        )

    # =========================================================
    # P04 — AUTHORITY BREACH
    # =========================================================

    if (
        facts.AuthorityLimit is not None
        and any(
            cost > facts.AuthorityLimit
            for cost in facts.QuotedCosts
        )
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P04_AUTHORITY_EXCEEDED",
            Reason=(
                "Known quoted cost exceeds autonomous "
                "repair authority."
            ),
        )

    # =========================================================
    # P05 / P05A — UNRESOLVED SECURITY STATUS
    # =========================================================

    if (
        "SECURITY_STATUS_UNRESOLVED"
        in conditions
    ):

        if facts.ExplicitNoResponseAfterAsk:
            return PolicyDecision(
                Outcome="ACT",
                Rule="P05_SECURITY_SILENCE",
                Reason=(
                    "Security status remains unresolved after "
                    "tenant silence; minimum protective action "
                    "is required."
                ),
                ProtectiveActionRequired=True,
            )

        return PolicyDecision(
            Outcome="ASK",
            Rule="P05A_SECURITY_CLARIFICATION",
            Reason=(
                "Security status requires one focused "
                "clarification."
            ),
        )

    # =========================================================
    # P06 — NON-SAFETY NO RESPONSE
    # =========================================================

    if facts.ExplicitNoResponseAfterAsk:
        return PolicyDecision(
            Outcome="AWAITING",
            Rule="P06_NONSAFETY_SILENCE",
            Reason=(
                "Clarification was requested but no response "
                "was received."
            ),
        )

    # =========================================================
    # P07 — NEEDS CLARIFICATION
    # =========================================================

    if (
        case.InformationState
        == "NEEDS_CLARIFICATION"
    ):
        return PolicyDecision(
            Outcome="ASK",
            Rule="P07_NEEDS_CLARIFICATION",
            Reason=(
                "A decision-changing fact is still missing."
            ),
        )

    # =========================================================
    # P08 — INSUFFICIENT AFTER ASK
    # =========================================================

    if (
        case.InformationState
        == "INSUFFICIENT_AFTER_ASK"
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P08_INSUFFICIENT_AFTER_ASK",
            Reason=(
                "The permitted clarification round did not "
                "establish sufficient decision-relevant facts."
            ),
        )

    # =========================================================
    # P00C — UNMAPPED CONDITION
    # =========================================================

    if (
        case.UnmappedCondition
        or "UNMAPPED_CONDITION" in conditions
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P00C_UNMAPPED_CONDITION",
            Reason=(
                "Maintenance condition cannot be "
                "autonomously classified."
            ),
            FailSafeType="JUDGMENT",
            ProtectiveActionRequired=False,
        )

    # =========================================================
    # P09 — REPEAT FAILURE
    # =========================================================

    if "REPEAT_FAILURE" in conditions:
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P09_REPEAT_FAILURE",
            Reason=(
                "The same or materially related failure mode "
                "has recurred."
            ),
        )

    # =========================================================
    # P10 — REPLACEMENT / UPGRADE
    # =========================================================

    if (
        "REPLACEMENT_OR_UPGRADE"
        in conditions
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P10_REPLACEMENT_UPGRADE",
            Reason=(
                "Replacement or upgrade requires owner "
                "judgment."
            ),
        )

    # =========================================================
    # P11 — CONSEQUENTIAL PROPERTY DAMAGE
    # =========================================================

    if "PROPERTY_DAMAGE" in conditions:
        return PolicyDecision(
            Outcome="ACT+ESCALATE",
            Rule="P11_PROPERTY_DAMAGE",
            Reason=(
                "Proceed with source maintenance while "
                "escalating consequential property damage."
            ),
        )

    # =========================================================
    # P12 — CONFIRMED SPREADING MOLD
    # =========================================================

    if "MOLD_SPREAD" in conditions:
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P12_MOLD_SPREAD",
            Reason=(
                "Confirmed spreading mold requires owner "
                "or expanded-scope review."
            ),
        )

    # =========================================================
    # P12A — PROGRESSIVE MOISTURE / BIOLOGICAL-TYPE SCOPE
    # =========================================================

    if (
        "PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE"
        in conditions
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P12A_PROGRESSIVE_SCOPE",
            Reason=(
                "Progressive abnormal moisture or biological-type "
                "surface evidence exceeds routine autonomous scope."
            ),
        )

    # =========================================================
    # P13 — MATERIAL MOISTURE DAMAGE
    # =========================================================

    if (
        "MATERIAL_MOISTURE_DAMAGE"
        in conditions
    ):
        return PolicyDecision(
            Outcome="ESCALATE",
            Rule="P13_MATERIAL_MOISTURE_DAMAGE",
            Reason=(
                "Established moisture-related material damage "
                "requires owner or expanded-scope review."
            ),
        )

    # =========================================================
    # P14 — RESOLVED
    # =========================================================

    if (
        "RESOLVED_NO_OUTSTANDING_NEED"
        in conditions
    ):
        return PolicyDecision(
            Outcome="CLOSE",
            Rule="P14_RESOLVED",
            Reason=(
                "No outstanding maintenance need remains."
            ),
        )

    # =========================================================
    # P15 — ROUTINE AUTHORIZED ACTION
    # =========================================================

    return PolicyDecision(
        Outcome="ACT",
        Rule="P15_ROUTINE_AUTHORIZED_ACTION",
        Reason=(
            "An unresolved maintenance need remains and no "
            "deterministic escalation rule applies."
        ),
    )