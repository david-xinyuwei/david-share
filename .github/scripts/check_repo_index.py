#!/usr/bin/env python3
"""Check the repository index pages.

Fails when an area page does not list one of its project folders, when an index page links to a path
that does not exist, when a moved notice points to a missing folder or to another moved notice, or when
a README still contains the generated `<this-repo-url>` placeholder.
"""
import posixpath
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREAS = ['Agents', 'Deep-Learning', 'Multimodal-Models', 'DL-Algorithm-Insights']
EXTRA_INDEX_PAGES = ['README.md', 'Code-of-Book/README.md', 'Code-of-Book-Edge-AI/README.md', 'Code-of-Book-Edge-AI/README-CN.md']
MOVED = re.compile(r'<!--\s*moved-to:\s*(\S+)\s*-->')
LINKS = [re.compile(r'\]\(\s*<?([^)\s>]+)'), re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.I), re.compile(r'^\s*\[[^\]]+\]:\s*(\S+)', re.M)]
THIS_REPO = re.compile(r'^https?://github\.com/(?:david-xinyuwei|xinyuwei-david)/david-share/(?:tree|blob)/master/(.*)$', re.I)


def git_files():
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], check=True, capture_output=True).stdout
    return {p for p in out.decode('utf-8').split('\0') if p}


FILES = git_files()
DIRS = {posixpath.dirname(p) for p in FILES}
DIRS |= {'/'.join(d.split('/')[:i]) for d in list(DIRS) for i in range(1, d.count('/') + 1)}


def read(path):
    disk = ROOT / path
    if disk.is_file():
        return disk.read_text(encoding='utf-8', errors='replace')
    out = subprocess.run(['git', '-C', str(ROOT), 'show', f'HEAD:{path}'], capture_output=True)
    return out.stdout.decode('utf-8', 'replace')


def readme_in(folder):
    return next((p for p in sorted(FILES) if posixpath.dirname(p) == folder and posixpath.basename(p).lower() == 'readme.md'), None)


def links(text):
    for pattern in LINKS:
        for m in pattern.finditer(text):
            yield m.group(1)


def resolve(page, link):
    """Return the repository path a link points to, or None when it is external or an in-page anchor."""
    m = THIS_REPO.match(link)
    if m:
        target = m.group(1)
    elif link.startswith('#') or re.match(r'^[a-z][a-z0-9+.-]*:', link, re.I):
        return None
    else:
        target = posixpath.join(posixpath.dirname(page), link)
    target = urllib.parse.unquote(target.split('#', 1)[0].split('?', 1)[0])
    return posixpath.normpath(target).strip('/') if target.strip('/') else ''


def exists(path):
    return path in ('', '.') or path in FILES or path in DIRS


problems = []
index_pages = [p for p in EXTRA_INDEX_PAGES if p in FILES]
for area in AREAS:
    page = next((f'{area}/{n}' for n in ('README.md', 'README.MD') if f'{area}/{n}' in FILES), None)
    if page is None:
        problems.append(f'{area}: no README.md index page')
        continue
    index_pages.append(page)
    listed = set()
    for link in links(read(page)):
        target = resolve(page, link)
        if target and target.startswith(area + '/'):
            listed.add(target.split('/')[1])
    projects = sorted({p.split('/')[1] for p in FILES if p.startswith(area + '/') and p.count('/') >= 2})
    for name in projects:
        folder = f'{area}/{name}'
        readme = readme_in(folder)
        if readme and MOVED.search(read(readme)):
            continue
        if name not in listed:
            problems.append(f'{page}: project folder {folder}/ is not listed')

for page in index_pages:
    for link in links(read(page)):
        target = resolve(page, link)
        if target is not None and not exists(target):
            problems.append(f'{page}: link to missing path {link}')

moved_pages = 0
for path in sorted(FILES):
    if not path.lower().endswith('.md'):
        continue
    text = read(path)
    if '<this-repo-url>' in text:
        problems.append(f'{path}: generated placeholder <this-repo-url>')
    m = MOVED.search(text)
    if not m:
        continue
    moved_pages += 1
    target = resolve(path, m.group(1))
    if target is None or target not in DIRS:
        problems.append(f'{path}: moved notice points to missing folder {m.group(1)}')
        continue
    target_readme = readme_in(target)
    if target_readme and MOVED.search(read(target_readme)):
        problems.append(f'{path}: moved notice points to another moved notice {m.group(1)}')

print(f'index pages checked: {len(index_pages)}; moved notices checked: {moved_pages}; problems: {len(problems)}')
for p in problems:
    print(f'  - {p}')
sys.exit(1 if problems else 0)
