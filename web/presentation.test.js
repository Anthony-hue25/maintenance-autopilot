"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  humanizeEnum,
  humanizeTrade,
  humanizeHazard,
  buildHumanInterpretation,
  buildOutcomePresentation,
  buildBoundaryExplanation
} = require("./presentation.js");

function result({
  decision = "ACT",
  hazard = ["NO_ACTIVE_HAZARD"],
  urgency = "ROUTINE",
  trade = "",
  information = "SUFFICIENT",
  boundary = "",
  technical = {}
} = {}) {
  return {
    decision,
    technical: {
      hazard,
      urgency,
      trade,
      information,
      ...technical
    },
    trace: {
      situation: "",
      boundary
    }
  };
}

test("all six governed outcomes have shared human presentation", () => {
  const expected = {
    ACT: [
      "Ready to arrange repair",
      "This repair can progress without landlord approval."
    ],
    ASK: [
      "More information needed",
      "One focused detail is needed before deciding what happens next."
    ],
    AWAITING: [
      "Waiting for more information",
      "The issue can continue once the required information is available."
    ],
    ESCALATE: [
      "Approval needed",
      "Landlord approval is needed before this repair can progress."
    ],
    "ACT+ESCALATE": [
      "Urgent action required",
      "Protective action should not wait for normal approval."
    ],
    CLOSE: [
      "No maintenance action needed",
      "No further maintenance action is needed."
    ]
  };

  for (const [outcome, copy] of Object.entries(expected)) {
    const actual = buildOutcomePresentation(outcome);
    assert.deepEqual(
      [actual.label, actual.supporting],
      copy
    );
  }
});

test("enum helpers normalize known and previously unseen values", () => {
  assert.equal(
    humanizeEnum("SPECIALTY_GLAZING"),
    "specialty glazing"
  );

  assert.equal(
    humanizeTrade("HVAC"),
    "HVAC"
  );

  assert.equal(
    humanizeTrade("SPECIALTY_GLAZING"),
    "specialty glazing"
  );

  assert.equal(
    humanizeHazard("FALL_RISK_HAZARD"),
    "fall risk hazard"
  );
});

const interpretationCases = [
  [
    "electrical sufficient routine",
    result({
      trade: "ELECTRICAL"
    }),
    "Routine electrical issue",
    "Autopilot identified this as an electrical maintenance issue."
  ],
  [
    "electrical hazard emergency",
    result({
      hazard: ["ELECTRICAL_HAZARD"],
      urgency: "EMERGENCY",
      trade: "ELECTRICAL"
    }),
    "Potential electrical hazard requiring urgent attention",
    "Autopilot identified a potential electrical hazard requiring urgent attention."
  ],
  [
    "unknown trade",
    result({
      trade: "SPECIALTY_GLAZING"
    }),
    "Maintenance issue",
    "The structured response does not include additional interpretation details."
  ],
  [
    "no trade insufficient",
    result({
      trade: "",
      information: "NEEDS_CLARIFICATION"
    }),
    "Maintenance issue",
    "More information is needed before the appropriate next step can be determined."
  ],
  [
    "hazard and no trade",
    result({
      hazard: ["FALL_RISK_HAZARD"],
      trade: ""
    }),
    "Potential fall risk hazard",
    "Autopilot identified a potential fall risk hazard."
  ],
  [
    "unknown urgency",
    result({
      trade: "PLUMBING",
      urgency: "SOMEDAY"
    }),
    "Plumbing issue",
    "Autopilot identified this as a plumbing maintenance issue."
  ],
  [
    "missing optional fields",
    {
      decision: "ASK",
      technical: {},
      trace: {}
    },
    "Maintenance issue",
    "The structured response does not include additional interpretation details."
  ]
];

for (const [name, input, title, description] of interpretationCases) {
  test(`synthetic interpretation: ${name}`, () => {
    assert.deepEqual(
      buildHumanInterpretation(input),
      {
        title,
        description
      }
    );
  });
}

test("authority boundary without quoted price does not invent one", () => {
  const input = result({
    decision: "ESCALATE",
    boundary: "Outside autonomous authority or requires owner judgment."
  });

  assert.equal(
    buildBoundaryExplanation(input),
    "This falls outside the property's configured autonomous authority."
  );

  assert.doesNotMatch(
    buildBoundaryExplanation(input),
    /\$/
  );
});

test("authority boundary uses explicitly supplied structured price facts", () => {
  const input = result({
    decision: "ESCALATE",
    boundary: "Outside autonomous authority.",
    technical: {
      quoted_cost: 285,
      authority_limit: 200
    }
  });

  assert.equal(
    buildBoundaryExplanation(input),
    "The quoted repair ($285) is above this property's configured autonomous authority ($200)."
  );
});

test("generic CLOSE and AWAITING boundaries remain outcome based", () => {
  assert.equal(
    buildBoundaryExplanation(
      result({
        decision: "CLOSE"
      })
    ),
    "The governed evaluation found no further maintenance action is needed."
  );

  assert.equal(
    buildBoundaryExplanation(
      result({
        decision: "AWAITING",
        information: "INSUFFICIENT_AFTER_ASK"
      })
    ),
    "The information needed to continue is not yet available."
  );
});

const showcaseCases = [
  [
    "dripping faucet",
    result({
      decision: "ACT",
      trade: "PLUMBING"
    }),
    "Routine plumbing issue",
    "Ready to arrange repair"
  ],
  [
    "window latch",
    result({
      decision: "ASK",
      trade: "LOCKSMITH",
      information: "NEEDS_CLARIFICATION"
    }),
    "Possible security-related issue",
    "More information needed"
  ],
  [
    "AC quote",
    result({
      decision: "ESCALATE",
      trade: "HVAC",
      urgency: "PRIORITY",
      boundary: "Outside autonomous authority or requires owner judgment."
    }),
    "HVAC issue",
    "Approval needed"
  ],
  [
    "gas smell",
    result({
      decision: "ACT+ESCALATE",
      hazard: ["GAS_HAZARD"],
      urgency: "EMERGENCY",
      trade: "GAS"
    }),
    "Potential gas hazard requiring urgent attention",
    "Urgent action required"
  ]
];

for (const [name, input, title, label] of showcaseCases) {
  test(`frozen showcase presentation regression: ${name}`, () => {
    assert.equal(
      buildHumanInterpretation(input).title,
      title
    );

    assert.equal(
      buildOutcomePresentation(input.decision).label,
      label
    );
  });
}

test("presentation module contains no frozen showcase report text or policy branching", () => {
  const source = require("node:fs").readFileSync(
    require.resolve("./presentation.js"),
    "utf8"
  );

  assert.doesNotMatch(
    source,
    /kitchen faucet|second bedroom window|condensate pump|strong smell of gas/i
  );

  assert.doesNotMatch(
    source,
    /policy_rule|P03_CRITICAL_HAZARD/
  );
});