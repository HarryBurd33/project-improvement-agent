import json
from unittest import mock
import unittest
import test_portfolio as base

CHECKS=base.CHECKS
p=base.p


class ComprehensiveTests(unittest.TestCase):
    setUp=base.PortfolioTests.setUp
    tearDown=base.PortfolioTests.tearDown
    event=base.PortfolioTests.event
    finish=base.PortfolioTests.finish
    review=base.PortfolioTests.review
    finding=base.PortfolioTests.finding

    def restart(self):
        self.finish();self.run=self.store.start(mode='comprehensive',owner='fixture',checks=CHECKS);self.token=self.run['token']
    def test_finished_depth_and_discovery_cursor_survive_continuation(self):
        self.review();self.restart();d=self.store.read()
        self.assertEqual(d['projects'][self.project]['status'],'deep')
        self.assertEqual(d['sources'][self.source]['cursor'],'next-page')
        self.assertEqual(len(d['projects'][self.project]['reviews']),1)
        self.assertEqual(d['active']['mode'],'comprehensive')
    def test_omitted_mode_retains_comprehensive_and_explicit_mode_can_change(self):
        self.restart();self.finish()
        run=self.store.start(owner='fixture',checks=CHECKS);self.token=run['token']
        self.assertEqual(run['mode'],'comprehensive')
        self.finish()
        run=self.store.start(mode='broad',owner='fixture',checks=CHECKS)
        self.assertEqual(run['mode'],'broad')

    def test_same_native_identity_deduplicates(self):
        other=self.event(op='project',identity='fixture:alpha',title='Renamed title',type='software',source=self.source)
        self.assertEqual(other,self.project);self.assertEqual(p.summary(self.store.read())['projects'],1)
    def test_uncertain_association_keeps_both_projects(self):
        other=self.event(op='project',identity='fixture:alpha-copy',title='Alpha',type='software',source=self.source)
        self.event(op='association',left=self.project,right=other,relationship='duplicate',certainty='uncertain',reason='Titles match only',evidence='inventory titles')
        status=p.summary(self.store.read());self.assertEqual(status['projects'],2);self.assertEqual(len(status['uncertain_associations']),1)
    def test_confirmed_duplicate_preserves_alias_and_finding_decision(self):
        other=self.event(op='project',identity='fixture:copy',title='Copy',type='software',source=self.source)
        fid=self.event(**self.finding());self.event(op='decision',finding=fid,decision='rejected',reason='Intentional contract',source='Current fixture user')
        self.event(op='association',left=other,right=self.project,relationship='duplicate',certainty='confirmed',reason='Same verified native repository ID',evidence='fixture identity registry')
        self.assertEqual(p.summary(self.store.read())['projects'],1)
        self.assertEqual(self.event(**self.finding()),fid)
        self.assertEqual(self.store.read()['findings'][fid]['decision'],'rejected')
        self.assertEqual(self.store.read()['projects'][other]['status'],'needs_recheck')
    def test_changed_material_invalidates_review_and_finding(self):
        self.review();fid=self.event(**self.finding())
        self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version='v2')
        d=self.store.read();self.assertEqual(d['projects'][self.project]['status'],'needs_recheck');self.assertTrue(d['findings'][fid]['stale'])
        with self.assertRaises(ValueError):self.review()
        self.assertNotIn('### '+fid,p.report(d))
    def test_unchanged_reliable_version_preserves_depth(self):
        self.review();self.restart()
        self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version='v1')
        self.assertEqual(self.store.read()['projects'][self.project]['status'],'deep')
    def test_unknown_version_requires_fresh_inspection_in_next_run(self):
        self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version=None)
        self.ev=self.event(op='evidence',project=self.project,material=self.material,location='actual re-read',observation='Null-version source inspected now')
        self.review();self.restart()
        self.assertEqual(self.store.read()['projects'][self.project]['status'],'needs_recheck')
        with self.assertRaises(ValueError):self.review()
    def test_unknown_version_reobservation_invalidates_same_run_evidence(self):
        self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version=None)
        self.ev=self.event(op='evidence',project=self.project,material=self.material,location='Read1',observation='Examined once')
        self.event(op='material',identity='fixture:alpha/readme',source=self.source,locator='/fixture/alpha/README.md',version=None)
        with self.assertRaises(ValueError):self.review()
    def test_blocked_source_and_project_cannot_complete(self):
        self.event(op='source',identity='fixture:denied',scope='private provider',discovery='blocked',limits='permission denied')
        self.event(op='blocked',project=self.project,reason='Missing work sample',next_action='Request exact missing material under current authority')
        status=p.summary(self.store.read());self.assertEqual(status['blocked'],[self.project]);self.assertFalse(status['depth_complete_for_discovered']);self.assertEqual(len(status['discovery_gaps']),2)
    def test_all_depth_with_partial_discovery_is_not_portfolio_completion(self):
        self.review();status=p.summary(self.store.read())
        self.assertTrue(status['depth_complete_for_discovered']);self.assertIn('discovery gaps remain',status['completion']);self.assertIn('unknown',status['completion'])
    def test_limit_stop_can_finish_and_resume_without_lost_work(self):
        self.finish();run=self.store.start(owner='fixture',checks=CHECKS,limits={'actions':1});self.token=run['token']
        self.event(op='usage',counts={'calls':1})
        with self.assertRaises(ValueError):self.event(op='usage',counts={'calls':1})
        self.restart();self.assertIn(self.project,self.store.read()['projects'])
        self.assertEqual(len(self.store.read()['runs']),2)
        self.assertIsNotNone(self.store.read()['active'])
    def test_time_limit_preserves_partial_and_finish(self):
        with mock.patch.object(p.time,'time',return_value=self.run['epoch']+1801):
            with self.assertRaises(ValueError):self.event(op='usage',counts={'calls':1})
            self.finish()
        self.assertEqual(self.store.read()['runs'][-1]['used']['seconds'],1801)
    def test_negative_and_nonfinite_or_expanded_limits_refused(self):
        self.finish()
        for limits in ({'seconds':0},{'calls':float('nan')},{'deep_reviews':4}):
            with self.assertRaises(ValueError):self.store.start(owner='fixture',checks=CHECKS,limits=limits)
    def test_rejection_survives_unchanged_repeat(self):
        fid=self.event(**self.finding());self.event(op='decision',finding=fid,decision='rejected',reason='Intentional',source='Current user fixture')
        self.restart();self.event(**self.finding());d=self.store.read()
        self.assertEqual(d['findings'][fid]['decision'],'rejected');self.assertNotIn('### '+fid,p.report(d));self.assertEqual(p.summary(d)['changes']['unchanged'],[fid])
    def test_new_wording_cannot_reopen_rejected_finding(self):
        fid=self.event(**self.finding());self.event(op='decision',finding=fid,decision='rejected',reason='Intentional',source='Current user fixture')
        f=self.finding();f.update(problem='Reworded issue',reopen_reason='New wording')
        self.event(**f);self.assertEqual(self.store.read()['findings'][fid]['decision'],'rejected')
    def test_changed_evidence_and_reason_can_reopen(self):
        fid=self.event(**self.finding());self.event(op='decision',finding=fid,decision='rejected',reason='Intentional',source='Current user fixture')
        self.ev=self.event(op='evidence',project=self.project,material=self.material,location='New observed failure section',observation='New independently observed failure')
        f=self.finding();f['reopen_reason']='New failure contradicts original tradeoff';self.event(**f)
        self.assertEqual(self.store.read()['findings'][fid]['decision'],'proposed');self.assertEqual(len(self.store.read()['findings'][fid]['history']),2)
    def test_resolved_requires_verification_and_stays_suppressed(self):
        fid=self.event(**self.finding())
        with self.assertRaises(ValueError):self.event(op='decision',finding=fid,decision='resolved',reason='Assume fixed',source='Fixture')
        self.event(op='decision',finding=fid,decision='resolved',reason='Verified fix in fixture',source='Fixture check',evidence=[self.ev])
        self.assertIn(fid,p.summary(self.store.read())['changes']['resolved'])
        self.restart();self.event(**self.finding());self.assertEqual(self.store.read()['findings'][fid]['decision'],'resolved')
    def test_deep_review_limit_stops_without_partial_mutation(self):
        self.review();self.review();self.review()
        with self.assertRaises(ValueError):self.review()
        self.assertEqual(len(self.store.read()['projects'][self.project]['reviews']),3)
    def test_nonsoftware_facets_are_required(self):
        other=self.event(op='project',identity='fixture:essay',title='Essay',type='writing',source=self.source)
        evidence=self.event(op='evidence',project=other,material=self.material,location='Essay draft and assignment fixture',observation='Draft argument and sources inspected')
        with self.assertRaises(ValueError):self.event(op='review',project=other,evidence=[evidence],facets={k:[evidence] for k in p.FACETS['software']},conclusion='Wrong rubric',questions=[],next_action='Check')


if __name__=='__main__':unittest.main()
