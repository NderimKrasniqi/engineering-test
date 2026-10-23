#!/usr/bin/env python3
"""Structural checks for the AI engineering workflow docs/state.

Human Markdown stays human-readable. Machine-only task dependencies, source refs,
release closure, and temporary gate state live in .workflow/tasks.json.

Fail-closed: a document that exists but defines no parseable IDs is an error,
and every reference must resolve against a document that exists.

Usage: python3 tools/validate-workflow.py [--root PATH]
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import os
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=".", help="Project root (default: current directory)")
ROOT = Path(ap.parse_args().root).resolve()
if not ROOT.is_dir():
    print(f"Workflow validation FAILED:\n\n- ERROR: project root {ROOT} does not exist")
    sys.exit(2)
DOCS = ROOT / "docs"
STATE_PATH = ROOT / ".workflow" / "tasks.json"
SKIP_DIRS = {".git", "node_modules", ".expo", "dist", "build", ".next", ".venv", "venv", "vendor", "__pycache__"}
errors: list[str] = []
warnings: list[str] = []


def canonical_numeric_id(prefix: str, digits: str) -> str:
    number = int(digits)
    width = 2 if number < 100 else len(str(number))
    return f"{prefix}-{number:0{width}d}"


def check_id_format(identifier: str) -> None:
    m = re.fullmatch(r"([A-Z]+)-(\d+)", identifier)
    if not m:
        return
    expected = canonical_numeric_id(m.group(1), m.group(2))
    if identifier != expected:
        errors.append(f"Non-canonical identifier {identifier}; use {expected}")


def strip_fences(text: str) -> tuple[str, int | None]:
    """Blank out fenced code blocks (keeping line count) so examples are not parsed as IDs.

    Returns the stripped text and the 1-based line of an unclosed fence, if any.
    """
    out: list[str] = []
    open_line: int | None = None
    for number, line in enumerate(text.split("\n"), start=1):
        if re.match(r"^\s*(```|~~~)", line):
            open_line = None if open_line else number
            out.append("")
        else:
            out.append("" if open_line else line)
    return "\n".join(out), open_line


def read_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    text, unclosed = strip_fences(path.read_text(encoding="utf-8", errors="replace"))
    if unclosed:
        errors.append(f"{path.relative_to(ROOT)} has an unclosed code fence opened at line {unclosed}; IDs after it are ignored")
    return text


def ids_from_headings(text: str | None, level: int, prefix: str) -> list[str]:
    if text is None:
        return []
    return re.findall(rf"^{'#' * level}\s+({re.escape(prefix)}-\d+)\b", text, re.M)


def check_heading_level(label: str, text: str | None, level: int, prefix: str) -> None:
    if text is None:
        return
    for hashes, ident in re.findall(rf"^(#+)\s+({re.escape(prefix)}-\d+)\b", text, re.M):
        if len(hashes) != level:
            errors.append(f"{label}: {ident} uses a level-{len(hashes)} heading; use {'#' * level} {ident} — …")


def walk_markdown(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".md"):
                yield Path(dirpath) / name


def load_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        obj = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f".workflow/tasks.json is invalid JSON: {exc}")
        return None
    if not isinstance(obj, dict) or obj.get("version") != 1 or not isinstance(obj.get("tasks"), dict):
        errors.append(".workflow/tasks.json must have {\"version\":1,\"tasks\":{...}}")
        return None
    return obj


product = read_if_exists(DOCS / "product.md")
domain = read_if_exists(DOCS / "domain.md")
specs = read_if_exists(DOCS / "specs.md")
architecture = read_if_exists(DOCS / "architecture.md")
plan = read_if_exists(DOCS / "implementation-plan.md")
state_exists = STATE_PATH.exists()
state = load_state()

# Canonical Markdown is plain Markdown: no machine-only HTML/comment syntax.
for name, text in [
    ("product.md", product), ("domain.md", domain), ("specs.md", specs),
    ("architecture.md", architecture), ("implementation-plan.md", plan),
]:
    if text is None:
        continue
    if "<!--" in text or "-->" in text:
        errors.append(f"docs/{name} contains HTML comments; keep machine metadata in .workflow/tasks.json")
    if re.search(r"<a\s+id=", text, re.I):
        errors.append(f"docs/{name} contains explicit HTML anchors; stable IDs must come from Markdown headings")

# Phase order: each artifact requires its upstream artifacts.
if any(t is not None for t in (domain, specs, architecture, plan)) and product is None:
    errors.append("Downstream docs exist but docs/product.md is missing")
if specs is not None and domain is None:
    errors.append("docs/specs.md exists but docs/domain.md is missing")
if architecture is not None and specs is None:
    errors.append("docs/architecture.md exists but docs/specs.md is missing")
if plan is not None:
    for name, text in [("specs.md", specs), ("architecture.md", architecture)]:
        if text is None:
            errors.append(f"docs/implementation-plan.md exists but docs/{name} is missing")
if plan is not None and not state_exists:
    errors.append("docs/implementation-plan.md exists but .workflow/tasks.json is missing")
if plan is None and state is not None and state.get("tasks"):
    errors.append(".workflow/tasks.json contains task state but docs/implementation-plan.md is missing")

# Product journeys: ### J-xx in product.md.
check_heading_level("docs/product.md", product, 3, "J")
journey_ids = ids_from_headings(product, 3, "J")
if product is not None and not journey_ids:
    errors.append("docs/product.md defines no journeys; use '### J-01 — <name>' headings")
if len(journey_ids) != len(set(journey_ids)):
    errors.append("Duplicate journey IDs in docs/product.md")
journeys = set(journey_ids)
for jid in journey_ids:
    check_id_format(jid)

# Domain core invariants: - **D-xx — …** bullets.
domain_ids: list[str] = []
if domain is not None:
    if not re.search(r"^## Core Invariants\s*$", domain, re.M):
        errors.append("docs/domain.md is missing ## Core Invariants")
    if not re.search(r"^## State Models\s*$", domain, re.M):
        errors.append("docs/domain.md is missing ## State Models")
    domain_ids = re.findall(r"^- \*\*(D-\d+)\s+—", domain, re.M)
    if not domain_ids:
        errors.append("docs/domain.md defines no core invariants; use '- **D-01 — <name>.** <rule>' bullets")
    stray = set(re.findall(r"^#+\s+(D-\d+)\b", domain, re.M))
    if stray:
        errors.append(f"docs/domain.md writes invariants as headings ({', '.join(sorted(stray))}); use '- **D-01 — …**' bullets")
    if len(domain_ids) != len(set(domain_ids)):
        errors.append("Duplicate core invariant IDs in docs/domain.md")
    for did in domain_ids:
        check_id_format(did)
    if len(domain_ids) > 30:
        warnings.append(f"docs/domain.md has {len(domain_ids)} core invariants; cluster transition/validation details before adding more")
domain_id_set = set(domain_ids)

# Behavioral specs: ## J-xx headings are the stable address.
check_heading_level("docs/specs.md", specs, 2, "J")
spec_ids = ids_from_headings(specs, 2, "J")
if specs is not None and not spec_ids:
    errors.append("docs/specs.md defines no journey sections; use '## J-01 — <name>' headings")
if len(spec_ids) != len(set(spec_ids)):
    errors.append("Duplicate journey IDs in docs/specs.md")
for jid in spec_ids:
    check_id_format(jid)
    if jid not in journeys:
        errors.append(f"Spec section {jid} has no matching Product Journey")
spec_id_set = set(spec_ids)

# ADRs: ### ADR-xx headings in architecture.md.
check_heading_level("docs/architecture.md", architecture, 3, "ADR")
adr_ids = ids_from_headings(architecture, 3, "ADR")
if len(adr_ids) != len(set(adr_ids)):
    errors.append("Duplicate ADR IDs in docs/architecture.md")
for aid in adr_ids:
    check_id_format(aid)
adr_id_set = set(adr_ids)


def check_ref(label: str, ref: str) -> bool:
    """Resolve one J/D/ADR reference; return False if the token is not a known kind."""
    if re.fullmatch(r"J-\d+", ref):
        check_id_format(ref)
        if ref not in journeys:
            errors.append(f"{label} references unknown journey {ref}")
        elif specs is not None and ref not in spec_id_set:
            errors.append(f"{label} references journey {ref} without a matching specs section")
    elif re.fullmatch(r"D-\d+", ref):
        check_id_format(ref)
        if ref not in domain_id_set:
            errors.append(f"{label} references unknown domain invariant {ref}")
    elif re.fullmatch(r"ADR-\d+", ref):
        check_id_format(ref)
        if ref not in adr_id_set:
            errors.append(f"{label} references unknown architecture decision {ref}")
    else:
        return False
    return True


POSITIONAL_RE = re.compile(r"\bdomain\s+(?:rules?\s+|invariants?\s+)?#?\d+(?:\s*[–-]\s*\d+)?\b", re.I)
REF_RE = re.compile(r"\b(?:J|D|ADR)-\d{2,}\b")

# Stable references in prose docs.
for label, text in [("docs/specs.md", specs), ("docs/architecture.md", architecture), ("docs/implementation-plan.md", plan)]:
    if text is None:
        continue
    if POSITIONAL_RE.search(text):
        errors.append(f"{label} uses positional domain-rule references; use stable D-xx IDs")
    if label != "docs/implementation-plan.md":
        for ref in sorted(set(REF_RE.findall(text))):
            check_ref(label, ref)

# Compact plan + machine state.
if plan is not None:
    if re.search(r"^###\s+TASK-", plan, re.M):
        errors.append("Implementation plan uses verbose TASK sections; use one checklist line per task")

    task_line_re = re.compile(r"^- \[(?P<check>[ xX])\] (?P<tid>TASK-\d{2,}) (?P<body>.+)$", re.M)
    matches = list(task_line_re.finditer(plan))
    lines = plan.split("\n")
    task_pos: dict[str, int] = {}
    task_done: dict[str, bool] = {}
    task_body: dict[str, str] = {}
    for m in matches:
        tid = m.group("tid")
        check_id_format(tid)
        if tid in task_pos:
            errors.append(f"Duplicate task ID: {tid}")
        task_pos[tid] = m.start()
        done = m.group("check").lower() == "x"
        task_done[tid] = done
        body = m.group("body").strip()
        task_body[tid] = body
        has_green = "✅" in body
        if done and not has_green:
            errors.append(f"{tid} is checked [x] but missing terminal ✅ sign-off")
        if not done and has_green:
            errors.append(f"{tid} has ✅ but is not checked [x]")
        if done and re.search(r"—\s*(In progress|Verification blocked|Changes required)\b", body, re.I):
            errors.append(f"{tid} is signed off but still carries an unfinished status suffix")

        # Acceptance line: the indented line directly under the task.
        line_no = plan.count("\n", 0, m.start())
        nxt = lines[line_no + 1] if line_no + 1 < len(lines) else ""
        done_when = re.match(r"^\s+Done when:\s*(\S.*)$", nxt)
        if not done and not done_when:
            errors.append(f"{tid} is missing an indented 'Done when: …' acceptance line")
        if done_when:
            for ref in sorted(set(REF_RE.findall(done_when.group(1)))):
                check_ref(f"{tid} Done when", ref)

    if not matches:
        errors.append("docs/implementation-plan.md defines no tasks; use '- [ ] TASK-01 <title>' lines")
    for line in lines:
        if re.search(r"\bTASK-\d+", line) and re.match(r"^\s*[-*+]\s*\[[ xX]?\]", line) and not task_line_re.match(line):
            errors.append(f"Non-canonical task line (use '- [ ] TASK-01 <title>' at column 0): {line.strip()[:80]}")

    if state is not None:
        stasks = state["tasks"]
        plan_ids = set(task_pos)
        state_ids = set(stasks)
        for tid in sorted(plan_ids - state_ids):
            errors.append(f"{tid} is missing from .workflow/tasks.json")
        for tid in sorted(state_ids - plan_ids):
            errors.append(f".workflow/tasks.json contains unknown task {tid}")

        deps_map: dict[str, set[str]] = {}
        release_gates: list[str] = []
        allowed_gate_values = {
            "implementation": {"pending", "pass", "verification_blocked", "blocked"},
            "codeReview": {"pending", "pass", "changes_required", "verify_implementation", "blocked"},
            "security": {"pending", "pass", "not_required", "blocked", "changes_required"},
            "e2e": {"pending", "pass", "not_applicable", "blocked", "changes_required"},
        }

        for tid, entry in stasks.items():
            check_id_format(tid)
            if not isinstance(entry, dict):
                errors.append(f"{tid} state must be an object")
                continue
            deps = entry.get("deps")
            refs = entry.get("refs")
            if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps):
                errors.append(f"{tid} state must have string-array deps")
                deps = []
            if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
                errors.append(f"{tid} state must have a non-empty string-array refs")
                refs = []
            deps_set = set(deps)
            deps_map[tid] = deps_set
            if len(deps) != len(deps_set):
                errors.append(f"{tid} has duplicate dependencies in .workflow/tasks.json")

            if tid in deps_set:
                errors.append(f"{tid} depends on itself")
            for dep in deps_set - {tid}:
                if not re.fullmatch(r"TASK-\d{2,}", dep):
                    errors.append(f"{tid} has invalid dependency token {dep}")
                    continue
                check_id_format(dep)
                if dep not in task_pos:
                    errors.append(f"{tid} depends on missing task {dep}")
                elif tid in task_pos and task_pos[dep] > task_pos[tid]:
                    errors.append(f"Forward dependency: {tid} depends on later task {dep}")

            for ref in refs:
                if not check_ref(tid, ref) and ref not in {"ARCH", "ENG"}:
                    errors.append(f"{tid} has unknown source reference token {ref}; use J-xx, D-xx, ADR-xx, ARCH or ENG")

            gate_flag = entry.get("releaseGate")
            if gate_flag is True:
                release_gates.append(tid)
            elif gate_flag is not None and not isinstance(gate_flag, bool):
                errors.append(f"{tid} releaseGate must be true or false")

            gates = entry.get("gates")
            if gates is not None:
                if task_done.get(tid):
                    errors.append(f"{tid} is signed off but still carries temporary gate state in .workflow/tasks.json")
                if not isinstance(gates, dict):
                    errors.append(f"{tid} gates must be an object")
                else:
                    for key, value in gates.items():
                        if not isinstance(value, str):
                            errors.append(f"{tid} gate {key} must be a string")
                        elif key not in allowed_gate_values:
                            errors.append(f"{tid} has unknown gate {key}")
                        elif value not in allowed_gate_values[key]:
                            errors.append(f"{tid} has invalid {key} gate value {value}")

        # Active/done tasks cannot outrun dependencies.
        for tid, deps in deps_map.items():
            if tid not in task_done:
                continue
            active_suffix = re.search(r"—\s*(In progress|Verification blocked|Changes required)\b", task_body.get(tid, ""), re.I)
            if task_done[tid] or active_suffix:
                unfinished = sorted(d for d in deps if d in task_done and not task_done[d])
                if unfinished:
                    state_name = "signed off" if task_done[tid] else active_suffix.group(1)
                    errors.append(f"{tid} is {state_name} but dependency task(s) are unfinished: {', '.join(unfinished)}")

        # Exactly one release closure task and it must join all branches.
        if matches:
            if len(release_gates) != 1:
                errors.append(f"Implementation plan must declare exactly one releaseGate task in .workflow/tasks.json; found {len(release_gates)}")
            else:
                gate = release_gates[0]

                def ancestors(tid: str) -> set[str]:
                    seen: set[str] = set()
                    stack = list(deps_map.get(tid, set()))
                    while stack:
                        dep = stack.pop()
                        if dep in seen or dep not in deps_map:
                            continue
                        seen.add(dep)
                        stack.extend(deps_map[dep])
                    return seen
                outside = sorted(set(task_pos) - {gate} - ancestors(gate))
                if outside:
                    errors.append(f"Release gate {gate} does not transitively require all plan tasks: {', '.join(outside)}")

    current_match = re.search(r"^\*\*Current:\*\*\s*(.+)$", plan, re.M)
    if current_match:
        ids = re.findall(r"TASK-\d{2,}", current_match.group(1))
        if ids:
            current = ids[0]
            if current not in task_pos:
                errors.append(f"Current task references missing task {current}")
            elif task_done.get(current):
                errors.append(f"Current task {current} is already signed off")

# Soft document-size budgets.
DOC_BUDGETS = {
    "product.md": 8 * 1024,
    "domain.md": 16 * 1024,
    "specs.md": 16 * 1024,
    "architecture.md": 16 * 1024,
    "implementation-plan.md": 16 * 1024,
}
for name, budget in DOC_BUDGETS.items():
    path = DOCS / name
    if path.exists() and path.stat().st_size > budget:
        warnings.append(f"{path.relative_to(ROOT)} is {path.stat().st_size} bytes, above soft budget {budget}; compress duplication before splitting")
if STATE_PATH.exists() and STATE_PATH.stat().st_size > 16 * 1024:
    warnings.append(f".workflow/tasks.json is {STATE_PATH.stat().st_size} bytes; keep machine task state compact and avoid duplicating titles/acceptance prose")

# One source of truth per concern: no competing docs.
competing_paths = [
    DOCS / "project-scope.md", DOCS / "tech-stack.md", DOCS / "decisions.md",
    DOCS / "domain", DOCS / "specs", DOCS / "adr",
]
for path in competing_paths:
    if path.is_file():
        errors.append(f"Competing source of truth exists: {path.relative_to(ROOT)}")
    elif path.is_dir() and any(path.rglob("*.md")):
        errors.append(f"Fragmented competing source of truth exists: {path.relative_to(ROOT)}/")

competing_ref_pattern = re.compile(r"docs/(?:project-scope\.md|tech-stack\.md|decisions\.md|domain/|specs/|adr/)")
for path in sorted(walk_markdown(ROOT)):
    if competing_ref_pattern.search(path.read_text(encoding="utf-8", errors="replace")):
        errors.append(f"Reference to a competing docs source remains in {path.relative_to(ROOT)}")

if not errors:
    print("Workflow structural validation passed.")
else:
    print("Workflow validation FAILED:\n")
    for error in errors:
        print(f"- ERROR: {error}")
if warnings:
    print("\nWarnings:")
    for warning in warnings:
        print(f"- {warning}")
if all(t is None for t in (product, domain, specs, architecture, plan)):
    print("\nNo workflow artifacts exist yet; nothing else to validate.")
sys.exit(1 if errors else 0)
