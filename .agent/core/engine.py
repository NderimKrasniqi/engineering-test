#!/usr/bin/env python3
"""Engineering Stack: verified delivery, user-controlled continuation, and durable learning."""
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
from datetime import datetime, timezone
from pathlib import Path

RISKS={'low':0,'medium':1,'high':2}
SKIP_DIR={'.git','.venv','venv','__pycache__','node_modules','.pytest_cache','.mypy_cache','dist','build','.tox','.next'}
SKIP_FILES={'.agent/core/active.json','.agent/core/clarification.json','.agent/core/continuation.json','.workflow/tasks.json','.agent/learning/events.jsonl','.coverage'}
SKIP_PREFIXES=('.agent/runs/','.agent/backup/','.agent/learning/records/','.agent/learning/cases/','.agent/learning/proofs/')
class Problem(Exception): pass

def encode(v): return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError) as e: raise Problem(f'Cannot read {p}: {e}') from e

def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.tmp-'+uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        temp.replace(p)
    finally: temp.unlink(missing_ok=True)

def locations(root):
    core=root/'.agent/core'
    return core/'checks.json',core/'active.json',root/'.workflow/tasks.json',root/'.agent/runs'

def operation_path(root):
    return root/'.agent/core/operation.json'


def operation(root):
    path=operation_path(root)
    if not path.exists():
        raise Problem('Continuation mode not selected. Ask the user once: automatic or after_each_task; then use engine.py mode <choice>.')
    value=read(path)
    if not isinstance(value,dict) or value.get('continuation_mode') not in ('unselected','automatic','after_each_task'):
        raise Problem('Invalid continuation mode configuration')
    if value['continuation_mode']=='unselected':
        raise Problem('Ask the user to choose automatic or after_each_task before implementation')
    if value.get('self_maintenance') is not True:
        raise Problem('Self-maintenance must remain enabled')
    return value


def continuation_path(root):
    return root/'.agent/core/continuation.json'


def pause_state(root):
    path=continuation_path(root)
    if not path.exists(): return {}
    data=read(path)
    if not isinstance(data,dict) or not isinstance(data.get('awaiting_user'),bool):
        raise Problem('Invalid continuation state')
    return data


def question_path(root):
    return root/'.agent/core/clarification.json'


def pending_question(root):
    path=question_path(root)
    if not path.exists(): return None
    data=read(path)
    if not isinstance(data,dict) or data.get('status')!='pending':
        raise Problem('Invalid clarification state')
    return data


def require_clear(root):
    q=pending_question(root)
    if q:
        raise Problem('Question awaiting a user answer: '+q['question'])


def require_continuation(root):
    operation(root)
    if pause_state(root).get('awaiting_user'):
        raise Problem('Waiting for the user to choose whether to continue after the last completed task')


def mode(root,args):
    path=operation_path(root)
    if args.choice is None:
        print('Continuation mode:',read(path).get('continuation_mode','unselected') if path.exists() else 'unselected')
        return 0
    # The adapter must call this only after the human has explicitly chosen the mode.
    existing=read(path) if path.exists() else {'schema_version':1,'self_maintenance':True}
    if not isinstance(existing,dict): raise Problem('Invalid operating policy')
    existing['continuation_mode']=args.choice
    existing['self_maintenance']=True
    write(path,existing)
    print('Continuation mode:',args.choice,'(human-selected; do not change without a user request)')
    if args.choice=='automatic' and pause_state(root).get('awaiting_user'):
        print('Previous pause still requires explicit continuation; run continue --decision yes after user authorization')
    return 0


def ask(root,args):
    if pending_question(root): raise Problem('Answer the current product question before opening another')
    if len(args.question.strip())<8 or len(args.why.strip())<12:
        raise Problem('Provide one concrete question and why the missing product decision matters')
    active=locations(root)[1]
    task=read(active).get('task_id') if active.exists() else None
    data={'schema_version':1,'id':uuid.uuid4().hex,'status':'pending','task_id':task,
          'question':args.question.strip(),'why':args.why.strip(),'created_at':datetime.now(timezone.utc).isoformat()}
    write(question_path(root),data)
    print('ASK USER:',data['question'])
    print('WHY:',data['why'])
    print('PAUSED: implementation and completion blocked until the user answers')
    return 0


