const cards=document.getElementById('cards'), total=document.getElementById('total'), last=document.getElementById('last'), count=document.getElementById('count');
const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function niceDate(s){if(!s)return 'Date not provided';let d=new Date(s);return isNaN(d)?s:d.toLocaleString();}
async function load(){
 const q=document.getElementById('search').value, category=document.getElementById('category').value;
 const res=await fetch('/api/projects?q='+encodeURIComponent(q)+'&category='+encodeURIComponent(category));
 const data=await res.json(); total.textContent=data.total; count.textContent=`${data.projects.length} paid project leads`;
 if(!data.projects.length){cards.innerHTML='<div class="empty">No matching paid project leads found yet. Try Refresh or a different skill keyword. Only posts with payment clues and project-request wording are shown.</div>';return;}
 cards.innerHTML=data.projects.map(p=>`<article class="project"><div class="projecttop"><span class="tag">${esc(p.category)}</span><span class="source">${esc(p.source)}</span></div><h3>${esc(p.title)}</h3><p class="desc">${esc(p.description||'No description supplied. Open the original post for details.')}</p><div class="paidline"><span class="paidtag">Paid terms detected</span><span class="budget">${esc(p.budget||'Payment mentioned; verify amount')}</span></div><div class="projectbottom"><span class="date">${esc(niceDate(p.published))}</span><a class="open" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">View original post ↗</a></div></article>`).join('');
}
async function status(){const r=await fetch('/api/status');const d=await r.json();total.textContent=d.total;last.textContent=d.last_refresh?niceDate(d.last_refresh):'Not yet';}
document.getElementById('searchBtn').onclick=load;document.getElementById('category').onchange=load;
document.getElementById('search').addEventListener('keydown',e=>{if(e.key==='Enter')load()});
document.getElementById('refresh').onclick=async()=>{const b=document.getElementById('refresh');b.disabled=true;b.textContent='Refreshing…';try{const r=await fetch('/api/refresh',{method:'POST'});const d=await r.json();const added=d.results.reduce((n,x)=>n+(x.added||0),0);const failed=d.results.filter(x=>!x.ok).length;document.getElementById('toast').textContent=`Refresh complete: ${added} new paid leads. ${failed} feeds could not be reached. Results are filtered automatically.`;document.getElementById('toast').style.display='block';setTimeout(()=>document.getElementById('toast').style.display='none',6500);await load();await status();}catch(e){alert('Refresh failed. Please try again.')}finally{b.disabled=false;b.textContent='↻ Refresh projects'}};
load();status();setInterval(()=>{load();status()},120000);
