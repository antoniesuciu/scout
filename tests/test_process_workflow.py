"""Actual downloader/engine subprocess contracts; stand-ins make zero network/model calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scout import app,library

DOWNLOADER = '''import json,sys
from pathlib import Path
args=sys.argv[1:]
if '-J' in args:
 print(json.dumps({'duration':60,'subtitles':{'en':[]},'live_status':'not_live'}))
else:
 output=args[args.index('-o')+1].replace('%(id)s','abcdefghijk').replace('%(ext)s','en.vtt')
 Path(output).write_text('WEBVTT\\n\\n00:00:01.000 --> 00:00:20.000\\n'+'Robotics notes stay local and users explicitly choose when to summarize. '*10+'\\n')
'''
ENGINE = '''import json,sys,os,re
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:];prompt=sys.stdin.read()
assert args[args.index('--model')+1]=='fixture-heavy'
assert not os.environ.get('OPENAI_API_KEY')
assert not os.environ.get('ANTHROPIC_API_KEY')
with open(os.environ['SCOUT_TEST_CALLS'],'a') as calls:calls.write(name+'\\n')
ids=re.findall(r'=== ID: (\\S+) \\|',prompt)
answer=json.dumps({key:{'thesis':'Notes remain local','points':['Users choose summary inputs'],'tickers':[],'check':[]} for key in ids})
if name=='claude':print(json.dumps({'result':answer,'usage':{'input_tokens':20}}))
elif name=='gemini':print(json.dumps({'response':answer,'stats':{'models':{}}}))
else:Path(args[args.index('-o')+1]).write_text(answer)
'''

class ProcessWorkflowTests(unittest.TestCase):
    def test_three_provider_workflows_prepare_export_and_reuse_cache(self):
        for provider in ('claude','codex','gemini'):
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
                base=Path(directory);binaries=base/'.venv/bin';binaries.mkdir(parents=True)
                def executable(name,body):
                    target=binaries/name;target.write_text('#!'+sys.executable+'\n'+body);target.chmod(0o755)
                executable('yt-dlp',DOWNLOADER)
                for name in ('claude','codex','gemini'):executable(name,ENGINE)
                for folder in ('auth/claude','auth/codex','auth/gemini/.gemini'):(base/folder).mkdir(parents=True)
                settings=base/'settings.json';settings.write_text(json.dumps(dict(channels=[],language='en',warn_words=10000)))
                stack.enter_context(patch.dict(os.environ,PATH=str(binaries)+os.pathsep+os.environ['PATH'],
                    CLAUDE_CONFIG_DIR=str(base/'auth/claude'),CODEX_HOME=str(base/'auth/codex'),
                    GEMINI_CLI_HOME=str(base/'auth/gemini'),SCOUT_TEST_CALLS=str(base/'calls'),
                    OPENAI_API_KEY='dummy-never-used',ANTHROPIC_API_KEY='dummy-never-used'))
                for target,key,value in ((app,'BASE',base),(app,'CACHE',base/'.cache'),
                    (app,'STATE_PATH',base/'scout.json'),(app.su,'SETTINGS_PATH',settings),
                    (app.su,'TRANSCRIPTS_DIR',base/'transcripts'),(app.su,'SUMMARIES_DIR',base/'summaries')):
                    stack.enter_context(patch.object(target,key,value))
                stack.enter_context(patch.object(app,'STATE',{'session':1,'videos':{
                    'abcdefghijk':dict(id='abcdefghijk',title='Fixture video',date='2026-11-17',source='fixture',status='new',**{'from':'fixture'})}}))
                stack.enter_context(patch.object(app,'PREVIEW',{}));stack.enter_context(patch.object(app,'PREPARED',[]))
                app.prepare_job(['abcdefghijk'],provider,'en',model='fixture-heavy')
                self.assertFalse((base/'calls').exists())
                app.summarize_job(['abcdefghijk'],provider,'en',model='fixture-heavy')
                self.assertEqual(app.STATE['videos']['abcdefghijk']['model'],'fixture-heavy')
                self.assertEqual(app.STATE['videos']['abcdefghijk']['status'],'summarized')
                docs=library.listing(base);self.assertTrue(any(doc['kind']=='summaries' for doc in docs))
                file=app.STATE['videos']['abcdefghijk']['file']
                self.assertIn('[00:00:01]',(base/'transcripts'/f'{file}.txt').read_text())
                app.prepare_job(['abcdefghijk'],provider,'en',model='fixture-heavy')
                self.assertEqual(app.PREVIEW['model_calls'],0)
                app.summarize_job(['abcdefghijk'],provider,'en',model='fixture-heavy')
                self.assertEqual((base/'calls').read_text().splitlines(),[provider])
