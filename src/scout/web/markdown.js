/* A deliberately small, escaped Markdown renderer: no raw HTML or remote images. */
(function (scope) {
  const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function inline(text) {
    const code = [];
    let result = escape(text).replace(/`([^`]+)`/g, (_, value) => {code.push(`<code>${value}</code>`);return `\u0000${code.length-1}\u0000`;});
    result = result.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (whole,label,url) => /^https?:\/\//i.test(url) ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>` : label);
    result = result.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\*([^*]+)\*/g,'<em>$1</em>');
    return result.replace(/\u0000(\d+)\u0000/g, (_,index)=>code[Number(index)]);
  }
  scope.renderMarkdown = function (text) {
    const output = []; let paragraph = [], list = null, fence = null, code = [];
    const flush = () => {if(paragraph.length){output.push(`<p>${inline(paragraph.join(' '))}</p>`);paragraph=[];} if(list){output.push(`</${list}>`);list=null;}};
    for (const line of String(text).replace(/\r\n?/g,'\n').split('\n')) {
      const marker = line.match(/^\s*(```+|~~~+)/);
      if(marker){if(fence){output.push(`<pre><code>${escape(code.join('\n'))}</code></pre>`);fence=null;code=[];}else{flush();fence=marker[1];}continue;}
      if(fence){code.push(line);continue;}
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      const item = line.match(/^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/);
      if(heading){flush();output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`);}
      else if(item){if(paragraph.length){output.push(`<p>${inline(paragraph.join(' '))}</p>`);paragraph=[];}const type=item[2]?'ol':'ul';if(list!==type){if(list)output.push(`</${list}>`);output.push(`<${type}>`);list=type;}output.push(`<li>${inline(item[3])}</li>`);}
      else if(/^>\s?/.test(line)){flush();output.push(`<blockquote>${inline(line.replace(/^>\s?/,''))}</blockquote>`);}
      else if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)){flush();output.push('<hr>');}
      else if(!line.trim()){flush();}
      else {if(list){output.push(`</${list}>`);list=null;}paragraph.push(line);}
    }
    flush();if(fence)output.push(`<pre><code>${escape(code.join('\n'))}</code></pre>`);
    return output.join('\n');
  };
})(globalThis);
