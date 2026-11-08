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


if __name__=='__main__':unittest.main()
