/* File library controller; raw text stays separate from escaped Markdown presentation. */
globalThis.FileLibrary = class {
  constructor({$, esc, changed, notify}) {
    Object.assign(this, {$, esc, changed, notify});
    this.files=[];this.document=null;this.loading=false;this.loaded=false;this.editing=false;this.dirty=false;
    $('new-note').onclick=()=>this.newNote();
    $('note-cancel').onclick=()=>this.closeNoteForm();
    $('note-form').onsubmit=event=>{event.preventDefault();this.createNote($('note-name').value.trim());};
    $('note-form').onkeydown=event=>{if(event.key==='Escape')this.closeNoteForm();};
    $('import-note').onclick=()=>$('import-file').click();
    $('import-file').onchange=async event=>{
      const file=event.target.files[0];if(!file)return;
      try {if(file.size>2000000)throw Error('Choose a text file under 2 MB.');await this.storeUnique(file.name,await file.text());}catch(error){notify(error.message);}
      event.target.value='';
    };
    $('reader').addEventListener('click',event=>{
      const button=event.target.closest('[data-file-action]');if(!button)return;
      const action=button.dataset.fileAction;
      if(action==='edit'){this.editing=true;this.changed();}
      if(action==='save')this.save();
      if(action==='cancel'){if(this.canLeave()){this.editing=false;this.dirty=false;this.changed();}}
      if(action==='open')this.openExternal();
    });
    $('reader').addEventListener('input',event=>{if(event.target.id==='note-editor')this.dirty=true;});
  }
  canLeave(){return !this.dirty || confirm('Discard unsaved note changes?');}
  async request(url,body){
    const response=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok || data.error)throw Error(data.error||'File request failed.');return data;
  }
  async refresh(){
    this.loading=true;this.changed();
    try{this.files=await this.request('/api/library');this.loaded=true;}
    catch(error){this.notify(error.message);}
    finally{this.loading=false;this.changed();}
  }
  async select(key){
    if(!this.canLeave())return;
    this.editing=false;this.dirty=false;this.loading=true;this.changed();
    try{this.document=await this.request('/api/document?key='+encodeURIComponent(key));}
    catch(error){this.notify(error.message);}
    finally{this.loading=false;this.changed();}
  }
  list(query,kind,matched){
    return this.files.filter(file=>(kind==='all'||file.kind===kind)&&(!query||file.name.toLowerCase().includes(query)||matched.has(file.key)))
      .map(file=>`<div class="row" aria-current="${this.document?.key===file.key}"><button class="open" data-doc="${this.esc(file.key)}"><b>${this.esc(file.name)}</b><span>${this.esc(file.kind)} | ${(file.bytes/1024).toFixed(1)} KB | ${this.esc(file.modified)}</span></button></div>`).join('') || `<div class="empty-list">${this.loading?'Loading your files…':query?'No files match this search.':'No files here yet. Import a Markdown file or create a note.'}</div>`;
  }
  reader(mode){
    if(this.editing && this.$('note-editor'))return null;
    const doc=this.document, escape=this.esc;
    if(!doc)return '<div class="dashed reader-text"><b>Your file library</b><span>Open a summary, transcript or note from the list. Imported files stay on this machine.</span></div>';
    const head=`<div class="between"><h1>${escape(doc.key.split('/').pop())}</h1><a class="link" href="/file/${doc.key.split('/').map(encodeURIComponent).join('/')}" download>Download</a></div>`;
    if(this.editing)return `${head}<label for="note-editor" class="small muted">Edit Markdown or plain text</label><textarea id="note-editor" class="field note-editor reader-text" spellcheck="false">${escape(doc.text)}</textarea><div class="between"><button class="btn" data-file-action="save">Save note</button><button class="btn" data-file-action="cancel">Cancel</button></div>`;
    const toggle=`<div class="between"><div class="segs" role="group" aria-label="Document view"><button class="seg" data-document-mode="rendered" aria-pressed="${mode==='rendered'}">Rendered</button><button class="seg" data-document-mode="raw" aria-pressed="${mode==='raw'}">Raw text</button></div><div class="segs">${doc.key.startsWith('notes/')?'<button class="btn" data-file-action="edit">Edit note</button>':''}<button class="btn" data-file-action="open">Open in editor</button></div></div>`;
    const body=mode==='rendered'&&doc.markdown?`<div class="document reader-text">${renderMarkdown(doc.text)}</div>`:`<pre class="raw-document reader-text">${escape(doc.text)}</pre>`;
    return head+toggle+body;
  }
  async save(){
    try{const data=await this.request('/api/document',{key:this.document.key,text:this.$('note-editor').value});this.document=data.document;this.editing=false;this.dirty=false;await this.refresh();this.notify('Note saved.');}
    catch(error){this.notify(error.message);}
  }
  async storeUnique(name,text){
    if(!/\.(md|txt)$/i.test(name))throw Error('Choose a .md or .txt file.');
    const clean=name.replace(/[^A-Za-z0-9_. -]/g,'-').replace(/^[^A-Za-z0-9]+/,'')||'note.md';
    const extension=clean.slice(clean.lastIndexOf('.')),base=clean.slice(0,-extension.length).slice(0,130);
    let key='notes/'+base+extension,index=2;
    while(this.files.some(file=>file.key===key))key=`notes/${base}-${index++}${extension}`;
    await this.request('/api/document',{key,text});await this.refresh();await this.select(key);this.notify('File saved in your library.');
  }
  newNote(){
    if(!this.canLeave())return;
    const form=this.$('note-form');
    if(!form.hidden){this.$('note-name').focus();return;}
    this.$('note-name').value='';Motion.show(form);this.$('new-note').setAttribute('aria-expanded','true');this.$('note-name').focus();
  }
  closeNoteForm(){Motion.hide(this.$('note-form'));this.$('new-note').setAttribute('aria-expanded','false');this.$('new-note').focus();}
  async createNote(name){
    if(!name)return;
    this.dirty=false;this.editing=false;
    try{await this.storeUnique(/\.(md|txt)$/i.test(name)?name:name+'.md','# '+name.replace(/\.(md|txt)$/i,'')+'\n\n');this.closeNoteForm();this.editing=true;this.changed();
      requestAnimationFrame(()=>{const ed=this.$('note-editor');if(ed){ed.focus();ed.setSelectionRange(ed.value.length,ed.value.length);}});}
    catch(error){this.notify(error.message);}
  }
  async openExternal(){
    try{await this.request('/api/open',{key:this.document.key});}catch(error){this.notify(error.message);}
  }
};
