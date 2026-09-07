# Architecture and roadmap

## Invocation flow

`spec-grade SPEC.md` loads and numbers the spec, loads the versioned rubric, asks one provider for structured observations, validates the response, computes scores/gates/confidence/verdict locally, and renders JSON plus Markdown from one canonical report object.

With `--improve`, the same provider creates a complete proposed revision plus provenance-tagged changes, assumptions, and questions. The engine then sends the revised spec through a fresh grading call and emits a before/after report. CI thresholds apply to the regraded revision. A higher score never converts unconfirmed assumptions into facts.

Providers implement one operation: accept a system instruction and prompt, then return a JSON object. `AnthropicProvider` uses Messages API; `OpenAICompatibleProvider` uses `/v1/chat/completions`, covering OpenAI and local servers such as Ollama, LM Studio, llama.cpp, or vLLM. HTTP uses only the Python standard library. Provider output never controls arithmetic.

## Extension points

- Add a provider without modifying scoring by implementing `complete_json`.
- Version or replace `config/rubric.json`; keep category IDs stable for trend reporting.
- Add gates as data when they depend on category ratings; add an engine rule for richer predicates.
- CI consumes exit status and the stable JSON schema.
- A future CTF companion can call the CLI or import `grade_spec`, store report JSON, and render its own UI.

## Recommended phases

1. **v1:** single-spec grading, Anthropic/OpenAI-compatible providers, deterministic score/gates, Markdown/JSON, CI exits.
2. **Calibration:** benchmark fixtures, human labels, rubric versioning, prompt/model lockfiles, variance tracking.
3. **Codebase-aware:** resolve claimed files/APIs/tests against a repository and report traceability separately from spec quality.
4. **Consensus:** parallel blinded evaluators, per-category median, disagreement flags, and adjudication, retaining local deterministic aggregation.
5. **Product/CI:** companion-app API, annotations, baselines, regression thresholds, waivers with owner/expiry, and SARIF or check-run output.
