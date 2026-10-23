#!/usr/bin/env python3
"""Discover actual project files and keep a compact, factual navigation map.

Catalog entries describe optional outputs of the user's product-workflow skills.
The map does not treat expected paths as evidence that files exist.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

PRODUCT_OUTPUTS = (
    ('docs/product.md', 'product-discovery', 'Product goals and requirements'),
    ('docs/domain.md', 'domain-modeling', 'Domain concepts and business rules'),
    ('docs/specs.md', 'journey-specification', 'User journeys and expected behavior'),
    ('docs/architecture.md', 'solution-design', 'Approved solution and architecture decisions'),
    ('docs/implementation-plan.md', 'implementation-plan', 'Task descriptions and acceptance criteria'),
    ('.workflow/tasks.json', 'implementation-plan', 'Task references and dependencies'),
    ('AGENTS.md', 'product-discovery', 'Shared project instructions and documentation entry points'),
    ('docs/engineering-principles.md', 'product-discovery', 'Project-specific engineering principles'),
    ('tools/validate-workflow.py', 'product-discovery', 'Product-workflow document validation'),
)
STACK_OUTPUTS = (
    ('.agent/core/CONTRACT.md', 'Engineering ownership contract'),
    ('.agent/core/AUTONOMY.md', 'Continuation and clarification rules'),
    ('.agent/core/QUALITY_STANDARD.md', 'Engineering quality standard'),
    ('.agent/core/TESTING_STYLE.md', 'Lean user-flow test policy'),
    ('.agent/core/checks.json', 'Executable project verification commands'),
    ('.agent/core/quality.json', 'Project quality gate policy'),
    ('.agent/core/operation.json', 'User-selected continuation mode'),
    ('.agent/learning/guide/WORKFLOW.md', 'Learning process'),
    ('.agent/decisions/clarifications.jsonl', 'Answered product clarifications'),
    ('.claude/skills/engineering-mode/SKILL.md', 'Claude Code engineering router'),
    ('.agents/skills/engineering-mode/SKILL.md', 'Codex engineering router'),
)
EXCLUDE_DIRS={'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.mypy_cache','.tox',
    '.next','dist','build','coverage','vendor','target','.cache','.agent/backup'}
EXCLUDE_PREFIXES=('.agent/runs/','.agent/backup/','.agent/learning/events.jsonl',
    '.agent/learning/cases/','.agent/learning/proofs/','.agent/learning/records/',
    '.agent/decisions/',
    '.agent/core/active.json','.agent/core/continuation.json','.agent/core/clarification.json')
EXCLUDE_NAMES={'.coverage','.DS_Store','.agent/project-index.json','.agent/project-map.md'}
SENSITIVE={'id_rsa','id_ed25519','credentials.json','secrets.json','secret.json','.npmrc','.pypirc'}
SENSITIVE_SUFFIXES={'.pem','.p12','.pfx','.key','.sqlite','.sqlite3','.db','.log','.lock'}
MANIFESTS={'pyproject.toml','requirements.txt','package.json','Cargo.toml','go.mod','composer.json',
    'Gemfile','Dockerfile','docker-compose.yml','compose.yaml','Makefile','.github/workflows'}
ENTRY_NAMES={'main.py','__main__.py','app.py','cli.py','manage.py','server.py','index.ts','main.ts',
    'server.ts','index.js','server.js','main.go','main.rs','Program.cs'}
GENERATED='engineering-stack/project-intelligence/v1'
MAX_FILES=20000

class MapError(Exception):
    pass

def ignored(rel: Path):
    name=rel.name
    s=rel.as_posix()
    if rel.is_absolute() or '..' in rel.parts or not rel.parts: return True
    if any(part in EXCLUDE_DIRS for part in rel.parts): return True
    if s in EXCLUDE_NAMES or s.startswith(EXCLUDE_PREFIXES): return True
    if name in SENSITIVE or name.startswith('.env') and name not in {'.env.example','.env.sample','.env.template'}:
        return True
    if name.endswith('~') or name.startswith('.#') or rel.suffix in SENSITIVE_SUFFIXES: return True
    return False

def discover_paths(root: Path):
    try:
        completed=subprocess.run(['git','ls-files','-co','--exclude-standard','-z'],cwd=root,
            capture_output=True, timeout=20,check=False)
    except (OSError,subprocess.TimeoutExpired):
        completed=None
    if completed and completed.returncode==0:
        candidates=[Path(os.fsdecode(v)) for v in completed.stdout.split(b'\0') if v]
    else:
        candidates=[p.relative_to(root) for p in root.rglob('*') if p.is_file() or p.is_symlink()]
    chosen=[]
    for rel in sorted(set(candidates),key=lambda p:p.as_posix()):
        if ignored(rel):continue
        absolute=root/rel
        # Skip symlinks, including links to data outside the repository.
        if absolute.is_symlink() or not absolute.is_file():continue
        chosen.append(rel)
        if len(chosen)>MAX_FILES: raise MapError('Project has >20,000 indexed files. Fix Git ignores or exclusions.')
    return chosen

def category(rel: Path):
    s=rel.as_posix(); parts=rel.parts
    if s in {p for p,_,_ in PRODUCT_OUTPUTS}: return 'product-workflow'
    if s.startswith('.agent/') or s.startswith('.claude/skills/') or s.startswith('.agents/skills/'):
        return 'engineering-stack'
    if parts[0] in {'docs','documentation'} or rel.suffix.lower() in {'.md','.mdx','.rst'}:return 'documentation'
    if parts[0] in {'tests','test','spec','specs','e2e','integration'} or 'tests' in parts or 'test' in parts:
        return 'tests'
    if s in MANIFESTS or rel.name in MANIFESTS or parts[0]=='.github':return 'configuration'
    if rel.suffix.lower() in {'.py','.ts','.tsx','.js','.jsx','.go','.rs','.java','.kt','.cs','.rb','.php','.swift','.vue','.svelte','.sql','.html','.css'}:
        return 'source'
    return 'other'

def digest(path: Path):
    try:
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(65536),b''):h.update(block)
        return h.hexdigest()
    except OSError as exc:raise MapError(f'Cannot index {path}: {exc}') from exc

def build(root: Path):
    root=root.resolve()
    paths=discover_paths(root)
    files=[]
    for rel in paths:
        f=root/rel
        try: st=f.stat()
        except OSError as exc:raise MapError(f'Cannot stat {rel}: {exc}') from exc
        # File paths and fingerprints only, never embed source code or secrets in the index.
        files.append({'path':rel.as_posix(),'kind':category(rel),'size':st.st_size,'sha256':digest(f)})
    known={f['path'] for f in files}
    outputs=[{'path':path,'producer':producer,'purpose':purpose,'present':path in known}
         for path,producer,purpose in PRODUCT_OUTPUTS]
    stack=[{'path':path,'purpose':purpose,'present':path in known} for path,purpose in STACK_OUTPUTS]
    # A decision may have been captured in other docs; do not assert why code exists.
    summary={k:v for k,v in sorted(Counter(f['kind'] for f in files).items())}
    dirs={}
    for f in files:
        parent=str(Path(f['path']).parent)
        if parent=='.':parent='(root)'
        dirs[parent]=dirs.get(parent,0)+1
    probable=[f['path'] for f in files if Path(f['path']).name in ENTRY_NAMES]
    return {'generated_by':GENERATED,'schema_version':1,'file_count':len(files),
            'files':files,'categories':summary,'directories':dict(sorted(dirs.items())),
            'product_workflow':outputs,'engineering_stack':stack,
            'possible_entrypoints':probable[:60]}

def render(index):
    lines=[
      '# Project Map',
      '',
      '> Generated by Engineering Stack Project Intelligence. Do not edit manually.',
      '> Navigation aid only: inspect current source and product documents before changes.',
      '',
      '## Sources of truth',
      '',
      'Product intent belongs to the product-workflow artifacts. Engineering Stack owns implementation,',
      'quality, verification, task continuation and maintenance. Missing files are not assumed to exist.',
      '',
      '### Product-workflow outputs',
      '',
      '| Status | File | Producing skill | Purpose |',
      '| --- | --- | --- | --- |',
    ]
    for item in index['product_workflow']:
        lines.append(f"| {'Present' if item['present'] else 'Not present'} | `{item['path']}` | `{item['producer']}` | {item['purpose']} |")
    lines += ['', '### Engineering Stack', '', '| Status | File | Purpose |', '| --- | --- | --- |']
    for item in index['engineering_stack']:
        lines.append(f"| {'Present' if item['present'] else 'Not present'} | `{item['path']}` | {item['purpose']} |")
    lines += ['', '## Discovered repository structure', '',
        f"Indexed files: **{index['file_count']}**. All indexed paths are recorded in `.agent/project-index.json`.",
        '', 'These folders and counts come from the actual filesystem; they are not architectural claims.', '',
        '| Directory | Indexed files |','| --- | ---: |']
    for folder,count in sorted(index['directories'].items(),key=lambda x:(-x[1],x[0]))[:70]:
        lines.append(f'| `{folder}` | {count} |')
    if len(index['directories'])>70:lines.append('| Other directories | See `project-index.json` |')
    lines += ['', '## Possible application entry points', '']
    if index['possible_entrypoints']:
        lines.extend(f'- `{path}` (name-based candidate; inspect before relying on it)' for path in index['possible_entrypoints'])
    else:lines.append('None identified by filename. Inspect the repository when needed.')
    lines += ['', '## How to use this map', '',
        '1. Read this map to locate relevant product documents, modules, verification and learning controls.',
        '2. Inspect the actual source before editing; the map does not store inferred code behavior.',
        '3. Use `python3 .agent/core/engine.py map` to update the map after files change.',
        '4. The engine refreshes it during `doctor`, `next`, `start`, `verify` and `maintenance`.',
        '5. `gate`/`finish` check freshness without silently rewriting verification evidence.',
        '', '## Unknown or unverified information', '',
        '- Missing product documents require product clarification or the relevant product-workflow step, not invented content.',
        '- Module responsibilities, architecture dependencies and business invariants must be read from actual source and approved docs.',
        '- Runtime behavior, deployment capability and test coverage are not inferred from filenames.',
        '']
    return '\n'.join(lines)

def _existing_generated(path:Path,is_json=False):
    if not path.exists():return True
    try:
        data=path.read_text(encoding='utf-8')
        if is_json:return json.loads(data).get('generated_by')==GENERATED
        return data.startswith('# Project Map\n') and 'Generated by Engineering Stack Project Intelligence' in data[:300]
    except (OSError,ValueError,AttributeError):return False

def refresh(root:Path,check_only=False):
    root=root.resolve()
    index=build(root)
    output=root/'.agent/project-index.json'
    markdown=root/'.agent/project-map.md'
    for path,js in ((output,True),(markdown,False)):
        if not _existing_generated(path,js):
            raise MapError(f'Existing {path.relative_to(root)} is not generated by Engineering Stack; preserve it and resolve the conflict manually')
    expected_json=json.dumps(index,indent=2,ensure_ascii=False)+'\n'
    expected_md=render(index)
    desired=((output,expected_json),(markdown,expected_md))
    changes=[p for p,data in desired if not p.exists() or p.read_text(encoding='utf-8')!=data]
    if check_only:return (not changes),[p.relative_to(root).as_posix() for p in changes]
    for path,data in desired:
        if path not in changes:continue
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+'.tmp')
        tmp.write_text(data,encoding='utf-8')
        tmp.replace(path)
    return True,[p.relative_to(root).as_posix() for p in changes]

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--check',action='store_true',help='Exit 2 if project map is outdated')
    args=parser.parse_args(argv)
    try:
        fresh,changed=refresh(args.root,check_only=args.check)
    except MapError as exc:
        print('BLOCKED:',exc,file=sys.stderr);return 2
    if args.check and not fresh:
        print('STALE:',', '.join(changed));return 2
    print('PROJECT MAP:', 'CURRENT' if fresh and not changed else 'UPDATED', ', '.join(changed))
    return 0

if __name__=='__main__':sys.exit(main())
