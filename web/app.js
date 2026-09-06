(() => {
  "use strict";

  const EXAMPLES = Object.freeze({
    routine: "Hi, the kitchen faucet has a steady drip even when it's fully off. Not urgent but wanted to report it.",
    security: "The second bedroom window doesn't latch.",
    authority: "The AC isn't cooling. A technician found a failed condensate pump and quoted $285 to replace it.",
    gas: "There is a strong smell of gas and it seems to be getting stronger."
  });
  const VALID_DECISIONS = new Set(["ACT", "ASK", "AWAITING", "ESCALATE", "ACT+ESCALATE", "CLOSE"]);
  const { buildHumanInterpretation, buildOutcomePresentation, buildBoundaryExplanation } = window.MaintenancePresentation;
  const API_BASE = String(window.MAINTENANCE_API_URL || "").replace(/\/$/, "");
  const HISTORY_KEY = "maintenance-autopilot-live-history-v1";
  const form = document.querySelector("#evaluate-form");
  const report = document.querySelector("#report");
  const button = document.querySelector("#evaluate-button");
  const backToLandlord = document.querySelector("#back-to-landlord");
  const workspace = document.querySelector(".workspace");
  const reportPanel = document.querySelector(".report-panel");
  const reviewContext = document.querySelector("#review-context");
  const originalReport = document.querySelector("#original-report");
  let evaluating = false;
  let reviewMode = false;

  if (API_BASE) {
    document.querySelector("#system-status-text").textContent = "Demo Property · Live system";
  } else {
    document.querySelector("#system-status").classList.add("local");
  }

  function selectView(name) {
    document.querySelectorAll(".view").forEach(view => {
      const active = view.id === `${name}-view`;
      view.classList.toggle("active", active);
      view.hidden = !active;
    });
    document.querySelectorAll(".tab").forEach(tab => {
      const active = tab.id === `tab-${name}`;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    if (name === "landlord") renderHistory();
  }

  document.querySelector("#tab-evaluate").addEventListener("click", () => {
    exitReviewMode(true);
    selectView("evaluate");
  });
  document.querySelector("#tab-landlord").addEventListener("click", () => selectView("landlord"));
  backToLandlord.addEventListener("click", () => selectView("landlord"));

  document.querySelectorAll("[data-example]").forEach(chip => chip.addEventListener("click", () => {
    report.value = EXAMPLES[chip.dataset.example];
    updateCount();
    report.focus();
  }));

  function updateCount() {
    document.querySelector("#char-count").textContent = `${report.value.length.toLocaleString()} / 4,000`;
    document.querySelector("#field-error").textContent = "";
  }
  report.addEventListener("input", updateCount);

  function showState(state) {
    ["empty", "loading", "error", "decision"].forEach(name => {
      document.querySelector(`#${name}-result`).hidden = name !== state;
    });
    const panel = document.querySelector("#result-panel");
    panel.className = `result-panel ${state}`;
    panel.setAttribute("aria-busy", String(state === "loading"));
  }

  function setEvaluating(value) {
    evaluating = value;
    button.disabled = value;
    button.classList.toggle("loading", value);
    button.querySelector(".button-label").textContent = value ? "Evaluating…" : "Evaluate issue";
  }

  function validateLiveResponse(value) {
    const object = value && typeof value === "object";
    const nested = object && value.presentation && value.trace && value.technical && value.runtime;
    if (!nested || !VALID_DECISIONS.has(value.decision) || typeof value.policy_rule !== "string" ||
        typeof value.evaluation_id !== "string" || typeof value.presentation.headline !== "string" ||
        typeof value.presentation.explanation !== "string" || typeof value.trace.next_action !== "string") {
      throw new Error("malformed-response");
    }
    return value;
  }

  function text(id, value) { document.querySelector(id).textContent = String(value ?? "—"); }

  function setOriginalReport(reportText, submittedAt = "") {
    originalReport.hidden = !reportText;
    text("#original-report-text", reportText || "");
    const submitted = document.querySelector("#original-report-time");
    const timestamp = typeof submittedAt === "string" && submittedAt ? new Date(submittedAt) : null;
    if (timestamp && !Number.isNaN(timestamp.getTime())) {
      submitted.dateTime = submittedAt;
      submitted.textContent = `Submitted ${timestamp.toLocaleString()}`;
      submitted.hidden = false;
    } else {
      submitted.removeAttribute("datetime");
      submitted.textContent = "";
      submitted.hidden = true;
    }
  }

  function renderDecision(value, context = {}) {
    const presentation = buildOutcomePresentation(value.decision);
    const interpretation = buildHumanInterpretation(value);
    document.querySelector("#decision-result details").open = false;
    setOriginalReport(context.report || "", context.submittedAt || "");
    text("#understood-heading", interpretation.title);
    text("#understood-detail", interpretation.description);
    text("#decision-headline", presentation.label);
    text("#decision-subheadline", presentation.supporting);
    text("#decision-explanation", buildBoundaryExplanation(value));
    text("#technical-outcome", value.decision);
    text("#trace-situation", value.trace.situation);
    text("#trace-boundary", value.trace.boundary);
    text("#trace-next", value.trace.next_action);
    text("#technical-rule", value.policy_rule);
    text("#technical-hazard", Array.isArray(value.technical.hazard) ? value.technical.hazard.join(", ") : value.technical.hazard);
    text("#technical-information", value.technical.information);
    text("#technical-urgency", value.technical.urgency);
    text("#technical-trade", value.technical.trade);
    text("#technical-latency", `${value.runtime.latency_ms} ms`);
    text("#technical-evaluation", value.evaluation_id);
    text("#technical-request", value.runtime.request_id);
    showState("decision");
  }

  function showError(kind, requestId = "") {
    const messages = {
      timeout: ["Evaluation timed out", "The live runtime did not respond within 35 seconds. No decision was produced. Please try again."],
      network: ["Network connection failed", "The live API could not be reached. Check the connection and API configuration, then try again."],
      server: ["Live service unavailable", "The server could not complete this evaluation. No decision was produced. Please try again."],
      malformed: ["Unusable live response", "The live service returned an unexpected response. No decision was produced."],
    };
    const [title, message] = messages[kind] || messages.server;
    text("#error-title", title);
    text("#error-message", message);
    text("#error-request", requestId ? `Request reference: ${requestId}` : "");
    showState("error");
  }

  function readHistory() {
    try {
      const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
      return Array.isArray(value) ? value.slice(0, 25) : [];
    } catch { return []; }
  }

  function saveHistory(result, reportText) {
    const entries = readHistory();
    entries.unshift({
      evaluation_id: result.evaluation_id,
      created_at: result.created_at,
      decision: result.decision,
      policy_rule: result.policy_rule,
      headline: result.presentation.headline,
      report: reportText,
      result
    });
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, 25))); } catch { /* optional local history */ }
  }

  function renderHistory() {
    const entries = readHistory();
    text("#history-evaluated", entries.length);
    text("#history-progressed", entries.filter(item => item.decision === "ACT" || item.decision === "CLOSE").length);
    text("#history-needs-you", entries.filter(item => item.decision === "ESCALATE" || item.decision === "ACT+ESCALATE").length);
    text("#history-waiting", entries.filter(item => item.decision === "ASK" || item.decision === "AWAITING").length);
    const list = document.querySelector("#history-list");
    list.replaceChildren();
    document.querySelector("#history-empty").hidden = entries.length > 0;
    entries.forEach(item => {
      const row = document.createElement("article");
      row.className = "history-item";
      const when = document.createElement("time");
      when.dateTime = item.created_at;
      when.textContent = new Date(item.created_at).toLocaleString();
      const detail = document.createElement("div");
      const resultPresentation = buildOutcomePresentation(item.decision);
      const title = document.createElement("strong"); title.textContent = resultPresentation.label;
      const summary = document.createElement("p"); summary.textContent = item.report;
      const understood = document.createElement("small");
      understood.textContent = item.result ? buildHumanInterpretation(item.result).title : "Earlier local evaluation";
      detail.append(title, summary, understood);
      const decision = document.createElement("span"); decision.className = "history-decision"; decision.textContent = resultPresentation.attention;
      const action = document.createElement("button");
      action.type = "button";
      action.className = "history-action";
      if (item.result) {
        action.textContent = "View details →";
        action.addEventListener("click", () => reopenHistoryItem(item));
      } else {
        action.textContent = "Details unavailable";
        action.disabled = true;
        action.title = "This evaluation was saved before detailed local history was enabled.";
      }
      row.append(when, detail, decision, action);
      list.append(row);
    });
  }

  function reopenHistoryItem(item) {
    if (!item?.result) return;
    const storedResult = validateLiveResponse(item.result);
    reviewMode = true;
    report.value = item.report;
    updateCount();
    workspace.classList.add("review-mode");
    reportPanel.hidden = true;
    reviewContext.hidden = false;
    selectView("evaluate");
    renderDecision(storedResult, { report: item.report, submittedAt: item.created_at });
  }

  function exitReviewMode(clearEvaluation) {
    if (!reviewMode) return;
    reviewMode = false;
    workspace.classList.remove("review-mode");
    reportPanel.hidden = false;
    reviewContext.hidden = true;
    setOriginalReport();
    if (clearEvaluation) {
      report.value = "";
      updateCount();
      showState("empty");
    }
  }

  document.querySelector("#clear-history").addEventListener("click", () => {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (evaluating || reviewMode) return;
    const reportText = report.value.trim();
    if (!reportText) {
      document.querySelector("#field-error").textContent = "Enter a maintenance report.";
      report.focus();
      return;
    }

    setEvaluating(true);
    showState("loading");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 35_000);
    try {
      const response = await fetch(`${API_BASE}/api/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: reportText }),
        signal: controller.signal,
      });
      let payload;
      try { payload = await response.json(); } catch { throw new Error("malformed-response"); }
      if (!response.ok) {
        showError(response.status === 504 ? "timeout" : "server", payload?.request_id || response.headers.get("x-request-id") || "");
        return;
      }
      const result = validateLiveResponse(payload);
      renderDecision(result, { report: reportText });
      saveHistory(result, reportText);
    } catch (error) {
      if (error?.name === "AbortError") showError("timeout");
      else if (error?.message === "malformed-response") showError("malformed");
      else showError("network");
    } finally {
      clearTimeout(timer);
      setEvaluating(false);
    }
  });

  renderHistory();
})();
