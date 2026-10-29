#!/usr/bin/env python3
"""Check packaged links, inventory, metadata and obvious private-path exclusions."""
import ast
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/project-improvement-agent'


def files():
    patterns=['README.md','LICENSE','NOTICE','.gitignore','.github/workflows/*.yml',
              'docs/*.md','docs/*.json','examples/*.md','scripts/*.py','tests/*.py',
              'skills/project-improvement-agent/**/*','toolbox/index.json']
    return sorted({f for pattern in patterns for f in ROOT.glob(pattern)
                   if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'})


def validate():
    errors=[];paths=files()
    for f in paths:
        relative=f.relative_to(ROOT).as_posix()
        if f.is_symlink():errors.append('symlink: '+relative)
        text=f.read_text()
        if re.search(r'/Users/[A-Za-z0-9_.-]+/|01a[0-9a-f]{5}-[0-9a-f-]{27,}',text):errors.append('private host path/id: '+relative)
        if f.suffix=='.py':ast.parse(text,filename=relative)
        if f.suffix=='.json':json.loads(text)
        if f.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',text):
                if '://' in target or target.startswith('#'):continue
                target=target.split('#',1)[0]
                if not (f.parent/target).is_file():errors.append('missing link '+relative+' -> '+target)
    for root in (ROOT,SKILL):
        try:
            index=json.loads((root/'toolbox/index.json').read_text())
        except (OSError, ValueError) as exc:
            errors.append('unreadable inventory at '+root.name+': '+str(exc))
            continue
        indexed={r['location'] for r in index['resources']}
        actual={f.relative_to(root).as_posix() for f in paths if root in f.parents}
        if indexed!=actual:errors.append('inventory mismatch at '+root.name+': '+str(indexed^actual))
    skill=(SKILL/'SKILL.md').read_text()
    if not skill.startswith('---\nname: project-improvement-agent\ndescription:'):errors.append('skill metadata')
    if 'allow_implicit_invocation: false' not in (SKILL/'agents/openai.yaml').read_text():errors.append('manual policy')
    print(json.dumps({'ok':not errors,'files':len(paths),'errors':errors,'limits':'Structural and narrow pattern checks only; exact publication review still required.'},indent=2))
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(validate())
