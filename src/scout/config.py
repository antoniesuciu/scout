"""Validated user settings; no CLI configuration or credentials are imported."""
import copy
import json
import re
from urllib.parse import urlsplit
from . import pipeline

PROVIDERS = ('claude', 'codex', 'gemini')
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}')
UI_CHOICES = dict(theme=('ink','paper','phosphor'), font=('sans','serif','mono'),
                  size=('s','m','l'), density=('comfortable','compact'), fileView=('rendered','raw'))
UI_DEFAULTS = dict(theme='ink', font='sans', size='m', density='comfortable', fileView='rendered')


def model_name(value):
    if not isinstance(value, str) or (value and not MODEL.fullmatch(value)):
        raise ValueError('Model must be a model ID/alias, or blank for the CLI default.')
    return value


def load(path=None):
    path = path or pipeline.SETTINGS_PATH
    sample = pipeline.BASE / 'settings.example.json'
    if path == pipeline.SETTINGS_PATH and not path.exists() and sample.is_file():
        try:
            with path.open('x',encoding='utf-8') as output:
                output.write(sample.read_text(encoding='utf-8'))
        except FileExistsError:
            pass
    raw = pipeline.read_json(path, {}) if not path.exists() else json.loads(pipeline.strip_comments(path.read_text()))
    if not isinstance(raw,dict) or not isinstance(raw.get('engine_models',{}),dict) or not isinstance(raw.get('ui',{}),dict):
        raise ValueError('Settings, engine_models and ui must be JSON objects.')
    models = dict(claude=raw.get('model', 'haiku'), codex='', gemini='flash')
    models.update(raw.get('engine_models', {}))
    return {**pipeline.DEFAULTS, 'channels':[], **raw, 'engine_models': models,
            'engine_timeout': raw.get('engine_timeout', 180),
            'ui': {**UI_DEFAULTS, **raw.get('ui', {})}, 'test': False}


def save(patch, path=None):
    if not isinstance(patch, dict):
        raise ValueError('Settings must be a JSON object.')
    path = path or pipeline.SETTINGS_PATH
    current = load(path)
    allowed = set(current) | {'engine_models','ui','engine_timeout','whisper_model_path'}
    if set(patch) - allowed:
        raise ValueError('Unknown setting: ' + ', '.join(sorted(set(patch)-allowed)))
    result = {**current, **copy.deepcopy(patch)}
    for key in ('engine_models','ui'):
        if not isinstance(patch.get(key, {}), dict):
            raise ValueError(f'{key} must be an object.')
        result[key] = {**current[key], **patch.get(key, {})}
    if set(result['engine_models']) - set(PROVIDERS):
        raise ValueError('Unknown summarizer provider.')
    for value in result['engine_models'].values():
        model_name(value)
    for key, value in result['ui'].items():
        if key not in UI_CHOICES or value not in UI_CHOICES[key]:
            raise ValueError('Invalid appearance preference: ' + key)
    if result.get('language') not in pipeline.LANG:
        raise ValueError('Unsupported summary language.')
    for key, low, high in (('engine_timeout',10,3600),('warn_words',1,1000000),
                           ('max_per_channel',1,100),('max_total',1,100),('max_age_days',1,3650)):
        value = result.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer between {low} and {high}.')
    if not isinstance(result.get('channels'), list):
        raise ValueError('Channels must be a list.')
    for channel in result['channels']:
        if not isinstance(channel, dict) or not isinstance(channel.get('name'), str) or not channel['name'].strip():
            raise ValueError('Each channel needs a name.')
        url = urlsplit(str(channel.get('url','')))
        if url.scheme != 'https' or url.hostname not in ('www.youtube.com','youtube.com') or url.username or url.password:
            raise ValueError('Channels must use public HTTPS YouTube URLs.')
    # Preserve legacy helper compatibility while using one explicit model per provider.
    result['model'] = result['engine_models']['claude']
    pipeline.write_json(path, result)
    return result


def run_settings(settings, engine, model=None):
    if engine not in PROVIDERS:
        raise ValueError('Unknown summarizer provider.')
    selected = model_name(model if model is not None else settings.get('engine_models', {}).get(engine, settings.get('model','haiku') if engine == 'claude' else ''))
    return {**settings, 'selected_model': selected}