def answer(root,args):
    q=pending_question(root)
    if not q: raise Problem('No pending user question')
    if len(args.answer.strip())<2: raise Problem('Record the actual user answer, not an invented assumption')
    record={**q,'status':'answered','answer':args.answer.strip(),'answered_at':datetime.now(timezone.utc).isoformat()}
    path=root/'.agent/decisions/clarifications.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f: f.write(json.dumps(record,sort_keys=True)+'\n')
    question_path(root).unlink()
    print('ANSWER RECORDED:',q['id'])
    print('Update the product-workflow source documents if this answer changes product intent before verification')
    return 0


def continue_after_task(root,args):
    operation(root)
    require_clear(root)
    state=pause_state(root)
    if not state.get('awaiting_user'):
        raise Problem('No task-completion pause awaiting a user decision')
    if args.decision=='no':
        print('PAUSED: no further task will begin until the user chooses to continue')
        return 0
    state.update({'awaiting_user':False,'continued_at':datetime.now(timezone.utc).isoformat()})
    write(continuation_path(root),state)
    print('CONTINUATION APPROVED by user instruction; the agent can select the next ready task')
    return 0


def maintenance_report(root):
    from learning_engine import cases, verified_proof, LearningProblem
    errors=[]
    from project_intelligence import refresh, MapError
    from instruction_linker import wire, LinkError
    try:
        links,unwired=wire(root,check_only=True)
        if not links:errors.append('Project instruction links missing: '+', '.join(unwired))
    except (LinkError,OSError) as exc:errors.append('Project instruction links invalid: '+str(exc))
    try:
        current,changed=refresh(root,check_only=True)
        if not current:errors.append('Project Map outdated: '+', '.join(changed)+'; run engine.py map then verify again')
    except MapError as exc:
        errors.append('Project Map invalid: '+str(exc))
    try: all_cases=cases(root)
    except LearningProblem as exc:
        return {'schema_version':1,'healthy':False,'issues':[f'Learning registry invalid: {exc}'],
                'learning_cases':None,'at':datetime.now(timezone.utc).isoformat()}
    for item in all_cases:
        if item.get('status')=='enforced':
            try:
                from learning_engine import active_guard_check
                verified_proof(root,item)
                if item.get('active_check_id')!=active_guard_check(root,item):
                    raise LearningProblem('Proven guard is no longer active in project verification')
            except LearningProblem as exc: errors.append(f"Stale enforced guard {item.get('id')}: {exc}")
    delegation_config=root/'.agent/core/delegation.json'
    if not delegation_config.exists() and (list((root/'.claude/agents').glob('engineering-*.md'))
                                          or list((root/'.codex/agents').glob('engineering-*.toml'))):
        errors.append('Native agent definitions exist but the canonical delegation policy is missing')
    if delegation_config.exists():
        try:
            from delegation import sync, DelegationError
            drift=sync(root,check=True)
            if drift:
                errors.append('Native agent definitions differ from delegated-role policy: '+', '.join(drift)+'; review before running delegation.py sync --replace')
        except (DelegationError,OSError,ValueError) as exc:
            errors.append('Native delegation configuration invalid: '+str(exc))
    paths=(root/'.claude/skills',root/'.agents/skills')
    for skill in ('engineering-mode','engineering-verify','engineering-learn'):
        left=paths[0]/skill/'SKILL.md';right=paths[1]/skill/'SKILL.md'
        if left.exists() != right.exists():
            errors.append(f'Skill adapter missing one runtime copy: {skill}')
        elif left.exists() and left.read_bytes()!=right.read_bytes():
            errors.append(f'Claude/Codex skill drift: {skill}')
    return {'schema_version':1,'healthy':not errors,'issues':errors,
            'learning_cases':len(all_cases),'at':datetime.now(timezone.utc).isoformat()}


