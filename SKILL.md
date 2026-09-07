---
name: spec-grader
description: Evaluate and improve Markdown product, technical, or implementation specifications with a deterministic weighted rubric, evidence-backed coaching, readiness blockers, and Markdown plus JSON reports. Use while authoring or refining a spec; do not treat scores as certification or substitute them for product decisions.
---

# Spec Grader

Grade the supplied Markdown spec with the bundled deterministic engine. The evaluator identifies evidence and assigns anchored ratings; the script owns all arithmetic, caps, grades, confidence, and verdicts.

## Workflow

1. Run `python3 "${CLAUDE_SKILL_DIR}/scripts/spec_grade.py" <spec.md> --provider <provider>` in Claude Code. Outside Claude Code, run `./bin/spec-grade <spec.md>`. Use `mock` only for examples/tests; use `anthropic` or `openai-compatible` for real grading.
2. Inspect both generated artifacts. Lead with improvement guidance, missing author decisions, and readiness blockers. Treat the score, grade, and confidence as secondary progress indicators.
3. Treat every issue as invalid unless it cites a heading/line range and a short snippet or explicitly states that expected evidence is absent.
4. Never adjust the calculated score subjectively. If the assessment seems wrong, rerun with a better evaluator/model or revise the rubric.
5. For CI, use `--fail-on ready-with-changes` or `--fail-on not-ready` as appropriate.

When the user asks to improve or raise the score, run with `--improve`. Review the resulting assumptions and questions with the user; a generated revision is a proposal until those decisions are confirmed.

Read [references/scoring.md](references/scoring.md) when changing the rubric or interpreting a score. Read [references/architecture.md](references/architecture.md) when adding providers, gates, integrations, or codebase-aware review.

## Required invariants

- Use only the input spec as evidence in v1; do not invent product or repository context.
- Rate every rubric category from 0–4 using its anchors.
- Preserve evaluator observations in JSON; calculate normalized category scores, total, grade, confidence, caps, and verdict locally.
- Readiness blockers cap the score/verdict even if the weighted raw score is higher; retain `gate_failures` as the stable JSON field name.
- Keep remediation concrete: name the missing decision, contract, scenario, threshold, or test.
- Explain how to earn the next rating in every category below 4/4, show the potential weighted point gain, and prioritize gate-clearing changes before ordinary improvements.
- Do not expose API keys in output or error messages.

## Output contract

Validate JSON against `schemas/report.schema.json`. Markdown is a human-readable projection of that same JSON. Default names are `<spec>.grade.md` and `<spec>.grade.json`; `--json` prints JSON to stdout instead.

## Installation and invocation

For Claude Code-style discovery, copy or link this folder as `.claude/skills/spec-grader` in a project (or the equivalent user skills directory). Invoke it conversationally or run the bundled CLI directly:

```sh
./bin/spec-grade ./SPEC.md --provider anthropic --model claude-sonnet-4-5
./bin/spec-grade ./SPEC.md --provider openai-compatible --model gpt-5
./bin/spec-grade ./SPEC.md --provider openai-compatible --base-url http://localhost:11434 --model qwen3
./bin/spec-grade ./SPEC.md --provider anthropic --model claude-sonnet-4-5 --json
./bin/spec-grade ./SPEC.md --provider anthropic --model claude-sonnet-4-5 --improve
```

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` as applicable. Local OpenAI-compatible servers may omit a real key. Configuration also accepts `SPEC_GRADE_PROVIDER`, `SPEC_GRADE_MODEL`, and `SPEC_GRADE_BASE_URL`.

For CI, an exit code of 2 means the selected threshold failed:

```sh
./bin/spec-grade ./SPEC.md --provider openai-compatible --model "$SPEC_GRADE_MODEL" --fail-on ready-with-changes
```
