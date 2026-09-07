# Spec Grader

Spec Grader is an evidence-backed specification evaluator and authoring coach for Claude Code, Cursor, and direct CLI use. It reviews a Markdown specification, identifies weak or missing decisions, recommends concrete improvements, and can produce a guarded revised draft followed by an independent regrade.

The numerical score is a draft-quality indicator. It measures rubric coverage, clarity, and implementation readiness; it does not certify that product decisions or technical claims are correct.

## Use cases

- Evaluate an early PRD, RFC, technical design, implementation plan, or feature specification.
- Find ambiguity, missing contracts, weak acceptance criteria, failure modes, security questions, and unmade product decisions.
- Give an author a prioritized next writing pass rather than a generic review.
- Improve a draft without silently inventing requirements, research, metrics, or policies.
- Compare the original and revised draft category by category.
- Produce Markdown for authors and structured JSON for a future app or integration.

This project is intended for iterative authorship. It is not a code reviewer, factual verifier, compliance certification system, or automatic approval gate.

## What the report contains

- Prioritized authoring guidance and potential rubric gains
- Evidence snippets and source locations
- Improvement opportunities with severity and suggested changes
- Readiness blockers
- Sixteen weighted category ratings
- A 0–100 draft-quality score and letter grade
- Autonomous-implementation confidence
- `READY`, `READY-WITH-CHANGES`, or `NOT-READY` authoring verdict
- Machine-readable JSON matching the bundled schema

With `--improve`, it additionally produces a revised spec, provenance-tagged changes, assumptions to confirm, questions requiring author decisions, a fresh evaluation, and a before/after comparison.

## Requirements

- Python 3.9 or newer
- No third-party Python packages
- An Anthropic API key, an OpenAI API key, or access to a local OpenAI-compatible model server

## Installation

### Clone for direct CLI use

```sh
git clone <repository-url> spec-grader
cd spec-grader
./bin/spec-grade --help
```

You can run `bin/spec-grade` in place or add its `bin` directory to your shell `PATH`.

### Claude Code: personal skill

Clone or copy the complete repository to:

```text
~/.claude/skills/spec-grader/
```

The resulting entrypoint must be:

```text
~/.claude/skills/spec-grader/SKILL.md
```

Claude Code can select the skill when relevant, or you can invoke it directly:

```text
/spec-grader path/to/SPEC.md
```

### Claude Code: project skill

Copy the repository into the project:

```text
your-project/.claude/skills/spec-grader/
```

Commit that directory if the whole team should share the evaluator. The skill uses `${CLAUDE_SKILL_DIR}` to locate its bundled CLI regardless of the project working directory. See the official [Claude Code skills documentation](https://code.claude.com/docs/en/slash-commands).

### Cursor

Keep this repository somewhere inside the project, such as:

```text
your-project/tools/spec-grader/
```

Then copy:

```text
integrations/cursor/spec-grade.md
```

to:

```text
your-project/.cursor/commands/spec-grade.md
```

Edit the grader path in that command if you installed it somewhere other than `tools/spec-grader`. Invoke the workflow from Cursor with `/spec-grade` and provide or reference the Markdown specification. Cursor custom commands are plain Markdown workflow instructions; see the official [Cursor commands documentation](https://docs.cursor.com/en/agent/chat/commands).

## Provider configuration

### Anthropic

```sh
export ANTHROPIC_API_KEY="your-key"
./bin/spec-grade ./SPEC.md \
  --provider anthropic \
  --model "your-claude-model"
```

### OpenAI

```sh
export OPENAI_API_KEY="your-key"
./bin/spec-grade ./SPEC.md \
  --provider openai-compatible \
  --model "your-openai-model"
```

### Local OpenAI-compatible server

```sh
./bin/spec-grade ./SPEC.md \
  --provider openai-compatible \
  --base-url http://localhost:11434 \
  --model "your-local-model"
```

The same values can be supplied through `SPEC_GRADE_PROVIDER`, `SPEC_GRADE_MODEL`, and `SPEC_GRADE_BASE_URL`. Local servers may omit a real API key.

## Usage

Evaluate a specification and write Markdown plus JSON beside it:

```sh
./bin/spec-grade ./SPEC.md \
  --provider anthropic \
  --model "your-claude-model"
```

Print JSON to standard output:

```sh
./bin/spec-grade ./SPEC.md \
  --provider openai-compatible \
  --model "your-model" \
  --json
```

Create a guarded revision and re-evaluate it:

```sh
./bin/spec-grade ./SPEC.md \
  --provider anthropic \
  --model "your-claude-model" \
  --improve
```

Choose a separate output directory:

```sh
./bin/spec-grade ./SPEC.md \
  --provider openai-compatible \
  --model "your-model" \
  --output-dir ./spec-review
```

## Improvement safeguards

The improvement workflow classifies every change as one of:

- `existing-evidence` — directly supported by the original draft
- `safe-clarification` — editorial clarification that preserves intent
- `proposed-assumption` — useful proposal that requires confirmation
- `user-decision-required` — a decision the model must not make for the author

Unresolved matters remain visible as assumptions or open questions. Regrading a generated draft measures improved rubric coverage; it does not validate newly supplied facts.

## Scoring summary

Each rubric category receives an anchored rating from 0 to 4. Its contribution is:

```text
category points = category weight × rating ÷ 4
```

Category weights total 100. Foundational omissions can activate readiness blockers that cap the final score or verdict. See [references/scoring.md](references/scoring.md) for the full rubric contract and [config/rubric.json](config/rubric.json) for the versioned weights.

## Output files

Ordinary evaluation creates:

```text
SPEC.grade.md
SPEC.grade.json
```

Improvement mode also creates:

```text
SPEC.improved.md
SPEC.improvement.md
SPEC.improvement.json
SPEC.improved.grade.md
SPEC.improved.grade.json
```

Examples are available in [examples](examples/). JSON contracts are in [schemas](schemas/).

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The fixture suite verifies deterministic aggregation, weight totals, readiness caps, malformed evaluation rejection, and the improvement provenance contract.

## Architecture and roadmap

Provider calls are isolated from scoring. Models return evidence-backed observations and anchored category ratings; local code validates their shape and performs all arithmetic, confidence calculations, caps, and rendering.

Planned hardening includes evidence-snippet verification, calibration fixtures, model and prompt provenance, retry handling, large-spec support, codebase-aware review, and optional multi-model consensus. See [references/architecture.md](references/architecture.md).

## Current limitations

- Ratings remain model judgments even though score calculation is deterministic.
- Different models may assign adjacent ratings differently.
- Evidence locations are structurally validated but not yet checked against the source text.
- Change provenance is declared by the model and not yet independently proven.
- A better score indicates better rubric coverage, not necessarily a better product decision.
- Authors should confirm all assumptions and answer open questions before implementation.

## Repository layout

```text
spec-grader/
├── SKILL.md
├── README.md
├── bin/spec-grade
├── config/rubric.json
├── scripts/spec_grade.py
├── schemas/
├── references/
├── integrations/cursor/
├── examples/
└── tests/
```

## Release status

The current package should be published as an experimental `v0.1.0`. Feedback is especially valuable on rubric calibration, rating consistency, and whether the improvement guidance helps authors make concrete decisions.
