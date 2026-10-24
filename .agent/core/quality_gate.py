#!/usr/bin/env python3
"""Evidence-linked engineering review for the v16 task gate.

The review is an agent judgment, NOT an independent security audit.
The tool verifies integrity, completeness, and evidence references only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DIMENSIONS = ("readability", "maintainability", "security", "reliability", "scalability", "compatibility")
CATEGORIES = ("e2e", "edge", "test", "static", "security", "build", "integration", "performance", "other")
RUN_ID = re.compile(r"^\d{8}T\d{6}Z-\d+-[0-9a-f]{8}$")
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
REVIEW_SCHEMA = 2
ASSURANCE = 'declared (local evidence checked for consistency; not authenticated)'

class QualityProblem(Exception):
    pass


def quality_policy(root):
    from engine import read
    path = root / '.agent/core/quality.json'
    try:
        policy = read(path)
    except Exception as e:
        raise QualityProblem(f'Cannot load quality policy: {e}') from e
    if not isinstance(policy, dict) or policy.get('schema_version') != 1:
        raise QualityProblem('Quality policy must have schema_version 1')
    required = policy.get('required_categories')
    if not isinstance(required, dict) or set(required) != {'low','medium','high'}:
        raise QualityProblem('required_categories must cover low/medium/high')
    for risk,categories in required.items():
        if not isinstance(categories, list) or not categories or any(c not in CATEGORIES for c in categories) or len(set(categories)) != len(categories):
            raise QualityProblem(f'Invalid required categories for {risk}')
    return policy


def review_path(root, task_id):
    return root / '.agent/runs' / task_id / 'quality-review.json'


def request_path(root, task_id):
    return root / '.agent/runs' / task_id / 'review-request.json'


def new_request(root, task, run):
    from engine import read, write, Problem
    path = request_path(root, task['task_id'])
    previous = None
    if path.is_file():
        try:
            prior = read(path)
        except (Problem, RecursionError):
            prior = None
        if isinstance(prior, dict) and prior.get('status') in ('open', 'consumed'):
            previous = (prior['status'], prior.get('request_id'))
    request = {
        'schema_version': 1,
        'request_id': uuid.uuid4().hex,
        'task_id': task['task_id'],
        'verification_run_id': run['run_id'],
        'workspace_sha256': run['workspace_sha256'],
        'status': 'open',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    write(path, request)
    return request, previous


def checked_request(root, task, run, request_id, status):
    from engine import read, Problem
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise QualityProblem('Review has no valid review_request_id. Run quality_gate.py init and review the new draft; '
                             'drafts and reviews created before v0.21.0 must be reinitialized')
    path = request_path(root, task['task_id'])
    if not path.is_file():
        raise QualityProblem('No review request exists for this task; run quality_gate.py init')
    try:
        request = read(path)
    except (Problem, RecursionError) as exc:
        raise QualityProblem('Review request record is unreadable; run quality_gate.py init') from exc
    if (not isinstance(request, dict) or request.get('schema_version') != 1
            or not isinstance(request.get('request_id'), str) or not REQUEST_ID.fullmatch(request['request_id'])
            or request.get('status') not in ('open', 'consumed') or request.get('task_id') != task['task_id']):
        raise QualityProblem('Review request record is invalid; run quality_gate.py init')
    if request['request_id'] != request_id:
        raise QualityProblem(f'Review request {request_id} was superseded or is unknown; '
                             f'the current request is {request["request_id"]}. Review and submit the current draft')
    if request.get('verification_run_id') != run['run_id'] or request.get('workspace_sha256') != run['workspace_sha256']:
        raise QualityProblem(f'Review request {request_id} belongs to an older verification run; '
                             'run quality_gate.py init after the latest verify and obtain a new review')
    if request['status'] != status:
        if request['status'] == 'consumed':
            raise QualityProblem(f'Review request {request_id} was already consumed by an accepted review; '
                                 'run quality_gate.py init for a new review')
        raise QualityProblem(f'Review request {request_id} has not been submitted; '
                             'submit the review with quality_gate.py submit instead of writing quality-review.json')
    return path, request


def status_lines(review):
    lines = ['Review assurance: ' + ASSURANCE]
    for finding in review.get('findings', []):
        if finding.get('status') == 'open':
            lines.append(f"Open {finding['severity']} finding: {' '.join(finding['summary'].split())}")
    return lines


def quality_template(task, run, checks_config, policy, request_id=None):
    """Bind a review request to the verified state BEFORE a reviewer starts.

    These fields are fixed when `init` runs. `submit` must never rebase an
    earlier review onto a newer verification after the code has changed.
    """
    from engine import encode, sha
    return {
        'schema_version': REVIEW_SCHEMA,
        'review_request_id': request_id,
        'task_id': task['task_id'],
        'verification_run_id': run['run_id'],
        'workspace_sha256': run['workspace_sha256'],
        'task_sha256': sha(encode(task)),
        'checks_sha256': sha(encode(checks_config)),
        'policy_sha256': sha(encode(policy)),
        'review_method': 'independent-agent-review' if task['risk']=='high' else 'agent-self-review',
        'reviewer_role': None,
        'reviewer_session_id': None,
        'implementer_session_id': None,
        'reviewer_invocation': None,  # Native tool attestation when session IDs are unavailable.
        'dimensions': {
            name: {'status': 'pending', 'rationale': '', 'evidence': []}
            for name in DIMENSIONS
        },
        'findings': [],
        'tradeoffs': '',
    }


def verification_record(root, task):
    from engine import read, final_verification_blocker
    directory = root / '.agent/runs' / task['task_id']
    candidates = sorted(p for p in directory.glob('*.json') if RUN_ID.fullmatch(p.stem)) if directory.exists() else []
    if not candidates:
        raise QualityProblem('No verification run exists; run engine.py verify first')
    path = candidates[-1]
    data = read(path)
    if not data.get('passed'):
        raise QualityProblem('Latest verification run did not pass')
    if data.get('run_id') != path.stem:
        raise QualityProblem('Verification record does not match its run identity')
    blocker = final_verification_blocker(root, task['task_id'], path.stem)
    if blocker:
        raise QualityProblem(blocker)
    return path, data


def validate_review(root, task, checks_config, run_path, run, submitting=False):
    from engine import read, encode, sha, snapshot
    policy = quality_policy(root)
    category_by_id = {c['id']:c.get('category','other') for c in checks_config['checks']}
    passed_ids = {c['id'] for c in run.get('checks',[]) if c.get('status')=='passed'}
    covered = {category_by_id[c] for c in passed_ids if c in category_by_id}
    missing = sorted(set(policy['required_categories'][task['risk']]) - covered)
    if missing:
        raise QualityProblem('Missing required executed check categories: '+', '.join(missing))
    if task['risk']=='high' and 'security' not in covered:
        raise QualityProblem('High-risk task needs a security check')
    rp = review_path(root,task['task_id'])
    if not rp.exists():
        raise QualityProblem('Missing engineering review. Generate with quality_gate.py init and submit after verification')
    review = read(rp)
    if isinstance(review,dict) and review.get('schema_version')==1:
        raise QualityProblem('Review uses schema 1 from before v0.21.0. Run quality_gate.py init for the latest '
                             'verification run and submit the review through the new request; do not edit the old file')
    if not isinstance(review,dict) or review.get('schema_version')!=REVIEW_SCHEMA:
        raise QualityProblem('Review schema invalid')
    if review.get('task_id')!=task['task_id'] or review.get('verification_run_id')!=run['run_id']:
        raise QualityProblem('Review does not reference the latest verification run')
    if review.get('workspace_sha256')!=run['workspace_sha256'] or snapshot(root)[0]!=run['workspace_sha256']:
        raise QualityProblem('Review is stale after code changed')
    if review.get('task_sha256')!=sha(encode(task)) or review.get('checks_sha256')!=sha(encode(checks_config)) or review.get('policy_sha256')!=sha(encode(policy)):
        raise QualityProblem('Review is stale after task/check/policy changed')
    method=review.get('review_method')
    if method not in ('agent-self-review','independent-agent-review'):
        raise QualityProblem('Unknown review method')
    settings={'require_independent_review_for_high_risk':True}
    if (root/'.agent/core/delegation.json').is_file():
        try:
            from delegation import policy as delegation_policy, DelegationError
            settings=delegation_policy(root)['policy']
        except (DelegationError, OSError, ValueError) as exc:
            raise QualityProblem('Invalid delegation policy: '+str(exc)) from exc
    if task['risk']=='high' and settings['require_independent_review_for_high_risk'] and method!='independent-agent-review':
        raise QualityProblem('High-risk task requires a separate independent reviewer attestation')
    if method=='independent-agent-review':
        if review.get('reviewer_role') != 'engineering-reviewer':
            raise QualityProblem('Independent review requires the engineering-reviewer role')
        reviewer = review.get('reviewer_session_id')
        implementer = review.get('implementer_session_id')
        for label, value in (('reviewer_session_id', reviewer), ('implementer_session_id', implementer)):
            if value is not None and (not isinstance(value, str) or len(value.strip()) < 8):
                raise QualityProblem(f'{label} must be an actual nonempty session ID or null')
        if reviewer is not None and implementer is not None and reviewer == implementer:
            raise QualityProblem('Reviewer and implementer session IDs must be distinct')
        if reviewer is None or implementer is None:
            # Claude/Codex may expose a native agent invocation but no session ID.
            # This remains an agent-reported attestation, not authenticated identity.
            invocation = review.get('reviewer_invocation')
            if not isinstance(invocation, dict) or set(invocation) != {
                    'runtime', 'tool', 'invocation_reference', 'status', 'session_ids_unavailable'}:
                raise QualityProblem('Missing native reviewer invocation attestation for unavailable session IDs')
            expected_tool = {'claude-code': 'Agent', 'codex': 'spawn_agent'}
            runtime = invocation.get('runtime')
            if (not isinstance(runtime, str) or runtime not in expected_tool
                    or invocation.get('tool') != expected_tool[runtime]
                    or invocation.get('status') != 'completed'
                    or invocation.get('session_ids_unavailable') is not True
                    or not isinstance(invocation.get('invocation_reference'), str)
                    or len(invocation['invocation_reference'].strip()) < 20):
                raise QualityProblem('Invalid native reviewer invocation attestation; record the actual tool call and result')
    dims=review.get('dimensions')
    if not isinstance(dims,dict) or set(dims)!=set(DIMENSIONS):
        raise QualityProblem('Review must assess exactly all quality dimensions')
    for dimension,assessment in dims.items():
        if not isinstance(assessment,dict) or assessment.get('status') not in ('pass','not_applicable'):
            raise QualityProblem(f'{dimension}: must pass or explain not applicable')
        reason=assessment.get('rationale')
        if not isinstance(reason,str) or len(reason.strip()) < 25:
            raise QualityProblem(f'{dimension}: give concrete rationale (at least 25 characters)')
        evidence=assessment.get('evidence')
        if not isinstance(evidence,list) or len(evidence)>20 or any(not isinstance(x,str) or not x for x in evidence):
            raise QualityProblem(f'{dimension}: evidence must be a string list')
        if assessment['status']=='pass' and not evidence:
            raise QualityProblem(f'{dimension}: passing assessment needs linked evidence')
        if dimension in ('security','reliability') and task['risk']=='high' and assessment['status'] != 'pass':
            raise QualityProblem(f'{dimension}: high risk cannot be marked not applicable')
        for item in evidence:
            if item.startswith('check:'):
                if item[6:] not in passed_ids:raise QualityProblem(f'{dimension}: unknown or failed check {item}')
            elif item.startswith('file:'):
                relative=Path(item[5:]);target=(root/relative).resolve()
                if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(root.resolve()) or not target.is_file():
                    raise QualityProblem(f'{dimension}: invalid file evidence {item}')
            else:
                raise QualityProblem(f'{dimension}: evidence must use check: or file:')
    findings=review.get('findings')
    if not isinstance(findings,list):raise QualityProblem('Review findings must be a list')
    for finding in findings:
        if not isinstance(finding,dict) or finding.get('severity') not in ('low','medium','high','critical') or finding.get('status') not in ('resolved','open'):
            raise QualityProblem('Invalid finding severity/status')
        if not isinstance(finding.get('summary'),str) or len(finding['summary'].strip())<12:
            raise QualityProblem('Finding needs a concrete summary')
        if finding['status']=='open' and finding['severity'] in ('high','critical'):
            raise QualityProblem('Unresolved high/critical code quality or security finding')
        if finding['status']=='resolved' and not finding.get('resolution'):
            raise QualityProblem('Resolved finding requires explanation')
    if submitting:
        return review
    _, request = checked_request(root, task, run, review.get('review_request_id'), 'consumed')
    if request.get('review_sha256') != sha(encode(review)):
        raise QualityProblem('Accepted review differs from the review submitted for request '
                             f'{request["request_id"]}; it was edited after submission or written without submit. '
                             'Run quality_gate.py init and submit a new review')
    return review


def main(argv=None):
    from engine import read, write, contract, checks, snapshot, encode, sha
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.cwd())
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('init')
    submit=sub.add_parser('submit');submit.add_argument('draft',type=Path)
    sub.add_parser('show')
    args=p.parse_args(argv);root=args.root.resolve()
    try:
        task=contract(root);config,_=checks(root);quality_policy(root)
        run_path,run=verification_record(root,task)
        if args.action=='init':
            if snapshot(root)[0] != run['workspace_sha256']:
                raise QualityProblem('Workspace changed after verification; rerun verify before requesting review')
            draft=review_path(root,task['task_id']).with_name('quality-draft.json')
            request,previous=new_request(root,task,run)
            write(draft,quality_template(task,run,config,quality_policy(root),request['request_id']))
            if previous and previous[0]=='open':
                print('Superseded open review request:',previous[1])
            elif previous:
                print('Replaced consumed review request',previous[1],'- its accepted review no longer passes the gate')
            print('Review request ID:',request['request_id'])
            print('Review request pinned to verified workspace:',run['workspace_sha256'])
            print('For high risk, send this snapshot ID to an independent reviewer BEFORE they inspect the code.')
            print('If reviewed code changes, rerun verify, init and independent review; do not reuse earlier findings.')
            print('Fill the review for actual code changes, then submit:',draft)
        elif args.action=='submit':
            try:
                draft_path=args.draft.resolve()
                if not draft_path.is_relative_to((root/'.agent/runs').resolve()):
                    raise QualityProblem('Keep review drafts under .agent/runs')
            except OSError as exc:
                raise QualityProblem(f'Invalid review draft: {exc}') from exc
            data=read(draft_path)
            if not isinstance(data,dict) or data.get('task_id')!=task['task_id'] or data.get('verification_run_id')!=run['run_id']:
                raise QualityProblem('Draft must reference the latest task and verification run')
            expected = quality_template(task,run,config,quality_policy(root))
            pinned = ('workspace_sha256','task_sha256','checks_sha256','policy_sha256')
            if any(data.get(key)!=expected[key] for key in pinned):
                raise QualityProblem('Review was prepared for a different workspace, task or policy. Reverify, reinitialize and review the final code again; never rebind old review evidence')
            if snapshot(root)[0] != run['workspace_sha256']:
                raise QualityProblem('Workspace changed since review request; rerun verification and review')
            request_file,request=checked_request(root,task,run,data.get('review_request_id'),'open')
            target=review_path(root,task['task_id'])
            # Validate candidate before writing it as the accepted review.
            temporary=target.with_name('quality-candidate.json')
            write(temporary,data)
            try:
                # validation reads review_path; replace temporarily but restore prior review on failure
                prior=target.read_bytes() if target.exists() else None
                write(target,data)
                try:
                    validate_review(root,task,config,run_path,run,submitting=True)
                    write(request_file,{**request,'status':'consumed','review_sha256':sha(encode(data)),
                                        'consumed_at':datetime.now(timezone.utc).isoformat()})
                except Exception:
                    if prior is None:target.unlink(missing_ok=True)
                    else:target.write_bytes(prior)
                    raise
            finally:temporary.unlink(missing_ok=True)
            print('Engineering quality review recorded:',target.relative_to(root))
            for line in status_lines(data):print(line)
        elif args.action=='show':
            validated=validate_review(root,task,config,run_path,run)
            print('PASS review',validated['task_id'],'based on',validated['review_method'])
            for line in status_lines(validated):print(line)
    except (QualityProblem, OSError, ValueError) as exc:
        print('BLOCKED:',exc,file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':sys.exit(main())
