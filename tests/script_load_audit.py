#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact index.html/script_manifest.json loading-order and hash gate."""
import argparse
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INDEX_HTML = os.path.join(BASE_DIR, 'index.html')
MANIFEST_JSON = os.path.join(os.path.dirname(__file__), 'script_manifest.json')
HEX8 = re.compile(r'^[0-9a-f]{8}$')


class ScriptParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.scripts = []
        self.active = False
        self.src = None
        self.body = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'script':
            self.active = True
            self.attrs = dict(attrs)
            self.src = self.attrs.get('src')
            self.body = []

    def handle_data(self, data):
        if self.active:
            self.body.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self.active:
            self.scripts.append((self.src, ''.join(self.body), self.attrs))
            self.active = False
            self.src = None
            self.body = []


def load_manifest(path=MANIFEST_JSON):
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    rows = doc.get('scripts') if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('manifest.scripts must be a non-empty list')
    return rows


def file_hash(path, base_dir=BASE_DIR):
    with open(os.path.join(base_dir, path), 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:8]


def split_src(src):
    if not isinstance(src, str):
        return '', None
    path, _, query = src.partition('?')
    params = dict(x.split('=', 1) for x in query.split('&') if '=' in x)
    return path, params.get('v')


def audit_text(html, manifest, base_dir=BASE_DIR, require_files=True, label='index.html'):
    p = ScriptParser()
    p.feed(html)
    tags = p.scripts
    paths = [split_src(src)[0] for src, _, _ in tags]
    expected = [row.get('path') for row in manifest]
    errors = []
    if any(not src for src, _, _ in tags):
        errors.append('script tag without src present')
    if len(expected) != len(set(expected)):
        errors.append('manifest duplicate path')
    if len(paths) != len(set(paths)):
        errors.append('HTML duplicate script path')
    if paths != expected:
        errors.append('HTML sequence is not exactly manifest (missing/extra/order)')
    by_path = {row.get('path'): row for row in manifest}
    for i, row in enumerate(manifest):
        path = row.get('path')
        if not isinstance(path, str) or not path:
            errors.append('manifest entry %d has invalid path' % i)
            continue
        if row.get('mode') != 'classic':
            errors.append('%s mode is not classic' % path)
        deps = row.get('dependsOn', [])
        if not isinstance(deps, list):
            errors.append('%s dependsOn is not a list' % path)
            deps = []
        for dep in deps:
            if dep not in by_path:
                errors.append('%s depends on missing %s' % (path, dep))
            elif expected.index(dep) >= i:
                errors.append('dependency order violation: %s -> %s' % (path, dep))
    vendors = [x for x in expected if x.startswith('js/vendor/')]
    if len(vendors) != 9:
        errors.append('vendor count %d, expected 9' % len(vendors))
    if expected[:9] != vendors:
        errors.append('vendor scripts are not first nine')
    core = sum(row.get('group') == 'core' for row in manifest)
    if core > 40:
        errors.append('core group exceeds 40 (%d)' % core)
    for i, (src, _, attrs) in enumerate(tags):
        if attrs.get('type') or 'async' in attrs or 'defer' in attrs:
            errors.append('%s tag %d is not classic synchronous script' % (label, i + 1))
        if not src:
            continue
        path, version = split_src(src)
        if not version or not HEX8.match(version):
            errors.append('%s tag %d lacks lowercase 8-char hash' % (label, i + 1))
            continue
        if require_files and path in by_path:
            try:
                actual = file_hash(path, base_dir)
            except OSError as exc:
                errors.append('%s unreadable: %s' % (path, exc))
                continue
            if version != actual:
                errors.append('%s hash %s != actual %s' % (path, version, actual))
    return errors


def synthetic_html(manifest, base_dir=BASE_DIR):
    return '\n'.join('<script src="%s?v=%s"></script>' % (row['path'], file_hash(row['path'], base_dir)) for row in manifest)


def self_test():
    manifest = load_manifest()
    positive = synthetic_html(manifest)
    cases = [('positive', positive, manifest, True)]
    bad = positive.replace(file_hash(manifest[0]['path']), '00000000', 1)
    cases.append(('wrong hash', bad, manifest, False))
    cases.append(('removed module', '\n'.join(positive.splitlines()[:-1]), manifest, False))
    i = next(i for i, row in enumerate(manifest) if row.get('dependsOn'))
    swapped = list(manifest)
    dep = swapped[i]['dependsOn'][0]
    j = next(j for j, row in enumerate(swapped) if row['path'] == dep)
    swapped[i], swapped[j] = swapped[j], swapped[i]
    cases.append(('dependency order', synthetic_html(swapped), swapped, False))
    duplicate = list(manifest) + [dict(manifest[-1])]
    cases.append(('duplicate', synthetic_html(duplicate), duplicate, False))
    cases.append(('empty inline', positive + '<script></script>', manifest, False))
    cases.append(('nonempty inline', positive + '<script>bad()</script>', manifest, False))
    cases.append(('module mode', positive.replace('<script src=', '<script type="module" src=', 1), manifest, False))
    failed = []
    for name, html, rows, expected_ok in cases:
        got = not audit_text(html, rows)
        print('[SELF-TEST %s] %s' % ('PASS' if got == expected_ok else 'FAIL', name))
        if got != expected_ok:
            failed.append('%s: %s' % (name, audit_text(html, rows)))
    if failed:
        for item in failed:
            print('[FAIL] ' + item)
        return 1
    print('[PASS] positive plus four negative gates')
    return 0


def audit_real():
    manifest = load_manifest()
    with open(INDEX_HTML, encoding='utf-8') as fh:
        html = fh.read()
    errors = audit_text(html, manifest)
    parser = ScriptParser()
    parser.feed(html)
    print('[INFO] manifest scripts: %d; HTML scripts: %d' % (len(manifest), len(parser.scripts)))
    for error in errors:
        print('[FAIL] ' + error)
    if not errors:
        print('[PASS] exact sequence, dependencies, hashes, vendor prefix, and budgets')
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    return self_test() if args.self_test else audit_real()


if __name__ == '__main__':
    sys.exit(main())
