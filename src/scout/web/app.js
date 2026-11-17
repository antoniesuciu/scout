const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// look-and-feel choices are per browser; everything else lives on the server
const ui = { theme: 'ink', font: 'sans', size: 'm', density: 'comfortable', lang: null, engine: 'claude', depth: 'auto', length: 'standard', creator: '', filter: 'all', view:'inbox', libraryKind:'all', fileView:'rendered', runMode:'headless', profile:'isolated', models:{} };
try { Object.assign(ui, JSON.parse(localStorage.getItem('scout-ui') || '{}')); } catch (e) {}

// A new app window never inherits an interactive/configured execution choice.
ui.runMode='headless';ui.profile='isolated';
let preferencesLoaded=false;
let S = { session: 0, busy: null, videos: [], log: [], engines: {}, language: 'en' };
let raw = '', q = '', openId = null, note = '';
let shownIds = [], renaming = null, activeJob = null, stopLoader = null, shownNote = '', readerKey = null;
const seenRows = new Set();
const picked = new Set();
let searchFiles = new Set(), searchKeys = new Set(), searchTimer;
const MODEL_SUGGESTIONS={claude:['haiku','sonnet','opus'],codex:[],gemini:['auto','flash','pro','flash-lite']};
const remember=()=>{try{localStorage.setItem('scout-ui',JSON.stringify(ui));}catch(error){}};
const modelForRun=()=>ui.models[ui.engine]??S.engine_models?.[ui.engine]??'';
const files=new FileLibrary({$,esc,changed:()=>render(),notify:message=>{note=message;render();}});
const preferences=new SettingsPanel({$,ui,repaint:()=>renderSettings(),notify:message=>{note=message;render();},saved:data=>{
  S.preferences=data.ui;S.engine_models=data.engine_models;S.language=data.language;ui.models={...data.engine_models};
  Object.assign(ui,data.ui);ui.lang=data.language;remember();render();
}});

async function post(path, body) {
  try {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  note = data.error || (!r.ok ? `Request failed (${r.status})` : '');
  await refresh(true);
  return r.ok && !data.error;
  } catch (error) { note = 'The Scout server is not answering.'; render(); return false; }
}

async function refresh(force) {
  try {
    const text = await (await fetch('/api/state')).text();
    if (text === raw && !force) return;
    raw = text;
    S = JSON.parse(text);
    if(!preferencesLoaded){
      Object.assign(ui,S.preferences||{});ui.lang=S.language||'en';ui.models={...(S.engine_models||{}),...(ui.models||{})};
      preferences.resetDraft();preferencesLoaded=true;
      autoCheck();
    }
  } catch (e) {
    note = 'The scout server is not answering. Start it again with ./scout';
  }
  render();
}

function segs(el, key, pairs, off) {
  const draftKey=['font','size','density'].includes(key);
  const current=draftKey?preferences.draft[key]:ui[key];
  // Buttons are built once and then updated in place, so the selection pill can glide between them.
  Motion.html(el, pairs.map(([v, label, mono]) =>
    `<button class="seg${mono ? ' mono' : ''}" data-fid="${key}:${v}" data-v="${v}">${esc(label)}</button>`).join(''));
  for (const b of el.querySelectorAll ? el.querySelectorAll('.seg') : []) {
    b.setAttribute('aria-pressed', String(current === b.dataset.v));
    b.disabled = !!(off && off[b.dataset.v]); b.title = (off && off[b.dataset.v]) || '';
  }
  if (el.querySelector) requestAnimationFrame(() => Motion.pill(el));
  el.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    if(key==='view' && !files.canLeave())return;
    if(draftKey){preferences.preview(key,b.dataset.v);return;}
    ui[key] = b.dataset.v;
    if(key==='view' && ui.view==='library')files.refresh();
    if(key==='lang')preferences.patch({language:ui.lang},false).catch(error=>{note=error.message;render();});
    if(['theme','font','size','density','fileView'].includes(key))preferences.appearance();
    try { localStorage.setItem('scout-ui', JSON.stringify(ui)); } catch (err) {}
    render();
  };
}

const text = (v) => [v.title, v.from, v.summary && JSON.stringify(v.summary)].join(' ').toLowerCase();
const todo = () => S.videos.filter(v=>picked.has(v.id));