def maintenance(root,_):
    refresh_project_map(root)
    # Safe self-repair: restore missing generated adapter files only. Never replace
    # an existing edited agent file or change the chosen role policy silently.
    if (root/'.agent/core/delegation.json').exists():
        from delegation import policy as delegation_policy, generated, sync
        expected=generated(delegation_policy(root))
        drift=[rel for rel,body in expected.items()
               if (root/rel).exists() and (root/rel).read_text(encoding='utf-8')!=body]
        if not drift:
            missing=[rel for rel in expected if not (root/rel).exists()]
            if missing:
                sync(root)
                refresh_project_map(root)
                print('SELF-MAINTENANCE restored missing agent files:',', '.join(str(p) for p in missing))
    report=maintenance_report(root)
    target=root/'.agent/runs/maintenance/last.json'
    write(target,report)
    print('SELF-MAINTENANCE:', 'PASS' if report['healthy'] else 'NEEDS REPAIR')
    for issue in report['issues']: print('  ',issue)
    print('Learning cases:',report['learning_cases'])
    return 0 if report['healthy'] else 2


def tasks(root):
    """Load canonical product-workflow tasks from Markdown + machine dependencies.

    The current product-workflow plugin intentionally keeps titles, acceptance,
    and completion in docs/implementation-plan.md. Do not duplicate them in
    .workflow/tasks.json. Legacy v15 list tasks remain supported.
    """
    p = locations(root)[2]
    doc = read(p)
    rows = doc.get('tasks') if isinstance(doc,dict) else None
    if isinstance(rows, dict):
        plan_path = root/'docs/implementation-plan.md'
        try:
            content = plan_path.read_text(encoding='utf-8')
        except OSError as exc:
            raise Problem(f'Cannot read canonical implementation plan: {exc}') from exc
        pattern = re.compile(r'^- \[([ x])\] (TASK-\d{2,}) (.+)$', re.M)
        matches = list(pattern.finditer(content))
        lines = content.splitlines()
        normalized = []
        seen = set()
        for m in matches:
            done, ident, title = m.groups()
            if ident in seen:
                raise Problem('Duplicate task in implementation plan: '+ident)
            seen.add(ident)
            index = content[:m.start()].count('\n')
            following = lines[index + 1] if index + 1<len(lines) else ''
            acceptance = re.match(r'^\s+Done when:\s*(\S.*)$', following)
            if not acceptance:
                raise Problem('Task missing Done when: '+ident)
            machine = rows.get(ident)
            if not isinstance(machine, dict) or not isinstance(machine.get('deps'), list):
                raise Problem('Task missing canonical machine dependencies: '+ident)
            normalized.append({'id':ident,'title':title,'status':'done' if done=='x' else 'todo',
                               'depends_on':machine['deps'],'acceptance':[acceptance.group(1)]})
        if not matches or set(rows)!=seen:
            raise Problem('Product plan and machine tasks disagree')
        ids=set(seen)
        for task in normalized:
            if any(dep not in ids for dep in task['depends_on']):
                raise Problem('Unknown task dependency in '+task['id'])
        return doc, normalized
    if not isinstance(rows,list): raise Problem('.workflow/tasks.json needs a tasks list or canonical product-workflow map')
    ids=[r.get('id') for r in rows if isinstance(r,dict)]
    if len(ids)!=len(rows) or any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):
        raise Problem('Tasks need unique nonempty string ids')
    for r in rows:
        deps=r.get('depends_on',[])
        if not isinstance(deps,list) or any(not isinstance(d,str) or d not in ids for d in deps):
            raise Problem(f"Invalid dependencies in {r['id']}")
    return doc,rows

def ready(rows):
    done={r['id'] for r in rows if r.get('status') in ('done','completed')}
    return [r for r in rows if r.get('status','todo') in ('todo','pending','ready') and all(dep in done for dep in r.get('depends_on',[]))]

