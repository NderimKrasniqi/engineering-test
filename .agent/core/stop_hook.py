#!/usr/bin/env python3
"""Optional Claude Code Stop hook. Checks gate; does not automatically grant authority."""
import json,os,subprocess,sys
from pathlib import Path

def main():
    try:payload=json.load(sys.stdin)
    except (ValueError,OSError):payload={}
    if payload.get('stop_hook_active'):return 0  # Avoid deadlock; report blocker visibly.
    root=Path(os.environ.get('CLAUDE_PROJECT_DIR',Path.cwd())).resolve()
    if (root/'.agent/core/clarification.json').exists():
        return 0  # The agent must be able to stop and ask the user.
    if not (root/'.agent/core/active.json').exists():return 0
    p=subprocess.run([sys.executable,str(root/'.agent/core/engine.py'),'--root',str(root),'gate'],
                     text=True,capture_output=True,timeout=40)
    if p.returncode:
        msg=(p.stderr or p.stdout).strip()[-900:]
        print(json.dumps({'decision':'block','reason':'Engineering task is not verified. '+msg+' Run checks or report a blocker.'}))
    return 0
if __name__=='__main__':sys.exit(main())
