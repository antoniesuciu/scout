/* Scout loaders: star + rotating verb for jobs, the brand mark "typing" while busy. Adapted from scout-loaders.html. */
globalThis.ScoutLoaders=(()=>{
  const STAR=['·','✢','✳','✶','✻','✽'],FRAMES=[...STAR,...STAR.slice(1,-1).reverse()];
  const VERBS={
    summarize:['Scouting','Skimming','Distilling','Condensing','Reading between the lines','Taking notes','Separating signal from noise','Boiling it down'],
    prepare:['Fetching captions','Cleaning transcript','Reading on-screen text','Sampling frames','Checking the cache','Counting words'],
    'new session':['Checking channels','Reading feeds','Looking for new uploads','Fetching video details'],
    'add link':['Fetching the link','Reading video details'],
  };
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const shuffle=a=>{a=[...a];for(let i=a.length-1;i>0;i--){const j=Math.random()*(i+1)|0;[a[i],a[j]]=[a[j],a[i]];}return a;};
  /** Star spinner with rotating verbs and elapsed seconds. Returns stop(). */
  function star(el,job){
    el.className='sl-star';
    el.innerHTML='<span class="sl-star__glyph" aria-hidden="true"></span><span class="sl-star__verb"></span><span class="sl-star__meta"></span>';
    const [g,v,m]=el.children,t0=Date.now(),verbs=VERBS[job]||[job[0].toUpperCase()+job.slice(1)];
    let f=0,order=shuffle(verbs),i=0;
    g.textContent=FRAMES[0];v.textContent=order[0]+'…';
    const timers=[
      reduced?0:setInterval(()=>{g.textContent=FRAMES[++f%FRAMES.length];},120),
      setInterval(()=>{if(++i>=order.length){order=shuffle(verbs);i=0;}v.textContent=order[i]+'…';},3000),
      setInterval(()=>{m.textContent=`${Math.round((Date.now()-t0)/1000)}s`;},1000),
    ];
    return()=>{timers.forEach(clearInterval);el.textContent='';el.className='';};
  }
  return {star,VERBS};
})();
