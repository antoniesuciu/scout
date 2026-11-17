import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import json
import unittest
import test_http


class SettingsRegression(unittest.TestCase):
    request = test_http.HTTPTests.request
    def test_settings_can_be_read_inside_app(self):
        status, body = self.request('GET', '/api/settings')
        self.assertEqual(status, 200, 'Settings currently only launch an external editor; no readable/editable app settings')
        self.assertIn('engine_models', json.loads(body))

    def test_library_exposes_saved_documents(self):
        status, body = self.request('GET', '/api/library')
        self.assertEqual(status, 200, 'There is no file library route')
        self.assertIsInstance(json.loads(body), list)

class SettingsPersistence(unittest.TestCase):
    def test_model_and_appearance_survive_reload_without_losing_channels(self):
        import tempfile
        from scout import config
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            path.write_text('{"channels":[], "language":"en"}')
            config.save({'engine_models':{'claude':'opus','codex':'my-model','gemini':'pro'},
                         'ui':{'font':'serif','size':'l','theme':'paper'}},path)
            restored=config.load(path)
            self.assertEqual(restored['engine_models'],{'claude':'opus','codex':'my-model','gemini':'pro'})
            self.assertEqual(restored['ui']['font'],'serif')
            self.assertEqual(restored['ui']['size'],'l')
            self.assertEqual(restored['channels'],[])

    def test_invalid_settings_do_not_modify_file(self):
        import tempfile
        from scout import config
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json';path.write_text('{"channels":[]}')
            original=path.read_text()
            for body in ({'engine_timeout':0},{'ui':{'font':'bad'}},{'engine_models':{'claude':'--dangerous'}},
                         {'channels':[{'name':'bad','url':'https://evil.example'}]}):
                with self.assertRaises(ValueError):config.save(body,path)
                self.assertEqual(path.read_text(),original)

    def test_first_run_creates_personal_settings_without_overwriting_them(self):
        import tempfile
        from unittest.mock import patch
        from scout import config
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'settings.json'
            (root/'settings.example.json').write_text('{"channels":[],"language":"en","model":"sonnet"}')
            with patch.object(config.pipeline,'BASE',root),patch.object(config.pipeline,'SETTINGS_PATH',path):
                self.assertEqual(config.load()['engine_models']['claude'],'sonnet')
                config.save({'ui':{'font':'serif'}})
                self.assertEqual(config.load()['ui']['font'],'serif')
                self.assertEqual(json.loads((root/'settings.example.json').read_text())['model'],'sonnet')
