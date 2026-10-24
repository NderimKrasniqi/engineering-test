#!/usr/bin/env python3
"""Render/check native Claude and Codex agents from a single policy and suggest delegation."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '.agent/core/delegation.json'
ROLE_ORDER = ('explorer', 'implementer', 'reviewer', 'investigator')
ALLOWED_EFFORT = {'low','medium','high','xhigh','max'}

class DelegationError(ValueError):
    pass


def policy(root=ROOT):
    path = root/'.agent/core/delegation.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise DelegationError('Unsupported delegation schema')
    limit = data.get('max_concurrent_subagents')
    depth = data.get('max_spawn_depth')
    if type(limit) is not int or not 1 <= limit <= 4:
        raise DelegationError('Subagent concurrency must be 1–4')
    if depth != 1:
        raise DelegationError('Nested delegation is not supported in this release')
    flags = data.get('policy', {})
    for key in ('delegate_small_tasks','require_independent_review_for_high_risk','isolate_implementer','main_owns_task_completion'):
        if type(flags.get(key)) is not bool:
            raise DelegationError('Missing boolean policy: '+key)
    if flags['main_owns_task_completion'] is not True:
        raise DelegationError('Only the main agent can complete tasks')
    roles = data.get('roles',{})
    if set(roles) != set(ROLE_ORDER):
        raise DelegationError('Role names must be '+', '.join(ROLE_ORDER))
    for name, value in {**roles,'main':data.get('main',{})}.items():
        if name != 'main' and not isinstance(value.get('description'),str):
            raise DelegationError(name+': description is missing')
        for runtime in ('claude','codex'):
            selected=value.get(runtime,{})
            if not isinstance(selected.get('model'),str) or not selected['model'].strip() or selected.get('effort') not in ALLOWED_EFFORT:
                raise DelegationError(f'{name}.{runtime}: invalid model or effort')
    return data


def body(role):
    common=('Read AGENTS.md and the relevant sections of .agent/project-map.md. Inspect actual source and product artifacts. '
            'Product requirements belong to the human; report unresolved product questions to the main agent. '
            'Use the chosen project stack. Keep code simple, readable, secure, maintainable and appropriately scalable; '
            'use minimal comments and only essential end-to-end or risk-focused tests. '
            'Do not mark tasks done, modify continuation mode, rewrite product requirements, or promote global learning rules. '
            'Return a concise summary, changed file paths, actual checks run, failures, and open risks.')
    specifics={
      'explorer':'Do not modify any files. Trace only the relevant code paths and return specific locations and uncertainties.',
      'implementer':'Implement only the assigned scope. If worktree-isolated, check the worktree base commit and dependency state before editing; tell the lead if required changes are absent. Run focused checks; do not approve your own work.',
      'reviewer':'Do not edit files. Review the integrated diff and real behavior, not the implementer summary. Check the review request snapshot ID against the code state before reviewing, and include that snapshot ID plus your session ID only if the runtime actually provides one. Never invent a session ID; the main agent may document the native invocation in reviewer_invocation. If the main agent makes changes after your review, perform a focused new review of the final state before completion. Prioritize genuine correctness, security, readability, complexity and scalability risks; avoid style-only nitpicks and unnecessary tests.',
      'investigator':'Do not modify files. Investigate root causes and high-risk invariants with concrete evidence. Propose the smallest enforceable correction and return risks and uncertainties.'
    }
    return specifics[role]+'\n\n'+common


def claude_agent(name, desc, config, isolated):
    cfg=config['claude']
    lines=['---',f'name: engineering-{name}',f'description: {desc}',f'model: {cfg["model"]}',f'effort: {cfg["effort"]}']
    if name in ('explorer','reviewer','investigator'):
        lines.append('tools: Read, Grep, Glob, Bash')
    if isolated:
        lines.append('isolation: worktree')
    lines.extend(['---','',body(name),''])
    return '\n'.join(lines)


def codex_agent(name, desc, config):
    cfg=config['codex']
    toml_escape = lambda value: json.dumps(value,ensure_ascii=False)
    return (f'name = {toml_escape("engineering_"+name)}\n'
            f'description = {toml_escape(desc)}\n'
            f'model = {toml_escape(cfg["model"])}\n'
            f'model_reasoning_effort = {toml_escape(cfg["effort"])}\n'
            'developer_instructions = """\n'+body(name)+'\n"""\n')


def generated(data):
    files={}
    for name in ROLE_ORDER:
        role=data['roles'][name]
        files[Path('.claude/agents')/f'engineering-{name}.md']=claude_agent(
            name,role['description'],role,
            bool(name=='implementer' and data['policy']['isolate_implementer']))
        files[Path('.codex/agents')/f'engineering-{name}.toml']=codex_agent(name,role['description'],role)
    # This is a safe additive snippet, not a replacement for project-owned config.toml.
    files[Path('.codex/config.engineering.example.toml')]=(f'[agents]\n'
        f'enabled = true\n'
        f'max_concurrent_threads_per_session = {data["max_concurrent_subagents"]}\n'
        f'default_subagent_model = {json.dumps(data["roles"]["implementer"]["codex"]["model"])}\n'
        f'default_subagent_reasoning_effort = {json.dumps(data["roles"]["implementer"]["codex"]["effort"])}\n')
    files[Path('.claude/settings.delegation.example.json')]=json.dumps({'env':{
      'CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS':str(data['max_concurrent_subagents']),
      'CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH':str(data['max_spawn_depth'])
    }},indent=2)+'\n'
    return files


def sync(root=ROOT, check=False, replace=False):
    from datetime import datetime, timezone
    import shutil
    desired=generated(policy(root))
    differing=[]
    conflicts=[]
    for rel,content in desired.items():
        dest=root/rel
        if not dest.exists() or dest.read_text(encoding='utf-8') != content:
            differing.append(rel.as_posix())
            if dest.exists():
                conflicts.append(rel.as_posix())
    if check:
        return differing
    if conflicts and not replace:
        return differing  # Fail without partial writes.
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    for rel,content in desired.items():
        dest=root/rel
        if rel.as_posix() not in differing:
            continue
        if dest.exists():
            backup=root/'.agent/backup'/('delegation-'+stamp)/rel
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,backup)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(content,encoding='utf-8')
    return []


def recommend(complexity='normal',risk='medium', read_heavy=False, independent=False, root=ROOT):
    if complexity not in {'small','normal','significant','complex'} or risk not in {'low','medium','high'}:
        raise DelegationError('Use small/normal/significant/complex and low/medium/high')
    config=policy(root)
    flags=config['policy']
    if complexity=='small' and risk=='low' and not read_heavy:
        roles=['implementer'] if flags['delegate_small_tasks'] else []
    elif risk=='high' and complexity in ('significant','complex'):
        roles=['investigator','implementer','reviewer']
    elif risk=='high':
        roles=['implementer','reviewer']
    elif complexity in ('significant','complex'):
        roles=['implementer','reviewer']
    elif read_heavy:
        roles=['explorer','implementer'] if complexity!='small' else ['explorer']
    else:
        roles=['implementer']
    if risk=='high' and flags['require_independent_review_for_high_risk'] and 'reviewer' not in roles:
        roles.append('reviewer')
    if risk=='high' and not flags['require_independent_review_for_high_risk']:
        roles=[role for role in roles if role != 'reviewer']
    return {
        'roles_in_order':roles,
        'concurrent_cap':config['max_concurrent_subagents'],
        'parallel_safe': bool(independent and 'implementer' not in roles),
        'review_after_integration': 'reviewer' in roles,
        'completion_owner':'main',
        'notes':'Do not edit the same files concurrently. Main runs the final verification gate, handles user questions, and follows continuation mode.'
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    s=sub.add_parser('sync');s.add_argument('--check',action='store_true');s.add_argument('--replace',action='store_true')
    r=sub.add_parser('recommend');r.add_argument('--complexity',choices=['small','normal','significant','complex'],default='normal')
    r.add_argument('--risk',choices=['low','medium','high'],default='medium');r.add_argument('--read-heavy',action='store_true');r.add_argument('--independent',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='sync':
            mismatches=sync(check=args.check, replace=args.replace)
            if mismatches:
                print('Generated files differ. Review before overwriting:\n'+'\n'.join(mismatches),file=sys.stderr)
                return 2
            print('Native agent definitions match the shared role policy.')
        else:
            print(json.dumps(recommend(args.complexity,args.risk,args.read_heavy,args.independent),indent=2))
        return 0
    except (DelegationError,OSError,ValueError) as exc:
        print('Delegation error:',exc,file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
