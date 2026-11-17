/* Settings editing/persistence is independent of video and file rendering. */
globalThis.SettingsPanel = class {
  constructor({$,ui,saved,notify,repaint}){
    Object.assign(this,{$,ui,saved,notify,repaint});this.appearanceQueue=Promise.resolve();this.resetDraft();
    $('save-settings').onclick=()=>this.saveJSON();
    $('save-default-model').onclick=()=>this.saveModel();
    $('save-appearance').onclick=()=>this.saveAppearance();
    $('revert-appearance').onclick=()=>{this.resetDraft();this.repaint();};
  }
  resetDraft(){this.draft=Object.fromEntries(['font','size','density'].map(key=>[key,this.ui[key]]));}
  preview(key,value){this.draft[key]=value;this.repaint();}
  previewState(){
    const sample=this.$('font-preview');
    for(const key of ['font','size','density'])sample.dataset[key]=this.draft[key];
    const changed=['font','size','density'].some(key=>this.draft[key]!==this.ui[key]);
    this.$('save-appearance').disabled=!changed;this.$('revert-appearance').disabled=!changed;
  }
  async saveAppearance(){
    try{
      await this.appearanceQueue;
      const data=await this.patch({ui:{...Object.fromEntries(['theme','fileView'].map(key=>[key,this.ui[key]])),...this.draft}});
      this.data=data;this.resetDraft();this.repaint();this.$('settings-status').textContent='Reading style saved.';
    }catch(error){this.$('settings-status').textContent=error.message;}
  }
  async patch(body,apply=true){
    const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok||data.error)throw Error(data.error||'Settings could not be saved.');
    if(apply)this.saved(data.settings);return data.settings;
  }
  async load(engine){
    try{const response=await fetch('/api/settings');const data=await response.json();if(!response.ok)throw Error(data.error||'Settings unavailable.');this.data=data;this.$('settings-json').value=JSON.stringify(data,null,2);this.$('default-model').value=data.engine_models[engine]||'';this.resetDraft();this.repaint();this.$('settings-status').textContent='Preview reading changes, then Save. Theme changes apply immediately.';}
    catch(error){this.$('settings-status').textContent=error.message;}
  }
  appearance(){
    const body={ui:Object.fromEntries(['theme','font','size','density','fileView'].map(key=>[key,this.ui[key]]))};
    this.appearanceQueue=this.appearanceQueue.then(()=>this.patch(body,false)).then(()=>{
      this.$('settings-status').textContent='Reading preferences saved.';
    }).catch(error=>{this.$('settings-status').textContent=error.message;});
    return this.appearanceQueue;
  }
  async saveJSON(){
    try{const body=JSON.parse(this.$('settings-json').value);const data=await this.patch(body);this.data=data;this.$('settings-json').value=JSON.stringify(data,null,2);this.$('settings-status').textContent='Settings saved.';this.notify('Settings saved.');}
    catch(error){this.$('settings-status').textContent=error.message;}
  }
  async saveModel(){
    try{const engine=this.ui.engine,model=this.$('default-model').value.trim();const data=await this.patch({engine_models:{[engine]:model}});this.ui.models[engine]=model;this.data=data;this.$('settings-json').value=JSON.stringify(data,null,2);this.$('settings-status').textContent='Model default saved.';this.notify('Model default saved.');}
    catch(error){this.$('settings-status').textContent=error.message;}
  }
};