// Summaries are English unless the user adds another language; the AI writes the summary in it.
let addingLanguage=false;
function saveLanguages(languages,language){
  ui.languages=languages;ui.lang=language;remember();renderSettings();render();
  preferences.patch({ui:{languages},language},false).catch(error=>{note=error.message;render();});
}
$('groups').addEventListener('click',e=>{
  const action=e.target.closest('[data-lang-action]')?.dataset.langAction;if(!action)return;
  if(action==='add'){addingLanguage=true;renderSettings();document.getElementById('lang-form')?.elements.language.focus();}
  if(action==='cancel'){addingLanguage=false;renderSettings();}
  if(action==='remove')saveLanguages((ui.languages||[]).filter(n=>n!==ui.lang),'en');
});
$('groups').addEventListener('submit',e=>{
  if(e.target.id!=='lang-form')return;e.preventDefault();
  const raw=e.target.elements.language.value.trim().replace(/\s+/g,' ');
  const name=raw.charAt(0).toUpperCase()+raw.slice(1);
  if(!/^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ -]{1,29}$/.test(name)){note='Type a language name using letters only, e.g. Romanian.';render();return;}
  addingLanguage=false;
  if(name.toLowerCase()==='english'){saveLanguages(ui.languages||[],'en');return;}
  const languages=(ui.languages||[]).some(n=>n.toLowerCase()===name.toLowerCase())?ui.languages:[...(ui.languages||[]),name];
  saveLanguages(languages,languages.find(n=>n.toLowerCase()===name.toLowerCase()));
});
function renderSettings(){
  const focus=document.activeElement?.dataset.fid;
  Motion.html($('groups'), [['Theme', 'theme'], ['Reading font', 'font'], ['Text size', 'size'], ['Inbox density', 'density'], ['Summary language', 'lang']]
    .map(([name, key]) => `<div class="group"><span class="small muted">${name}</span><div class="segs" id="g-${key}" role="group" aria-label="${name}"></div>${key==='lang'?'<div class="lang-add" id="lang-add"></div>':''}</div>`).join(''));
  segs($('g-theme'), 'theme', [['ink', 'Ink'], ['paper', 'Paper'], ['phosphor', 'Phosphor']]);
  segs($('g-font'), 'font', [['sans', 'Sans'], ['serif', 'Serif'], ['mono', 'Mono']]);
  segs($('g-size'), 'size', [['s', 'Small'], ['m', 'Medium'], ['l', 'Large']]);
  segs($('g-density'), 'density', [['comfortable', 'Comfortable'], ['compact', 'Compact']]);
  segs($('g-lang'), 'lang', [['en', 'English'], ...(ui.languages||[]).map(name=>[name, name])]);
  Motion.html(document.getElementById('lang-add'), addingLanguage
    ? `<form class="lang-form" id="lang-form"><input class="field sunk" name="language" maxlength="30" placeholder="e.g. Romanian" aria-label="Language name" data-fid="lang-name" required><button class="btn">Add</button><button type="button" class="btn ghost" data-lang-action="cancel">Cancel</button></form>`
    : `<button type="button" class="btn ghost small" data-lang-action="add">+ Add language</button>${ui.lang!=='en'?`<button type="button" class="btn ghost small" data-lang-action="remove">Remove ${esc(ui.lang)}</button>`:''}`);

  preferences.previewState();
  const again=focus&&document.querySelector(`[data-fid="${CSS.escape(focus)}"]`);if(again)again.focus();
}

