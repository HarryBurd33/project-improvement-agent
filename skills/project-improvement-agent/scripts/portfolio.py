#!/usr/bin/env python3
"""Private portfolio records. No source crawler, model calls or project mutations."""
import argparse
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

VERSION = 1
LIMITS = dict(seconds=1800, actions=120, projects=300, materials=30,
              bytes=2097152, calls=40, deep_reviews=3)
FACETS = {
    'software': ['purpose', 'implementation', 'validation', 'limitations'],
    'skill': ['purpose', 'implementation', 'validation', 'limitations'],
    'agent': ['purpose', 'implementation', 'validation', 'limitations'],
    'writing': ['purpose', 'draft', 'sources', 'audience'],
    'research': ['question', 'method', 'evidence', 'limitations'],
    'coursework': ['objectives', 'work', 'feedback', 'gaps'],
    'design': ['purpose', 'output', 'validation', 'limitations'],
    'other': ['purpose', 'output', 'validation', 'limitations'],
}
PROMPT_FIELDS = ['context', 'targets', 'outcome', 'scope', 'constraints', 'preserve', 'verification']


def need(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def stable(kind, identity):
    need(nonempty(identity), 'stable native identity required')
    return kind + '-' + hashlib.sha256(identity.encode()).hexdigest()[:20]


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def safe(path):
    p = Path(path).expanduser().absolute()
    need('..' not in p.parts, 'parent traversal refused')
    for part in [*reversed(p.parents), p]:
        need(not part.is_symlink(), 'symlink path refused')
    return p


def atomic(path, value):
    data = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.write-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def envelope(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'data': data}


def load(path):
    x = json.loads(path.read_text())
    need(x == envelope(x['data']), 'state checksum mismatch; inspect previous.json before recovery')
    need(x['data']['schema_version'] == VERSION, 'unsupported state schema')
    return x['data']


class Store:
    def __init__(self, path):
        self.path = safe(path)
        package = Path(__file__).resolve().parents[1]
        need(self.path != package and package not in self.path.parents,
             'private state must be outside reusable package')

    def init(self):
        self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
        d = dict(schema_version=VERSION, created_at=now(), projects={}, sources={},
                 materials={}, evidence={}, findings={}, associations=[], runs=[], active=None)
        atomic(self.path / 'state.json', envelope(d))
        return self.path.as_posix()

    @contextlib.contextmanager
    def transaction(self):
        need(self.path.is_dir(), 'initialize private state first')
        safe(self.path / 'lock')
        fd = os.open(str(self.path / 'lock'), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            d = load(safe(self.path / 'state.json'))
            yield d
            atomic(safe(self.path / 'previous.json'), load_envelope(self.path / 'state.json'))
            atomic(self.path / 'state.json', envelope(d))

    def read(self):
        return load(safe(self.path / 'state.json'))

    def start(self, mode=None, owner='', checks=None, limits=None):
        need(mode in (None, 'broad', 'comprehensive'), 'invalid mode')
        need(nonempty(owner), 'current owner required')
        need(checks and all(nonempty(c.get('id')) and nonempty(c.get('expected')) and
                           nonempty(c.get('method')) for c in checks), 'freeze checks before run')
        with self.transaction() as d:
            need(d['active'] is None, 'active run exists; reconcile exact owner/token, never steal')
            if mode is None:
                mode = d['runs'][-1]['mode'] if d['runs'] else 'broad'
            for project in d['projects'].values():
                if project['status'] == 'deep' and any(
                    d['materials'][d['evidence'][eid]['material']]['version'] is None
                    for rev in project['reviews'][-1:] for eid in rev['evidence']):
                    project['status'] = 'needs_recheck'
            for finding in d['findings'].values():
                if any(d['materials'][d['evidence'][eid]['material']]['version'] is None for eid in finding['evidence']):
                    finding['stale'] = True
            bounds = dict(LIMITS)
            if limits:
                need(set(limits) <= set(bounds), 'unknown limit')
                need(all(type(x) is int and x > 0 for x in limits.values()), 'finite positive limits required')
                need(all(x <= LIMITS[k] for k, x in limits.items()), 'helper limits may only be lowered')
                bounds.update(limits)
            r = dict(id=str(uuid.uuid4()), token=str(uuid.uuid4()), owner=owner, mode=mode,
                     started=now(), epoch=time.time(), limits=bounds, used=dict.fromkeys(bounds, 0),
                     checks=[dict(c, status='not_run', evidence=[], observed=None) for c in checks],
                     status='active', baseline={k:dict(revision=v['revision'],decision=v['decision']) for k,v in d['findings'].items()}, events=[])
            d['active'] = r
        return copy.deepcopy(r)

    def event(self, token, event):
        need(len(json.dumps(event).encode()) <= 2097152, 'event too large')
        with self.transaction() as d:
            r = d['active']
            need(r and token == r['token'], 'exact active token required')
            need(time.time() - r['epoch'] <= r['limits']['seconds'], 'time limit reached; finish partial')
            need(r['used']['actions'] < r['limits']['actions'], 'action limit reached; finish partial')
            result = apply(d, r, event)
            r['used']['actions'] += 1
            r['events'].append(dict(at=now(), op=event['op'], result=result))
            for key in r['limits']:
                if key != 'seconds':
                    need(r['used'][key] <= r['limits'][key], key + ' limit reached; event rolled back')
        return result

    def finish(self, token, next_action, verification, results, reason='manual boundary'):
        need(nonempty(next_action) and nonempty(verification), 'verified continuation point required')
        with self.transaction() as d:
            r = d['active']
            need(r and token == r['token'], 'exact active token required')
            need(set(results) == {c['id'] for c in r['checks']}, 'result required for every frozen check')
            for c in r['checks']:
                x = results[c['id']]
                need(x.get('status') in ('passed', 'failed', 'partial', 'blocked', 'not_run'), 'invalid result')
                need(nonempty(x.get('observed')), 'actual observation required')
                need(isinstance(x.get('evidence'), list), 'evidence list required')
                need(x['status'] != 'passed' or bool(x['evidence']), 'pass requires evidence')
                c.update({k:x[k] for k in ('status', 'evidence', 'observed')})
            r.update(status='finished', finished=now(), reason=reason,
                     next_action=next_action, verification=verification)
            r['used']['seconds'] = round(time.time() - r['epoch'], 3)
            d['runs'].append(r)
            d['active'] = None
        return summary(d)


def load_envelope(path):
    load(path)
    return json.loads(path.read_text())


def apply(d, r, e):
    e = copy.deepcopy(e)
    if 'project' in e:
        e['project'] = canonical(d, e['project'])
    op = e['op']
    if op == 'usage':
        for k,v in e['counts'].items():
            need(k in ('bytes', 'calls') and type(v) is int and v >= 0, 'invalid usage charge')
            r['used'][k] += v
        return 'charged'
    if op == 'source':
        need(e['discovery'] in ('complete', 'partial', 'blocked', 'unknown'), 'invalid discovery')
        need(nonempty(e['scope']) and nonempty(e['limits']), 'source boundary and limitations required')
        sid = stable('source', e['identity'])
        d['sources'][sid] = dict(identity=e['identity'], scope=e['scope'], discovery=e['discovery'],
            limits=e['limits'], cursor=e.get('cursor'), observed_at=now(), run=r['id'])
        return sid
    if op == 'project':
        pid = stable('project', e['identity'])
        need(e['type'] in FACETS and nonempty(e['title']), 'project title/type required')
        need(e['source'] in d['sources'], 'known source required')
        if pid not in d['projects']:
            r['used']['projects'] += 1
            d['projects'][pid] = dict(identity=e['identity'], title=e['title'], type=e['type'],
                sources=[e['source']], aliases=[], status='inventoried', assessment=None,
                reviews=[], questions=[], next_action='Read purpose and representative output')
        elif e['source'] not in d['projects'][pid]['sources']:
            d['projects'][pid]['sources'].append(e['source'])
        return canonical(d, pid)
    if op == 'material':
        need(e['source'] in d['sources'], 'known source required')
        mid = stable('material', e['identity'])
        old = d['materials'].get(mid)
        m = dict(identity=e['identity'], source=e['source'], locator=e['locator'],
                 version=e.get('version'), observed_at=now(), run=r['id'], observation_id=str(uuid.uuid4()))
        need(nonempty(m['locator']), 'material locator required')
        if old and (old['version'] != m['version'] or m['version'] is None):
            for p in d['projects'].values():
                if any(d['evidence'][eid]['material'] == mid for rev in p['reviews'] for eid in rev['evidence']):
                    p['status'] = 'needs_recheck'
            for f in d['findings'].values():
                if any(d['evidence'][eid]['material'] == mid for eid in f['evidence']):
                    f['stale'] = True
        d['materials'][mid] = m
        return mid
    if op == 'evidence':
        need(e['project'] in d['projects'] and e['material'] in d['materials'], 'known project/material required')
        need(nonempty(e['location']) and nonempty(e['observation']), 'actual examined boundary and observation required')
        m = d['materials'][e['material']]
        eid = stable('evidence', json.dumps([e['project'], e['material'], m['version'], e['location'], e['observation'], r['id']]))
        r['used']['materials'] += int(not any(v['material'] == e['material'] and v['run'] == r['id'] for v in d['evidence'].values()))
        d['evidence'][eid] = dict(project=e['project'], material=e['material'], version=m['version'],
            material_observation=m['observation_id'],location=e['location'], observation=e['observation'], examined_at=now(), run=r['id'])
        return eid
    if op in ('assess', 'review'):
        p = d['projects'][e['project']]
        ids = e['evidence']
        need(ids and all(x in d['evidence'] and d['evidence'][x]['project'] == e['project'] for x in ids), 'examined project evidence required')
        need(nonempty(e['conclusion']), 'reasoned conclusion required')
        if op == 'assess':
            p['assessment'] = dict(conclusion=e['conclusion'], evidence=ids, at=now())
            if p['status'] == 'inventoried':
                p['status'] = 'assessed'
        else:
            facets = e['facets']
            need(all(k in facets and facets[k] and set(facets[k]) <= set(ids) for k in FACETS[p['type']]), 'all type depth facets require examined evidence')
            need(all(fresh(d, x, r['id']) for x in ids), 'stale evidence cannot close depth review')
            need(nonempty(e['next_action']) and isinstance(e['questions'], list), 'next action and outstanding questions required')
            r['used']['deep_reviews'] += 1
            p['reviews'].append(dict(evidence=ids, facets=facets, conclusion=e['conclusion'], at=now(), run=r['id']))
            p.update(status='deep', questions=e['questions'], next_action=e['next_action'])
        return e['project']
    if op == 'finding':
        need(e['project'] in d['projects'], 'known project required')
        need(e['kind'] in ('observed', 'inferred', 'speculative'), 'separate fact/inference/speculation')
        need(e['confidence'] in ('low', 'medium', 'high'), 'confidence required')
        need(e['evidence'] and all(x in d['evidence'] and d['evidence'][x]['project'] == e['project'] for x in e['evidence']), 'finding requires examined project evidence')
        for field in ('problem', 'improvement', 'benefit', 'effort', 'tradeoffs', 'dependencies', 'questions', 'ranking_reason'):
            need(nonempty(e.get(field)), 'finding requires ' + field)
        need(all(nonempty(e['prompt'].get(k)) for k in PROMPT_FIELDS), 'standalone prompt fields required')
        scores = e['scores']
        need(set(scores) == {'benefit','relevance','evidence','urgency','effort','risk'}, 'ranking dimensions required')
        need(all(type(x) is int and 0 <= x <= 3 for x in scores.values()), 'ranking estimates must be 0..3')
        fid = next((key for key,value in d['findings'].items() if value['project']==e['project'] and value['key']==e['key']),stable('finding', e['project'] + ':' + e['key']))
        previous = d['findings'].get(fid)
        evidence_signature = sorted(json.dumps({k:d['evidence'][eid][k] for k in ('material','version','location','observation')},sort_keys=True) for eid in e['evidence'])
        content = {k:v for k,v in e.items() if k not in ('op','evidence','reopen_reason')}
        content['evidence_signature'] = evidence_signature
        revision = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        f = copy.deepcopy(e)
        f.update(revision=revision, evidence_signature=evidence_signature,
                 stale=not all(fresh(d,x,r['id']) for x in e['evidence']),
                 at=now(), run=r['id'], decision='proposed', history=[])
        if previous:
            f['decision'], f['history'] = previous['decision'], previous['history']
            if (f['decision'] in ('rejected','resolved') and evidence_signature != previous.get('evidence_signature') and nonempty(e.get('reopen_reason'))):
                f['history'].append(dict(decision='reopened',at=now(),reason=e['reopen_reason'],previous=f['decision']))
                f['decision']='proposed'
        f['score'] = sum(scores[k]*w for k,w in dict(benefit=3,relevance=2,evidence=2,urgency=1,effort=-1,risk=-1).items())
        d['findings'][fid] = f
        return fid
    if op == 'decision':
        f=d['findings'][e['finding']]
        need(e['decision'] in ('rejected','resolved','accepted','deferred','proposed'), 'invalid decision')
        need(nonempty(e['reason']) and nonempty(e['source']), 'decision needs current source and reason')
        if e['decision']=='resolved':
            need(e.get('evidence') and all(x in d['evidence'] and d['evidence'][x]['project']==f['project'] and fresh(d,x,r['id']) for x in e['evidence']), 'resolution requires fresh project verification evidence')
        f['history'].append(dict(decision=e['decision'],reason=e['reason'],source=e['source'],evidence=e.get('evidence',[]),at=now()))
        f['decision']=e['decision']
        return e['finding']
    if op == 'association':
        a,b=canonical(d,e['left']),canonical(d,e['right'])
        need(a!=b and a in d['projects'] and b in d['projects'], 'distinct known projects required')
        need(e['certainty'] in ('uncertain','confirmed'), 'association certainty required')
        need(e['relationship'] in ('related','duplicate'), 'association relationship required')
        need(nonempty(e['reason']) and nonempty(e['evidence']), 'association evidence and reason required')
        relation=dict(left=a,right=b,certainty=e['certainty'],relationship=e['relationship'],reason=e['reason'],evidence=e['evidence'],at=now())
        d['associations'].append(relation)
        if e['certainty']=='confirmed' and e['relationship']=='duplicate':
            left,right=d['projects'][a],d['projects'][b]
            need(left['type']==right['type'], 'reconcile differing project purpose/types before merge')
            left['aliases']+= [right['identity']]+right['aliases']
            left['sources']=sorted(set(left['sources']+right['sources']))
            left['reviews']+=right['reviews']
            left['questions']+=right['questions']
            left['assessment']=left['assessment'] or right['assessment']
            # Keep a conservative union: merging must never manufacture depth coverage.
            left['status']='needs_recheck'
            left['next_action']='Reconcile union of duplicate project evidence and outstanding questions'
            right['merged_into']=a
            for ev in d['evidence'].values():
                if ev['project']==b:ev['project']=a
            for f in d['findings'].values():
                if f['project']==b:f['project']=a
        return relation
    if op == 'blocked':
        project=d['projects'][e['project']]
        need(nonempty(e['reason']) and nonempty(e['next_action']), 'blocker and recovery required')
        project.update(status='blocked',questions=[e['reason']],next_action=e['next_action'])
        return e['project']
    raise ValueError('unknown event operation: ' + str(op))


def canonical(d, pid):
    seen=set()
    while pid in d['projects'] and d['projects'][pid].get('merged_into'):
        need(pid not in seen,'alias cycle');seen.add(pid)
        pid=d['projects'][pid]['merged_into']
    return pid


def fresh(d, eid, run):
    ev = d['evidence'][eid]
    m = d['materials'][ev['material']]
    return ev['version'] == m['version'] and (m['version'] is not None or (
        ev['run'] == run and ev.get('material_observation') == m.get('observation_id')))


def summary(d):
    ps = {k:v for k,v in d['projects'].items() if not v.get('merged_into')}
    remaining=[k for k,p in ps.items() if p['status']!='deep']
    latest=d['active'] or (d['runs'][-1] if d['runs'] else {})
    baseline=latest.get('baseline',{})
    changes=dict(new=[],changed=[],unchanged=[],resolved=[])
    for fid,f in d['findings'].items():
        old=baseline.get(fid)
        category='resolved' if f['decision']=='resolved' and (not old or old['decision']!='resolved') else 'new' if not old else 'changed' if old['revision']!=f['revision'] or old['decision']!=f['decision'] else 'unchanged'
        changes[category].append(fid)
    discovery_gaps=[k for k,v in d['sources'].items() if v['discovery']!='complete']
    return dict(observed_at=now(), projects=len(ps), inventoried_only=sum(p['status']=='inventoried' for p in ps.values()),
        assessed=sum(p['assessment'] is not None for p in ps.values()),
        deep=sum(p['status']=='deep' for p in ps.values()),
        blocked=[k for k,p in ps.items() if p['status']=='blocked'],
        remaining=remaining, sources=d['sources'], discovery_gaps=discovery_gaps,
        uncertain_associations=[x for x in d['associations'] if x['certainty']=='uncertain'],changes=changes,
        depth_complete_for_discovered=bool(ps) and not remaining,
        active={k:v for k,v in d['active'].items() if k!='token'} if d['active'] else None,
        next_action=d['runs'][-1]['next_action'] if d['runs'] else 'Start a bounded manual run',
        completion=('Depth criteria met for discovered inventory at recorded evidence dates; ' if ps and not remaining else 'Partial discovered-inventory review; ')+('discovery gaps remain; ' if discovery_gaps else 'complete only for recorded source scopes; ')+'total portfolio population unknown')


def report(d):
    s = summary(d)
    lines = ['# Project improvement review', '', json.dumps(s, indent=2), '', '## Recommendations',
             '', 'Ranking is provisional: usefulness and reliability before novelty. Scores are estimates.']
    for fid,f in sorted(d['findings'].items(), key=lambda x:-x[1]['score']):
        if f['decision'] != 'proposed' or f['stale']:
            continue
        lines += ['', '### ' + fid + ': ' + f['problem'],
                  'Project: ' + d['projects'][f['project']]['title'] + ' ('+f['project']+')',
                  f['kind'] + '; confidence ' + f['confidence'] + '; score ' + str(f['score']),
                  'Ranking: ' + f['ranking_reason']]
        for field in ('improvement','benefit','effort','tradeoffs','dependencies','questions'):
            lines += [field.title() + ': ' + f[field]]
        for eid in f['evidence']:
            ev=d['evidence'][eid]; m=d['materials'][ev['material']]
            lines += ['Evidence '+eid+': '+m['locator']+' '+ev['location']+'; version '+str(ev['version'])+'; examined '+ev['examined_at']+'; '+ev['observation']]
        lines += ['', '```text'] + [k.title()+': '+f['prompt'][k] for k in PROMPT_FIELDS] + ['```']
    lines += ['', '## Project progress']
    for pid,p in d['projects'].items():
        if p.get('merged_into'):
            continue
        lines += [pid+' '+p['title']+': '+p['status']+'; next: '+p['next_action']]
    lines += ['', '## Decisions and stale findings']
    for fid,f in d['findings'].items():
        if f['decision']!='proposed' or f['stale']:
            lines += [fid+': '+f['decision']+'; stale='+str(f['stale'])+'; history='+json.dumps(f['history'])]
    lines += ['', '## Run checks', json.dumps(d['runs'][-1]['checks'] if d['runs'] else [], indent=2)]
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    sub=parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init'); sub.add_parser('status'); sub.add_parser('report')
    p=sub.add_parser('start');p.add_argument('--owner',required=True);p.add_argument('--mode',choices=['broad','comprehensive'],default=None);p.add_argument('--checks',required=True)
    p=sub.add_parser('event');p.add_argument('--token',required=True);p.add_argument('--json',required=True)
    p=sub.add_parser('finish');p.add_argument('--token',required=True);p.add_argument('--json',required=True)
    args=parser.parse_args(); store=Store(args.state)
    try:
        if args.command=='init': value=store.init()
        elif args.command=='start': value=store.start(args.mode,args.owner,json.loads(Path(args.checks).read_text()))
        elif args.command=='event': value=store.event(args.token,json.loads(Path(args.json).read_text()))
        elif args.command=='finish': value=store.finish(args.token,**json.loads(Path(args.json).read_text()))
        elif args.command=='status': value=summary(store.read())
        else:
            print(report(store.read()));return
        print(json.dumps(value,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,json.dumps({'error':str(exc),'next':'Inspect state and active owner; preserve partial work. No retry or takeover implied.'})+'\n')


if __name__=='__main__':
    main()
