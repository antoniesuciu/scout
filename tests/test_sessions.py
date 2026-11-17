import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scout import config, engines
from scout import app


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        for folder,auth in [('claude','.credentials.json'),('codex','auth.json'),('gemini/.gemini','oauth_creds.json')]:
            target=self.root/folder;target.mkdir(parents=True)
            (target/auth).write_text('{"test_auth_only":true}')
            (target/'settings.json').write_text('{"hooks":{"SessionStart":"record-memory"},"skills":["coding"]}')
            (target/'AGENTS.md').write_text('Private global instructions must not be loaded')
        self.environment=patch.dict(os.environ,CLAUDE_CONFIG_DIR=str(self.root/'claude'),
                                    CODEX_HOME=str(self.root/'codex'),GEMINI_CLI_HOME=str(self.root/'gemini'))
        self.environment.start()
        self.program=patch('scout.engines.shutil.which',side_effect=lambda name:'/bin/'+name)
        self.program.start()

    def tearDown(self):
        self.program.stop();self.environment.stop();self.directory.cleanup()

    def test_claude_isolates_hooks_skills_memory_and_persistence(self):
        with engines.session('claude','opus') as launch:
            self.assertEqual(launch.argv[launch.argv.index('--model')+1],'opus')
            for flag in ('--safe-mode','--strict-mcp-config','--disable-slash-commands','--no-session-persistence'):
                self.assertIn(flag,launch.argv)
            home=Path(launch.env['CLAUDE_CONFIG_DIR'])
            self.assertEqual({p.name for p in home.iterdir()},{'.credentials.json'})
            self.assertTrue((home/'.credentials.json').is_symlink())
            override=json.loads(launch.argv[launch.argv.index('--settings')+1])
            self.assertTrue(override['disableAllHooks']);self.assertFalse(override['autoMemoryEnabled'])
            self.assertEqual(list(Path(launch.cwd).iterdir()),[])
            temporary=home.parent
        self.assertFalse(temporary.exists())

    def test_codex_uses_auth_only_home_and_no_skill_catalog(self):
        with engines.session('codex','my-model') as launch:
            home=Path(launch.env['CODEX_HOME'])
            self.assertNotEqual(home,self.root/'codex')
            self.assertEqual({p.name for p in home.iterdir()},{'auth.json'})
            for value in ('hooks','plugins','skills.include_instructions=false','skills.bundled.enabled=false','skip_host_skill_discovery','--ephemeral'):
                self.assertIn(value,launch.argv)
            self.assertEqual(launch.argv[launch.argv.index('--model')+1],'my-model')
            instruction=next(arg for arg in launch.argv if arg.startswith('model_instructions_file='))
            self.assertEqual(Path(json.loads(instruction.split('=',1)[1])).read_text(),engines.SYSTEM)

    def test_gemini_disables_all_context_sources(self):
        with engines.session('gemini','pro') as launch:
            settings=json.loads(Path(launch.env['GEMINI_CLI_SYSTEM_SETTINGS_PATH']).read_text())
            self.assertEqual(settings['tools']['core'],[])
            self.assertFalse(settings['hooksConfig']['enabled'])
            self.assertFalse(settings['skills']['enabled'])
            self.assertFalse(settings['admin']['mcp']['enabled'])
            self.assertFalse(settings['experimental']['autoMemory'])
            self.assertEqual({p.name for p in (Path(launch.env['GEMINI_CLI_HOME'])/'.gemini').iterdir()},{'oauth_creds.json'})
            self.assertEqual(launch.argv[launch.argv.index('--model')+1],'pro')

    def test_configured_context_is_forbidden_for_headless_jobs(self):
        with self.assertRaisesRegex(ValueError,'always run isolated'):
            with engines.session('claude',configured=True):
                self.fail('Configured headless session was allowed')

    def test_configured_interactive_terminal_retains_user_setup(self):
        with engines.session('claude','sonnet',interactive=True,configured=True,project=self.root) as launch:
            self.assertEqual(launch.cwd,str(self.root))
            self.assertNotIn('-p',launch.argv)
            self.assertNotIn('--safe-mode',launch.argv)
            self.assertEqual(launch.env['CLAUDE_CONFIG_DIR'],str(self.root/'claude'))

    def test_gemini_model_and_json_usage_reach_caller(self):
        def execute(argv,prompt,cwd,timeout,env):
            self.assertEqual(argv[argv.index('--model')+1],'flash')
            return json.dumps({'response':'answer','stats':{'models':{'flash':{'tokens':5}}}})
        with patch('scout.engines.execute',side_effect=execute):
            answer,usage=engines.run('gemini','transcript',{'selected_model':'flash'})
        self.assertEqual(answer,'answer');self.assertIn('models',usage)

    def test_cache_keys_include_every_providers_model(self):
        video={'id':'a','transcript':'A transcript'}
        for provider in config.PROVIDERS:
            first=app.cache_key(video,provider,'en',{'selected_model':'light'}, {'depth':'text'})
            second=app.cache_key(video,provider,'en',{'selected_model':'heavy'}, {'depth':'text'})
            self.assertNotEqual(first,second,provider)

    def test_models_cannot_be_command_arguments(self):
        for model in ('--yolo','model; touch file','model\n--tools', ['haiku']):
            with self.assertRaises(ValueError):
                config.model_name(model)

    def test_codex_api_key_auth_is_refused_before_call(self):
        (self.root/'codex/auth.json').write_text('{"auth_mode":"api_key","OPENAI_API_KEY":"dummy-never-used"}')
        with self.assertRaisesRegex(RuntimeError,'subscription login'):
            with engines.session('codex'):
                self.fail('API-key session was allowed')

    def test_model_suggestions_read_only_non_secret_catalog_fields(self):
        (self.root/'codex/models_cache.json').write_text(json.dumps({'models':[
            {'slug':'heavy-model','visibility':'list','private_metadata':'never-return'},
            {'slug':'hidden-model','visibility':'hide'}, {'slug':'--bad'}]}))
        choices=engines.model_choices()
        self.assertEqual(choices['codex'],['heavy-model'])
        self.assertNotIn('never-return',json.dumps(choices))
