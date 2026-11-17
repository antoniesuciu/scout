/* Motion: transform/opacity only (compositor-friendly), one easing, nothing replays on a re-render. */
globalThis.Motion=(()=>{
  const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  const EASE='cubic-bezier(.2,.8,.2,1)';
  const play=(el,frames,opts)=>reduced()||!el.animate?null:el.animate(frames,{duration:260,easing:EASE,fill:'backwards',...opts});
  /** Write markup only when it changed, so live polling never rebuilds (or re-animates) a stable DOM. */
  function html(el,markup){if(el._markup===markup)return false;el._markup=markup;el.innerHTML=markup;return true;}
  /** Fade/rise children in with a short stagger. */
  function enter(nodes,{rise=6,step=28,max=10}={}){
    [...nodes].forEach((node,i)=>play(node,[{opacity:0,transform:`translateY(${rise}px)`},{opacity:1,transform:'none'}],{delay:Math.min(i,max)*step}));
  }
  function show(el){el.hidden=false;play(el,[{opacity:0,transform:'translateY(-4px) scale(.985)'},{opacity:1,transform:'none'}],{duration:200});}
  function hide(el){
    const a=play(el,[{opacity:1,transform:'none'},{opacity:0,transform:'translateY(-4px) scale(.985)'}],{duration:140,fill:'forwards'});
    if(!a){el.hidden=true;return;}
    a.onfinish=()=>{el.hidden=true;a.cancel();};
  }
  /** Sliding selection pill for a segmented row. */
  function pill(group){
    const on=group.querySelector('[aria-pressed="true"]');
    let p=group.querySelector(':scope>.seg-pill');
    if(!on||!on.offsetWidth){if(p)p.style.opacity=0;return;}
    if(!p){p=document.createElement('span');p.className='seg-pill';p.setAttribute('aria-hidden','true');group.prepend(p);}
    const placed=p.dataset.placed&&p.style.opacity!=='0';
    p.style.transition=placed&&!reduced()?'':'none';
    p.style.width=on.offsetWidth+'px';p.style.height=on.offsetHeight+'px';
    p.style.transform=`translate(${on.offsetLeft}px,${on.offsetTop}px)`;p.style.opacity=1;
    if(!placed){p.offsetWidth;p.style.transition='';p.dataset.placed=1;}
    group.classList.add('has-pill');
  }
  /** The brand mark re-types its lines while a job runs, and finishes its current cycle when the job ends. */
  function mark(svg,busy){
    if(!svg||!svg.animate)return;
    if(busy&&!svg._running){
      if(reduced())return;
      svg._running=[...svg.querySelectorAll('.bar')].map((bar,i)=>bar.animate(
        [{transform:'scaleX(1)'},{transform:'scaleX(0)',offset:.32},{transform:'scaleX(0)',offset:.42},{transform:'scaleX(1)',offset:.8},{transform:'scaleX(1)'}],
        {duration:2600,delay:i*90,iterations:Infinity,easing:EASE}));
      svg._running.push(svg.querySelector('.cur').animate([{opacity:1},{opacity:0,offset:.5},{opacity:1}],{duration:1100,iterations:Infinity,easing:'steps(1,end)'}));
    }else if(!busy&&svg._running){
      for(const a of svg._running){
        const t=a.effect.getComputedTiming();
        a.effect.updateTiming({iterations:(t.currentIteration||0)+1});
      }
      svg._running=null;
    }
  }
  return {html,enter,show,hide,pill,mark,play,reduced};
})();
