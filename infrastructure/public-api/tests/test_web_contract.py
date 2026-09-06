import hashlib
import pathlib
import unittest

WEB = pathlib.Path(__file__).parents[3] / "web"

FROZEN_PROMPTS = [
    "Hi, the kitchen faucet has a steady drip even when it's fully off. Not urgent but wanted to report it.",
    "The second bedroom window doesn't latch.",
    "The AC isn't cooling. A technician found a failed condensate pump and quoted $285 to replace it.",
    "There is a strong smell of gas and it seems to be getting stronger.",
]


class WebContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (WEB / "index.html").read_text(encoding="utf-8")
        cls.js = (WEB / "app.js").read_text(encoding="utf-8")
        cls.presentation = (WEB / "presentation.js").read_text(encoding="utf-8")
        cls.evidence = (WEB / "evaluation.html").read_text(encoding="utf-8")

    def test_all_showcase_prompts_are_exact(self):
        for prompt in FROZEN_PROMPTS:
            self.assertIn(prompt, self.js)

    def test_browser_sends_only_report(self):
        self.assertIn("JSON.stringify({ report: reportText })", self.js)
        self.assertNotIn('name="unit"', self.html.lower())
        self.assertNotIn('name="clarification"', self.html.lower())

    def test_double_submit_is_blocked(self):
        self.assertIn("if (evaluating || reviewMode) return", self.js)
        self.assertIn("button.disabled = value", self.js)

    def test_live_and_failure_labels_are_unambiguous(self):
        self.assertIn("LIVE RESPONSE · AMAZON BEDROCK AGENTCORE", self.html)
        self.assertIn("LIVE EVALUATION FAILED", self.html)
        self.assertIn("No decision was produced", self.js)
        self.assertNotIn("VERIFIED EXAMPLE · NOT LIVE", self.html)

    def test_frontend_timeout_is_35_seconds(self):
        self.assertIn("35_000", self.js)
        self.assertNotIn("45_000", self.js)

    def test_two_required_tabs_exist(self):
        self.assertIn("Evaluate issue", self.html)
        self.assertIn("Landlord view", self.html)

    def test_judge_facing_copy(self):
        self.assertIn("What should happen next?", self.html)
        self.assertIn("Try an example", self.html)
        self.assertIn("Decision will appear here", self.html)
        self.assertIn("Autopilot will show the next action, boundary and reason.", self.html)

    def test_live_label_requires_api_configuration(self):
        self.assertIn("Local preview", self.html)
        self.assertIn('if (API_BASE)', self.js)
        self.assertIn('textContent = "Demo Property · Live system"', self.js)

    def test_landlord_outcome_groups_are_operational_not_completion_claims(self):
        self.assertIn('item.decision === "ACT" || item.decision === "CLOSE"', self.js)
        self.assertIn('item.decision === "ESCALATE" || item.decision === "ACT+ESCALATE"', self.js)
        self.assertIn('item.decision === "ASK" || item.decision === "AWAITING"', self.js)
        for label in ("Evaluated", "Progressed", "Needs you", "Waiting"):
            self.assertIn(label, self.html)
        self.assertNotIn("physical repair", self.html.lower())

    def test_landlord_copy_keeps_persistence_quiet_and_accurate(self):
        self.assertIn("See what Autopilot progressed and what still needs your attention.", self.html)
        self.assertIn("Demo history is stored in this browser only.", self.html)
        self.assertIn("No maintenance activity yet", self.html)
        self.assertNotIn("LOCAL DEMO HISTORY", self.html)

    def test_evidence_link_and_page_contract(self):
        self.assertIn('href="/evaluation.html"', self.html)
        self.assertTrue((WEB / "evaluation.html").is_file())
        self.assertIn("111 / 111", self.evidence)
        self.assertIn("labelled development cases", self.evidence)
        self.assertIn("frozen V2.5 development evaluation", self.evidence)
        self.assertIn("prototype operating envelope", self.evidence)
        self.assertIn("not an unseen holdout", self.evidence)
        self.assertIn("40 / 40", self.evidence)
        self.assertIn("Deployed showcase hardening", self.evidence)
        self.assertNotIn("151/151", self.evidence)
        self.assertNotIn("151 / 151", self.evidence)
        self.assertIn("← Back to live evaluator", self.evidence)
        self.assertIn('href="/"', self.evidence)

    def test_history_details_restore_without_fetch_or_duplicate(self):
        self.assertIn('action.textContent = "View details →"', self.js)
        self.assertIn('action.addEventListener("click", () => reopenHistoryItem(item))', self.js)
        reopen = self.js.split("function reopenHistoryItem(item)", 1)[1].split("document.querySelector(\"#clear-history\")", 1)[0]
        self.assertIn("report.value = item.report", reopen)
        self.assertIn('selectView("evaluate")', reopen)
        self.assertIn("renderDecision(storedResult, { report: item.report, submittedAt: item.created_at })", reopen)
        self.assertNotIn("fetch(", reopen)
        self.assertNotIn("saveHistory(", reopen)
        self.assertIn("result", self.js.split("function saveHistory", 1)[1].split("function renderHistory", 1)[0])

    def test_history_details_enter_review_mode(self):
        reopen = self.js.split("function reopenHistoryItem(item)", 1)[1].split("function exitReviewMode", 1)[0]
        self.assertIn("reviewMode = true", reopen)
        self.assertIn("report.value = item.report", reopen)
        self.assertIn("renderDecision(storedResult, { report: item.report, submittedAt: item.created_at })", reopen)
        self.assertIn('workspace.classList.add("review-mode")', reopen)
        self.assertIn("reportPanel.hidden = true", reopen)
        self.assertIn("reviewContext.hidden = false", reopen)
        self.assertNotIn("fetch(", reopen)
        self.assertNotIn("saveHistory(", reopen)

    def test_review_mode_has_contextual_return_without_history_mutation(self):
        self.assertIn("← Back to Landlord view", self.html)
        self.assertIn('backToLandlord.addEventListener("click", () => selectView("landlord"))', self.js)
        return_handler = self.js.split('backToLandlord.addEventListener', 1)[1].split("document.querySelectorAll", 1)[0]
        self.assertNotIn("fetch(", return_handler)
        self.assertNotIn("saveHistory(", return_handler)
        self.assertNotIn("localStorage", return_handler)

    def test_normal_evaluate_navigation_exits_review_mode(self):
        navigation = self.js.split('document.querySelector("#tab-evaluate")', 1)[1].split('document.querySelector("#tab-landlord")', 1)[0]
        self.assertIn("exitReviewMode(true)", navigation)
        exit_mode = self.js.split("function exitReviewMode(clearEvaluation)", 1)[1].split('document.querySelector("#clear-history")', 1)[0]
        self.assertIn("reviewMode = false", exit_mode)
        self.assertIn('workspace.classList.remove("review-mode")', exit_mode)
        self.assertIn("reportPanel.hidden = false", exit_mode)
        self.assertIn("reviewContext.hidden = true", exit_mode)
        self.assertIn("setOriginalReport()", exit_mode)
        self.assertIn("report.value = \"\"", exit_mode)
        self.assertIn('showState("empty")', exit_mode)

    def test_review_mode_cannot_submit(self):
        submit = self.js.split('form.addEventListener("submit"', 1)[1]
        self.assertIn("if (evaluating || reviewMode) return", submit)

    def test_review_layout_replaces_evaluator_and_shows_report(self):
        self.assertIn('id="review-context"', self.html)
        self.assertIn("Reviewing a past evaluation", self.html)
        self.assertIn("This is a previously evaluated maintenance issue. Review the decision details below.", self.html)
        self.assertIn('id="original-report"', self.html)
        self.assertIn("Original maintenance report", self.html)
        reopen = self.js.split("function reopenHistoryItem(item)", 1)[1].split("function exitReviewMode", 1)[0]
        self.assertIn("report: item.report", reopen)

    def test_review_timestamp_is_only_shown_when_valid_and_stored(self):
        original = self.js.split("function setOriginalReport", 1)[1].split("function renderDecision", 1)[0]
        self.assertIn('typeof submittedAt === "string"', original)
        self.assertIn("!Number.isNaN(timestamp.getTime())", original)
        self.assertIn("submitted.hidden = false", original)
        self.assertIn("submitted.hidden = true", original)

    def test_history_counts_still_use_top_level_outcomes(self):
        render = self.js.split("function renderHistory()", 1)[1].split("function reopenHistoryItem", 1)[0]
        self.assertIn('text("#history-evaluated", entries.length)', render)
        self.assertIn('item.decision === "ACT" || item.decision === "CLOSE"', render)
        self.assertIn('item.decision === "ESCALATE" || item.decision === "ACT+ESCALATE"', render)
        self.assertIn('item.decision === "ASK" || item.decision === "AWAITING"', render)

    def test_all_outcomes_use_one_human_operational_mapping(self):
        expected = {
            "ACT": "Ready to arrange repair",
            "ASK": "More information needed",
            "AWAITING": "Waiting for more information",
            "ESCALATE": "Approval needed",
            '"ACT+ESCALATE"': "Urgent action required",
            "CLOSE": "No maintenance action needed",
        }
        mapping = self.presentation.split("const OUTCOMES", 1)[1].split("const EMPTY_HAZARDS", 1)[0]
        for outcome, label in expected.items():
            self.assertIn(outcome, mapping)
            self.assertIn(label, mapping)
        self.assertIn("buildOutcomePresentation(value.decision)", self.js)
        self.assertIn("buildOutcomePresentation(item.decision)", self.js)

    def test_machine_values_are_technical_not_primary(self):
        self.assertNotIn('id="decision-code"', self.html)
        self.assertIn("What happens next", self.html)
        self.assertIn("Raw outcome", self.html)
        self.assertIn('id="technical-outcome"', self.html)
        self.assertIn('id="technical-rule"', self.html)
        render = self.js.split("function renderDecision", 1)[1].split("function showError", 1)[0]
        self.assertIn('text("#technical-outcome", value.decision)', render)
        self.assertIn('text("#technical-rule", value.policy_rule)', render)
        self.assertIn('document.querySelector("#decision-result details").open = false', render)

    def test_landlord_rows_do_not_surface_raw_outcome_or_policy_rule(self):
        render = self.js.split("function renderHistory()", 1)[1].split("function reopenHistoryItem", 1)[0]
        self.assertIn("resultPresentation.label", render)
        self.assertIn("resultPresentation.attention", render)
        self.assertNotIn("item.policy_rule", render)
        self.assertNotIn("decision.textContent = item.decision", render)

    def test_interpretation_uses_only_structured_response_fields(self):
        interpretation = self.presentation.split("function buildHumanInterpretation(result)", 1)[1].split("function buildOutcomePresentation", 1)[0]
        for field in ("technical.hazard", "technical.urgency", "technical.trade", "technical.information"):
            self.assertIn(field, self.presentation)
        self.assertNotIn("policy_rule", interpretation)
        self.assertIn('let title = "Maintenance issue"', interpretation)
        self.assertIn("description: clauses.join", interpretation)
        self.assertIn("buildHumanInterpretation(value)", self.js)
        self.assertIn("buildHumanInterpretation(item.result)", self.js)

    def test_no_execution_claims_are_introduced(self):
        public_copy = (self.html + self.js + self.presentation).lower()
        forbidden = (
            "technician dispatched", "tenant contacted", "landlord notified",
            "emergency response initiated", "repair scheduled", "request closed",
        )
        for claim in forbidden:
            self.assertNotIn(claim, public_copy)

    def test_routine_language_does_not_imply_estimated_cost(self):
        mapping = self.presentation.split("const OUTCOMES", 1)[1].split("const EMPTY_HAZARDS", 1)[0]
        self.assertIn("Ready to arrange repair", mapping)
        self.assertNotIn("estimated", mapping.lower())
        self.assertNotIn("cost", mapping.lower())

    def test_live_flow_renders_exact_report_without_changing_request(self):
        submit = self.js.split('form.addEventListener("submit"', 1)[1]
        self.assertIn("JSON.stringify({ report: reportText })", submit)
        self.assertIn("renderDecision(result, { report: reportText })", submit)

    def test_repository_evaluation_evidence_is_unchanged(self):
        evidence_source = WEB.parent / "docs" / "EVALUATION.md"
        digest = hashlib.sha256(evidence_source.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, "4AF0C88DA18B549B78C8E7D66D37260DFC3F215AB8CA7C90DE71A217D0BB6CB2")


if __name__ == "__main__":
    unittest.main()
