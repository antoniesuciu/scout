// End-to-end: real Scout server on a throwaway copy of the app + headless Chromium driven over CDP.
// No model calls and no access to your inbox. Run: node tests/e2e_browser.mjs
// Needs a Chromium binary: set SCOUT_CHROME, or have Playwright's chrome-headless-shell installed.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';

const repo = path.resolve(import.meta.dirname, '..');
const chrome = process.env.SCOUT_CHROME || (() => {
  const root = path.join(os.homedir(), '.cache/ms-playwright');
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith('chromium_headless_shell')) continue;
    for (const sub of fs.readdirSync(path.join(root, dir))) {
      const bin = path.join(root, dir, sub, 'chrome-headless-shell');
      if (fs.existsSync(bin)) return bin;
    }
  }
})();
if (!chrome) { console.log('e2e skipped: no Chromium (set SCOUT_CHROME)'); process.exit(0); }

// Throwaway app copy with fixture data.
const base = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'scout-e2e-'));
fs.cpSync(path.join(repo, 'src'), path.join(base, 'src'), {recursive: true});
fs.copyFileSync(path.join(repo, 'scout'), path.join(base, 'scout'));
fs.symlinkSync(path.join(repo, '.venv'), path.join(base, '.venv'));
const channel = (name, handle) => ({name, url: `https://www.youtube.com/@${handle}`, channel_id: 'UC' + handle.padEnd(22, 'x'), group: null});
fs.writeFileSync(path.join(base, 'settings.json'), JSON.stringify({language: 'en', ui: {checkOnOpen: 'on'}, channels: [channel('Alpha', 'alpha'), channel('Beta', 'beta')]}));
const video = (id, from, title) => ({id, title, from, source: from, date: '2026-11-1' + id.length % 9, duration: 600, status: 'new', session: 1});
fs.writeFileSync(path.join(base, 'scout.json'), JSON.stringify({session: 1, videos: {
  aaaaaaaaaaa: video('aaaaaaaaaaa', 'Alpha', 'Alpha one'), bbbbbbbbbbb: video('bbbbbbbbbbb', 'Alpha', 'Alpha two'),
  ccccccccccc: video('ccccccccccc', 'Beta', 'Beta one')}}));

const children = [];
const start = (cmd, args, pattern) => new Promise((resolve, reject) => {
  const child = spawn(cmd, args, {cwd: base}); children.push(child);
  let out = '';
  const read = chunk => { out += chunk; const m = out.match(pattern); if (m) resolve(m[1]); };
  child.stdout.on('data', read); child.stderr.on('data', read);
  child.on('exit', code => reject(new Error(`${cmd} exited ${code}: ${out.slice(-400)}`)));
});
const cleanup = () => { for (const c of children) c.kill('SIGTERM'); fs.rmSync(base, {recursive: true, force: true}); };
process.on('exit', cleanup);

const app = await start(path.join(base, 'scout'), ['--no-browser', '--port', '0'], /running at (http:\/\/127\.0\.0\.1:\d+)/);
const browserWs = await start(chrome, ['--no-sandbox', '--disable-gpu', '--headless', '--remote-debugging-port=0',
  '--window-size=1600,900', `--user-data-dir=${path.join(base, 'profile')}`, 'about:blank'], /DevTools listening on (ws:\/\/\S+)/);
