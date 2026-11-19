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
    def test_copied_prompt_preserves_route_dependencies_and_all_fields(self):
        finding = self.finding()
        finding.update(model='Synthetic Model', reasoning_effort='High', destination='synthetic chat',
                       dependencies='Check storage before export')
        self.event(**finding)
        before = (self.store.path / 'state.json').read_bytes()
        rendered = p.report(self.store.read())
        block = rendered.split('```text\n', 1)[1].split('\n```', 1)[0]
        for value in ('Synthetic Model / High', 'Destination: synthetic chat',
                      'Dependencies: Check storage before export', *finding['prompt'].values()):
            self.assertIn(value, block)
        self.assertNotIn('Small estimate', block)
        self.assertIn('Work estimate: Small estimate', rendered)
        self.assertEqual(before, (self.store.path / 'state.json').read_bytes())

    def test_legacy_and_invalid_routes_do_not_inherit_or_replace_work_estimate(self):
        self.event(**self.finding())
        state = self.store.read()
        finding = next(iter(state['findings'].values()))
        for mode in ('broad', 'comprehensive'):
            state['active']['mode'] = mode
            block = p.report(state).split('```text\n', 1)[1].split('\n```', 1)[0]
            self.assertIn('Starting model/effort: Unknown (not supplied) / Unknown (not supplied)', block)
            self.assertIn('Destination: Unknown (not supplied)', block)
            finding.update(model=['invalid'], reasoning_effort=None, destination=False)
            block = p.report(state).split('```text\n', 1)[1].split('\n```', 1)[0]
            self.assertIn('Unknown (invalid supplied value)', block)
            for key in ('model', 'reasoning_effort', 'destination'):
                del finding[key]

    def test_copy_fence_covers_every_included_field_and_missing_prompt(self):
        record = self.finding()
        record.update(model='synthetic\n````\nmodel', reasoning_effort='Medium',
                      destination='chat\n```\ncopy', dependencies='dep\n``````\nkeep')
        record['prompt']['verification'] = 'check\n`````\nfinish'
        lines = p.copied_prompt(record)
        self.assertEqual(lines[0], '```````text')
        self.assertEqual(lines[-1], '```````')
        self.assertIn(record['prompt']['verification'], lines[1])
        record['prompt'] = None
        self.assertIn('Verification: Unknown (not supplied)', p.copied_prompt(record)[1])

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
    def test_active_report_uses_new_run_checks_in_both_broad_modes(self):
        self.finish()  # A previous passing check must not stand in for this run.
        for mode in ('broad', 'comprehensive'):
            checks=[dict(id=mode+'-current',expected='Inspect this revision',method='Read current source evidence')]
            run=self.store.start(mode=mode,owner='fixture',checks=checks)
            with self.subTest(mode=mode):
                rendered=json.loads(p.report(self.store.read()).rsplit('\n## Run checks\n',1)[1])
                self.assertEqual(rendered,run['checks'])
                self.assertEqual(rendered[0]['status'],'not_run')
                self.assertEqual(rendered[0]['evidence'],[])
            self.store.finish(run['token'],'Read current revision','Inspect current evidence',
                              {checks[0]['id']:dict(status='partial',evidence=[],observed='This revision still needs inspection')})
    def test_finished_report_preserves_latest_actual_results_in_both_broad_modes(self):
        self.finish()
        for mode in ('broad', 'comprehensive'):
            check=dict(id=mode+'-finished',expected='Current revision meets criteria',method='Compare current evidence')
            run=self.store.start(mode=mode,owner='fixture',checks=[check])
            result=dict(status='failed',evidence=['current fixture result'],observed='Current revision does not meet the criterion')
            self.store.finish(run['token'],'Inspect the failed criterion','Compare the recorded result',{check['id']:result})
            with self.subTest(mode=mode):
                data=self.store.read()
                self.assertIsNone(data['active'])
                rendered=json.loads(p.report(data).rsplit('\n## Run checks\n',1)[1])
                self.assertEqual(rendered,[dict(check,**result)])


if __name__=='__main__':unittest.main()
