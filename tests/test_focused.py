"""Synthetic contract tests; these do not certify autonomous model judgment."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/'skills/project-improvement-agent/scripts/portfolio.py'
spec=importlib.util.spec_from_file_location('focused_portfolio',FILE)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
CHECKS=[dict(id='precision',expected='No invented unfinished work',method='Compare original fixture turns and independent outcomes')]


class FocusedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.store=p.Store(self.root/'private');self.store.init()
        self.scope=dict(chat='fixture-chat',project='fixture:app',basis='User explicitly names fixture repository')
        self.start()
        self.source=self.event(op='source',identity='fixture:source',scope='one chat and fixture repository',discovery='partial',limits='older page inaccessible',cursor='page-2')
        self.project=self.event(op='project',identity='fixture:app',title='App',type='software',source=self.source)
        self.user=self.evidence('u1','Add CSV export.','user')
        self.code=self.evidence('code','Complete fixture tree has JSON only. CSV acceptance command reports unsupported.','artifact')
        self.accept=self.evidence('checks','CSV acceptance passes on fixture-v2.','acceptance')
        self.install=self.evidence('installed','Installed hashes match fixture-v2.','installation')
        self.release=self.evidence('release','Remote commit and release tag match fixture-v2.','release')
    def tearDown(self):self.tmp.cleanup()
    def start(self):
        self.run=self.store.start(mode='focused',scope=self.scope,owner='fixture',checks=CHECKS);self.token=self.run['token']
    def event(self,**e):return self.store.event(self.token,e)
    def evidence(self,key,text,role='artifact',version='v1'):
        mid=self.event(op='material',identity='fixture:'+key,source=self.source,locator='/fixture/'+key,version=version)
        return self.event(op='evidence',project=self.project,material=mid,location='entire fixture record',observation=text,role=role)
    def finish(self):
        self.store.finish(self.token,'Reinspect changed evidence','Compare recorded versions',{'precision':dict(status='passed',evidence=['frozen fixture oracle'],observed='Compared source facts and output')})
    def row(self,**updates):
        unknown=dict(status='unknown',observed='Not inspected',evidence=[])
        layer=dict(status='not started',observed='Complete fixture source excludes CSV; acceptance command rejects it.',evidence=[self.code],absence_established=True)
        action=dict(basis='Original user u1 requests CSV; source fixture lacks it.',impact='User can export data.',dependencies='None known.',next_action='Implement the CSV format in the existing exporter.',acceptance='CSV output round-trips representative rows.',destination='fixture:app / fixture-chat',model='GPT-6.1 Sol',effort='Medium',rank=1,ranking_reason='Supported requested capability before optional convenience.',prompt=dict(context='Fixture App exports JSON; user u1 requested CSV, complete source record code lacks CSV.',targets='/fixture/app exporter and tests',outcome='CSV export',scope='CSV format only',constraints='Verify current source and authority',preserve='JSON exports and saved data',verification='CSV round-trip and existing JSON acceptance pass'))
        e=dict(op='requirement',project=self.project,key='chat/u1:csv',title='CSV export',kind='user_request',origins=[self.user],evidence=[self.code],coverage='Complete bounded fixture source; older unrelated page unread.',next_check='Run CSV acceptance on current revision.',layers=dict(source=layer,installation=copy.deepcopy(unknown),release=copy.deepcopy(unknown)),required_layers=['source'],action=action)
        e.update(updates);return e
    def test_absence_requires_discriminating_evidence(self):
        e=self.row();e['layers']['source'].pop('absence_established')
        with self.assertRaises(ValueError):self.event(**e)
        rid=self.event(**self.row());self.assertEqual(self.store.read()['requirements'][rid]['status'],'not started')
    def test_code_without_acceptance_stays_unverified(self):
        e=self.row();e['layers']['source']['status']='implemented but unverified'
        rid=self.event(**e);self.assertEqual(self.store.read()['requirements'][rid]['status'],'implemented but unverified')
    def test_verified_needs_acceptance_role(self):
        e=self.row();e['layers']['source'].update(status='verified complete',verification=[self.user])
        with self.assertRaises(ValueError):self.event(**e)
        e['layers']['source']['verification']=[self.accept];rid=self.event(**e)
        report=p.report(self.store.read());self.assertEqual(self.store.read()['requirements'][rid]['status'],'verified complete')
        self.assertNotIn('### 1. CSV',report)
    def test_source_install_release_are_separate(self):
        e=self.row(required_layers=['source','installation','release'])
        e['layers']['source'].update(status='verified complete',verification=[self.accept])
        for name in ('installation','release'):
            e['layers'][name]=dict(status='not started',observed='Old fixture version lacks capability',evidence=[getattr(self,name if name=='release' else 'install')],absence_established=True)
        rid=self.event(**e);self.assertEqual(self.store.read()['requirements'][rid]['status'],'partially implemented')
    def test_later_completion_reuses_id_without_recommendation(self):
        rid=self.event(**self.row());self.finish();self.start()
        e=self.row();e['layers']['source'].update(status='verified complete',verification=[self.accept]);rid2=self.event(**e)
        self.assertEqual(rid,rid2);self.assertEqual(len(self.store.read()['requirements']),1)
        self.assertNotIn('### 1. CSV',p.report(self.store.read()))
    def test_stale_old_todo_cannot_reopen_complete(self):
        e=self.row();e['layers']['source'].update(status='verified complete',verification=[self.accept]);rid=self.event(**e)
        self.finish();self.start()
        report=p.report(self.store.read());self.assertIn('reinspection needed',report);self.assertNotIn('### 1. CSV',report)
        self.event(**e);self.assertEqual(self.store.read()['requirements'][rid]['status'],'verified complete')
    def test_rejection_and_deferral_need_new_user_decision(self):
        for hold in ('rejected','deferred'):
            e=self.row(key=hold,disposition=hold,decision_evidence=[self.user]);rid=self.event(**e)
            self.assertNotIn('### 1. CSV export ('+rid+')',p.report(self.store.read()))
            e['disposition']='active'
            with self.assertRaises(ValueError):self.event(**e)
            e.update(decision_evidence=[self.evidence(hold+'-new','Resume this request now.','user')],decision_reason='New explicit instruction')
            self.event(**e);self.assertEqual(self.store.read()['requirements'][rid]['status'],'not started')
    def test_proposals_do_not_become_commitments(self):
        assistant=self.evidence('assistant','Maybe add dashboard.','assistant')
        e=self.row(kind='assistant_proposal',origins=[assistant]);self.event(**e)
        report=p.report(self.store.read());unfinished=report.split('## Ranked unfinished work')[1].split('## Optional opportunities')[0]
        self.assertNotIn('### 1.',unfinished);self.assertIn('### 1.',report.split('## Optional opportunities')[1])
        e['kind']='user_request'
        with self.assertRaises(ValueError):self.event(**e)
    def test_correction_supersedes_original(self):
        original=self.event(**self.row(title='PDF export'))
        correction=self.evidence('u2','Replace PDF with CSV.','user')
        newer=self.event(**self.row(key='chat/u2:csv',origins=[correction],supersedes=[original],decision_evidence=[correction]))
        self.assertEqual(self.store.read()['requirements'][original]['status'],'superseded')
        self.assertEqual(self.store.read()['requirements'][original]['superseded_by'],newer)
    def test_duplicate_preserves_canonical_id_and_origins(self):
        rid=self.event(**self.row());second=self.evidence('u-repeat','Please add CSV.','user')
        out=self.event(op='requirement',project=self.project,key='other-chat/u3',kind='user_request',origins=[second],duplicate_of=rid,duplicate_reason='Same app and export behavior explicitly referenced.')
        self.assertEqual(out,rid);self.assertEqual(len(self.store.read()['requirements']),1)
        self.assertIn(second,self.store.read()['requirements'][rid]['origins'])
        with self.assertRaises(ValueError):self.event(**self.row(key='other-chat/u3'))
    def test_missing_history_is_unknown_and_coverage_visible(self):
        e=self.row();e['layers']['source']=dict(status='unknown',observed='Not evidenced in inspected scope',evidence=[])
        rid=self.event(**e);report=p.report(self.store.read())
        self.assertEqual(self.store.read()['requirements'][rid]['status'],'unknown')
        self.assertIn('page-2',report);self.assertIn('older page inaccessible',report)
    def test_focused_scope_blocks_other_project_even_same_title(self):
        with self.assertRaises(ValueError):self.event(op='project',identity='fixture:other',title='App',type='software',source=self.source)
    def test_standalone_scope_and_continuation(self):
        self.finish();self.scope=dict(chat='standalone',project=None,basis='No associated project proven');self.start()
        pid=self.event(op='project',identity='chat:standalone',title='Standalone',type='other',source=self.source)
        self.assertTrue(pid);self.finish()
        r=self.store.start(owner='fixture',checks=CHECKS);self.assertEqual(r['mode'],'focused');self.assertEqual(r['scope'],self.scope)
    def test_broader_scope_remains_available(self):
        self.finish();r=self.store.start(mode='comprehensive',owner='fixture',checks=CHECKS)
        self.store.event(r['token'],dict(op='project',identity='fixture:other',title='App',type='software',source=self.source))
        self.assertEqual(len(self.store.read()['projects']),2)
    def test_old_state_and_foreign_owner_are_preserved(self):
        before=self.store.read();self.assertNotIn('requirements',before)
        with self.assertRaises(ValueError):self.store.start(mode='focused',scope=self.scope,owner='other',checks=CHECKS)
        self.event(**self.row());after=self.store.read()
        for field in ('projects','sources','associations','findings'):
            self.assertEqual(before[field],after[field])
    def test_changed_material_prevents_stale_acceptance(self):
        e=self.row();e['layers']['source'].update(status='verified complete',verification=[self.accept]);self.event(**e)
        self.evidence('checks','New revision has no acceptance result.','artifact',version='v3')
        self.assertIn('reinspection needed',p.report(self.store.read()))
        with self.assertRaises(ValueError):self.event(**e)
    def test_all_action_fields_are_required(self):
        for field in ('basis','impact','dependencies','next_action','acceptance','destination','model','effort','ranking_reason','prompt'):
            e=self.row();del e['action'][field]
            with self.assertRaises((ValueError,KeyError)):self.event(**e)


class FocusedIsolationTests(unittest.TestCase):
    """Regression fixtures for scope isolation, separate from judgment evaluation."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = p.Store(Path(self.tmp.name).resolve() / 'private')
        self.store.init()
        self.run = self.store.start(mode='broad', owner='isolation', checks=CHECKS)
        self.ids = {}
        for name in ('A', 'B'):
            source = self.event(op='source', identity='source:' + name, scope='only ' + name,
                                discovery='partial', limits='bounded fixture', cursor=name + '-cursor')
            project = self.event(op='project', identity='project:' + name, title=name,
                                 type='software', source=source)
            material = self.event(op='material', identity='material:' + name, source=source,
                                  locator='/fixture/' + name, version=None)
            evidence = self.event(op='evidence', project=project, material=material,
                                  location='all', observation=name + ' examined')
            self.event(op='review', project=project, evidence=[evidence],
                       facets={key: [evidence] for key in p.FACETS['software']},
                       conclusion='All fixture facets inspected', questions=[], next_action='Reinspect ' + name)
            finding = dict(op='finding', project=project, key='gap', kind='observed',
                           confidence='high', evidence=[evidence],
                           scores={key: 1 for key in ('benefit', 'relevance', 'evidence', 'urgency', 'effort', 'risk')},
                           prompt={key: name + ' fixture instruction' for key in p.PROMPT_FIELDS})
            finding.update({key: name + ' fixture detail' for key in
                            ('problem', 'improvement', 'benefit', 'effort', 'tradeoffs', 'dependencies', 'questions', 'ranking_reason')})
            fid = self.event(**finding)
            self.ids[name] = dict(project=project, source=source, material=material,
                                  evidence=evidence, finding=fid)
        self.event(op='association', left=self.ids['A']['project'], right=self.ids['B']['project'],
                   certainty='uncertain', relationship='related', reason='Titles alone are insufficient',
                   evidence='fixture association observation')
        self.finish('Continue unrelated B')
        self.before = self.store.read()
        self.scope = dict(chat='chat-A', project='project:A', basis='Verified project identity')

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, **event):
        return self.store.event(self.run['token'], event)

    def start(self, mode='focused', scope=None):
        self.run = self.store.start(mode=mode, scope=scope or self.scope, owner='isolation', checks=CHECKS)
        return self.run

    def finish(self, next_action='Continue A'):
        return self.store.finish(self.run['token'], next_action, 'Compare scoped snapshots',
                                 {'precision': dict(status='passed', evidence=['isolation fixture'],
                                                    observed='Compared exact records')})

    def assert_b_unchanged(self, before=None):
        before = before or self.before
        after = self.store.read()
        for table, key in (('projects', 'project'), ('sources', 'source'), ('materials', 'material'),
                           ('evidence', 'evidence'), ('findings', 'finding')):
            self.assertEqual(before[table][self.ids['B'][key]], after[table][self.ids['B'][key]], table)
        self.assertEqual(before['associations'], after['associations'])

    def assert_focused_summary(self, result):
        self.assertEqual(result['projects'], 1)
        self.assertEqual(result['uncertain_associations'], [])
        serialized = json.dumps(result)
        for identifier in self.ids['B'].values():
            self.assertNotIn(identifier, serialized)
        self.assertNotIn('Continue unrelated B', serialized)
        self.assertEqual(set(sum(result['changes'].values(), [])), {self.ids['A']['finding']})

    def test_start_preserves_deep_nonstale_unrelated_project(self):
        self.assertEqual(self.before['projects'][self.ids['B']['project']]['status'], 'deep')
        self.assertFalse(self.before['findings'][self.ids['B']['finding']]['stale'])
        self.start()
        self.assert_b_unchanged()
        after = self.store.read()
        self.assertEqual(after['projects'][self.ids['A']['project']]['status'], 'needs_recheck')
        self.assertTrue(after['findings'][self.ids['A']['finding']]['stale'])

    def test_active_status_and_start_baseline_are_scoped(self):
        run = self.start()
        self.assertEqual(set(run['baseline']), {self.ids['A']['finding']})
        self.assert_focused_summary(p.summary(self.store.read()))

    def test_finished_status_and_omitted_mode_continuation_are_scoped(self):
        self.start()
        self.assert_focused_summary(self.finish())
        self.assert_focused_summary(p.summary(self.store.read()))
        self.run = self.store.start(owner='isolation', checks=CHECKS)
        self.assertEqual(self.run['mode'], 'focused')
        self.assertEqual(self.run['scope'], self.scope)
        self.assert_focused_summary(p.summary(self.store.read()))
        self.assert_b_unchanged()

    def test_focused_sources_require_current_run_observation(self):
        self.start()
        self.assertEqual(p.summary(self.store.read())['sources'], {})
        self.event(op='source', identity='source:A', scope='only A', discovery='partial',
                   limits='bounded A fixture', cursor='A-page-2')
        status = p.summary(self.store.read())
        self.assertEqual(set(status['sources']), {self.ids['A']['source']})
        self.assertEqual(status['discovery_gaps'], [self.ids['A']['source']])
        self.assertIn('A-page-2', p.report(self.store.read()))
        self.assertNotIn('B-cursor', p.report(self.store.read()))
        self.assert_b_unchanged()

    def test_unrelated_source_and_material_updates_are_atomic_rejections(self):
        self.start()
        events = [dict(op='source', identity='source:B', scope='overwrite', discovery='complete', limits='none'),
                  dict(op='material', identity='material:B', source=self.ids['A']['source'],
                       locator='/fixture/replacement', version='changed'),
                  dict(op='evidence', project=self.ids['A']['project'], material=self.ids['B']['material'],
                       location='all', observation='Do not import unrelated material')]
        for event in events:
            with self.subTest(op=event['op']):
                before = (self.store.path / 'state.json').read_bytes()
                with self.assertRaises(ValueError):
                    self.event(**event)
                self.assertEqual(before, (self.store.path / 'state.json').read_bytes())

    def test_shared_material_cannot_invalidate_other_project(self):
        self.start(mode='broad')
        self.event(op='evidence', project=self.ids['A']['project'], material=self.ids['B']['material'],
                   location='shared', observation='Shared source is explicitly linked in broad mode')
        self.finish()
        self.start()
        before = self.store.read()
        with self.assertRaises(ValueError):
            self.event(op='material', identity='material:B', source=self.ids['B']['source'],
                       locator='/fixture/B', version='v2')
        self.assert_b_unchanged(before)

    def test_shared_source_cannot_replace_other_projects_coverage(self):
        self.start(mode='broad')
        self.event(op='project', identity='project:A', title='A', type='software', source=self.ids['B']['source'])
        self.finish()
        self.start()
        before = self.store.read()
        with self.assertRaises(ValueError):
            self.event(op='source', identity='source:B', scope='A only', discovery='complete', limits='focused')
        self.assert_b_unchanged(before)

    def test_project_decision_association_and_requirement_cannot_cross_scope(self):
        self.start()
        events = [dict(op='blocked', project=self.ids['B']['project'], reason='wrong scope', next_action='none'),
                  dict(op='decision', finding=self.ids['B']['finding'], decision='rejected', reason='wrong scope', source='fixture'),
                  dict(op='association', left=self.ids['A']['project'], right=self.ids['B']['project'],
                       certainty='confirmed', relationship='duplicate', reason='wrong scope', evidence='fixture'),
                  dict(op='requirement', project=self.ids['B']['project'], key='foreign')]
        for event in events:
            with self.subTest(op=event['op']):
                before = (self.store.path / 'state.json').read_bytes()
                with self.assertRaises(ValueError):
                    self.event(**event)
                self.assertEqual(before, (self.store.path / 'state.json').read_bytes())

    def test_alias_scope_uses_canonical_project_for_reads_and_updates(self):
        self.start(mode='broad')
        alias = self.event(op='project', identity='project:A-alias', title='A alias', type='software', source=self.ids['A']['source'])
        self.event(op='association', left=self.ids['A']['project'], right=alias, certainty='confirmed',
                   relationship='duplicate', reason='Verified same repository', evidence='fixture identity match')
        self.finish()
        self.start(scope=dict(self.scope, project='project:A-alias'))
        self.assert_focused_summary(p.summary(self.store.read()))
        source = self.event(op='source', identity='source:A-alias-focused', scope='A', discovery='complete', limits='fixture')
        result = self.event(op='project', identity='project:A-alias', title='A alias', type='software', source=source)
        self.assertEqual(result, self.ids['A']['project'])
        self.assertIn(source, self.store.read()['projects'][result]['sources'])
        self.event(op='blocked', project=alias, reason='Fixture blocker', next_action='Read A')
        self.assertEqual(p.summary(self.store.read())['blocked'], [self.ids['A']['project']])

    def test_standalone_chat_scope_excludes_portfolio(self):
        self.start(scope=dict(chat='standalone', project=None, basis='No project association proven'))
        self.assertEqual(p.summary(self.store.read())['projects'], 0)
        self.assertEqual(self.run['baseline'], {})
        project = self.event(op='project', identity='chat:standalone', title='Standalone', type='other', source=self.ids['A']['source'])
        self.assertEqual(p.summary(self.store.read())['remaining'], [project])
        self.assert_b_unchanged()

    def test_broad_and_comprehensive_keep_portfolio_rechecks_and_summary(self):
        for mode in ('broad', 'comprehensive'):
            with self.subTest(mode=mode):
                self.start(mode=mode)
                state = self.store.read()
                self.assertEqual(state['projects'][self.ids['B']['project']]['status'], 'needs_recheck')
                self.assertTrue(state['findings'][self.ids['B']['finding']]['stale'])
                result = p.summary(state)
                self.assertEqual(result['projects'], 2)
                self.assertEqual(set(result['sources']), {self.ids[name]['source'] for name in ('A', 'B')})
                self.assertEqual(len(result['uncertain_associations']), 1)
                self.assertEqual(len(self.run['baseline']), 2)
                self.event(op='material', identity='material:B', source=self.ids['B']['source'], locator='/fixture/B', version=None)
                self.finish()

    def test_legacy_current_run_sources_stay_scoped_in_summary_and_report(self):
        self.start()
        # An older helper allowed these observations during focused A. Preserve
        # the legacy records, but do not render B as this audit's coverage.
        with self.store.transaction() as data:
            for name in ('A', 'B'):
                data['sources'][self.ids[name]['source']]['run'] = self.run['id']
        for phase in ('active', 'finished'):
            if phase == 'finished':
                self.finish()
            data = self.store.read()
            original = copy.deepcopy(data)
            for view in ('summary', 'report'):
                with self.subTest(phase=phase, view=view):
                    result = json.dumps(p.summary(data)) if view == 'summary' else p.report(data)
                    self.assertIn(self.ids['A']['source'], result)
                    self.assertNotIn(self.ids['B']['source'], result)
                    self.assertNotIn('B-cursor', result)
            self.assertEqual(data, original, 'presentation must not rewrite legacy state')

    def test_unexamined_material_source_ownership_blocks_overwrite_and_import(self):
        self.start(mode='broad')
        material = self.event(op='material', identity='material:B-unexamined', source=self.ids['B']['source'],
                              locator='/fixture/B/unexamined', version='v1')
        self.finish()
        self.start()
        events = [dict(op='material', identity='material:B-unexamined', source=self.ids['A']['source'],
                       locator='/fixture/replacement', version='v2'),
                  dict(op='evidence', project=self.ids['A']['project'], material=material,
                       location='all', observation='Outside material without an evidence owner')]
        for event in events:
            with self.subTest(op=event['op']):
                before = (self.store.path / 'state.json').read_bytes()
                with self.assertRaises(ValueError):
                    self.event(**event)
                self.assertEqual(before, (self.store.path / 'state.json').read_bytes())

    def test_new_material_requires_scoped_source_and_new_scoped_observation_works(self):
        self.start()
        before = (self.store.path / 'state.json').read_bytes()
        with self.assertRaises(ValueError):
            self.event(op='material', identity='material:B-new', source=self.ids['B']['source'],
                       locator='/fixture/B/new', version='v1')
        self.assertEqual(before, (self.store.path / 'state.json').read_bytes())
        source = self.event(op='source', identity='source:A-focused-new', scope='A only',
                            discovery='complete', limits='new bounded observation')
        material = self.event(op='material', identity='material:A-focused-new', source=source,
                              locator='/fixture/A/new', version='v1')
        self.event(op='evidence', project=self.ids['A']['project'], material=material,
                   location='all', observation='Actual new A observation')
        self.assertEqual(set(p.summary(self.store.read())['sources']), {source})
        self.assert_b_unchanged()

    def test_evidenced_material_owner_survives_shared_provider_source(self):
        self.start(mode='broad')
        self.event(op='project', identity='project:B', title='B', type='software', source=self.ids['A']['source'])
        self.finish()
        before = self.store.read()
        self.start()
        # This material is already proven to belong only to A; its provider's
        # broad discovery record is shared, but updating A's material is safe.
        self.event(op='material', identity='material:A', source=self.ids['A']['source'],
                   locator='/fixture/A', version='v2')
        self.assert_b_unchanged(before)
        with self.assertRaises(ValueError):
            self.event(op='material', identity='material:A', source=self.ids['B']['source'],
                       locator='/fixture/A', version='v3')

    def test_broad_modes_retain_source_coverage_and_unexamined_material_updates(self):
        for mode in ('broad', 'comprehensive'):
            with self.subTest(mode=mode):
                self.start(mode=mode)
                self.event(op='source', identity='source:B', scope='B only', discovery='partial',
                           limits='broad fixture', cursor='B-current-page')
                material = self.event(op='material', identity='material:B-unexamined',
                                      source=self.ids['B']['source'], locator='/fixture/B/unexamined', version='v1')
                self.event(op='material', identity='material:B-unexamined', source=self.ids['A']['source'],
                           locator='/fixture/broad-reinspection', version='v2')
                self.event(op='evidence', project=self.ids['A']['project'], material=material,
                           location='all', observation='Broad scope can establish shared material')
                self.assertIn(self.ids['B']['source'], p.summary(self.store.read())['sources'])
                self.assertIn('B-current-page', p.requirement_report(self.store.read()))
                self.finish()


if __name__=='__main__':unittest.main()
