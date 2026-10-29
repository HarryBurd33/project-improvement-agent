import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_portfolio as base

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
SOURCE=ROOT/'skills/project-improvement-agent'


class InstallTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def test_install_hashes_and_unrelated_skill_are_preserved(self):
        parent=self.root/'skills';parent.mkdir();other=parent/'other';other.mkdir();(other/'SKILL.md').write_text('custom')
        receipt=installer.install(SOURCE,parent)
        self.assertEqual(installer.manifest(SOURCE),installer.manifest(Path(receipt['installed'])))
        self.assertEqual((other/'SKILL.md').read_text(),'custom')
    def test_existing_install_is_never_overwritten(self):
        parent=self.root/'skills';installer.install(SOURCE,parent)
        path=parent/'project-improvement-agent/SKILL.md';path.write_text('user edits')
        with self.assertRaises(FileExistsError):installer.install(SOURCE,parent)
        self.assertEqual(path.read_text(),'user edits')
    def test_symlink_and_parent_traversal_destinations_are_refused(self):
        real=self.root/'real';real.mkdir();link=self.root/'link';link.symlink_to(real,target_is_directory=True)
        with self.assertRaises(ValueError):installer.install(SOURCE,link)
        with self.assertRaises(ValueError):installer.install(SOURCE,self.root/'real/../nested')
    def test_installed_helper_runs_from_an_unrelated_directory(self):
        receipt=installer.install(SOURCE,self.root/'skills');helper=Path(receipt['installed'])/'scripts/portfolio.py';state=self.root/'private'
        subprocess.run([sys.executable,'-B',str(helper),'--state',str(state),'init'],cwd=self.root,check=True,capture_output=True)
        result=subprocess.run([sys.executable,'-B',str(helper),'--state',str(state),'status'],cwd=self.root,check=True,capture_output=True,text=True)
        self.assertEqual(json.loads(result.stdout)['projects'],0)
        self.assertIn('unknown',json.loads(result.stdout)['completion'])

    def test_cli_continuation_preserves_saved_mode(self):
        receipt=installer.install(SOURCE,self.root/'skills')
        helper=Path(receipt['installed'])/'scripts/portfolio.py';state=self.root/'private'
        checks=self.root/'checks.json';checks.write_text(json.dumps(base.CHECKS))
        def cli(*args):
            result=subprocess.run([sys.executable,'-B',str(helper),'--state',str(state),*args],cwd=self.root,check=True,capture_output=True,text=True)
            return json.loads(result.stdout)
        cli('init')
        run=cli('start','--owner','fixture','--mode','comprehensive','--checks',str(checks))
        finish=self.root/'finish.json'
        finish.write_text(json.dumps(dict(next_action='Read the next fixture',verification='Check its purpose and output',results={'honesty':dict(status='passed',evidence=['fixture facts'],observed='Compared fixture facts')})))
        cli('finish','--token',run['token'],'--json',str(finish))
        resumed=cli('start','--owner','fixture','--checks',str(checks))
        self.assertEqual(resumed['mode'],'comprehensive')


class LockTests(unittest.TestCase):
    def test_actual_second_process_cannot_write_during_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();store=base.p.Store(root/'private');store.init();run=store.start(owner='fixture',checks=base.CHECKS)
            event=root/'event.json';event.write_text(json.dumps(dict(op='usage',counts={'calls':1})))
            with store.transaction():
                child=subprocess.run([sys.executable,'-B',str(base.FILE),'--state',str(store.path),'event','--token',run['token'],'--json',str(event)],capture_output=True,text=True,timeout=10)
                self.assertEqual(child.returncode,2)
            self.assertEqual(store.read()['active']['used']['calls'],0)


if __name__=='__main__':unittest.main()
