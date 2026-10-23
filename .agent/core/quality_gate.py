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
from pathlib import Path

DIMENSIONS = ("readability", "maintainability", "security", "reliability", "scalability", "compatibility")
CATEGORIES = ("e2e", "edge", "test", "static", "security", "build", "integration", "performance", "other")
RUN_ID = re.compile(r"^\d{8}T\d{6}Z-\d+-[0-9a-f]{8}$")

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


def quality_template(task, run_id):
    return {
        'schema_version': 1,
        'task_id': task['task_id'],
        'verification_run_id': run_id,
        'review_method': 'independent-agent-review' if task['risk']=='high' else 'agent-self-review',
        'reviewer_role': None,
        'reviewer_session_id': None,
        'implementer_session_id': None,
        'dimensions': {
            name: {'status': 'pending', 'rationale': '', 'evidence': []}
            for name in DIMENSIONS
        },
        'findings': [],
        'tradeoffs': '',
    }


def verification_record(root, task):
    from engine import read
    directory = root / '.agent/runs' / task['task_id']
    candidates = sorted(p for p in directory.glob('*.json') if RUN_ID.fullmatch(p.stem)) if directory.exists() else []
    if not candidates:
        raise QualityProblem('No verification run exists; run engine.py verify first')
    path = candidates[-1]
    data = read(path)
    if not data.get('passed'):
        raise QualityProblem('Latest verification run did not pass')
    return path, data


def validate_review(root, task, checks_config, run_path, run):
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
    if not isinstance(review,dict) or review.get('schema_version')!=1:
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
        reviewer=review.get('reviewer_session_id')
        implementer=review.get('implementer_session_id')
        if (review.get('reviewer_role')!='engineering-reviewer'
                or not isinstance(reviewer,str) or len(reviewer.strip())<8
                or not isinstance(implementer,str) or len(implementer.strip())<8
                or reviewer==implementer):
            raise QualityProblem('Independent review needs a named reviewer role and distinct nonempty session IDs')
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
            draft=review_path(root,task['task_id']).with_name('quality-draft.json')
            write(draft,quality_template(task,run['run_id']))
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
            data['workspace_sha256']=run['workspace_sha256']
            data['task_sha256']=sha(encode(task))
            data['checks_sha256']=sha(encode(config))
            data['policy_sha256']=sha(encode(quality_policy(root)))
            target=review_path(root,task['task_id'])
            # Validate candidate before writing it as the accepted review.
            temporary=target.with_name('quality-candidate.json')
            write(temporary,data)
            try:
                # validation reads review_path; replace temporarily but restore prior review on failure
                prior=target.read_bytes() if target.exists() else None
                write(target,data)
                try:validate_review(root,task,config,run_path,run)
                except Exception:
                    if prior is None:target.unlink(missing_ok=True)
                    else:target.write_bytes(prior)
                    raise
            finally:temporary.unlink(missing_ok=True)
            print('Engineering quality review recorded:',target.relative_to(root))
        elif args.action=='show':
            validated=validate_review(root,task,config,run_path,run)
            print('PASS review',validated['task_id'],'based on',validated['review_method'])
    except (QualityProblem, OSError, ValueError) as exc:
        print('BLOCKED:',exc,file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':sys.exit(main())
