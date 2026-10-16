"""Independent audit around read:dafeng:L1:0245.

Two purposes, both re-derivable from disk (no build-time intermediates):
  1. Is the EXISTING candidate (written by w-dafeng-1) sound? -> quote offsets,
     uniqueness, five-slot discipline, worldSettings discriminators.
  2. Was this task already completed when w-read-3 claimed it? -> done_ids() etc.

Run: python3 -B -s loop/state/out/read_dafeng_L1_0245.w-read-3.build/audit_conflict.py
"""
import hashlib
import importlib.util
import json
import pathlib
import time

ROOT = pathlib.Path('/Users/carmen/Desktop/星系')
BUILD = ROOT / 'loop/state/out/read_dafeng_L1_0245.w-read-3.build'
R = {}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ── A. source identity ───────────────────────────────────────────────────────
docs_p = ROOT / 'data/cache/1063b17ca65ec1b76f30e460.docs.json'
raw = docs_p.read_bytes()
R['source_sha256'] = hashlib.sha256(raw).hexdigest()
T = json.loads(raw.decode('utf-8'))[0]['text']
S, E = 994884, 1001227
sl = T[S:E]
R['slice_codepoints'] = len(sl)
R['slice_sha256'] = hashlib.sha256(sl.encode('utf-8')).hexdigest()
R['slice_starts_with_unit_head'] = sl.startswith('第十六章 金莲道长：把许七安推出来背锅')
R['text_total_codepoints'] = len(T)

# ── B. candidate / record identity ───────────────────────────────────────────
cand_p = ROOT / 'loop/state/out/read_dafeng_L1_0245.candidate.json'
rec_p = ROOT / 'loop/state/out/read_dafeng_L1_0245.json'
R['candidate_sha256'] = sha(cand_p)
R['record_sha256'] = sha(rec_p)
cand = json.loads(cand_p.read_text())

# ── C. quote audit (all sections, recursive) ─────────────────────────────────
nodes = []


def walk(o, path=''):
    if isinstance(o, dict):
        if isinstance(o.get('quote'), str):
            nodes.append((path, o))
        for k, v in o.items():
            walk(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + '[%d]' % i)


walk(cand)

has_ref = lambda d: isinstance(d, dict) and 'start' in d and 'end' in d

mismatch, outrange, nonuniq, badhash, orphan = [], [], [], [], []
verified = set()
for p, d in nodes:
    if has_ref(d):
        s, e, q, h = d['start'], d['end'], d['quote'], d.get('sourceHash')
    elif has_ref(d.get('quoteRef')):
        qr = d['quoteRef']
        if qr.get('quote') != d['quote']:
            mismatch.append([p, 'quote != quoteRef.quote'])
            continue
        s, e, q, h = qr['start'], qr['end'], d['quote'], qr.get('sourceHash')
    else:
        orphan.append([p, d['quote'][:40]])
        continue
    if T[s:e] != q:
        mismatch.append([p, q[:40]])
        continue
    if not (S <= s and e <= E):
        outrange.append([p, q[:40]])
    n = T.count(q)
    if n != 1:
        nonuniq.append([p, n, q[:40]])
    if h and h != R['source_sha256']:
        badhash.append([p, str(h)[:12]])
    verified.add((s, e, q))

R['quote_nodes'] = len(nodes)
R['quotes_verified_unique_refs'] = len(verified)
R['quotes_offset_mismatch'] = mismatch
R['quotes_out_of_range'] = outrange
R['quotes_not_unique_in_range'] = nonuniq
R['quotes_sourcehash_mismatch'] = badhash
R['quotes_orphan_no_offset'] = orphan

# ── D. tasks: five slots, each with its own evidence ─────────────────────────
SLOTS = ('objective', 'obstacle', 'action', 'result', 'cost')
slot_problems, shared_in_task = [], []
for t in cand.get('tasks', []):
    per = {}
    for s in SLOTS:
        v = t.get(s)
        if v is None:
            if not t.get(s + 'Note'):
                slot_problems.append([t.get('id'), s, 'null-without-Note'])
            continue
        qs = [x.get('quote') for x in (v.get('quotes') or [])]
        if not qs:
            slot_problems.append([t.get('id'), s, 'non-null-without-quotes'])
        for q in qs:
            per.setdefault(q, []).append(s)
    for q, ss in per.items():
        if len(ss) > 1:
            shared_in_task.append([t.get('id'), ss, q[:40]])
R['tasks_count'] = len(cand.get('tasks', []))
R['tasks_slot_problems'] = slot_problems
R['tasks_shared_quote_across_slots'] = shared_in_task

