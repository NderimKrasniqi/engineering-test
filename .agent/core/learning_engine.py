#!/usr/bin/env python3
"""Engineering Stack Stage 2: evidenced learning, guard replay, future-task observations.

This module is local project tooling, NOT a proof of autonomous model learning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LAYERS = ('architecture', 'types', 'static-check', 'test', 'workflow', 'instruction')
CASE_ID = re.compile(r'^L-[a-f0-9]{12}$')
TASK_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')

class LearningProblem(Exception):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise LearningProblem(f'Cannot read {path}: {exc}') from exc


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def store(root: Path) -> Path:
    return root / '.agent/learning'


def case_path(root: Path, case_id: str) -> Path:
    if not CASE_ID.fullmatch(case_id):
        raise LearningProblem('Bad learning case id')
    return store(root) / 'cases' / (case_id + '.json')


def get_case(root: Path, case_id: str):
    result = load(case_path(root, case_id))
    if not isinstance(result, dict) or result.get('id') != case_id:
        raise LearningProblem('Invalid case record')
    return result


def cases(root: Path):
    folder = store(root) / 'cases'
    return [load(path) for path in sorted(folder.glob('L-*.json'))] if folder.exists() else []


def safe_relative(root: Path, value: str, *, must_exist=True) -> Path:
    """Allow a project file, not a traversal or symlink path escaping the project."""
    if not isinstance(value, str) or not value or '\x00' in value:
        raise LearningProblem('Expected a non-empty relative path')
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts or rel.as_posix() in ('.', ''):
        raise LearningProblem('Path must be project-relative, without traversal')
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise LearningProblem('Path escapes project root')
    if must_exist and not target.is_file():
        raise LearningProblem(f'File does not exist: {value}')
    return target


def evidence_file(root: Path, value: str) -> Path:
    target = safe_relative(root, value)
    expected = (store(root).parent / 'runs').resolve()
    if not target.is_relative_to(expected):
        raise LearningProblem('Reuse evidence must be a verification run under .agent/runs')
    return target


def scan(root: Path, quiet=False):
    """Flag same check/output repeated at distinct workspace states; never infer root cause."""
    path = store(root) / 'events.jsonl'
    events = []
    if path.exists():
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise LearningProblem(f'Malformed learning event line {number}: {exc}') from exc
            if not isinstance(item, dict):
                raise LearningProblem(f'Learning event line {number} is not an object')
            events.append(item)
    groups = defaultdict(list)
    for e in events:
        if (e.get('kind') == 'verification-failure' and not e.get('expected_red')
                and isinstance(e.get('workspace_sha256'), str)
                and len(e['workspace_sha256']) == 64 and isinstance(e.get('check_id'), str)
                and isinstance(e.get('output_sha256'), str)):
            groups[(e['check_id'], e['output_sha256'])].append(e)
    added = []
    for (check_id, output_hash), group in groups.items():
        states = {e['workspace_sha256'] for e in group}
        run_ids = {e.get('run_id') for e in group if e.get('run_id')}
        if len(states) < 2 or len(run_ids) < 2:
            continue
        case_id = 'L-' + digest(canonical([check_id, output_hash]))[:12]
        path = case_path(root, case_id)
        if path.exists():
            case = get_case(root, case_id)
            # Do not overwrite a human/agent diagnosis or decision on rescanning.
            continue
        refs = sorted({e['evidence'] for e in group if isinstance(e.get('evidence'), str)})
        source_tasks = sorted({e['task_id'] for e in group if isinstance(e.get('task_id'), str)})
        case = {
            'schema_version': 1, 'id': case_id, 'status': 'candidate', 'source': 'repeated-failed-check',
            'created_at': utc(), 'impact': 'unassessed', 'check_id': check_id,
            'output_sha256': output_hash, 'distinct_workspace_states': len(states),
            'source_tasks': source_tasks, 'source_evidence': refs,
            'note': 'Candidate only. Same output in changed workspaces does not establish root cause.'
        }
        save(path, case)
        added.append(case_id)
    if not quiet:
        print(f'Failure events: {len(events)} | learning cases: {len(cases(root))} | new candidates: {len(added)}')
        for item in added:
            print('CANDIDATE', item, 'requires triage')
    return added


def incident(root: Path, impact: str, summary: str, evidence: str, task_id: str | None):
    if impact not in ('high', 'critical'):
        raise LearningProblem('Manual incident must be high or critical impact')
    if len(summary.strip()) < 12:
        raise LearningProblem('Incident summary must be specific')
    if task_id and not TASK_ID.fullmatch(task_id):
        raise LearningProblem('Bad task id')
    file = safe_relative(root, evidence)
    case_id = 'L-' + uuid.uuid4().hex[:12]
    case = {
        'schema_version': 1, 'id': case_id, 'status': 'candidate',
        'source': 'high-impact-incident', 'created_at': utc(), 'impact': impact,
        'summary': summary.strip(), 'source_tasks': [task_id] if task_id else [],
        'source_evidence': [evidence], 'incident_evidence_sha256': digest(file.read_bytes()),
        'note': 'Reported incident, not a verified root cause.'
    }
    save(case_path(root, case_id), case)
    return case_id


def triage(root: Path, case_id: str, decision: str, reason: str):
    case = get_case(root, case_id)
    if case['status'] != 'candidate':
        raise LearningProblem('Only candidate cases can be triaged')
    if decision not in ('investigate', 'defer') or len(reason.strip()) < 15:
        raise LearningProblem('Choose investigate/defer and supply a meaningful reason')
    if decision == 'defer' and case.get('impact') == 'critical':
        raise LearningProblem('Critical incidents cannot be deferred by this tool')
    case['triage'] = {'decision': decision, 'reason': reason.strip(), 'at': utc()}
    case['status'] = 'investigating' if decision == 'investigate' else 'deferred'
    save(case_path(root, case_id), case)


def validate_argv(argv):
    if (not isinstance(argv, list) or not argv or len(argv) > 24 or
        any(not isinstance(x, str) or not x or '\x00' in x for x in argv)):
        raise LearningProblem('Guard argv must be a nonempty JSON string list (max 24 items)')
    if any(x in ('sh', 'bash', 'zsh', 'fish', '-c') for x in argv[:2]):
        raise LearningProblem('Use a direct check command, not a shell wrapper')


def propose(root: Path, case_id: str, cause: str, layer: str, guard_path: str, argv: list[str]):
    case = get_case(root, case_id)
    if case.get('status') != 'investigating':
        raise LearningProblem('Triage case for investigation before proposing a guard')
    if len(cause.strip()) < 20 or layer not in LAYERS:
        raise LearningProblem('Supply a concrete root cause and valid control layer')
    guard = safe_relative(root, guard_path)
    if guard.stat().st_size > 2 * 1024 * 1024:
        raise LearningProblem('Guard file exceeds 2 MB')
    validate_argv(argv)
    case['proposal'] = {'root_cause': cause.strip(), 'control_layer': layer,
                        'guard_path': guard_path, 'guard_argv': argv, 'at': utc()}
    case['status'] = 'proposed'
    save(case_path(root, case_id), case)


def guard_digest(root: Path, case):
    proposal = case.get('proposal') or {}
    guard = safe_relative(root, proposal.get('guard_path', ''))
    return digest(guard.read_bytes())


def run_guard(root: Path, argv: list[str]):
    try:
        result = subprocess.run(argv, cwd=root, capture_output=True, timeout=90, check=False)
        return {'exit_code': result.returncode, 'status': 'executed',
                'output_sha256': digest(result.stdout + b'\0' + result.stderr)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'exit_code': None, 'status': type(exc).__name__, 'output_sha256': digest(str(exc).encode())}


def prove(root: Path, case_id: str, bad_root: Path, good_root: Path):
    case = get_case(root, case_id)
    if case.get('status') != 'proposed':
        raise LearningProblem('First propose a guard for the investigated case')
    bad_root = bad_root.resolve(); good_root = good_root.resolve(); root = root.resolve()
    if (bad_root == good_root or root in (bad_root, good_root) or
            not bad_root.is_dir() or not good_root.is_dir()):
        raise LearningProblem('Provide two distinct isolated bad/good fixture roots, not the live project')
    proposal = case['proposal']
    control_sha = guard_digest(root, case)
    for label, folder in (('bad', bad_root), ('good', good_root)):
        actual = safe_relative(folder, proposal['guard_path'])
        if digest(actual.read_bytes()) != control_sha:
            raise LearningProblem(f'{label} fixture does not contain exactly the current guard file')
    bad = run_guard(bad_root, proposal['guard_argv'])
    good = run_guard(good_root, proposal['guard_argv'])
    passed = (bad['status'] == good['status'] == 'executed'
              and bad['exit_code'] != 0 and good['exit_code'] == 0)
    proof = {'schema_version': 1, 'case_id': case_id, 'at': utc(),
             'created_ns': time.time_ns(), 'guard_sha256': control_sha,
             'proposal_sha256': digest(canonical(proposal)),
             'bad_fixture': str(bad_root), 'good_fixture': str(good_root),
             'bad': bad, 'good': good, 'passed': passed,
             'limitation': 'Exit-code differential only; inspect that bad failure is the intended regression.'}
    path = store(root) / 'proofs' / case_id / (str(proof['created_ns']) + '.json')
    save(path, proof)
    case['latest_proof'] = path.relative_to(root).as_posix()
    # If failure, remain proposed so the agent has to repair/re-prove.
    save(case_path(root, case_id), case)
    return passed, path


def verified_proof(root: Path, case):
    if not case.get('proposal') or not case.get('latest_proof'):
        raise LearningProblem('Missing proposed control or proof')
    proof = load(safe_relative(root, case['latest_proof']))
    if proof.get('case_id') != case['id'] or not proof.get('passed'):
        raise LearningProblem('Guard has no passing bad/good proof')
    if proof.get('guard_sha256') != guard_digest(root, case):
        raise LearningProblem('Guard file changed after proof; re-prove before promotion/reuse')
    if proof.get('proposal_sha256') != digest(canonical(case['proposal'])):
        raise LearningProblem('Control proposal changed after proof')
    return proof


def active_guard_check(root: Path, case):
    """Find an enabled, low-risk check that actually invokes the proven guard."""
    from engine import checks, Problem
    proposal=case.get('proposal') or {}
    try:
        _, configured=checks(root)
    except Problem as exc:
        raise LearningProblem('Cannot verify active guard registration: '+str(exc)) from exc
    suitable=[row for row in configured if row['argv']==proposal.get('guard_argv')
              and row.get('min_risk','low')=='low']
    if len(suitable)!=1:
        raise LearningProblem('Promoted guard requires exactly one low-risk project check with its proven argv')
    return suitable[0]['id']


def promote(root: Path, case_id: str):
    case = get_case(root, case_id)
    if case.get('status') != 'proposed':
        raise LearningProblem('Only a proposed case can be promoted')
    verified_proof(root, case)
    case['active_check_id']=active_guard_check(root,case)
    case['status'] = 'enforced'
    case['enforced_at'] = utc()
    case['reuse_observations'] = []
    save(case_path(root, case_id), case)


def observe_reuse(root: Path, case_id: str, task_id: str, evidence: str, notes: str):
    case = get_case(root, case_id)
    if case.get('status') != 'enforced':
        raise LearningProblem('Case must have a promoted, proven guard')
    if not TASK_ID.fullmatch(task_id) or task_id in case.get('source_tasks', []):
        raise LearningProblem('Reuse needs a different future task from the source tasks')
    if len(notes.strip()) < 15:
        raise LearningProblem('Explain how the guard related to this later task')
    proof = verified_proof(root, case)
    if case.get('active_check_id')!=active_guard_check(root,case):
        raise LearningProblem('The promoted guard is no longer registered as the same project check')
    path = evidence_file(root, evidence)
    record = load(path)
    if (record.get('task_id') != task_id or not record.get('passed') or not record.get('workspace_stable')
            or not isinstance(record.get('workspace_sha256'), str)
            or not isinstance(record.get('task_sha256'), str)
            or not isinstance(record.get('checks_sha256'), str)
            or not isinstance(record.get('checks'), list) or not record['checks']
            or any(check.get('status') != 'passed' for check in record['checks'])):
        raise LearningProblem('Reuse evidence must be a full, passing verification run for this task')
    from engine import tasks, Problem
    try:
        registry, normalized=tasks(root)
    except Problem as exc:
        raise LearningProblem('Cannot verify the future task completion: '+str(exc)) from exc
    completed=any(row['id']==task_id and row['status'] in ('done','completed') for row in normalized)
    if isinstance(registry.get('tasks'),list):
        completed=completed and any(row.get('id')==task_id and row.get('verification_evidence')==evidence
                                    for row in registry['tasks'])
    else:
        # Canonical product workflow stores checked completion in the Markdown plan,
        # and verification evidence only under .agent/runs/<task>/<run-id>.json.
        directory=(root/'.agent/runs'/task_id).resolve()
        completed=completed and path.parent==directory and path.stem==record.get('run_id')
        current=sorted(p for p in directory.glob('*.json') if re.fullmatch(r'\d{8}T\d{6}Z-\d+-[0-9a-f]{8}',p.stem))
        completed=completed and bool(current) and current[-1]==path
    if not completed:
        raise LearningProblem('Future task must be finished in product task registry with the exact evidence path')
    if not any(row.get('id')==case['active_check_id'] and row.get('status')=='passed'
               for row in record['checks']):
        raise LearningProblem('Future task verification did not execute the promoted regression guard')
    if path.stat().st_mtime_ns <= proof['created_ns']:
        raise LearningProblem('Reuse verification must be generated after the guard proof')
    if any(entry.get('task_id') == task_id for entry in case.get('reuse_observations', [])):
        raise LearningProblem('Reuse for this later task was already recorded')
    case.setdefault('reuse_observations', []).append({
        'task_id': task_id, 'evidence': evidence, 'evidence_sha256': digest(path.read_bytes()),
        'notes': notes.strip(), 'at': utc(), 'level': 'observed-not-causal'
    })
    save(case_path(root, case_id), case)


def unresolved_for_task(root: Path, task_id: str):
    return [c['id'] for c in cases(root)
            if task_id in c.get('source_tasks', [])
            and c.get('status') in ('candidate', 'investigating', 'proposed')]


def status(root: Path):
    items = cases(root)
    print('Learning cases:', len(items))
    for case in items:
        state = case.get('status', 'unknown')
        if state == 'enforced':
            try:
                verified_proof(root, case)
            except LearningProblem:
                state += ' (STALE: guard changed or proof unavailable)'
        print(case['id'], state, 'reuse observations:', len(case.get('reuse_observations', [])))
    print('Reuse observations do not prove a causal improvement. Compare blinded runs in Stage 3.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('scan'); sub.add_parser('status')
    q = sub.add_parser('incident');q.add_argument('--impact', choices=['high', 'critical'], required=True)
    q.add_argument('--summary', required=True);q.add_argument('--evidence', required=True);q.add_argument('--task')
    q = sub.add_parser('triage');q.add_argument('case');q.add_argument('--decision', choices=['investigate','defer'], required=True);q.add_argument('--reason', required=True)
    q = sub.add_parser('propose');q.add_argument('case');q.add_argument('--cause', required=True);q.add_argument('--layer', choices=LAYERS, required=True)
    q.add_argument('--guard-path', required=True);q.add_argument('--argv-json', required=True)
    q = sub.add_parser('prove');q.add_argument('case');q.add_argument('--bad-root', type=Path, required=True);q.add_argument('--good-root', type=Path, required=True)
    q = sub.add_parser('promote');q.add_argument('case')
    q = sub.add_parser('reuse');q.add_argument('case');q.add_argument('--task', required=True);q.add_argument('--evidence', required=True);q.add_argument('--notes', required=True)
    args = parser.parse_args(argv);root = args.root.resolve()
    try:
        if not root.is_dir():
            raise LearningProblem('Project root does not exist')
        if args.cmd == 'scan': scan(root)
        elif args.cmd == 'status': status(root)
        elif args.cmd == 'incident':print('CANDIDATE',incident(root,args.impact,args.summary,args.evidence,args.task))
        elif args.cmd == 'triage':triage(root,args.case,args.decision,args.reason);print('TRIAGED',args.case)
        elif args.cmd == 'propose':
            try: argv = json.loads(args.argv_json)
            except ValueError as exc: raise LearningProblem('argv-json must be a JSON string list') from exc
            propose(root,args.case,args.cause,args.layer,args.guard_path,argv);print('PROPOSED',args.case)
        elif args.cmd == 'prove':
            passed,path=prove(root,args.case,args.bad_root,args.good_root)
            print('PASS' if passed else 'FAIL','guard differential:',path)
            return 0 if passed else 1
        elif args.cmd == 'promote':promote(root,args.case);print('ENFORCED',args.case)
        elif args.cmd == 'reuse':observe_reuse(root,args.case,args.task,args.evidence,args.notes);print('OBSERVED (not causal proof)',args.case)
        return 0
    except LearningProblem as exc:
        print('BLOCKED:',exc,file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
