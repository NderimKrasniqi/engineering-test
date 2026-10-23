#!/usr/bin/env python3
"""Safely add a small managed Project Intelligence pointer to agent instructions."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

BEGIN='<!-- ENGINEERING-STACK:BEGIN -->'
END='<!-- ENGINEERING-STACK:END -->'
CLAUDE_BEGIN='<!-- ENGINEERING-STACK:CLAUDE -->'
CLAUDE_END='<!-- /ENGINEERING-STACK:CLAUDE -->'
BLOCK=(BEGIN+'\n'
       '## Engineering Stack — Project Navigation and Execution\n\n'
       '- The user and `product-workflow` documents own WHAT. The agent owns HOW: readable, maintainable, secure, and appropriately scalable code.\n'
       '- Ask about material missing product decisions; never invent requirements. Make ordinary engineering decisions independently.\n'
       '- Read `.agent/project-map.md` first to find approved product artifacts and actual project files.\n'
       '- Use `.agent/project-index.json` for indexed paths; inspect real source before changes. Missing files are not assumed to exist.\n'
       '- Respect the user-selected continuation mode in `.agent/core/operation.json`.\n'
       '- Implement with few meaningful E2E user-flow tests, justified edge-case guards, and minimal comments.\n'
       '- Run the Engineering Stack verification, quality gate, and learning maintenance before completing tasks.\n'
       '- Delegate selectively through native subagents; main owns integration and completion. Read `.agent/core/DELEGATION.md` and respect `.agent/core/delegation.json`.\n'
       '- Use `.agent/core/CONTRACT.md`, `AUTONOMY.md`, `QUALITY_STANDARD.md` and `PROJECT_INTELLIGENCE.md` when relevant.\n'
       +END+'\n')
CLAUDE_BLOCK=(CLAUDE_BEGIN+'\n@AGENTS.md\n'+CLAUDE_END+'\n')

class LinkError(Exception): pass

def plan(path:Path,begin:str,end:str,block:str,require=None):
    if path.is_symlink():raise LinkError(f'Refusing to edit symlink: {path.name}')
    content=path.read_text(encoding='utf-8') if path.exists() else ''
    if content.count(begin)!=content.count(end) or content.count(begin)>1:
        raise LinkError(f'Invalid managed section in {path.name}')
    if require and require in content:
        return None
    if begin in content:
        a=content.index(begin);b=content.index(end)+len(end)
        updated=content[:a]+block.rstrip('\n')+content[b:]
    else:
        updated=content.rstrip('\n')+'\n\n'+block if content.strip() else block
    return updated if updated!=content else None

def changes(root:Path):
    root=root.resolve()
    shared=root/'AGENTS.md'; claude=root/'CLAUDE.md'
    shared_new=plan(shared,BEGIN,END,BLOCK)
    # Claude Code reads AGENTS.md in certain configurations, but explicit import
    # avoids relying on the project's instructionFiles mode.
    claude_new=plan(claude,CLAUDE_BEGIN,CLAUDE_END,CLAUDE_BLOCK,require='@AGENTS.md')
    return [(p,text) for p,text in ((shared,shared_new),(claude,claude_new)) if text is not None]

def wire(root:Path,check_only=False):
    todo=changes(root)
    if check_only:return not todo,[p.name for p,_ in todo]
    for path,new_text in todo:
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_name(path.name+'.engineering-tmp')
        temp.write_text(new_text,encoding='utf-8')
        temp.replace(path)
    return True,[p.name for p,_ in todo]

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd());parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    try:good,files=wire(args.root,check_only=args.check)
    except (LinkError,OSError) as exc:
        print('BLOCKED:',exc,file=sys.stderr);return 2
    if not good:print('MISSING INSTRUCTION LINKS:',', '.join(files));return 2
    print('INSTRUCTIONS:', 'updated '+', '.join(files) if files else 'current')
    return 0
if __name__=='__main__':raise SystemExit(main())
