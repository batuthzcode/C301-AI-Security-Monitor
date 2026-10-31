"""Safe update discovery: read GitHub Releases metadata, never execute downloads.
To install an update user manually reviews ZIP + changelog, installer verifies hashes,
and Ti creates a local backup for rollback.
"""
from __future__ import annotations
import json
import os
import re
import urllib.request


def latest_release(repo=None):
    repo=(repo or os.environ.get('TI_GITHUB_REPO','')).strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,70}/[A-Za-z0-9_.-]{1,100}',repo):
        raise RuntimeError('TI_GITHUB_REPO owner/repo şeklinde ayarlanmalı.')
    req=urllib.request.Request('https://api.github.com/repos/'+repo+'/releases/latest',
        headers={'User-Agent':'TiAI/2.0','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=10) as response:
        data=json.loads(response.read(160000))
    return {'version':str(data.get('tag_name',''))[:80],
            'url':str(data.get('html_url',''))[:400],
            'summary':str(data.get('name',''))[:120]}
