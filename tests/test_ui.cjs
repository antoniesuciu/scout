// Run the actual dashboard script with a minimal DOM transport; no browser dependency.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {dataset:{}, value:id === 'frame-method' ? 'periodic' : '',
    innerHTML:'', textContent:'', hidden:false, addEventListener(){}, setAttribute(){}, focus(){}});
  return elements.get(id);
};
const context = vm.createContext({document:{getElementById:element, documentElement:{dataset:{}}, activeElement:null,querySelector(){return null}},
  localStorage:{getItem(){return null},setItem(){}}, setInterval(){},setTimeout(){},clearTimeout(){},
  fetch:async()=>({text:async()=>JSON.stringify({session:0,videos:[],log:[],engines:{claude:true},language:'en'})}),
  CSS:{escape:s=>s},window:{addEventListener(){}},matchMedia:()=>({matches:true}),requestAnimationFrame(){},console});
for(const file of ['motion.js','loaders.js','markdown.js','library-ui.js','settings-ui.js','app.js'])vm.runInContext(fs.readFileSync('src/scout/web/'+file,'utf8'),context);
vm.runInContext(`
S={session:1,busy:null,log:[],engines:{claude:true},language:'en',videos:[{
 id:'a',title:'<img src=x onerror=evil()>',from:'channel',len:'1:00',date:'2026-11-17',status:'new'}]};
ui.lang='en'; render();
`,context);
assert.match(element('list').innerHTML,/&lt;img/);
assert.equal(element('run').disabled,true);
vm.runInContext(`picked.add('a'); render();`,context);
assert.equal(element('prepare').disabled,false);
assert.equal(element('run').disabled,true);
vm.runInContext(`S.preview={ready:true,ids:['a'],engine:'claude',model:modelForRun(),language:'en',options:inputOptions(),words:200,characters:1200,cached:0,model_calls:1};render();`,context);
assert.equal(element('run').disabled,false);
vm.runInContext(`ui.lang='de';render();`,context);
assert.equal(element('run').disabled,true);
vm.runInContext(`S.videos[0].status='summarized'; S.videos[0].summary={thesis:'<script>evil()</script>',points:[],tickers:[],check:[]};render();`,context);
assert.match(element('reader').innerHTML,/&lt;script&gt;/);
assert.doesNotMatch(element('reader').innerHTML,/<script>/);
console.log('Dashboard checks passed: escaping, selection, preview gating, language invalidation, reader.');
// Controls use the same delegated handlers a browser click invokes.
vm.runInContext(`$('g-font').onclick({target:{closest:()=>({dataset:{v:'serif'},disabled:false})}});`,context);
assert.equal(element('app').dataset.font,'sans');
assert.equal(element('font-preview').dataset.font,'serif');
vm.runInContext(`$('g-size').onclick({target:{closest:()=>({dataset:{v:'l'},disabled:false})}});`,context);
assert.equal(element('app').dataset.size,'m');
assert.equal(element('font-preview').dataset.size,'l');
vm.runInContext(`$('revert-appearance').onclick();`,context);
assert.equal(element('font-preview').dataset.font,'sans');
assert.equal(element('save-appearance').disabled,true);
vm.runInContext(`ui.models.claude='heavy-model';render();`,context);
assert.equal(element('run').disabled,true);
vm.runInContext(`ui.view='library';files.document={key:'notes/a.md',text:'# Rendered note',markdown:true};render();`,context);
assert.match(element('reader').innerHTML,/<h1>Rendered note<\/h1>/);
vm.runInContext(`ui.fileView='raw';render();`,context);
assert.match(element('reader').innerHTML,/<pre[^>]+># Rendered note<\/pre>/);
vm.runInContext(`ui.view='inbox';ui.runMode='terminal';ui.profile='configured';render();`,context);
assert.equal(element('prepare').hidden,true);
assert.match(element('context-note').textContent,/inherits your CLI/);
vm.runInContext(`ui.runMode='headless';render();`,context);
assert.match(element('context-note').textContent,/No coding skills, hooks, memory or MCP/);
const markup=fs.readFileSync('src/scout/web/index.html','utf8')+fs.readFileSync('src/scout/web/library-ui.js','utf8');
for(const filename of ['app.js','library-ui.js','settings-ui.js']){
  const code=fs.readFileSync('src/scout/web/'+filename,'utf8');
  for(const match of code.matchAll(/\$\('([a-z][a-z-]+)'\)/g)){
    if(match[1].startsWith('g-'))continue;
    assert.ok(markup.includes(`id="${match[1]}"`),`Missing actual HTML element: ${match[1]}`);
  }
}
console.log('Workbench checks passed: font/size controls, model invalidation, Markdown/raw library, terminal context and actual element IDs.');
