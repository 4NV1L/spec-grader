#!/usr/bin/env python3
"""Model-agnostic specification grader with deterministic aggregation."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC = ROOT / "config" / "rubric.json"
CONFIDENCE_CATEGORIES = {"functional_requirements", "architecture", "interfaces_contracts", "failure_modes", "acceptance_criteria", "dependencies", "implementation_readiness", "ambiguity_testability"}
VERDICT_RANK = {"NOT-READY": 0, "READY-WITH-CHANGES": 1, "READY": 2}


class GradeError(Exception):
    pass


def http_json(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:500]
        raise GradeError(f"Provider HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GradeError(f"Provider request failed: {exc}") from exc


def extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise GradeError("Evaluator did not return a JSON object")
        text = text[start:end + 1]
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GradeError(f"Evaluator returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise GradeError("Evaluator response must be a JSON object")
    return value


class AnthropicProvider:
    def __init__(self, model: str, base_url: str, timeout: int):
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout

    def complete_json(self, system: str, prompt: str) -> dict:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise GradeError("ANTHROPIC_API_KEY is required")
        result = http_json(f"{self.base_url}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, {"model": self.model, "max_tokens": 12000, "temperature": 0, "system": system, "messages": [{"role": "user", "content": prompt}]}, self.timeout)
        text = "".join(block.get("text", "") for block in result.get("content", []) if block.get("type") == "text")
        return extract_json(text)


class OpenAICompatibleProvider:
    def __init__(self, model: str, base_url: str, timeout: int):
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout

    def complete_json(self, system: str, prompt: str) -> dict:
        key = os.environ.get("OPENAI_API_KEY", "local")
        result = http_json(f"{self.base_url}/v1/chat/completions", {"Authorization": f"Bearer {key}"}, {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, self.timeout)
        try:
            return extract_json(result["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise GradeError("Unexpected OpenAI-compatible response shape") from exc


class MockProvider:
    def __init__(self, fixtures: list[pathlib.Path]): self.fixtures, self.calls = fixtures, 0
    def complete_json(self, system: str, prompt: str) -> dict:
        fixture = self.fixtures[min(self.calls, len(self.fixtures) - 1)]
        self.calls += 1
        return json.loads(fixture.read_text())


def evaluator_prompt(rubric: dict, numbered_spec: str) -> tuple[str, str]:
    system = "You are a strict specification auditor. Output JSON only. Use only the supplied spec as evidence. Never infer missing intent. Prefer the lower adjacent rating when uncertain."
    shape = {"security_relevant": False, "categories": [{"id": "category_id", "rating": 0, "rationale": "why", "evidence": [{"location": "lines 1-2 / heading, or MISSING", "snippet": "short exact snippet or Expected evidence is absent"}]}], "issues": [{"id": "I-001", "category": "category_id", "severity": "critical|high|medium|low", "title": "concise gap", "evidence": {"location": "lines/heading or MISSING", "snippet": "short snippet or Expected evidence is absent"}, "remediation": "specific change"}]}
    prompt = "Rate every category exactly once from 0 to 4 using the scale and guidance. A promise to define something later scores at most 1. Every issue must cite evidence or MISSING. Set security_relevant as defined in the rubric.\n\nRUBRIC:\n" + json.dumps({"scale": rubric["scale"], "categories": rubric["categories"]}, indent=2) + "\n\nRESPONSE SHAPE:\n" + json.dumps(shape, indent=2) + "\n\nLINE-NUMBERED SPEC:\n" + numbered_spec
    return system, prompt


def improvement_prompt(spec_text: str, report: dict, rubric: dict) -> tuple[str, str]:
    system = "You improve specifications without inventing facts. Output JSON only. Preserve product intent and existing requirements. Clearly mark unresolved decisions instead of guessing."
    shape = {"improved_spec": "complete revised Markdown", "changes": [{"category": "rubric category id", "summary": "what changed", "rationale": "why it improves implementation readiness", "source": "existing-evidence|safe-clarification|proposed-assumption|user-decision-required"}], "assumptions": [{"text": "proposed assumption", "status": "needs-confirmation"}], "questions": [{"category": "category id", "question": "specific question", "why_needed": "what cannot be safely specified without it"}]}
    prompt = "Revise the complete spec to address the score-improvement plan. You may reorganize and clarify existing content. Do not fabricate research, metrics, policies, user decisions, system behavior, or architecture choices. Put unresolved matters in an 'Open Questions' section and return them in questions. Label any suggested assumption as unconfirmed. Every change must name its provenance using one of the allowed source values. Return the entire improved Markdown spec.\n\nRUBRIC:\n" + json.dumps(rubric["categories"], indent=2) + "\n\nGRADE REPORT:\n" + json.dumps(report, indent=2) + "\n\nRESPONSE SHAPE:\n" + json.dumps(shape, indent=2) + "\n\nORIGINAL SPEC:\n" + spec_text
    return system, prompt


def validate_improvement(value: dict, rubric: dict) -> None:
    ids = {c["id"] for c in rubric["categories"]}
    if not isinstance(value.get("improved_spec"), str) or not value["improved_spec"].strip(): raise GradeError("Improver returned no revised spec")
    if not isinstance(value.get("changes"), list) or not isinstance(value.get("assumptions"), list) or not isinstance(value.get("questions"), list): raise GradeError("Improver response lacks changes, assumptions, or questions")
    sources = {"existing-evidence", "safe-clarification", "proposed-assumption", "user-decision-required"}
    for change in value["changes"]:
        if change.get("category") not in ids or change.get("source") not in sources or not change.get("summary") or not change.get("rationale"): raise GradeError("Invalid improvement change record")
    for question in value["questions"]:
        if question.get("category") not in ids or not question.get("question") or not question.get("why_needed"): raise GradeError("Invalid improvement question")


def improvement_markdown(before: dict, after: dict, improvement: dict) -> str:
    lines = ["# Spec Improvement Report", "", "This report is an authoring aid. Confirm unresolved decisions before treating the revised draft as implementation-ready.", "", "## Decisions needed from the author", ""]
    lines += ([f"- **{q['category']}:** {q['question']} — {q['why_needed']}" for q in improvement["questions"]] or ["None."])
    lines += ["", "## Assumptions to confirm", ""] + ([f"- {a['text']}" for a in improvement["assumptions"]] or ["None."])
    lines += ["", "## Improvements made", ""]
    for change in improvement["changes"]: lines += [f"- **{change['summary']}** (`{change['source']}`): {change['rationale']}"]
    lines += ["", "## Progress indicators", "", f"**Before: {before['score']}/100 · {before['verdict']}**  ", f"**After: {after['score']}/100 · {after['verdict']}**  ", f"Draft-quality change: **{after['score'] - before['score']:+d} points**", "", "The score measures rubric coverage and clarity; it is not a certification of factual correctness.", "", "### Category movement", "", "| Category | Before | After | Change |", "|---|---:|---:|---:|"]
    after_by_id = {c["id"]: c for c in after["categories"]}
    for old in before["categories"]:
        new = after_by_id[old["id"]]
        lines.append(f"| {old['label']} | {old['rating']}/4 | {new['rating']}/4 | {new['score'] - old['score']:+.2f} pts |")
    lines += ["", "## Remaining readiness blockers", ""] + ([f"- **{g['id']}:** {g['reason']}" for g in after["gate_failures"]] or ["None."])
    return "\n".join(lines)


def validate_observations(obs: dict, rubric: dict) -> None:
    expected = [c["id"] for c in rubric["categories"]]
    categories = obs.get("categories")
    if not isinstance(categories, list) or [c.get("id") for c in categories] != expected:
        raise GradeError("Evaluator categories must appear exactly once in rubric order")
    for category in categories:
        if type(category.get("rating")) is not int or not 0 <= category["rating"] <= 4:
            raise GradeError(f"Invalid rating for {category.get('id')}")
        if not isinstance(category.get("rationale"), str) or not isinstance(category.get("evidence"), list):
            raise GradeError(f"Invalid rationale/evidence for {category['id']}")
    for issue in obs.get("issues", []):
        if issue.get("category") not in expected or issue.get("severity") not in rubric["severity"]:
            raise GradeError(f"Invalid issue category/severity: {issue.get('id', '?')}")
        ev = issue.get("evidence", {})
        if not ev.get("location") or not ev.get("snippet") or not issue.get("remediation"):
            raise GradeError(f"Issue lacks evidence/remediation: {issue.get('id', '?')}")


def grade_observations(obs: dict, rubric: dict, source: str, generated_at: str | None = None) -> dict:
    validate_observations(obs, rubric)
    by_id = {item["id"]: item for item in obs["categories"]}
    categories, raw = [], 0.0
    for rule in rubric["categories"]:
        item = by_id[rule["id"]]
        contribution = rule["weight"] * item["rating"] / 4
        raw += contribution
        categories.append({"id": rule["id"], "label": rule["label"], "weight": rule["weight"], "rating": item["rating"], "score": round(contribution, 2), "rationale": item["rationale"], "evidence": item["evidence"]})
    raw = round(raw, 2)
    gates = []
    for gate in rubric["gates"]:
        conditional = gate.get("conditional_flag")
        if by_id[gate["category"]]["rating"] <= gate["trigger_max_rating"] and (not conditional or obs.get(conditional) is True):
            gates.append({"id": gate["id"], "reason": gate["description"], "score_cap": gate["score_cap"], "verdict_cap": gate["verdict_cap"]})
    score = min([round(raw)] + [g["score_cap"] for g in gates])
    grade = next(g["grade"] for g in rubric["grades"] if score >= g["min"])
    relevant = [c for c in categories if c["id"] in CONFIDENCE_CATEGORIES]
    confidence = sum(c["score"] for c in relevant) / sum(c["weight"] for c in relevant) * 100
    penalties = {"critical": 12, "high": 6, "medium": 2, "low": 0}
    confidence = round(max(0, min(100, confidence - sum(penalties[i["severity"]] for i in obs.get("issues", [])))))
    if score >= rubric["verdicts"]["READY"]["min_score"] and confidence >= rubric["verdicts"]["READY"]["min_confidence"]: verdict = "READY"
    elif score >= rubric["verdicts"]["READY-WITH-CHANGES"]["min_score"] and confidence >= rubric["verdicts"]["READY-WITH-CHANGES"]["min_confidence"]: verdict = "READY-WITH-CHANGES"
    else: verdict = "NOT-READY"
    for gate in gates:
        if VERDICT_RANK[verdict] > VERDICT_RANK[gate["verdict_cap"]]: verdict = gate["verdict_cap"]
    gate_categories = {g["category"] for g in rubric["gates"] if any(f["id"] == g["id"] for f in gates)}
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    improvements = []
    for rule in rubric["categories"]:
        category = by_id[rule["id"]]
        if category["rating"] >= 4:
            continue
        related = [i for i in obs.get("issues", []) if i["category"] == rule["id"]]
        actions = [i["remediation"] for i in sorted(related, key=lambda i: severity_rank[i["severity"]], reverse=True)]
        if not actions:
            actions = [f"Add explicit, measurable evidence so this section satisfies: {rule['guidance']}"]
        improvements.append({
            "category": rule["id"], "label": rule["label"], "current_rating": category["rating"],
            "target_rating": category["rating"] + 1, "potential_point_gain": round(rule["weight"] / 4, 2),
            "clears_gate": rule["id"] in gate_categories, "rubric_target": rule["guidance"], "actions": actions
        })
    improvements.sort(key=lambda x: (not x["clears_gate"], -max([severity_rank[i["severity"]] for i in obs.get("issues", []) if i["category"] == x["category"]] or [0]), -x["potential_point_gain"], x["category"]))
    return {"schema_version": "1.0.0", "source": source, "rubric_version": rubric["version"], "generated_at": generated_at or datetime.now(timezone.utc).isoformat(), "score": score, "raw_score": raw, "grade": grade, "verdict": verdict, "autonomous_implementation_confidence": confidence, "gate_failures": gates, "categories": categories, "issues": obs.get("issues", []), "score_improvement_plan": improvements}


def markdown_report(report: dict) -> str:
    lines = [f"# Spec Evaluation: {pathlib.Path(report['source']).name}", "", "This evaluation is an authoring aid: use it to clarify the draft, expose missing decisions, and improve implementation readiness.", "", "## Where to focus next", "", "Work top-to-bottom. Potential gain is a secondary indicator of rubric coverage, not the purpose of the edit.", ""]
    for index, item in enumerate(report["score_improvement_plan"], 1):
        gate = " **Resolves a current readiness blocker.**" if item["clears_gate"] else ""
        lines += [f"### {index}. {item['label']}: {item['current_rating']}/4 → {item['target_rating']}/4 (+{item['potential_point_gain']} points)", "", f"Target: {item['rubric_target']}{gate}", "", "Actions:"]
        lines += [f"- {action}" for action in item["actions"]]
        lines.append("")
    lines += ["", "## Improvement opportunities", ""]
    if not report["issues"]: lines.append("No improvement opportunities reported.")
    for issue in sorted(report["issues"], key=lambda x: ["critical", "high", "medium", "low"].index(x["severity"])):
        ev = issue["evidence"]
        lines += [f"### {issue['id']} · {issue['severity'].upper()} · {issue['title']}", "", f"Category: `{issue['category']}`  ", f"Evidence: {ev['location']} — “{ev['snippet']}”  ", f"Suggested improvement: {issue['remediation']}", ""]
    lines += ["## Readiness blockers", ""]
    lines += ([f"- **{g['id']}** — {g['reason']} (score cap {g['score_cap']}, verdict cap {g['verdict_cap']})" for g in report["gate_failures"]] or ["None."])
    lines += ["", "## Draft-quality indicators", "", f"**{report['score']}/100 · {report['grade']} · {report['verdict']}**", "", f"Autonomous implementation confidence: **{report['autonomous_implementation_confidence']}%**  ", f"Raw rubric score before blocker caps: {report['raw_score']}", "", "### Category scores", "", "| Category | Weight | Rating | Points |", "|---|---:|---:|---:|"]
    lines += [f"| {c['label']} | {c['weight']} | {c['rating']}/4 | {c['score']} |" for c in report["categories"]]
    lines += ["", "## Why each category received its rating", ""]
    for c in report["categories"]: lines += [f"- **{c['label']} ({c['rating']}/4):** {c['rationale']}"]
    return "\n".join(lines) + "\n"


def provider_from_args(args):
    if args.provider == "mock":
        fixtures = [pathlib.Path(args.fixture or ROOT / "tests" / "fixtures" / "evaluator_response.json")]
        if args.improve:
            fixtures += [pathlib.Path(args.improvement_fixture or ROOT / "tests" / "fixtures" / "improvement_response.json"), pathlib.Path(args.regrade_fixture or ROOT / "tests" / "fixtures" / "improved_evaluator_response.json")]
        return MockProvider(fixtures)
    if not args.model: raise GradeError("--model is required for non-mock providers")
    if args.provider == "anthropic": return AnthropicProvider(args.model, args.base_url or "https://api.anthropic.com", args.timeout)
    return OpenAICompatibleProvider(args.model, args.base_url or "https://api.openai.com", args.timeout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spec-grade", description="Grade a Markdown specification")
    parser.add_argument("spec", type=pathlib.Path); parser.add_argument("--provider", choices=["anthropic", "openai-compatible", "mock"], default=os.environ.get("SPEC_GRADE_PROVIDER", "openai-compatible")); parser.add_argument("--model", default=os.environ.get("SPEC_GRADE_MODEL")); parser.add_argument("--base-url", default=os.environ.get("SPEC_GRADE_BASE_URL")); parser.add_argument("--rubric", type=pathlib.Path, default=DEFAULT_RUBRIC); parser.add_argument("--fixture"); parser.add_argument("--improvement-fixture"); parser.add_argument("--regrade-fixture"); parser.add_argument("--output-dir", type=pathlib.Path); parser.add_argument("--json", action="store_true", help="Print JSON to stdout instead of writing files"); parser.add_argument("--improve", action="store_true", help="Revise, independently regrade, and produce a before/after report"); parser.add_argument("--fail-on", choices=["not-ready", "ready-with-changes"]); parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        spec_text = args.spec.read_text(); rubric = json.loads(args.rubric.read_text())
        if args.spec.suffix.lower() not in {".md", ".markdown"}: raise GradeError("Input must be a Markdown file")
        if sum(c["weight"] for c in rubric["categories"]) != 100: raise GradeError("Rubric weights must total 100")
        numbered = "\n".join(f"{i:04d}: {line}" for i, line in enumerate(spec_text.splitlines(), 1))
        system, prompt = evaluator_prompt(rubric, numbered); provider = provider_from_args(args)
        report = grade_observations(provider.complete_json(system, prompt), rubric, str(args.spec))
        improvement = after = None
        if args.improve:
            improve_system, improve_prompt = improvement_prompt(spec_text, report, rubric)
            improvement = provider.complete_json(improve_system, improve_prompt); validate_improvement(improvement, rubric)
            improved_numbered = "\n".join(f"{i:04d}: {line}" for i, line in enumerate(improvement["improved_spec"].splitlines(), 1))
            regrade_system, regrade_prompt = evaluator_prompt(rubric, improved_numbered)
            after = grade_observations(provider.complete_json(regrade_system, regrade_prompt), rubric, str(args.spec.with_name(args.spec.stem + ".improved.md")))
        bundle = None
        if improvement:
            bundle = {"schema_version": "1.0.0", "before": report, "after": after, "changes": improvement["changes"], "assumptions": improvement["assumptions"], "questions": improvement["questions"]}
        if args.json: print(json.dumps(bundle or report, indent=2))
        else:
            out = args.output_dir or args.spec.parent; out.mkdir(parents=True, exist_ok=True)
            stem = args.spec.stem + ".grade"
            (out / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
            (out / f"{stem}.md").write_text(markdown_report(report))
            if improvement:
                (out / f"{args.spec.stem}.improved.md").write_text(improvement["improved_spec"].rstrip() + "\n")
                (out / f"{args.spec.stem}.improvement.json").write_text(json.dumps(bundle, indent=2) + "\n")
                (out / f"{args.spec.stem}.improvement.md").write_text(improvement_markdown(report, after, improvement))
                (out / f"{args.spec.stem}.improved.grade.json").write_text(json.dumps(after, indent=2) + "\n")
                (out / f"{args.spec.stem}.improved.grade.md").write_text(markdown_report(after))
            summary = f"{report['score']}/100 {report['grade']} {report['verdict']}"
            if after: summary += f" -> {after['score']}/100 {after['grade']} {after['verdict']}"
            print(f"{summary}\n{out / (stem + '.md')}\n{out / (stem + '.json')}")
        threshold_report = after or report
        if args.fail_on == "not-ready" and threshold_report["verdict"] == "NOT-READY": return 2
        if args.fail_on == "ready-with-changes" and threshold_report["verdict"] != "READY": return 2
        return 0
    except (OSError, ValueError, GradeError) as exc:
        print(f"spec-grade: {exc}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