def contract(root):
    doc=read(locations(root)[1])
    if not isinstance(doc,dict) or not isinstance(doc.get('task_id'),str) or not doc['task_id']: raise Problem('Active contract missing task_id')
    if doc.get('risk') not in RISKS: raise Problem('Active task risk must be low/medium/high')
    claims=doc.get('claims')
    if not isinstance(claims,list) or not claims: raise Problem('At least one acceptance claim is required')
    seen=set()
    for claim in claims:
        if not isinstance(claim,dict) or not isinstance(claim.get('id'),str) or not claim['id'] or not isinstance(claim.get('description'),str) or not claim['description'].strip() or not isinstance(claim.get('check_ids'),list) or not claim['check_ids'] or not all(isinstance(x,str) and x for x in claim['check_ids']):
            raise Problem('Each claim needs id, description, and nonempty check_ids')
        if claim['id'] in seen: raise Problem('Duplicate claim id')
        seen.add(claim['id'])
    return doc

def checks(root):
    doc=read(locations(root)[0]); rows=doc.get('checks') if isinstance(doc,dict) else None
    if not isinstance(rows,list) or not rows: raise Problem('Configure real project checks in .agent/core/checks.json')
    ids=set()
    for c in rows:
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}',c['id']):
            raise Problem('Bad check id')
        if c['id'] in ids: raise Problem('Duplicate check id')
        ids.add(c['id'])
        args=c.get('argv')
        if not isinstance(args,list) or not args or any(not isinstance(a,str) or not a or '\x00' in a for a in args):
            raise Problem(f"Check {c['id']} needs argv as string list, not shell command")
        if c.get('min_risk','low') not in RISKS: raise Problem('Invalid check min_risk')
        if c.get('category','other') not in ('e2e','edge','test','static','security','build','integration','performance','other'):
            raise Problem('Invalid check category')
        timeout=c.get('timeout_seconds',120)
        if type(timeout)!=int or not 1<=timeout<=600: raise Problem('timeout_seconds outside [1,600]')
    return doc,rows

def selected_checks(task,rows):
    selected=[c for c in rows if RISKS[c.get('min_risk','low')]<=RISKS[task['risk']]]
    if task['risk']=='high' and not any(c.get('min_risk')=='high' for c in selected):
        raise Problem('High-risk task requires a high-risk-specific check')
    ids={c['id'] for c in selected}
    missing={id for claim in task['claims'] for id in claim['check_ids']} - ids
    if missing: raise Problem('Claims reference unavailable checks: '+', '.join(sorted(missing)))
    return selected

def snapshot(root):
    p=subprocess.run(['git','ls-files','-co','--exclude-standard','-z'],cwd=root,capture_output=True)
    if p.returncode==0: names=[Path(os.fsdecode(s)) for s in p.stdout.split(b'\0') if s]
    else: names=[f.relative_to(root) for f in root.rglob('*') if f.is_file() or f.is_symlink()]
    result=[]
    for rel in sorted(set(names),key=lambda n:n.as_posix()):
        path=rel.as_posix()
        if rel.is_absolute() or '..' in rel.parts or SKIP_DIR.intersection(rel.parts) or path in SKIP_FILES or path.startswith(SKIP_PREFIXES) or path.endswith('.pyc'):
            continue
        if (root/rel).is_file() or (root/rel).is_symlink(): result.append(rel)
    if len(result)>20000: raise Problem('More than 20000 source files; configure Git ignores')
    h=hashlib.sha256(); size=0
    for rel in result:
        f=root/rel
        h.update(rel.as_posix().encode()+b'\0')
        if f.is_symlink(): h.update(b'link\0'+os.readlink(f).encode()+b'\0');continue
        try:
            with f.open('rb') as stream:
                for block in iter(lambda:stream.read(65536),b''):
                    size+=len(block)
                    if size>200*1024*1024: raise Problem('Snapshot exceeds 200MB; narrow Git-tracked project inputs')
                    h.update(block)
        except OSError as e: raise Problem(f'Snapshot failed on {rel}: {e}') from e
        h.update(b'\0')
    return h.hexdigest(),len(result)

