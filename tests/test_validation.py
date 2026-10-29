import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validation',ROOT/'scripts/validate.py')
validation=importlib.util.module_from_spec(spec);spec.loader.exec_module(validation)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'package'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('.git','.checkpoint','__pycache__','HANDOFF.md'))
    def tearDown(self):self.tmp.cleanup()
    def check(self):
        with mock.patch.object(validation,'ROOT',self.root),mock.patch.object(validation,'SKILL',self.root/'skills/project-improvement-agent'),contextlib.redirect_stdout(io.StringIO()) as output:
            result=validation.validate()
        return result,output.getvalue()
    def test_missing_markdown_target_fails_publication_gate(self):
        path=self.root/'README.md';path.write_text(path.read_text()+'\n[Broken reference](docs/does-not-exist.md)\n')
        result,output=self.check()
        self.assertEqual(result,1);self.assertIn('missing link README.md -> docs/does-not-exist.md',output)
    def test_missing_inventory_reports_a_failed_gate(self):
        (self.root/'toolbox/index.json').unlink()
        result,output=self.check()
        self.assertEqual(result,1);self.assertIn('unreadable inventory',output)


if __name__=='__main__':unittest.main()