# ── E. worldSettings discriminators ──────────────────────────────────────────
ws = cand.get('worldSettings', [])
wshare = {}
for w in ws:
    for q in {w.get('quote')}:
        if q:
            wshare.setdefault(q, []).append(w.get('id'))
R['worldSettings_count'] = len(ws)
R['worldSettings_kinds'] = {k: sum(1 for w in ws if w.get('kind') == k)
                            for k in ('rule', 'place', 'item')}
R['worldSettings_shared_quotes'] = {k[:40]: v for k, v in wshare.items() if len(v) > 1}
R['worldSettings_missing_discriminator'] = {
    'place': [w.get('id') for w in ws if w.get('kind') == 'place' and not w.get('placeState')],
    'item': [w.get('id') for w in ws if w.get('kind') == 'item' and not w.get('itemStates')],
    'rule': [w.get('id') for w in ws if w.get('kind') == 'rule' and not w.get('institution')],
}
R['worldSettings_bad_enum'] = (
    [[w.get('id'), 'placeState', w.get('placeState')] for w in ws
     if w.get('kind') == 'place' and w.get('placeState') not in ('arrived', 'mentioned')]
    + [[w.get('id'), 'institution', w.get('institution')] for w in ws
       if w.get('kind') == 'rule' and w.get('institution') not in
       ('declared', 'executed', 'misunderstood')]
    + [[w.get('id'), 'itemState', s] for w in ws if w.get('kind') == 'item'
       for s in (w.get('itemStates') or []) if s not in ('hold', 'transfer', 'use', 'lose')]
)

# ── F. other sections shape ──────────────────────────────────────────────────
R['causeEdges_keys'] = sorted({k for e in cand.get('causeEdges', []) for k in e})
R['causeEdges_count'] = len(cand.get('causeEdges', []))
R['states_count'] = len(cand.get('states', []))
R['foreshadows'] = [[f.get('id'), f.get('unresolved'), bool(f.get('setup')), bool(f.get('payoff'))]
                    for f in cand.get('foreshadows', [])]
R['themeReadings_fields'] = [[t.get('id'), bool(t.get('perspective')),
                              bool(t.get('support')), bool(t.get('counter'))]
                             for t in cand.get('themeReadings', [])]
R['themeReadings_count'] = len(cand.get('themeReadings', []))
R['unknowns_count'] = len(cand.get('unknowns', []))
R['selfCritique_count'] = len(cand.get('selfCritique', []))

# ── G. scheduler view: was the task already done? ────────────────────────────
spec = importlib.util.spec_from_file_location('lm', ROOT / 'loop/bin/loop.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

t0 = time.time()
done = m.done_ids()
R['done_ids_seconds'] = round(time.time() - t0, 2)
R['done_ids_count'] = len(done)
R['record_files_count'] = len(m.record_files())
TID = 'read:dafeng:L1:0245'
R['task_in_done_ids'] = TID in done
R['done_ids_agent'] = (done.get(TID) or {}).get('agent')
rec = m.load_json(ROOT / 'loop/state/out/read_dafeng_L1_0245.json', {}) or {}
R['record_validated'] = m.validated(rec)
R['record_evidence_stale'] = m.evidence_stale(rec)
R['record_verifyState'] = rec.get('verifyState')
R['record_submittedAt'] = rec.get('submittedAt')
R['verify_verdict_exists'] = (ROOT / 'loop/state/out/verify_dafeng_L1_0245.verdict.json').exists()
R['lease_agent'] = (m.load_json(m.lease_dir(TID) / 'lease.json', {}) or {}).get('agent')

(BUILD / 'audit_conflict_report.json').write_text(
    json.dumps(R, ensure_ascii=False, indent=1), encoding='utf-8')

for k in ('source_sha256', 'slice_codepoints', 'slice_sha256', 'slice_starts_with_unit_head',
          'candidate_sha256', 'record_sha256', 'quote_nodes', 'quotes_verified_unique_refs',
          'quotes_offset_mismatch', 'quotes_out_of_range', 'quotes_not_unique_in_range',
          'quotes_sourcehash_mismatch', 'quotes_orphan_no_offset',
          'tasks_count', 'tasks_slot_problems', 'tasks_shared_quote_across_slots',
          'worldSettings_count', 'worldSettings_kinds', 'worldSettings_shared_quotes',
          'worldSettings_missing_discriminator', 'worldSettings_bad_enum',
          'foreshadows', 'themeReadings_fields',
          'done_ids_seconds', 'done_ids_count', 'record_files_count',
          'task_in_done_ids', 'done_ids_agent', 'record_validated',
          'record_evidence_stale', 'record_verifyState', 'record_submittedAt',
          'verify_verdict_exists', 'lease_agent'):
    print(k, '=', json.dumps(R.get(k), ensure_ascii=False))
