import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/'skills/project-improvement-agent/scripts/portfolio.py'
spec=importlib.util.spec_from_file_location('portfolio',FILE)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
CHECKS=[dict(id='honesty',expected='No unsupported review claim',method='Compare independent source facts')]


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.store=p.Store(self.root/'private');self.store.init()
        self.run=self.store.start(owner='fixture',checks=CHECKS);self.token=self.run['token']
        self.source=self.event(op='source',identity='fixture:local',scope='selected fixture root',discovery='partial',limits='not a full filesystem listing',cursor='next-page')
        self.project=self.event(op='project',identity='fixture:alpha',title='Alpha',type='software',source=self.source)
        self.material=self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version='v1')
        self.ev=self.event(op='evidence',project=self.project,material=self.material,location='lines 1-5',observation='Goal and implementation differ on empty input')

    def tearDown(self):self.tmp.cleanup()
    def event(self,**kw):return self.store.event(self.token,kw)
    def finish(self):return self.store.finish(self.token,'Read next queued project','Check purpose and current output',{'honesty':dict(status='passed',evidence=['fixture facts'],observed='Compared examined boundary')})
    def review(self):return self.event(op='review',project=self.project,evidence=[self.ev],facets={k:[self.ev] for k in p.FACETS['software']},conclusion='Fixture deliberately supplies each facet',questions=[],next_action='Recheck on change')
    def finding(self):
        return dict(op='finding',project=self.project,key='empty-input',kind='observed',confidence='high',evidence=[self.ev],problem='Empty input fails',improvement='Define empty case',benefit='Predictable input',effort='Small estimate',tradeoffs='Preserve valid output',dependencies='None known',questions='Confirm expected empty result',ranking_reason='Reliability issue supported by fixture',scores=dict(benefit=3,relevance=3,evidence=3,urgency=1,effort=1,risk=1),prompt=dict(context='Alpha renders items; empty list fails at README lines1-5 versionv1',targets='/fixture/alpha/README.md and renderer',outcome='Handle empty lists',scope='Renderer input behavior only',constraints='No new dependencies',preserve='Existing nonempty rendering',verification='Empty and nonempty cases match declared behavior'))
    def test_inventory_does_not_establish_assessment_or_depth(self):
        s=p.summary(self.store.read());self.assertEqual((s['projects'],s['assessed'],s['deep']),(1,0,0))
    def test_initial_assessment_requires_actual_evidence(self):
        with self.assertRaises(ValueError):self.event(op='assess',project=self.project,evidence=[],conclusion='Guess')
        self.event(op='assess',project=self.project,evidence=[self.ev],conclusion='Needs examination');self.assertEqual(p.summary(self.store.read())['assessed'],1)
    def test_partial_source_remains_partial(self):
        s=p.summary(self.store.read());self.assertEqual(s['sources'][self.source]['discovery'],'partial');self.assertEqual(s['sources'][self.source]['cursor'],'next-page');self.assertIn('unknown',s['completion'])
    def test_no_deep_claim_without_facets(self):
        with self.assertRaises(ValueError):self.event(op='review',project=self.project,evidence=[self.ev],facets={},conclusion='Read one line',questions=[],next_action='Check')
        self.assertEqual(p.summary(self.store.read())['deep'],0)
    def test_report_contains_standalone_prompt_evidence_and_rank(self):
        self.event(**self.finding());report=p.report(self.store.read())
        for term in ['Context: Alpha','Targets: /fixture','Preserve:','Verification:','Ranking: Reliability','lines 1-5']:
            self.assertIn(term,report)
    def test_incomplete_prompt_and_unexamined_findings_rejected(self):
        f=self.finding();f['prompt'].pop('preserve')
        with self.assertRaises(ValueError):self.event(**f)
        f=self.finding();f['evidence']=['listed-title']
        with self.assertRaises(ValueError):self.event(**f)
    def test_owner_token_and_active_run_are_exclusive(self):
        with self.assertRaises(ValueError):self.store.start(owner='other',checks=CHECKS)
        with self.assertRaises(ValueError):self.store.event('wrong',dict(op='usage',counts={'calls':1}))
    def test_failed_event_is_transactional(self):
        before=(self.store.path/'state.json').read_bytes()
        with self.assertRaises(ValueError):self.event(op='usage',counts={'calls':999})
        self.assertEqual(before,(self.store.path/'state.json').read_bytes())
    def test_pass_requires_real_record_fields(self):
        with self.assertRaises(ValueError):self.store.finish(self.token,'Next','Verify',{'honesty':dict(status='passed',evidence=[],observed='Trust me')})
        self.finish();self.assertIsNone(self.store.read()['active'])
    def test_state_refuses_reinit_and_source_storage(self):
        with self.assertRaises(FileExistsError):self.store.init()
        with self.assertRaises(ValueError):p.Store(FILE.parent/'private')
    def test_checksums_detect_corruption(self):
        path=self.store.path/'state.json';x=json.loads(path.read_text());x['data']['projects']={};path.write_text(json.dumps(x))
        with self.assertRaises(ValueError):self.store.read()
    def test_source_projects_are_not_modified(self):
        source=self.root/'source.txt';source.write_text('keep')
        self.event(op='material',identity='fixture:ordinary',source=self.source,locator=str(source),version='hash')
        self.finish();self.assertEqual(source.read_text(),'keep')


if __name__=='__main__':unittest.main()
