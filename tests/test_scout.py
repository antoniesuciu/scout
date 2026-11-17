import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from scout import app as scout
from scout import pipeline
from scout import engines


class TranscriptTests(unittest.TestCase):
    def test_rolling_captions_keep_times_and_later_repetition(self):
        vtt = '''WEBVTT

00:00:01.000 --> 00:00:02.000
Hello &amp; welcome

00:00:02.000 --> 00:00:03.000
Hello &amp; welcome to Scout

00:00:05.000 --> 00:00:06.000
Other words

00:00:08.000 --> 00:00:09.000
Hello &amp; welcome
'''
        self.assertEqual(pipeline.clean_vtt(vtt), '[00:00:01] Hello & welcome\n[00:00:02] to Scout\n[00:00:05] Other words\n[00:00:08] Hello & welcome')

    def test_short_timestamp_and_tags(self):
        self.assertEqual(pipeline.clean_vtt('WEBVTT\n\n01:02.100 --> 01:03.000\n<v A>Some <b>text</b> [Music]\n'), '[00:01:02] Some text')

    def test_discovery_cap_applies_after_known_ids(self):
        videos = [dict(id=str(i), date='2026-11-17') for i in range(4)]
        settings = dict(test=False, channels=[dict(name='channel')], mode='latest', max_per_channel=2, max_total=2)
        with patch.object(pipeline, 'fetch_feed', return_value=videos):
            self.assertEqual([v['id'] for v in pipeline.get_candidates(settings, {'0': {}, '1': {}}, 'unused')], ['2', '3'])

    def test_days_mode_skips_old_and_known_videos(self):
        from datetime import datetime, timedelta
        day = lambda n: (datetime.now() - timedelta(days=n)).strftime('%Y-%m-%d')
        videos = [dict(id='new', date=day(1)), dict(id='known', date=day(2)), dict(id='old', date=day(30))]
        settings = dict(test=False, channels=[dict(name='c')], mode='days', max_age_days=7, max_per_channel=5, max_total=5)
        with patch.object(pipeline, 'fetch_feed', return_value=videos):
            self.assertEqual([v['id'] for v in pipeline.get_candidates(settings, {'known': {}}, 'unused')], ['new'])


class EngineTests(unittest.TestCase):
    def test_claude_is_tool_free_and_isolated(self):
        calls = []
        def execute(argv, prompt, cwd, timeout, env=None):
            self.assertEqual(list(Path(cwd).iterdir()), [])
            calls.append(argv)
            return json.dumps(dict(result='answer', usage=dict(input_tokens=4)))
        with patch('scout.engines.shutil.which', return_value='/bin/claude'), patch('scout.engines.execute', side_effect=execute):
            self.assertEqual(engines.run('claude', 'transcript', dict(model='haiku'))[0], 'answer')
        self.assertEqual(calls[0][calls[0].index('--tools') + 1], '')
        self.assertIn('--strict-mcp-config', calls[0])

    def test_codex_output_file_and_constraints(self):
        def execute(argv, prompt, cwd, timeout, env=None):
            self.assertIn('read-only', argv)
            self.assertIn('shell_tool', argv)
            self.assertIn('--ignore-user-config', argv)
            Path(argv[argv.index('-o') + 1]).write_text('answer')
            return ''
        with patch('scout.engines.shutil.which', return_value='/bin/codex'), patch('scout.engines.execute', side_effect=execute):
            self.assertEqual(engines.run('codex', 'text', {})[0], 'answer')

    def test_agy_fails_before_any_model_call(self):
        with patch('scout.engines.shutil.which', return_value='/bin/agy'), patch('scout.engines.execute') as execute:
            with self.assertRaisesRegex(RuntimeError, 'no verified tool-free'):
                engines.run('agy', 'text', {})
            execute.assert_not_called()

    def test_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                engines.execute(['/bin/sleep', '3'], '', directory, .01)

    def test_nonzero_does_not_echo_sensitive_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError) as error:
                engines.execute(['/bin/sh', '-c', 'echo secret >&2; exit 1'], '', directory, 1)
            self.assertNotIn('secret', str(error.exception))


class SummaryTests(unittest.TestCase):
    def test_parser_rejects_missing_or_malformed_entries(self):
        scout.selftest()

if __name__ == '__main__':
    unittest.main()
