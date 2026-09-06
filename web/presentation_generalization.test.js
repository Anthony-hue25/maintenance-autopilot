"use strict";

const assert = require("assert");
const p = require("./presentation.js");

let passed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`PASS  ${name}`);
  } catch (error) {
    console.error(`FAIL  ${name}`);
    throw error;
  }
}

function result({
  decision = "ACT",
  hazard = [],
  condition = [],
  trade = "",
  information = "SUFFICIENT",
  rule = ""
} = {}) {
  return {
    decision,
    rule,
    technical: {
      hazard,
      condition,
      trade,
      information
    }
  };
}

test("unknown future trade degrades gracefully", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "ROOFING" })
  );

  assert.strictEqual(output.title, "Roofing issue");
  assert.match(output.description, /roofing maintenance issue/i);
});

test("multiword unknown trade is humanized", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "GARAGE_DOOR" })
  );

  assert.strictEqual(output.title, "Garage door issue");
});

test("unknown future condition is humanized", () => {
  const output = p.buildHumanInterpretation(
    result({
      condition: ["DOOR_ALIGNMENT_PROBLEM"],
      trade: "GENERAL"
    })
  );

  assert.strictEqual(
    output.title,
    "Door alignment problem"
  );
});

test("unknown future hazard remains readable", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "ACT+ESCALATE",
      hazard: ["FALLING_OBJECT_RISK"],
      trade: "GENERAL"
    })
  );

  assert.strictEqual(
    output.title,
    "Potential falling object risk"
  );
});

test("hazard outranks condition and trade", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "ACT+ESCALATE",
      hazard: ["GAS_HAZARD"],
      condition: ["MOISTURE_PRESENT"],
      trade: "PLUMBING"
    })
  );

  assert.strictEqual(
    output.title,
    "Potential gas hazard"
  );
});

test("meaningful condition outranks trade", () => {
  const output = p.buildHumanInterpretation(
    result({
      condition: ["MOLD_SPREAD"],
      trade: "MOISTURE"
    })
  );

  assert.strictEqual(
    output.title,
    "Spreading mold issue"
  );
});

test("appliance is no longer generic", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "APPLIANCE" })
  );

  assert.strictEqual(
    output.title,
    "Appliance issue"
  );

  assert.doesNotMatch(
    output.description,
    /structured response/i
  );
});

test("moisture is no longer generic", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "MOISTURE" })
  );

  assert.strictEqual(
    output.title,
    "Moisture issue"
  );
});

test("pest is no longer generic", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "PEST" })
  );

  assert.strictEqual(
    output.title,
    "Pest issue"
  );
});

test("general trade degrades sensibly", () => {
  const output = p.buildHumanInterpretation(
    result({ trade: "GENERAL" })
  );

  assert.strictEqual(
    output.title,
    "General maintenance issue"
  );
});

test("resolved condition produces resolved interpretation", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "CLOSE",
      condition: ["RESOLVED_NO_OUTSTANDING_NEED"],
      trade: "NONE"
    })
  );

  assert.strictEqual(
    output.title,
    "Issue resolved"
  );
});

test("ACT does not contradict itself with clarification language", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "ACT",
      hazard: ["SECURITY_EXPOSURE"],
      trade: "LOCKSMITH",
      information: "NEEDS_CLARIFICATION"
    })
  );

  assert.doesNotMatch(
    output.description,
    /More information is needed/i
  );
});

test("ACT+ESCALATE does not add clarification noise", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "ACT+ESCALATE",
      hazard: ["GAS_HAZARD"],
      information: "NEEDS_CLARIFICATION"
    })
  );

  assert.doesNotMatch(
    output.description,
    /More information is needed/i
  );
});

test("ASK still explains missing information", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "ASK",
      trade: "LOCKSMITH",
      information: "NEEDS_CLARIFICATION"
    })
  );

  assert.match(
    output.description,
    /More information is needed/i
  );
});

test("AWAITING still explains unavailable information", () => {
  const output = p.buildHumanInterpretation(
    result({
      decision: "AWAITING",
      trade: "GENERAL",
      information: "NO_RESPONSE_AFTER_ASK"
    })
  );

  assert.match(
    output.description,
    /More information is needed/i
  );
});

test("authority escalation keeps authority explanation", () => {
  const why = p.buildBoundaryExplanation(
    result({
      decision: "ESCALATE",
      trade: "HVAC",
      rule: "P04_AUTHORITY_EXCEEDED"
    })
  );

  assert.strictEqual(
    why,
    "This falls outside the property's configured autonomous authority."
  );
});

test("insufficient-after-ask escalation is explained accurately", () => {
  const why = p.buildBoundaryExplanation(
    result({
      decision: "ESCALATE",
      information: "INSUFFICIENT_AFTER_ASK",
      rule: "P08_INSUFFICIENT_AFTER_ASK"
    })
  );

  assert.match(
    why,
    /still insufficient/i
  );
});

test("unknown outcome fails closed", () => {
  const output = p.buildOutcomePresentation(
    "SOME_FUTURE_OUTCOME"
  );

  assert.strictEqual(
    output.label,
    "Human review required"
  );

  assert.strictEqual(
    output.attention,
    "Needs you"
  );
});

console.log();
console.log(
  `${passed} generalization presentation tests passed`
);