def refresh_project_map(root):
    from instruction_linker import wire, LinkError
    try:wire(root)
    except (LinkError,OSError) as exc:raise Problem('Project instruction links: '+str(exc)) from exc
    from project_intelligence import refresh, MapError
    try:return refresh(root)
    except MapError as exc:raise Problem('Project Intelligence: '+str(exc)) from exc

def project_map(root,_):
    _,updated=refresh_project_map(root)
    print('PROJECT MAP:', ', '.join(updated) if updated else 'current')
    return 0

def next_task(root,_):
    refresh_project_map(root)
    require_clear(root)
    require_continuation(root)
    _,rows=tasks(root)
    found=ready(rows)
    for r in found: print(r['id'],r.get('title',''))
    if not found: print('No ready tasks')
    return 0

def start(root,args):
    refresh_project_map(root)
    require_clear(root)
    require_continuation(root)
    if locations(root)[1].exists():raise Problem('Another active task exists; finish or archive it first')
    _,rows=tasks(root); queue=ready(rows)
    t=next((r for r in queue if r['id']==args.task),None) if args.task else (queue[0] if queue else None)
    if t is None:raise Problem('No matching ready task')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',t['id']):raise Problem('Unsafe task id')
    conditions=t.get('acceptance',[])
    if not isinstance(conditions,list): raise Problem('acceptance must be a list')
    conditions=[str(s) for s in conditions] or [str(t.get('title','Task acceptance'))]
    data={'schema_version':1,'task_id':t['id'],'risk':args.risk,'claims':[
        {'id':f'acceptance-{i+1}','description':s,'check_ids':[]} for i,s in enumerate(conditions)]}
    write(locations(root)[1],data)
    print('Started',t['id'],'; map each claim to real checks in .agent/core/active.json')
    return 0

def append_event(root,event):
    p=root/'.agent/learning/events.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(event,sort_keys=True)+'\n')