function render() {
  const focus = document.activeElement && document.activeElement.dataset.fid;
  const app = $('app');
  for (const k of ['theme', 'font', 'size', 'density']) { app.dataset[k] = ui[k]; document.documentElement.dataset[k] = ui[k]; }
  if (!ui.lang) ui.lang = S.language;
  if (S.engines[ui.engine] === false) ui.engine = Object.keys(S.engines).find(key=>S.engines[key])||'claude';
  if (ui.depth === 'frames') ui.depth = 'ocr';

  $('sub').textContent = `${S.videos.length} video${S.videos.length===1?'':'s'}`;
  if (S.busy !== activeJob) {
    if (stopLoader) { stopLoader(); stopLoader = null; }
    activeJob = S.busy;
    if (S.busy) { stopLoader = ScoutLoaders.star($('activity'), S.busy); Motion.play($('activity'), [{opacity:0},{opacity:1}]); }
    Motion.mark($('mark'), !!S.busy);
  }

  renderSettings();

  segs($('views'),'view',[['inbox','Inbox'],['library','Library']]);
  segs($('library-filters'),'libraryKind',[['all','All'],['summaries','Summaries'],['transcripts','Transcripts'],['notes','Notes']]);
  const libraryOpen=ui.view==='library';
  $('inbox-title').textContent=libraryOpen?'Files':'Inbox';
  $('library-toolbar').hidden=!libraryOpen;$('video-toolbar').hidden=libraryOpen;$('video-controls').hidden=libraryOpen;
  $('feedback').textContent=note;$('feedback').hidden=!note;
  if(note&&note!==shownNote)Motion.play($('feedback'),[{opacity:0,transform:'translateY(-4px)'},{opacity:1,transform:'none'}]);
  shownNote=note;
  segs($('filters'), 'filter', [['all', 'All'], ['yt', 'YouTube'], ['reels', 'Reels'], ['saved', 'Reels, saved']], {saved: 'Saved-post fetching is deferred'});
  const missing = (n) => (S.engines[n] === false ? `${n} is not installed` : '');
  segs($('engines'), 'engine', [['claude', 'Claude', 1], ['codex', 'Codex', 1], ['gemini', 'Gemini', 1]], { claude: missing('claude'), codex: missing('codex'), gemini: missing('gemini') });
  if(document.activeElement!==$('model'))$('model').value=modelForRun();
  $('model-choices').innerHTML=(S.model_choices?.[ui.engine]||MODEL_SUGGESTIONS[ui.engine]||[]).map(model=>`<option value="${esc(model)}"></option>`).join('');
  segs($('run-modes'),'runMode',[['headless','Summarize in background'],['terminal','Open AI in a terminal']]);
  segs($('profiles'),'profile',[['isolated','Isolated'],['configured','My CLI setup']]);
  const terminal=ui.runMode==='terminal';
  $('terminal-options').hidden=!terminal;$('depth-choice').hidden=terminal;$('prepare').hidden=terminal;
  $('context-note').textContent=terminal&&ui.profile==='configured'
    ? 'Interactive only: inherits your CLI tools, hooks, skills and memory. May use extra quota.'
    : 'Runs your AI app quietly using your existing subscription. No coding skills, hooks, memory or MCP.';
  segs($('depths'), 'depth', [['auto', 'Best for source'], ['text', 'Spoken words only'], ['ocr', 'Spoken + on-screen text']]);
  const depthNames={auto:'best for source',text:'spoken words',ocr:'spoken + on-screen'};
  $('ai-summary').textContent=terminal?`${ui.engine} · terminal`:`${ui.engine} · ${modelForRun()||'default model'} · ${depthNames[ui.depth]||ui.depth}`;
  segs($('lengths'), 'length', [['brief', 'Brief'], ['standard', 'Standard'], ['deep', 'Deep dive'], ['plain', 'Plain words']]);
  $('length-choice').hidden=terminal;
  const channels=S.channels||[];
  $('following-title').textContent=`Following ${channels.length} channel${channels.length===1?'':'s'}`;
  const skipped=new Set(ui.skipChannels||[]),checking=channels.filter(c=>!skipped.has(c.name));
  const tally=name=>{const mine=S.videos.filter(v=>v.from===name);return [mine.length,mine.filter(v=>v.status!=='summarized').length];};
  Motion.html($('channels'),channels.map((c,i)=>{const [all,fresh]=tally(c.name);return `<li>
    <label class="tick"><input type="checkbox" data-include="${esc(c.name)}" ${skipped.has(c.name)?'':'checked'} aria-label="Include ${esc(c.name)} when checking"></label>
    ${renaming===c.name
      ?`<form class="rename" data-rename="${esc(c.name)}"><input class="field" name="title" value="${esc(c.name)}" maxlength="80" aria-label="New name for ${esc(c.name)}" data-fid="rename"><button class="btn">Save</button></form>`
      :`<button class="creator-link" data-creator="${esc(c.name)}" title="Show only ${esc(c.name)} in the inbox"><b>${esc(c.name)}</b><span>${all} video${all===1?'':'s'}${fresh?` · ${fresh} to read`:''}</span></button>
    <span class="ch-actions"><button class="btn ghost icon mini" data-check-one="${esc(c.name)}" aria-label="Check ${esc(c.name)} for new videos" title="Check only this channel"><svg aria-hidden="true" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13 8a5 5 0 1 1-1.5-3.5M13 2.5V5h-2.5"/></svg></button>
    <button class="btn ghost icon mini" data-rename-start="${esc(c.name)}" aria-label="Rename ${esc(c.name)}" title="Rename"><svg aria-hidden="true" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.5 3.5l2 2L6 12H4v-2z"/></svg></button>
    <a class="btn ghost icon mini" href="${esc(c.url)}" target="_blank" rel="noopener" aria-label="Open ${esc(c.name)} on YouTube" title="Open on YouTube"><svg aria-hidden="true" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h4v4M13 3 7 9M11 9.5V13H3V5h3.5"/></svg></a>
    <button class="btn ghost icon mini" data-unfollow="${i}" aria-label="Unfollow ${esc(c.name)}" title="Unfollow"><svg aria-hidden="true" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m4 4 8 8m0-8-8 8"/></svg></button></span>`}
  </li>`;}).join('')||'<li class="muted small">No channels yet. Paste a channel link below, e.g. https://www.youtube.com/@name</li>');
  for(const box of $('channels').querySelectorAll?$('channels').querySelectorAll('[data-include]'):[])box.checked=!skipped.has(box.dataset.include);
  for(const b of $('channels').querySelectorAll?$('channels').querySelectorAll('[data-check-one]'):[])b.disabled=!!S.busy;
  const d={mode:'latest',max_per_channel:3,max_age_days:7,...S.discovery,...discDraft};
  for(const b of $('disc-mode').querySelectorAll?$('disc-mode').querySelectorAll('.seg'):[])b.setAttribute('aria-pressed',String(b.dataset.mode===d.mode));
  requestAnimationFrame(()=>Motion.pill($('disc-mode')));
  $('disc-days').textContent=d.max_age_days;$('disc-per').textContent=d.max_per_channel;
  $('disc-days-wrap').hidden=d.mode!=='days';
  $('check-on-open').checked=ui.checkOnOpen==='on';
  const label=!channels.length?'Check for new videos':checking.length===channels.length?'Check all channels for new videos':`Check ${checking.length} of ${channels.length} channels`;
  $('session').textContent=label;$('check-new').textContent=label;
  $('session').disabled=$('check-new').disabled=!!S.busy||!checking.length;
  $('session').title=channels.length?'Looks for new uploads on the ticked channels. Free: no AI is used.':'Follow a channel first (Following, in the inbox)';

  const counts=new Map();for(const v of S.videos)counts.set(v.from,(counts.get(v.from)||0)+1);
  if(ui.creator&&!counts.has(ui.creator))ui.creator='';
  $('creators-row').hidden=counts.size<2;
  segs($('creators'),'creator',[['',`Everyone · ${S.videos.length}`],...[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([name,n])=>[name,`${name} · ${n}`])]);
  const items = ui.filter === 'saved' ? [] : S.videos.filter((v) => (ui.filter === 'all' || (v.platform || 'youtube') === (ui.filter === 'yt' ? 'youtube' : 'reels')) && (!ui.creator || v.from === ui.creator) && (!q || text(v).includes(q) || searchFiles.has(v.file)));
  if (!S.videos.some((v) => v.id === openId)) openId = S.videos.length ? S.videos[0].id : null;
  const listMarkup = items.map((v) => `
    <div class="row" aria-current="${v.id === openId}">
      <label class="tick"><input type="checkbox" data-fid="pick:${esc(v.id)}" data-pick="${esc(v.id)}" ${picked.has(v.id) ? 'checked' : ''} aria-label="Select ${esc(v.title)}"></label>
      <button class="open" data-fid="open:${esc(v.id)}" data-open="${esc(v.id)}"><b>${esc(v.title)}</b><span>${v.platform === 'reels' ? 'Reels' : 'YouTube'} | ${esc(v.from)} | ${esc(v.len)}</span></button>
      <span class="status">${esc(v.status)}</span>
      <button class="btn ghost icon remove" data-remove="${esc(v.id)}" aria-label="Remove ${esc(v.title)} from the inbox" title="Remove from inbox"><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="m4 4 8 8m0-8-8 8"/></svg></button>
    </div>`).join('') || `<div class="empty-list">${
      ui.filter === 'saved' ? 'Reels are not built yet. Only YouTube works so far.'
        : q ? 'Nothing matches that search.'
        : ui.creator ? `No videos from ${esc(ui.creator)} here. Try Check for new videos.`
        : `<b>Welcome to Scout.</b><ol class="steps"><li><b>Follow</b> YouTube channels (Following, above) or paste a single video link.</li><li><b>Check for new videos</b>: free, no AI used.</li><li><b>Tick</b> the videos you want, choose a length, then <b>Summarize</b>.</li></ol>`}</div>`;
  if (Motion.html($('list'), libraryOpen ? files.list(q,ui.libraryKind,searchKeys) : listMarkup) && $('list').querySelectorAll) {
    const fresh = [...$('list').querySelectorAll('.row')].filter(row => { const id = row.querySelector('[data-open],[data-doc]')?.dataset; const key = id && (id.open || id.doc); if (!key || seenRows.has(key)) return false; seenRows.add(key); return true; });
    Motion.enter(fresh, {rise: 4, step: 24});
  }
  $('pick-bar').hidden = libraryOpen || !items.length;
  shownIds = items.map(v => v.id);
  const shownPicked = shownIds.filter(id => picked.has(id)).length;
  $('pick-master').checked = !!shownIds.length && shownPicked === shownIds.length;
  $('pick-master').indeterminate = shownPicked > 0 && shownPicked < shownIds.length;
  $('pick-remove').hidden = !picked.size;
  $('pick-count').textContent = picked.size ? `${picked.size} selected` : 'Tick videos to summarize, or open one and summarize just that';
  const n = todo().length;
  const options = inputOptions();
  const preview = S.preview || {};
  const ids = todo().map((v) => v.id);
  const ready = preview.ready && JSON.stringify(ids) === JSON.stringify(preview.ids) &&
    preview.engine === ui.engine && preview.model===modelForRun() && preview.language === ui.lang && JSON.stringify(preview.options) === JSON.stringify(options);
  $('frame-options').hidden = terminal || (ui.depth !== 'ocr' && !(ui.depth === 'auto' && todo().some(v => v.platform === 'reels')));
  $('frame-times').hidden = $('frame-method').value !== 'manual';
  $('prepare').disabled = !!S.busy || !n || !S.engines[ui.engine];
  $('note').textContent = note || (ready
    ? `${preview.words.toLocaleString()} words, ${preview.characters.toLocaleString()} characters. ${preview.cached} cached. ${preview.model_calls} model call. Exact tokens depend on the engine.`
    : 'Step 1: Prepare fetches the transcripts and shows the size. Free: no AI is used yet. Step 2: Summarize.');
  $('run').textContent = S.busy ? 'Working…' : n ? (ready ? `Summarize ${n} selected` : `Prepare first, then summarize ${n}`) : 'Tick videos to summarize';
  $('run').disabled = terminal ? !S.engines[ui.engine] : !!S.busy || !n || !ready || !S.engines[ui.engine];
  if(terminal)$('run').textContent=`Open ${ui.engine} terminal`;

  renderReader();
  const lines = $('lines');
  if (Motion.html(lines, S.log.map((l) => `<span>${esc(l)}</span>`).join('') || '<span class="muted">Nothing has run yet.</span>'))
    lines.scrollTo ? lines.scrollTo({top: lines.scrollHeight, behavior: Motion.reduced() ? 'auto' : 'smooth'}) : (lines.scrollTop = lines.scrollHeight);

  const again = focus && document.querySelector(`[data-fid="${CSS.escape(focus)}"]`);
  if (again) again.focus();
}

function setReader(markup,key){
  const reader=$('reader');
  if(!Motion.html(reader,markup))return;
  if(key!==readerKey&&reader.children)Motion.enter(reader.querySelectorAll(':scope>*,.read>section,.read>.links'),{rise:6,step:35});
  readerKey=key;
}

function renderReader() {
  if(ui.view==='library'){
    const markup=files.reader(ui.fileView);if(markup!==null)setReader(markup,'doc:'+(files.document?.key||''));return;
  }
  const v = S.videos.find((x) => x.id === openId);
  if (!v) {
    setReader(`<div class="dashed"><b>No video open</b><span class="muted">Follow channels, press Check for new videos, then pick one from the list. Nothing is sent to an AI until you press Summarize.</span></div>`,'none');
    return;
  }
  const head = `<div class="group"><span class="meta">${v.platform === 'reels' ? 'Reels' : 'YouTube'} | ${esc(v.from)} | ${esc(v.len)} | ${esc(v.date)}</span><h1>${esc(v.title)}</h1></div>`;
  const original = `<a class="link" href="${esc(v.url || 'https://www.youtube.com/watch?v=' + encodeURIComponent(v.id))}" target="_blank" rel="noopener">Open original</a>`;
  const sm = v.summary;
  if (v.status !== 'summarized' || !sm) {
    const why = {
      failed: ['Summary failed', 'The process log says why. Tick it in the inbox and run the summarizer again.'],
      'no transcript': ['No transcript available', 'This video has no subtitles yet, or it is a livestream. Try again later.'],
    }[v.status] || ['Not summarized yet', 'Press the button to fetch its transcript (free), then press Summarize. Nothing is sent to an AI until you do.'];
    const only = v.status === 'no transcript' ? '' : `<button class="run only" data-only="${esc(v.id)}">Summarize just this video</button>`;
    setReader(`${head}<div class="dashed"><b>${why[0]}</b><span class="muted">${why[1]}</span>${only}</div><div class="links">${original}</div>`,v.id+v.status);
    return;
  }
  const list = (xs, none) => (xs.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : `<p class="muted">${none}</p>`);
  const tickers = sm.tickers.length
    ? `<div class="tickers">${sm.tickers.map((t) => `<span>${esc(t.symbol)} | ${esc(t.note)}${t.price ? ` | price snapshot ${esc(t.price)}` : ''}</span>`).join('')}</div>`
    : '<p class="muted">None discussed.</p>';
  setReader(`${head}
    <div class="read">
      <section><h2 class="label">Thesis</h2><p class="thesis">${esc(sm.thesis)}</p></section>
      <section><h2 class="label">Key points</h2>${list(sm.points, 'None returned.')}</section>
      <section><h2 class="label">Tickers</h2>${tickers}</section>
      <section><h2 class="label">On screen, not spoken</h2>${v.ocr_mode ? list((v.ocr || []).map(x => `${x.seconds}s: ${x.text}`), "No additional text detected by local OCR.") : '<p class="muted">Not read. This summary used the transcript only.</p>'}</section>
      <section><h2 class="label">Check before trusting</h2>${list(sm.check, 'Nothing flagged.')}</section>
      <div class="links">${original}
        <a class="link" href="/file/transcripts/${encodeURIComponent(v.file)}.txt" target="_blank">Cleaned transcript</a>
        <a class="link" href="/file/summaries/${encodeURIComponent(v.file)}.md" target="_blank">Summary file (.md)</a>
        <span class="link meta">${esc(v.engine)} ${esc(v.model||'')} | ${esc(v.summarized || '')}</span>
      </div>
    </div>`,v.id+v.status);
}

$('list').addEventListener('click', (e) => {
  const doc=e.target.closest('[data-doc]');if(doc){files.select(doc.dataset.doc);return;}
  const gone=e.target.closest('[data-remove]');if(gone){removeVideos([gone.dataset.remove]);return;}
  const b = e.target.closest('[data-open]');
  if (b) { openId = b.dataset.open; render(); }
});
$('list').addEventListener('change', (e) => {
  const id = e.target.dataset.pick;
  if (!id) return;
  e.target.checked ? picked.add(id) : picked.delete(id);
  render();
});
$('search').addEventListener('input', (e) => {
  q = e.target.value.trim().toLowerCase(); searchFiles = new Set();searchKeys=new Set(); render();
  clearTimeout(searchTimer);
  const query = q;
  searchTimer = setTimeout(async () => {
    if (!query) return;
    try {
      const results = await (await fetch('/api/search?q=' + encodeURIComponent(query))).json();
      if (q !== query) return;
      searchKeys=new Set(results.map(r=>r.path));
      searchFiles = new Set(results.map(r => r.path.split('/').pop().replace(/\.(txt|md)$/, '')));
      render();
    } catch (error) { note = 'Transcript search is unavailable. Titles and summaries still work.'; render(); }
  }, 200);
});
$('session').onclick = () => {
  ui.runMode='headless';ui.profile='isolated';remember();
  const skipped=new Set(ui.skipChannels||[]);
  post('/api/session',{channels:(S.channels||[]).map(c=>c.name).filter(n=>!skipped.has(n))});
};
$('addform').onsubmit = (e) => {
  e.preventDefault();
  const url = $('addlink').value.trim();
  if (!url) return;
  try{const parsed=new URL(url);if(channelLink(parsed)){if(follow(parsed,''))$('addlink').value='';return;}}catch(error){}
  $('addlink').value = '';
  post('/api/add', { url });
};
function inputOptions() {
  return {depth: ui.depth === 'text' ? 'text' : ui.depth, length: ui.length, frames: {
    method: $('frame-method').value, interval: 15, cap: 12,
    manual: $('frame-times').value.split(',').filter(s => s.trim()).map(Number)
  }};
}
async function saveChannels(channels){
  const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channels})});
  const data=await r.json().catch(()=>({}));note=data.error||'';await refresh(true);
}
$('follow-form').onsubmit=(e)=>{
  e.preventDefault();
  let url;try{url=new URL($('follow-url').value.trim());}catch(error){note='Paste a full channel link, e.g. https://www.youtube.com/@name';render();return;}
  if(follow(url,$('follow-name').value.trim())){$('follow-url').value='';$('follow-name').value='';}
};
// Channel links look like /@name, /channel/UC…, /c/name or /user/name.
const channelLink=url=>/^(www\.|m\.)?youtube\.com$/.test(url.hostname)&&/^\/(@[^/]+|channel\/[^/]+|c\/[^/]+|user\/[^/]+)\/?$/.test(url.pathname);
function follow(url,title){
  if(!channelLink(url)){note='Use a YouTube channel link like https://www.youtube.com/@name';render();return false;}
  url=new URL(url.origin.replace('m.youtube','www.youtube').replace('//youtube','//www.youtube')+url.pathname.replace(/\/$/,''));
  const name=title||decodeURIComponent(url.pathname.split('/').pop()).replace(/^@/,'');
  const channels=S.channels||[];
  if(channels.some(c=>c.url.replace(/\/$/,'')===url.href)){note='Already following that channel.';render();return false;}
  if(channels.some(c=>c.name===name)){note=`You already follow a channel named ${name}. Give this one another name.`;render();return false;}
  saveChannels([...channels,{name,url:url.href,channel_id:null,group:null}]).then(()=>{if(!note){note=`Following ${name}. Press Check to fetch its latest videos.`;render();}});
  return true;
}
$('channels').onchange=(e)=>{
  const name=e.target.dataset.include;if(!name)return;
  const skipped=new Set(ui.skipChannels||[]);e.target.checked?skipped.delete(name):skipped.add(name);
  ui.skipChannels=[...skipped];savePreference({skipChannels:ui.skipChannels});
};
$('check-on-open').onchange=e=>{ui.checkOnOpen=e.target.checked?'on':'off';savePreference({checkOnOpen:ui.checkOnOpen});};
// Channel ticks and launch behaviour live in the settings file: the desktop webview's localStorage is not reliable.
function savePreference(patch){
  remember();render();
  fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ui:patch})})
    .then(r=>r.json()).then(d=>{if(d.error){note=d.error;render();}}).catch(()=>{note='Could not save that choice.';render();});
}
// Like a mail client: with nothing shown selected it selects all shown; otherwise it clears them.
$('pick-master').onchange=()=>{const any=shownIds.some(id=>picked.has(id));for(const id of shownIds)any?picked.delete(id):picked.add(id);render();};
function autoCheck(){
  if(ui.checkOnOpen!=='on')return;
  let done=false;try{done=sessionStorage.getItem('scout-checked');sessionStorage.setItem('scout-checked','1');}catch(error){}
  if(!done&&!S.busy&&(S.channels||[]).length)setTimeout(()=>{if(!$('session').disabled)$('session').click();},400);
}
let undoIds=[];
async function removeVideos(ids){
  if(!ids.length)return;
  // Collapse the rows first, then drop them from the list.
  const rows=ids.map(id=>$('list').querySelector(`[data-open="${CSS.escape(id)}"]`)?.closest('.row')).filter(Boolean);
  await Promise.all(rows.map(row=>Motion.play(row,[{opacity:1,transform:'none',height:row.offsetHeight+'px'},{opacity:0,transform:'translateX(-12px)',height:'0px',paddingBlock:'0px'}],{duration:220,fill:'forwards'})?.finished).filter(Boolean));
  ids.forEach(id=>picked.delete(id));
  if(await post('/api/hide',{ids})){undoIds=ids;note='';showUndo(ids.length);}
}
function showUndo(n){
  $('undo-text').textContent=`Removed ${n} video${n===1?'':'s'}. New checks will not bring ${n===1?'it':'them'} back.`;
  Motion.show($('undo'));clearTimeout(showUndo.timer);showUndo.timer=setTimeout(()=>Motion.hide($('undo')),8000);
}
$('undo-button').onclick=async()=>{clearTimeout(showUndo.timer);Motion.hide($('undo'));if(undoIds.length)await post('/api/hide',{ids:undoIds,hidden:false});undoIds=[];};
$('pick-remove').onclick=()=>removeVideos([...picked].filter(id=>S.videos.some(v=>v.id===id)));
$('channels').addEventListener('submit',async(e)=>{
  const form=e.target.closest('[data-rename]');if(!form)return;e.preventDefault();
  const title=form.elements.title.value.trim();
  if(title&&title!==form.dataset.rename){
    const old=form.dataset.rename;
    if(await post('/api/creator',{old,new:title})){
      if(ui.creator===old){ui.creator=title;remember();}
      if((ui.skipChannels||[]).includes(old)){ui.skipChannels=ui.skipChannels.map(n=>n===old?title:n);savePreference({skipChannels:ui.skipChannels});}
    }
  }
  renaming=null;render();
});
$('channels').addEventListener('keydown',e=>{if(e.key==='Escape'&&renaming){renaming=null;render();}});
$('channels').onclick=(e)=>{
  const one=e.target.closest('[data-check-one]');if(one){post('/api/session',{channels:[one.dataset.checkOne]});return;}
  const who=e.target.closest('[data-creator]');if(who){ui.creator=ui.creator===who.dataset.creator?'':who.dataset.creator;ui.filter='all';remember();render();return;}
  const start=e.target.closest('[data-rename-start]');if(start){renaming=start.dataset.renameStart;render();$('channels').querySelector('[data-fid="rename"]')?.select();return;}
  const b=e.target.closest('[data-unfollow]');if(!b)return;
  saveChannels((S.channels||[]).filter((_,i)=>i!==Number(b.dataset.unfollow)));
};
// Check window: newest N per channel, or unseen ones from the last N days (already-seen, removed or summarized videos never come back).
// Unsaved discovery edits win over polled state, so a refresh never snaps the stepper back mid-click.
let discDraft={},discTimer;
function editDiscovery(patch){
  Object.assign(discDraft,patch);render();
  clearTimeout(discTimer);discTimer=setTimeout(async()=>{
    const body={...discDraft};
    const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).catch(()=>null);
    const data=r?await r.json().catch(()=>({})):{error:'Could not save that choice.'};
    note=data.error||'';
    if(Object.keys(body).every(k=>discDraft[k]===body[k]))discDraft={};
    await refresh(true);
  },350);
}
$('disc-mode').onclick=e=>{const b=e.target.closest('[data-mode]');if(b)editDiscovery({mode:b.dataset.mode});};
$('discovery').addEventListener('click',e=>{
  const b=e.target.closest('[data-step]');if(!b)return;
  const box=b.closest('.stepper'),key=box.dataset.key,min=+box.dataset.min,max=+box.dataset.max;
  const now=Number(box.querySelector('output').textContent)||min;
  const next=Math.min(max,Math.max(min,now+Number(b.dataset.step)));
  if(next!==now)editDiscovery({[key]:next});
  Motion.play(box.querySelector('output'),[{transform:`translateY(${b.dataset.step>0?-6:6}px)`,opacity:.3},{transform:'none',opacity:1}],{duration:180});
});
$('check-new').onclick=()=>$('session').click();
$('frame-method').onchange = render;
$('frame-times').oninput = render;
$('prepare').onclick = () => post('/api/prepare', {ids: todo().map(v => v.id), engine: ui.engine, model:modelForRun(), language: ui.lang, options: inputOptions()});
$('run').onclick = () => {
  if(ui.runMode==='terminal'){post('/api/terminal',{engine:ui.engine,model:modelForRun(),profile:ui.profile});return;}
  const ids = todo().map((v) => v.id);
  if (!ids.length) return;
  post('/api/run', { ids, engine: ui.engine, model:modelForRun(), language: ui.lang });
};
const toggle = (show) => { show ? Motion.show($('pop')) : Motion.hide($('pop')); $('gear').setAttribute('aria-expanded', show); (show ? $('close') : $('gear')).focus(); };
$('gear').onclick = () => {const show=$('pop').hidden;toggle(show);if(show)preferences.load(ui.engine);};
$('close').onclick = () => toggle(false);
$('pop').addEventListener('keydown', (e) => { if (e.key === 'Escape') toggle(false); });
$('model').oninput=event=>{ui.models[ui.engine]=event.target.value.trim();remember();render();};
$('reader').addEventListener('click',event=>{
  const only=event.target.closest('[data-only]');
  if(only){picked.clear();picked.add(only.dataset.only);ui.runMode='headless';render();if(!$('prepare').disabled)$('prepare').click();return;}
  const button=event.target.closest('[data-document-mode]');if(!button)return;
  ui.fileView=button.dataset.documentMode;remember();preferences.appearance();render();
});
window.addEventListener('beforeunload',event=>{if(files.dirty){event.preventDefault();event.returnValue='';}});

refresh(true);
setInterval(refresh, 1500);
// Keep selection pills aligned when the window resizes or web fonts finish loading.
const realignPills=()=>document.querySelectorAll('.segs').forEach(group=>Motion.pill(group));
window.addEventListener('resize',realignPills);
document.fonts?.ready.then(realignPills);
$('ai-options').addEventListener('toggle',()=>requestAnimationFrame(realignPills));
$('following').addEventListener('toggle',()=>requestAnimationFrame(realignPills));
