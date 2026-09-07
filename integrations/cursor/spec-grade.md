# Evaluate and improve a specification

Act as an authoring coach, not an approval gate. Ask the user for the Markdown specification path if it is not clear from the request or current context.

Use the bundled grader at `./tools/spec-grader/bin/spec-grade`. If that path does not exist, locate `spec-grader/bin/spec-grade` in the workspace; do not download or install a different package without asking.

For an evaluation, run the grader with the configured provider and model. Add `--improve` only when the user asks for a revised draft. Read the generated Markdown report and lead with:

1. The most important authoring improvements
2. Decisions and assumptions requiring confirmation
3. Readiness blockers
4. The draft-quality score and category ratings as secondary indicators

Do not describe the score as certification, approval, or proof of factual correctness. Never insert unconfirmed assumptions into the specification as facts.
