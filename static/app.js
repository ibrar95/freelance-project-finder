const cards=document.getElementById('cards'), total=document.getElementById('total'), last=document.getElementById('last'), count=document.getElementById('count');
const sourceHealth=document.getElementById('sourceHealth');
const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function niceDate(s){if(!s)return 'Date not provided';let d=new Date(s);return isNaN(d)?s:d.toLocaleString();}
function ageLabel(s){if(!s)return 'Date unavailable';const d=new Date(s);if(isNaN(d))return 'Date unavailable';const h=Math.max(0,Math.floor((Date.now()-d.getTime())/3600000));return h<1?'Posted less than 1 hour ago':h<24?`Posted ${h}h ago`:`Posted ${Math.floor(h/24)}d ago`; }
async function load(){
 const q=document.getElementById('search').value, category=document.getElementById('category').value;
 const res=await fetch('/api/projects?q='+encodeURIComponent(q)+'&category='+encodeURIComponent(category));
 const data=await res.json(); total.textContent=data.total; count.textContent=`${data.projects.length} paid project leads`;
 if(!data.projects.length){cards.innerHTML='<div class="empty">No matching paid project leads found yet. Try Refresh or a different skill keyword. Only posts with payment clues, project-request wording and a publication date within the last 72 hours are shown. Listing availability must still be checked at source.</div>';return;}
 cards.innerHTML=data.projects.map(p=>`<article class="project"><div class="projecttop"><span class="tag">${esc(p.category)}</span><span class="source">${esc(p.source)}</span></div><h3>${esc(p.title)}</h3><p class="desc">${esc(p.description||'No description supplied. Open the original post for details.')}</p><div class="paidline"><span class="paidtag">${p.status==='budget_confirmed'?'Budget/payment amount detected':'Paid intent · budget to confirm'}</span><span class="budget">${esc(p.budget||'Payment mentioned; verify amount')}</span></div><div class="projectbottom"><span class="date">${esc(ageLabel(p.published))} · ${esc(niceDate(p.published))}</span><a class="open" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">View original post ↗</a></div></article>`).join('');
}
async function status(){
 const r=await fetch('/api/status');const d=await r.json();total.textContent=d.total;last.textContent=d.last_refresh?niceDate(d.last_refresh):'Not yet';
 if(sourceHealth && d.source_runs){
  const runs=d.source_runs;
  sourceHealth.innerHTML=runs.length?runs.map(x=>`<div class="healthrow"><span>${esc(x.source)}</span><span class="healthstate ${x.ok?'ok':'bad'}">${x.ok?'OK':'Error'}</span><small>${x.ok?`${x.checked} checked · ${x.accepted||0} matched · ${x.added} new`  : esc(x.error||'Feed unavailable')}</small></div>`).join(''):'<p class="healthnote">No source check recorded yet. Press Refresh projects to run the feeds.</p>';
 }
}
document.getElementById('searchBtn').onclick=load;document.getElementById('category').onchange=load;
document.getElementById('search').addEventListener('keydown',e=>{if(e.key==='Enter')load()});
document.getElementById('refresh').onclick=async()=>{const b=document.getElementById('refresh');b.disabled=true;b.textContent='Refreshing…';try{const r=await fetch('/api/refresh',{method:'POST'});const d=await r.json();const added=d.results.reduce((n,x)=>n+(x.added||0),0);const failed=d.results.filter(x=>!x.ok).length;document.getElementById('toast').textContent=`Refresh complete: ${added} new client-side leads. ${failed} feeds could not be reached. Check Source health below for per-feed results.`;document.getElementById('toast').style.display='block';setTimeout(()=>document.getElementById('toast').style.display='none',6500);await load();await status();}catch(e){alert('Refresh failed. Please try again.')}finally{b.disabled=false;b.textContent='↻ Refresh projects'}};
load();status();setInterval(()=>{load();status()},120000);