def verify(root,args):
    # Refresh before hashing the repository, never during an evidence gate.
    refresh_project_map(root)
    require_clear(root)
    operation(root)
    task=contract(root);config,items=checks(root);items=selected_checks(task,items)
    before,n=snapshot(root); records=[]
    print('Verifying',task['task_id'],'risk',task['risk'],'files',n,flush=True)
    for item in items:
        begin=time.monotonic();out=b'';status='error';code=None
        try:
            p=subprocess.run(item['argv'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             timeout=item.get('timeout_seconds',120),check=False)
            out=p.stdout+b'\0'+p.stderr;code=p.returncode;status='passed' if code==0 else 'failed'
            if code:print('FAIL',item['id'],out.decode('utf-8','replace')[-700:],flush=True)
            else:print('PASS',item['id'],flush=True)
        except subprocess.TimeoutExpired: out=b'timeout';status='timeout';print('TIMEOUT',item['id'],flush=True)
        except OSError as e:out=str(e).encode();status='error';print('ERROR',item['id'],type(e).__name__,flush=True)
        records.append({'id':item['id'],'status':status,'exit_code':code,'output_sha256':sha(out),
                        'duration_seconds':round(time.monotonic()-begin,3)})
    after,_=snapshot(root);stable=after==before
    if not stable: print('FAIL workspace changed during verification',flush=True)
    success=stable and all(c['status']=='passed' for c in records)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+f'-{time.time_ns():019d}-'+uuid.uuid4().hex[:8]
    target=locations(root)[3]/task['task_id']/(run_id+'.json')
    write(target,{'schema_version':1,'task_id':task['task_id'],'run_id':run_id,'passed':success,
                  'workspace_stable':stable,'workspace_sha256':after,'task_sha256':sha(encode(task)),
                  'checks_sha256':sha(encode(config)),'checks':records})
    for c in records:
        if c['status']!='passed' and not args.expected_red:
            append_event(root,{'event_id':uuid.uuid4().hex,'kind':'verification-failure',
                               'task_id':task['task_id'],'run_id':run_id,
                               'workspace_sha256':after,'check_id':c['id'],
                               'output_sha256':c['output_sha256'],'evidence':str(target.relative_to(root))})
    if not stable and not args.expected_red:
        append_event(root,{'event_id':uuid.uuid4().hex,'kind':'verification-workspace-changed',
                           'task_id':task['task_id'],'run_id':run_id,
                           'workspace_sha256':after,'evidence':str(target.relative_to(root))})
    if not success and not args.expected_red:
        # Deterministic signal detection; agent judgment is still needed to diagnose cause.
        from learning_engine import scan
        added=scan(root,quiet=True)
        for candidate in added:
            print('LEARNING CANDIDATE',candidate,'— investigate before finishing',flush=True)
    print('Evidence:',target.relative_to(root),'result:', 'PASS' if success else 'FAIL',flush=True)
    return 0 if success else 1

def gate(root):
    from instruction_linker import wire, LinkError
    try: linked,missing=wire(root,check_only=True)
    except (LinkError,OSError) as exc:raise Problem('Project instruction links: '+str(exc)) from exc
    if not linked:raise Problem('Project instructions missing Engineering Stack links: '+', '.join(missing))
    from project_intelligence import refresh, MapError
    try: current,changed=refresh(root,check_only=True)
    except MapError as exc:raise Problem('Project Intelligence: '+str(exc)) from exc
    if not current:raise Problem('Project Map stale: '+', '.join(changed)+'; refresh map and rerun verification')
    require_clear(root)
    operation(root)
    task=contract(root);config,items=checks(root);required={c['id'] for c in selected_checks(task,items)}
    directory=locations(root)[3]/task['task_id'];runs=sorted((p for p in directory.glob('*.json') if re.fullmatch(r'\d{8}T\d{6}Z-\d+-[0-9a-f]{8}',p.stem))) if directory.exists() else []
    if not runs:raise Problem('No verification evidence')
    path=runs[-1];data=read(path)
    if data.get('task_id')!=task['task_id'] or not data.get('passed') or not data.get('workspace_stable'):
        raise Problem('Latest verification failed')
    if data.get('task_sha256')!=sha(encode(task)):raise Problem('Acceptance contract changed since verification')
    if data.get('checks_sha256')!=sha(encode(config)):raise Problem('Verification configuration changed')
    if {c['id'] for c in data.get('checks',[]) if c.get('status')=='passed'}!=required:
        raise Problem('Missing required passing checks')
    if snapshot(root)[0]!=data.get('workspace_sha256'):raise Problem('Workspace changed after verification')
    from quality_gate import validate_review, QualityProblem
    try:validate_review(root, task, config, path, data)
    except QualityProblem as exc:raise Problem('Quality gate: '+str(exc)) from exc
    return path,data

def check_gate(root,_):
    path,data=gate(root);print('PASS gate',data['task_id'],path.relative_to(root));return 0

def finish(root,_):
    path,data=gate(root)
    state=maintenance_report(root)
    if not state['healthy']:raise Problem('Self-maintenance requires repair: '+'; '.join(state['issues']))
    write(root/'.agent/runs/maintenance/last.json',state)
    doc,rows=tasks(root); matches=[r for r in rows if r['id']==data['task_id']]
    if len(matches)!=1 or matches[0] not in ready(rows):raise Problem('Task not ready; cannot update task registry')
    from learning_engine import unresolved_for_task
    pending=unresolved_for_task(root,data['task_id'])
    if pending:raise Problem('Unresolved learning candidates: '+', '.join(pending)+'. Diagnose and prove a guard, or defer with reason.')
    write(locations(root)[3]/data['task_id']/'contract.json',contract(root))
    if isinstance(doc.get('tasks'),dict):
        # Canonical product-workflow: completion status lives only in the plan.
        plan = root/'docs/implementation-plan.md'
        content = plan.read_text(encoding='utf-8')
        expression = re.compile(r'^- \[ \] ('+re.escape(data['task_id'])+r') (.+)$',re.M)
        updated,count = expression.subn(lambda m:'- [x] '+m.group(1)+' '+m.group(2).rstrip()+' ✅',content)
        if count != 1:
            raise Problem('Could not sign off exactly one canonical plan task')
        # The verification evidence remains outside task bookkeeping.
        # Atomic Markdown replace; no additional task state is invented.
        tmp=plan.with_name(plan.name+'.tmp-'+uuid.uuid4().hex)
        try:
            tmp.write_text(updated,encoding='utf-8')
            tmp.replace(plan)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        matches[0]['status']='done';matches[0]['verification_evidence']=str(path.relative_to(root))
        write(locations(root)[2],doc)
    locations(root)[1].unlink()
    print('DONE',data['task_id'],'with evidence',path.relative_to(root))
    remaining=ready(tasks(root)[1])
    if remaining and operation(root)['continuation_mode']=='after_each_task':
        write(continuation_path(root),{'schema_version':1,'awaiting_user':True,
              'completed_task_id':data['task_id'],'next_task_id':remaining[0]['id']})
        print('ASK USER: Task complete and verified. Continue with',remaining[0]['id']+'?')
        print('Wait for a real user answer before calling continue --decision yes')
    elif remaining:
        print('AUTOMATIC: Continue with',remaining[0]['id'],'after normal verification and learning maintenance')
    else:
        print('All eligible tasks are complete; no continuation prompt needed')
    return 0

def learning(root,_):
    from learning_engine import scan,status
    scan(root)
    status(root)
    return 0

def doctor(root,_):
    _,changed=refresh_project_map(root)
    print('Project Map:', 'updated '+', '.join(changed) if changed else 'current')
    print('Continuation mode:',read(operation_path(root)).get('continuation_mode') if operation_path(root).exists() else 'unselected')
    print('Pending clarification:', 'yes' if pending_question(root) else 'no')
    print('Awaiting continuation:', 'yes' if pause_state(root).get('awaiting_user') else 'no')
    for description,path in [('AGENTS',root/'AGENTS.md'),('product tasks',locations(root)[2]),('active task',locations(root)[1])]:
        print(description, 'present' if path.exists() else 'missing')
    try:print('configured checks',len(checks(root)[1]));print('quality policy', 'present' if (root/'.agent/core/quality.json').exists() else 'missing')
    except Problem as e:print('verification not ready:',e)
    return 0

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd())
    sub=p.add_subparsers(dest='command',required=True)
    for action in ['doctor','map','next','gate','finish','learning','maintenance']:sub.add_parser(action)
    m=sub.add_parser('mode');m.add_argument('choice',nargs='?',choices=['automatic','after_each_task'])
    a=sub.add_parser('ask');a.add_argument('--question',required=True);a.add_argument('--why',required=True)
    q=sub.add_parser('answer');q.add_argument('--answer',required=True)
    c=sub.add_parser('continue');c.add_argument('--decision',required=True,choices=['yes','no'])
    v=sub.add_parser('verify');v.add_argument('--expected-red',action='store_true',help='Expected TDD red phase; does not emit learning signals')
    s=sub.add_parser('start');s.add_argument('--task');s.add_argument('--risk',choices=list(RISKS),default='medium')
    args=p.parse_args(argv);root=args.root.resolve()
    if not root.is_dir():print('BLOCKED: project root does not exist',file=sys.stderr);return 2
    try:return {'doctor':doctor,'map':project_map,'next':next_task,'start':start,'verify':verify,'gate':check_gate,'finish':finish,'learning':learning,'maintenance':maintenance,'mode':mode,'ask':ask,'answer':answer,'continue':continue_after_task}[args.command](root,args)
    except Problem as e:print('BLOCKED:',e,file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