const port = new URL(browserWs).port;
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?${app}`, {method: 'PUT'})).json();

// Minimal CDP client.
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, {once: true}));
let seq = 0; const pending = new Map(); const errors = [];
ws.addEventListener('message', ({data}) => {
  const msg = JSON.parse(data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === 'Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
});
const send = (method, params = {}) => new Promise(r => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({id, method, params})); });
const js = async (expression) => {
  const {result} = await send('Runtime.evaluate', {expression: `(async()=>{${expression}})()`, awaitPromise: true, returnByValue: true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
};
const until = async (expression, what, ms = 8000) => {
  for (const end = Date.now() + ms; Date.now() < end; await new Promise(r => setTimeout(r, 100)))
    if (await js(`return !!(${expression})`)) return;
  throw new Error('Timed out waiting for: ' + what);
};
const step = async (name, fn) => { await fn(); console.log('  ok', name); };
await send('Runtime.enable');
await send('Page.reload');

console.log('Scout e2e (real browser, throwaway data):');
await step('inbox loads with fixture videos', () => until(`document.querySelectorAll('#list .row').length===3`, '3 rows'));
await step('auto-check runs on open (network failure is handled)', () => until(`S.log.some(l=>l.includes('fetch youtube rss'))`, 'auto check'));
await until(`!S.busy`, 'auto check to finish', 30000);
await step('three-column desktop layout', async () => {
  const [inbox, reader, side] = await js(`return ['.inbox','.reader','.summarize'].map(s=>document.querySelector(s).getBoundingClientRect().left)`);
  assert.ok(inbox < reader && reader < side, `columns out of order: ${inbox}, ${reader}, ${side}`);
});
await step('creator filter shows one creator', async () => {
  await js(`[...document.querySelectorAll('#creators .seg')].find(b=>b.dataset.v==='Beta').click()`);
  await until(`document.querySelectorAll('#list .row').length===1`, 'Beta only');
  await js(`document.querySelector('#creators .seg[data-v=""]').click()`);
  await until(`document.querySelectorAll('#list .row').length===3`, 'everyone');
});
await step('follow a channel with a custom name', async () => {
  await js(`document.getElementById('following').open=true;$('follow-url').value='https://www.youtube.com/@gamma';$('follow-name').value='Gamma TV';$('follow-form').requestSubmit()`);
  await until(`(S.channels||[]).some(c=>c.name==='Gamma TV')`, 'Gamma TV followed');
  assert.ok(JSON.parse(fs.readFileSync(path.join(base, 'settings.json'), 'utf8')).channels.some(c => c.name === 'Gamma TV'));
});
await step('pasting a channel link in the video field follows it', async () => {
  await js(`$('addlink').value='https://www.youtube.com/@delta';$('addform').requestSubmit()`);
  await until(`(S.channels||[]).some(c=>c.name==='delta')`, 'delta followed');
});
await step('rename a channel relabels its videos', async () => {
  await js(`document.querySelector('[data-rename-start="Alpha"]').click()`);
  await js(`const f=document.querySelector('[data-rename="Alpha"]');f.elements.title.value='Alpha Prime';f.requestSubmit()`);
  await until(`S.videos.filter(v=>v.from==='Alpha Prime').length===2`, 'videos relabelled');
});
await step('master checkbox selects all shown, then clears', async () => {
  await js(`$('pick-master').click()`);
  await until(`picked.size===3&&$('pick-count').textContent==='3 selected'`, 'all selected');
  await js(`$('pick-master').click()`);
  await until(`picked.size===0`, 'cleared');
});
await step('remove a video, then undo', async () => {
  await js(`document.querySelector('[data-remove="ccccccccccc"]').click()`);
  await until(`!S.videos.some(v=>v.id==='ccccccccccc')&&!$('undo').hidden`, 'removed + undo shown');
  await js(`$('undo-button').click()`);
  await until(`S.videos.some(v=>v.id==='ccccccccccc')`, 'restored');
});
await step('summary length choice reaches the run options', async () => {
  await js(`document.querySelector('#lengths [data-v="deep"]').click()`);
  await until(`inputOptions().length==='deep'&&document.querySelector('#lengths [data-v="deep"]').getAttribute('aria-pressed')==='true'`, 'deep');
});
await step('"Summarize just this video" selects only that video and prepares it', async () => {
  await js(`document.querySelector('[data-open="aaaaaaaaaaa"]').click()`);
  await until(`document.querySelector('[data-only]')`, 'button');
  await js(`document.querySelector('[data-only]').click()`);
  await until(`picked.size===1&&picked.has('aaaaaaaaaaa')`, 'only one picked');
  await until(`S.log.some(l=>l.includes('prepare transcripts for 1'))`, 'prepare started');
  await until(`!S.busy`, 'prepare to finish', 30000);
});
await step('channel tick and check-on-open are saved to settings', async () => {
  await js(`const b=document.querySelector('#channels [data-include="Beta"]');b.click();$('check-on-open').click()`);
  await until(`await fetch('/api/settings').then(r=>r.json()).then(s=>s.ui.skipChannels.includes('Beta')&&s.ui.checkOnOpen==='off')`, 'saved on server');
  await js(`document.querySelector('#channels [data-include="Beta"]').click()`);
});
await step('mode switch and stepper save discovery settings', async () => {
  await js(`document.querySelector('#disc-mode [data-mode="days"]').click()`);
  await until(`!$('disc-days-wrap').hidden`, 'days stepper shown');
  const per = await js(`return Number($('disc-per').textContent)`);
  await js(`const b=document.querySelector('[data-key="max_per_channel"] [data-step="1"]');b.click();b.click()`);
  await until(`Number($('disc-per').textContent)===${per + 2}`, 'stepper counts up');
  await until(`await fetch('/api/settings').then(r=>r.json()).then(s=>s.max_per_channel===${per + 2}&&s.mode==='days')`, 'saved once debounced');
});
await step('add a summary language, use it, then remove it', async () => {
  await js(`$('gear').click()`);
  await until(`document.querySelector('[data-lang-action="add"]')`, 'add language button');
  assert.equal(await js(`return !!document.querySelector('#g-lang [data-v="de"]')`), false, 'Deutsch should be gone');
  await js(`document.querySelector('[data-lang-action="add"]').click()`);
  await until(`$('lang-form')`, 'language form');
  await js(`const f=$('lang-form');f.elements.language.value='romanian';f.requestSubmit()`);
  await until(`await fetch('/api/settings').then(r=>r.json()).then(s=>s.language==='Romanian'&&s.ui.languages.includes('Romanian'))`, 'Romanian saved');
  await js(`document.querySelector('[data-lang-action="remove"]').click()`);
  await until(`await fetch('/api/settings').then(r=>r.json()).then(s=>s.language==='en'&&!s.ui.languages.length)`, 'back to English');
  await js(`$('gear').click()`);
});
await step('inbox scrolls as one column, never sideways', async () => {
  const [head, wide] = await js(`const i=document.querySelector('.inbox');return [getComputedStyle(document.querySelector('.inbox-head')).overflowY, i.scrollWidth>i.clientWidth]`);
  assert.equal(head, 'visible'); assert.equal(wide, false);
});
await step('long channel names wrap; row buttons stay inside the panel', async () => {
  await js(`$('follow-url').value='https://www.youtube.com/@longname';$('follow-name').value='Jeremy Lefebvre Makes Money With Very Long Names';$('follow-form').requestSubmit()`);
  await until(`[...document.querySelectorAll('#channels li')].length===S.channels.length&&S.channels.length>=4`, 'long channel listed');
  const out = await js(`const r=$('channels').getBoundingClientRect().right;return [...document.querySelectorAll('#channels .ch-actions')].filter(a=>a.getBoundingClientRect().right>r+1).length`);
  assert.equal(out, 0, 'channel buttons overflow the panel');
});
await step('channel action icons keep their size', async () => {
  const w = await js(`return Math.min(...[...document.querySelectorAll('#channels .icon.mini svg')].map(s=>s.getBoundingClientRect().width))`);
  assert.ok(w >= 14, `icon squashed to ${w}px`);
});
await step('new note: inline name field, then the editor opens', async () => {
  await js(`document.querySelector('#views [data-v="library"]').click()`);
  await js(`$('new-note').click()`);
  await until(`!$('note-form').hidden&&document.activeElement===$('note-name')`, 'name field focused');
  await js(`$('note-name').value='Ideas';$('note-form').requestSubmit()`);
  await until(`$('note-editor')&&$('note-form').hidden`, 'editor open, form closed');
  assert.equal(await js(`return $('note-editor').value`), '# Ideas\n\n');
  await js(`document.querySelector('#views [data-v="inbox"]').click()`);
});
await step('theme switch recolours the app and the brand mark', async () => {
  await js(`$('gear').click()`);
  await until(`!$('pop').hidden&&document.querySelector('#g-theme [data-v="paper"]')`, 'settings open');
  await js(`document.querySelector('#g-theme [data-v="paper"]').click()`);
  await until(`document.documentElement.dataset.theme==='paper'`, 'paper theme');
  assert.equal(await js(`return getComputedStyle(document.querySelector('#mark .bar')).fill`), 'rgb(31, 79, 216)');
});
assert.deepEqual(errors, [], 'page threw: ' + errors.join('\n'));
console.log('All e2e checks passed with no page errors.');
process.exit(0);
