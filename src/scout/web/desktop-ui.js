/* A narrow native window bridge. Browser mode keeps its own browser controls. */
(()=>{
  const bridge=window.webkit?.messageHandlers?.scout;
  if(!bridge)return;
  const send=(action,event)=>bridge.postMessage(JSON.stringify({action,x:Math.round(event?.screenX||0),y:Math.round(event?.screenY||0)}));
  document.getElementById('desktop-controls').hidden=false;
  document.getElementById('desktop-resize').hidden=false;
  document.getElementById('desktop-controls').addEventListener('click',event=>{
    const button=event.target.closest('[data-window-action]');if(button)send(button.dataset.windowAction);
  });
  const brand=document.querySelector('.brand');brand.classList.add('native-drag');
  brand.addEventListener('pointerdown',event=>{if(event.button===0){event.preventDefault();send('drag',event);}});
  brand.addEventListener('dblclick',()=>send('maximize'));
  document.getElementById('desktop-resize').addEventListener('pointerdown',event=>{if(event.button===0){event.preventDefault();send('resize',event);}});
})();
