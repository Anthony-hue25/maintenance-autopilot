"use strict";

/*
 * Maintenance Autopilot
 * Deterministic presentation layer.
 *
 * Structured interpretation -> human-readable explanation.
 *
 * No report-text parsing.
 * No LLM call.
 * No policy-rule branching.
 * No downstream execution claims.
 */

(function (root, factory) {
  const api = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  if (root) {
    root.MaintenancePresentation = api;
    root.MaintenanceAutopilotPresentation = api;
    root.Presentation = api;

    root.humanizeEnum = api.humanizeEnum;
    root.humanizeTrade = api.humanizeTrade;
    root.humanizeHazard = api.humanizeHazard;
    root.buildHumanInterpretation = api.buildHumanInterpretation;
    root.buildOutcomePresentation = api.buildOutcomePresentation;
    root.buildBoundaryExplanation = api.buildBoundaryExplanation;
  }
})(
  typeof globalThis !== "undefined" ? globalThis : this,
  function () {
    /*
     * Recognized residential maintenance/service categories.
     *
     * We intentionally do not accept every arbitrary enum as a trade.
     * That lets unexpected model vocabulary fail safely while still
     * covering a broad, realistic residential maintenance envelope.
     */
    const KNOWN_TRADES = new Set([
      "PLUMBING",
      "HVAC",
      "ELECTRICAL",
      "LOCKSMITH",
      "GAS",

      "APPLIANCE",
      "MOISTURE",
      "PEST",
      "PEST_CONTROL",
      "GENERAL",
      "STRUCTURAL",

      "ROOFING",
      "LANDSCAPING",
      "LAWN_CARE",
      "WELDING",
      "TILING",
      "CARPENTRY",
      "PAINTING",
      "MASONRY",
      "HANDYMAN",

      "GARAGE_DOOR",
      "DRAINAGE",
      "FENCING",
      "GLAZING",
      "POOL"
    ]);

    const CONDITION_PRESENTATIONS = {
      RESOLVED_NO_OUTSTANDING_NEED: {
        title: "Issue resolved",
        description:
          "Autopilot identified that no outstanding maintenance need remains."
      },

      COSMETIC_ONLY: {
        title: "Cosmetic maintenance issue",
        description:
          "Autopilot identified this as a cosmetic maintenance issue."
      },

      REPLACEMENT_OR_UPGRADE: {
        title: "Replacement or upgrade request",
        description:
          "Autopilot identified a replacement or upgrade request."
      },

      MOLD_SPREAD: {
        title: "Spreading mold issue",
        description:
          "Autopilot identified a spreading mold issue."
      },

      PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE: {
        title: "Progressive moisture issue",
        description:
          "Autopilot identified a progressive moisture-related issue."
      },

      MATERIAL_MOISTURE_DAMAGE: {
        title: "Moisture-related property damage",
        description:
          "Autopilot identified moisture-related property damage."
      },

      PROPERTY_DAMAGE: {
        title: "Property damage",
        description:
          "Autopilot identified property damage requiring maintenance review."
      },

      PEST_ACTIVITY: {
        title: "Pest issue",
        description:
          "Autopilot identified a pest-related maintenance issue."
      },

      MOISTURE_PRESENT: {
        title: "Moisture issue",
        description:
          "Autopilot identified a moisture-related maintenance issue."
      },

      SECURITY_STATUS_UNRESOLVED: {
        title: "Possible security-related issue",
        description:
          "Autopilot identified a possible security-related issue."
      }
    };

    const CONDITION_PRIORITY = {
      MOLD_SPREAD: 100,
      PROGRESSIVE_MOISTURE_OR_BIOLOGICAL_SCOPE: 95,
      MATERIAL_MOISTURE_DAMAGE: 90,
      PROPERTY_DAMAGE: 85,
      REPLACEMENT_OR_UPGRADE: 80,
      SECURITY_STATUS_UNRESOLVED: 75,
      PEST_ACTIVITY: 65,
      MOISTURE_PRESENT: 60,
      COSMETIC_ONLY: 50,
      RESOLVED_NO_OUTSTANDING_NEED: 40
    };

    const HAZARD_PRIORITY = {
      ACTIVE_FIRE_OR_SMOKE: 100,
      GAS_HAZARD: 95,
      WATER_ELECTRICAL_CONTACT: 90,
      ELECTRICAL_HAZARD: 85,
      STRUCTURAL_FALL_RISK: 80,
      FALL_RISK_HAZARD: 80,
      PRIMARY_ENTRANCE_SECURITY_EXPOSURE: 70,
      SECURITY_EXPOSURE: 60
    };

    function normalize(value) {
      return String(value == null ? "" : value)
        .trim()
        .toUpperCase();
    }

    function humanizeEnum(value) {
      return normalize(value)
        .toLowerCase()
        .replace(/_/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }

    function humanizeTrade(value) {
      const normalized = normalize(value);

      if (!normalized || normalized === "NONE") {
        return "";
      }

      if (normalized === "HVAC") {
        return "HVAC";
      }

      return humanizeEnum(normalized);
    }

    function humanizeHazard(value) {
      const normalized = normalize(value);

      if (
        !normalized ||
        normalized === "NONE" ||
        normalized === "NO_ACTIVE_HAZARD" ||
        normalized === "NO_HAZARD"
      ) {
        return "";
      }

      const known = {
        GAS_HAZARD: "gas hazard",
        ELECTRICAL_HAZARD: "electrical hazard",
        ACTIVE_FIRE_OR_SMOKE: "fire or smoke hazard",
        WATER_ELECTRICAL_CONTACT: "water/electrical hazard",
        STRUCTURAL_FALL_RISK: "structural fall risk",
        SECURITY_EXPOSURE: "security-related issue",
        PRIMARY_ENTRANCE_SECURITY_EXPOSURE:
          "primary entrance security issue"
      };

      if (known[normalized]) {
        return known[normalized];
      }

      let text = humanizeEnum(normalized);

      if (
        !text.endsWith("hazard") &&
        !text.endsWith("risk") &&
        !text.endsWith("issue") &&
        !text.endsWith("exposure")
      ) {
        text += " hazard";
      }

      return text;
    }

    function asList(value) {
      if (Array.isArray(value)) {
        return value
          .flatMap(asList)
          .map(normalize)
          .filter(Boolean);
      }

      if (value == null || value === "") {
        return [];
      }

      return String(value)
        .split("|")
        .map(normalize)
        .filter(Boolean);
    }

    function decisionOf(result) {
      return normalize(
        result?.decision ||
        result?.outcome ||
        result?.PolicyOutcome
      );
    }

    function urgencyOf(result) {
      return normalize(
        result?.technical?.urgency ||
        result?.Predicted_Urgency
      );
    }

    function informationOf(result) {
      return normalize(
        result?.technical?.information ||
        result?.InformationState
      );
    }

    function tradeOf(result) {
      return normalize(
        result?.technical?.trade ||
        result?.technical?.primary_trade ||
        result?.Predicted_PrimaryTrade
      );
    }

    function hazardsOf(result) {
      return asList(
        result?.technical?.hazard ??
        result?.technical?.hazards ??
        result?.HazardConcepts
      ).filter(
        value =>
          value !== "NO_ACTIVE_HAZARD" &&
          value !== "NO_HAZARD" &&
          value !== "NONE"
      );
    }

    function conditionsOf(result) {
      return asList(
        result?.technical?.condition ??
        result?.technical?.conditions ??
        result?.ConditionConcepts
      ).filter(
        value =>
          value !== "ACTIVE_MAINTENANCE_NEED" &&
          value !== "NONE"
      );
    }

    function highestPriority(values, priorities) {
      if (!values.length) {
        return "";
      }

      return [...values].sort(
        (a, b) =>
          (priorities[b] || 10) -
          (priorities[a] || 10)
      )[0];
    }

    function isMissingInformation(value) {
      return new Set([
        "INSUFFICIENT",
        "NEEDS_CLARIFICATION",
        "INSUFFICIENT_AFTER_ASK",
        "NO_RESPONSE_AFTER_ASK"
      ]).has(normalize(value));
    }

    /*
     * Missing-information wording should only be added to a meaningful
     * interpretation when the governed outcome still depends on it.
     *
     * ACT and ACT+ESCALATE have already established the next action, so
     * adding "more information is needed" would contradict the decision.
     */
    function missingInformationMatters(result) {
      if (!isMissingInformation(informationOf(result))) {
        return false;
      }

      return new Set([
        "ASK",
        "AWAITING",
        "ESCALATE"
      ]).has(decisionOf(result));
    }

    function hazardPresentation(result) {
      const hazards = hazardsOf(result);

      if (!hazards.length) {
        return null;
      }

      const hazard = highestPriority(
        hazards,
        HAZARD_PRIORITY
      );

      const text = humanizeHazard(hazard);
      const urgent = urgencyOf(result) === "EMERGENCY";

      if (
        hazard === "SECURITY_EXPOSURE" ||
        hazard === "PRIMARY_ENTRANCE_SECURITY_EXPOSURE"
      ) {
        return {
          title: "Possible security-related issue",
          description:
            "Autopilot identified a possible security-related issue."
        };
      }

      const suffix = urgent
        ? " requiring urgent attention"
        : "";

      return {
        title: `Potential ${text}${suffix}`,
        description:
          `Autopilot identified a potential ${text}${suffix}.`
      };
    }

    function conditionPresentation(result) {
      const conditions = conditionsOf(result);

      if (!conditions.length) {
        return null;
      }

      const condition = highestPriority(
        conditions,
        CONDITION_PRIORITY
      );

      if (CONDITION_PRESENTATIONS[condition]) {
        return CONDITION_PRESENTATIONS[condition];
      }

      /*
       * Safe generalized condition fallback.
       *
       * Example:
       * DOOR_ALIGNMENT_PROBLEM
       * -> Door alignment problem
       */
      const text = humanizeEnum(condition);

      if (!text) {
        return null;
      }

      return {
        title:
          text.charAt(0).toUpperCase() +
          text.slice(1),
        description:
          `Autopilot identified a ${text}.`
      };
    }

    function tradePresentation(result) {
      const trade = tradeOf(result);

      if (
        !trade ||
        trade === "NONE"
      ) {
        return null;
      }

      /*
       * Do not automatically treat arbitrary model vocabulary as a
       * recognized residential trade.
       *
       * This deliberately preserves the original safe fallback for
       * unexpected values such as SPECIALTY_GLAZING, while common
       * residential trades such as ROOFING and GARAGE_DOOR are recognized.
       */
      if (!KNOWN_TRADES.has(trade)) {
        return null;
      }

      const label = humanizeTrade(trade);

      if (!label) {
        return null;
      }

      /*
       * GENERAL is clearer as "General maintenance issue" than
       * "General issue".
       */
      if (trade === "GENERAL") {
        return {
          title: "General maintenance issue",
          description:
            "Autopilot identified this as a general maintenance issue."
        };
      }

      const display =
        label === "HVAC"
          ? "HVAC"
          : label.charAt(0).toUpperCase() +
            label.slice(1);

      let title = `${display} issue`;

      /*
       * Preserve the established routine wording used by the original
       * presentation contract and showcase regression tests.
       */
      if (
        urgencyOf(result) === "ROUTINE" &&
        new Set([
          "PLUMBING",
          "ELECTRICAL",
          "LOCKSMITH",
          "GAS"
        ]).has(trade)
      ) {
        title = `Routine ${label} issue`;
      }

      /*
       * Preserve the established ASK + locksmith presentation.
       * This is based only on structured decision/trade state.
       */
      if (
        decisionOf(result) === "ASK" &&
        trade === "LOCKSMITH"
      ) {
        return {
          title: "Possible security-related issue",
          description:
            "Autopilot identified a possible security-related issue."
        };
      }

      const article =
        label === "HVAC" ||
        /^[aeiou]/i.test(label)
          ? "an"
          : "a";

      return {
        title,
        description:
          `Autopilot identified this as ${article} ${label} maintenance issue.`
      };
    }

    function buildHumanInterpretation(result) {
      const presentation =
        hazardPresentation(result) ||
        conditionPresentation(result) ||
        tradePresentation(result);

      const missing = missingInformationMatters(result);

      /*
       * If no meaningful structured interpretation exists, the information
       * state itself is still useful context.
       *
       * This preserves the established regression behaviour for an
       * information-deficient case with no usable trade/hazard/condition.
       */
      if (!presentation) {
        if (isMissingInformation(informationOf(result))) {
          return {
            title: "Maintenance issue",
            description:
              "More information is needed before the appropriate next step can be determined."
          };
        }

        return {
          title: "Maintenance issue",
          description:
            "The structured response does not include additional interpretation details."
        };
      }

      const clauses = [presentation.description];

      if (missing) {
        clauses.push(
          "More information is needed before the appropriate next step can be determined."
        );
      }

      return {
        title: presentation.title,
        description: clauses.join(" ") ||
          "The structured response does not include additional interpretation details."
      };
    }

    function buildOutcomePresentation(outcome) {
      const presentations = {
        ACT: {
          label: "Ready to arrange repair",
          supporting:
            "This repair can progress without landlord approval.",
          attention: "Progressed"
        },

        ASK: {
          label: "More information needed",
          supporting:
            "One focused detail is needed before deciding what happens next.",
          attention: "Waiting"
        },

        AWAITING: {
          label: "Waiting for more information",
          supporting:
            "The issue can continue once the required information is available.",
          attention: "Waiting"
        },

        ESCALATE: {
          label: "Approval needed",
          supporting:
            "Landlord approval is needed before this repair can progress.",
          attention: "Needs you"
        },

        "ACT+ESCALATE": {
          label: "Urgent action required",
          supporting:
            "Protective action should not wait for normal approval.",
          attention: "Needs you"
        },

        CLOSE: {
          label: "No maintenance action needed",
          supporting:
            "No further maintenance action is needed.",
          attention: "Progressed"
        }
      };

      return presentations[normalize(outcome)] || {
        label: "Human review required",
        supporting:
          "The returned decision could not be presented safely.",
        attention: "Needs you"
      };
    }

    function finiteNumber(value) {
      if (
        value === null ||
        value === undefined ||
        value === ""
      ) {
        return null;
      }

      const number = Number(value);

      return Number.isFinite(number)
        ? number
        : null;
    }

    function money(value) {
      const number = finiteNumber(value);

      if (number === null) {
        return "";
      }

      return `$${Number.isInteger(number)
        ? number
        : number.toFixed(2)}`;
    }

    function buildBoundaryExplanation(result) {
      const decision = decisionOf(result);
      const information = informationOf(result);

      if (decision === "ACT") {
        return "This falls within the property's configured autonomous authority.";
      }

      if (decision === "ASK") {
        return "A decision-changing fact is still required.";
      }

      if (decision === "AWAITING") {
        return "The information needed to continue is not yet available.";
      }

      if (decision === "ACT+ESCALATE") {
        return "Protective action may proceed immediately, while human oversight is required.";
      }

      if (decision === "CLOSE") {
        return "The governed evaluation found no further maintenance action is needed.";
      }

      if (decision === "ESCALATE") {
        /*
         * Explain an exhausted clarification cycle from the structured
         * information state itself. No policy-rule inspection is required.
         */
        if (information === "INSUFFICIENT_AFTER_ASK") {
          return "The information remains still insufficient to determine a safe autonomous next step, so human review is required.";
        }

        const quoted = finiteNumber(
          result?.technical?.quoted_cost
        );

        const authority = finiteNumber(
          result?.technical?.authority_limit
        );

        if (
          quoted !== null &&
          authority !== null &&
          quoted > authority
        ) {
          return (
            `The quoted repair (${money(quoted)}) is above ` +
            `this property's configured autonomous authority ` +
            `(${money(authority)}).`
          );
        }

        return "This falls outside the property's configured autonomous authority.";
      }

      return "Human review is required because the governed decision could not be presented safely.";
    }

    return {
      humanizeEnum,
      humanizeTrade,
      humanizeHazard,
      buildHumanInterpretation,
      buildOutcomePresentation,
      buildBoundaryExplanation
    };
  }
);