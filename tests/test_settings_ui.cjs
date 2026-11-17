const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,{dataset:{},value:'',textContent:''});return elements.get(id);};
let stored={ui:{theme:'ink',font:'sans',size:'m',density:'comfortable',fileView:'rendered'},engine_models:{claude:'haiku'},language:'en'};
const calls=[],ui={...stored.ui,engine:'claude',models:{claude:'haiku'}};
let fail=false;
const context=vm.createContext({fetch:async(url,options)=>{
  const body=JSON.parse(options.body);calls.push(body);
  if(fail)return {ok:false,json:async()=>({error:'Save failed'})};
  stored={...stored,ui:{...stored.ui,...body.ui}};
  return {ok:true,json:async()=>({settings:stored})};
}});
vm.runInContext(fs.readFileSync('src/scout/web/settings-ui.js','utf8'),context);
let panel;
panel=new context.SettingsPanel({$:get,ui,saved:data=>Object.assign(ui,data.ui),notify(){},repaint:()=>panel.previewState()});
(async()=>{
  panel.preview('font','serif');panel.preview('size','l');
  assert.equal(ui.font,'sans');assert.equal(ui.size,'m');assert.equal(calls.length,0);
  assert.equal(get('font-preview').dataset.font,'serif');
  await panel.saveAppearance();
  assert.equal(calls.length,1);assert.equal(ui.font,'serif');assert.equal(ui.size,'l');
  assert.equal(get('save-appearance').disabled,true);
  panel.preview('font','mono');get('revert-appearance').onclick();
  assert.equal(get('font-preview').dataset.font,'serif');assert.equal(calls.length,1);
  panel.preview('font','mono');fail=true;await panel.saveAppearance();
  assert.equal(ui.font,'serif');assert.equal(get('settings-status').textContent,'Save failed');
  assert.equal(get('save-appearance').disabled,false);
  console.log('Settings flow passed: preview is local, Save applies/persists, Revert discards, failed saves retain current style.');
})().catch(error=>{console.error(error);process.exitCode=1;});
