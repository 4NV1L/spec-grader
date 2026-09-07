# Scoring contract

The evaluator returns one integer rating per category. Anchors are global: 0 absent, 1 materially incomplete, 2 partial with major questions, 3 substantially complete, and 4 explicit/measurable/ready. Category contribution is `weight × rating ÷ 4`; weights total 100.

The engine rounds the summed raw score, then applies the lowest triggered score cap. Letter grade reflects the capped score. Verdict thresholds are READY ≥85 with confidence ≥80; READY-WITH-CHANGES ≥65 with confidence ≥55; otherwise NOT-READY. A readiness blocker may further cap the verdict. These are draft-quality indicators for authorship, not approval or certification.

Autonomous-implementation confidence is deterministic: take the weighted score across functional requirements, architecture, interfaces/contracts, failure modes, acceptance criteria, dependencies, implementation readiness, and ambiguity/testability; subtract 12 per critical issue, 6 per high issue, and 2 per medium issue, then clamp to 0–100.

Evaluator stability rules: use only cited spec evidence; never award credit for inferred intent; prefer the lower rating when adjacent anchors both seem plausible; rate missing evidence 0; rate prose that merely promises future definition no higher than 1. Temperature should be zero where supported. The local engine rejects missing/duplicate categories and invalid ratings.

The security gate is conditional. The evaluator sets `security_relevant` true when the spec processes identity, authorization, secrets, payments, personal/sensitive data, untrusted input, or externally reachable interfaces.

## Score-improvement guidance

For every category below 4/4, the engine produces a next-step target. Potential gain is one rating step, `weight ÷ 4`; it is not a promised final score because gate caps still apply. Plans are ordered by current gate clearance, related issue severity, and point gain. Actions come from evidence-backed issue remediation when available, otherwise from the category's rubric target. This makes guidance specific without allowing the evaluator to manipulate scoring math.
