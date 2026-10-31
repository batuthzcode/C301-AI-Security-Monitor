"""Explicit GitHub draft-PR publishing of a reviewed Markdown proposal.
Never commits or uploads camera data, passwords, app settings, or source files.
Creates a throwaway git worktree; never writes into the working source tree.
This is NOT autonomous code editing or merging.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def _run(args,*,cwd,timeout=25):
    result=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=timeout,check=False)
    if result.returncode:raise RuntimeError(f'{args[0]} başarısız: {(result.stderr or result.stdout)[-350:]}')
    return result.stdout.strip()


def publish_proposal(repository,proposal,*,base='main',confirmed=False):
    if not confirmed:raise PermissionError('GitHub yayınlama için açık kullanıcı onayı gerekir.')
    if not re.fullmatch(r'[A-Za-z0-9._/-]{1,90}',base) or base.startswith('-') or '..' in base:
        raise ValueError('Geçersiz temel dal.')
    repo=Path(repository).resolve()
    note=Path(proposal).resolve()
    if not (repo/'.git').exists() or not note.is_file() or note.suffix.lower()!='.md':
        raise ValueError('Yerel git deposu ve hazırlanmış .md öneri dosyası gerekli.')
    if note.stat().st_size>15000:raise ValueError('Öneri en fazla 15 KB olabilir.')
    content=note.read_text(encoding='utf-8')
    if not content.startswith('# Ti Developer'):
        raise ValueError('Yalnızca Ti Developer önerisi gönderilebilir.')
    if not shutil.which('git') or not shutil.which('gh'):
        raise RuntimeError('git ve GitHub CLI (gh) gerekli.')
    # These are solely metadata; never send full repo status or environment variables to model.
    _run(['gh','auth','status'],cwd=repo)
    name='ti/proposal-'+datetime.now().strftime('%Y%m%d%H%M%S')
    with tempfile.TemporaryDirectory(prefix='ti-github-worktree-') as td:
        worktree=Path(td)/'repo'
        _run(['git','worktree','add','-b',name,str(worktree),base],cwd=repo)
        try:
            dest=worktree/'docs'/'ti-proposals'/'suggestion.md'
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(content,encoding='utf-8')
            _run(['git','add','--','docs/ti-proposals/suggestion.md'],cwd=worktree)
            _run(['git','commit','-m','docs: add reviewed Ti improvement proposal'],cwd=worktree)
            _run(['git','push','-u','origin',name],cwd=worktree,timeout=55)
            link=_run(['gh','pr','create','--draft','--base',base,'--head',name,
                     '--title','Ti AI: Reviewed improvement proposal',
                     '--body','Read-only development proposal. No automatic code changes.'],cwd=worktree,timeout=35)
            return link
        finally:
            _run(['git','worktree','remove','--force',str(worktree)],cwd=repo)
