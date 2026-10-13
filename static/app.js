'use strict';
const $ = (id) => document.getElementById(id);
const N = 12;
let positions = [], history = [], page = 1, total = 0, search = '', activeSolution = null;
let busy = false, loadingFile = false, listRequest = 0, toastTimer, searchTimer, fileRequest = 0;
const key = ([x, y]) => `${x},${y}`;
const dateFormat = new Intl.DateTimeFormat('vi-VN', {day:'2-digit',month:'2-digit',year:'numeric'});
function evaluate(items) {
  const attacked = new Set(); let conflicts = 0;
  items.forEach(([x,y], i) => items.slice(i+1).forEach(([a,b], offset) => {
    if (x===a || y===b || Math.abs(x-a)===Math.abs(y-b)) {
      attacked.add(key(items[i])); attacked.add(key(items[i+offset+1])); conflicts++;
    }
  }));
  return {score:items.length-attacked.size, attacked, conflicts};
}
function toast(message, error=false) {
  clearTimeout(toastTimer); $('toast').textContent=message;
  $('toast').classList.toggle('error',error); $('toast').hidden=false;
  toastTimer=setTimeout(()=>$('toast').hidden=true, 5000);
}
async function api(url, options={}) {
  const response=await fetch(url, {cache:'no-store', ...options});
  let data;
  try {data=await response.json();} catch {throw new Error('Máy chủ chưa sẵn sàng. Vui lòng thử lại.');}
  if (!response.ok) throw new Error(data.error || 'Có lỗi xảy ra. Vui lòng thử lại.');
  return data;
}
function post(url, body) {return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
function makeBoard(container, items, interactive=false, mini=false) {
  const result=evaluate(items), occupied=new Set(items.map(key));
  const fragment=document.createDocumentFragment();
  for (let y=1;y<=N;y++) for(let x=1;x<=N;x++) {
    const cell=document.createElement(interactive?'button':'span');
    const coordinate=`${x},${y}`, hasQueen=occupied.has(coordinate), hit=result.attacked.has(coordinate);
    cell.className=mini?'mini-cell':'cell';
    if((x+y)%2) cell.classList.add('dark');
    if(hasQueen) cell.classList.add(mini?'queen':'occupied');
    if(hit && (!interactive || $('show-conflicts').checked)) cell.classList.add('attacked');
    if(hasQueen && !mini) cell.textContent='♛';
    if(interactive) {
      cell.type='button'; cell.dataset.x=x; cell.dataset.y=y;
      cell.setAttribute('aria-label',`Cột ${x}, hàng ${y}${hasQueen ? (hit?', hậu bị tấn công':', hậu an toàn'):', ô trống'}`);
      cell.setAttribute('aria-pressed',String(hasQueen));
      cell.tabIndex=x===1&&y===1?0:-1;
      cell.title=`(${x}, ${y})${hasQueen?(hit?' · Bị tấn công':' · An toàn'):''}`;
    }
    fragment.append(cell);
  }
  container.replaceChildren(fragment);
}
function render(focusCoordinate=null) {
  const result=evaluate(positions);
  makeBoard($('board'),positions,true);
  if(focusCoordinate) {
    const cell=$('board').querySelector(`[data-x="${focusCoordinate[0]}"][data-y="${focusCoordinate[1]}"]`);
    if(cell) { $('board').querySelector('[tabindex="0"]').tabIndex=-1; cell.tabIndex=0; cell.focus({preventScroll:true}); }
  }
  $('score').textContent=result.score; $('safe-count').textContent=result.score;
  $('placed').textContent=`${positions.length} / 12`; $('conflict-count').textContent=result.conflicts;
  $('progress').replaceChildren(...Array.from({length:12},(_,i)=>{
    const segment=document.createElement('span');if(i<result.score)segment.className='filled';return segment;
  }));
  $('score-message').textContent=!positions.length?'Mọi lời giải bắt đầu từ một quân hậu.':result.score===12?'Hoàn hảo! 12 quân hậu, không một xung đột.':result.conflicts?`${result.attacked.size} quân bị tấn công. Thử một vị trí khác nhé.`:`${result.score} quân an toàn. Tiếp tục tìm chỗ cho các quân còn lại.`;
  $('submit-hint').textContent=positions.length===12?'Sẵn sàng! Máy chủ sẽ kiểm tra điểm trước khi lưu.':`Đặt thêm ${12-positions.length} quân hậu để nộp bài.`;
  $('submit-button').disabled=positions.length!==12||busy||loadingFile;
  $('undo').disabled=!history.length||busy||loadingFile;
  $('clear').disabled=!positions.length||busy||loadingFile;
  $('download').disabled=!positions.length;
  $('file-input').disabled=busy||loadingFile;
  $('board').setAttribute('aria-label',`Bàn cờ 12 × 12. ${positions.length} quân, ${result.score} hậu an toàn. Dùng phím mũi tên để di chuyển, Enter hoặc Space để đặt hậu.`);
}
function update(next) {
  history.push(positions.map(p=>[...p])); if(history.length>100)history.shift();
  positions=next;render();
  try {localStorage.setItem('queens12-draft',JSON.stringify({positions,author:$('author').value,title:$('title').value}));} catch {}
}
$('board').addEventListener('click', event=>{
  const cell=event.target.closest('[data-x]');if(!cell||busy||loadingFile)return;
  const x=Number(cell.dataset.x),y=Number(cell.dataset.y);
  const exists=positions.some(p=>p[0]===x&&p[1]===y);
  if(!exists&&positions.length>=N){toast('Đã đủ 12 quân. Bỏ một quân trước khi đặt vị trí mới.',true);return;}
  update(exists?positions.filter(p=>p[0]!==x||p[1]!==y):[...positions,[x,y]]);render([x,y]);
});
$('board').addEventListener('keydown', event=>{
  const movement={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];
  if(!movement||!event.target.dataset.x)return;
  event.preventDefault();
  const x=Math.max(1,Math.min(N,Number(event.target.dataset.x)+movement[0]));
  const y=Math.max(1,Math.min(N,Number(event.target.dataset.y)+movement[1]));
  const next=$('board').querySelector(`[data-x="${x}"][data-y="${y}"]`);
  event.target.tabIndex=-1;next.tabIndex=0;next.focus();
});
$('undo').onclick=()=>{if(history.length){positions=history.pop();render();saveDraft();}};
$('clear').onclick=()=>{update([]);toast('Đã xóa bàn cờ. Bạn có thể hoàn tác bằng nút ↶.');};
$('show-conflicts').onchange=()=>render();
function saveDraft(){try{localStorage.setItem('queens12-draft',JSON.stringify({positions,author:$('author').value,title:$('title').value}));}catch{}}
$('author').oninput=saveDraft;$('title').oninput=saveDraft;
function download(items) {
  const text=[...items].sort((a,b)=>a[1]-b[1]||a[0]-b[0]).map(p=>p.join(' ')).join('\n')+'\n';
  const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='input.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('download').onclick=()=>download(positions);
function setMode(file) {
  $('upload-panel').hidden=!file;
  $('manual-tab').classList.toggle('active',!file);$('file-tab').classList.toggle('active',file);
  $('manual-tab').setAttribute('aria-pressed',String(!file));$('file-tab').setAttribute('aria-pressed',String(file));
}
$('manual-tab').onclick=()=>setMode(false);$('file-tab').onclick=()=>setMode(true);
async function importFile(file) {
  if(!file||busy||loadingFile)return;
  if(!file.name.toLowerCase().endsWith('.txt')){toast('Vui lòng chọn file .txt.',true);return;}
  if(file.size>4096){toast('File quá lớn. Giới hạn là 4 KB.',true);return;}
  const id=++fileRequest;loadingFile=true;render();
  try {
    const data=await post('/api/parse',{text:await file.text()});
    if(id!==fileRequest)return;
    update(data.positions);setMode(false);toast(`Đã nhập 12 quân hậu từ ${file.name}. Điểm: ${data.score}/12.`);
  } catch(error){toast(error.message,true);}
  finally{loadingFile=false;$('file-input').value='';render();}
}
$('file-input').onchange=event=>importFile(event.target.files[0]);
for(const type of ['dragover','dragenter'])$('upload-panel').addEventListener(type,event=>{event.preventDefault();$('upload-panel').classList.add('dragging');});
for(const type of ['dragleave','drop'])$('upload-panel').addEventListener(type,event=>{event.preventDefault();$('upload-panel').classList.remove('dragging');if(type==='drop')importFile(event.dataTransfer.files[0]);});
$('submit-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy||loadingFile||positions.length!==N)return;
  busy=true;render();$('submit-button').firstElementChild.textContent='Đang gửi…';
  try {
    const item=await post('/api/submissions',{author:$('author').value.trim(),title:$('title').value.trim(),positions});
    toast(`Đã đăng lời giải! Điểm được máy chủ xác nhận: ${item.score}/12.`);
    search='';page=1;$('search').value='';await loadLeaderboard();
    await openSolution(item.id);
  } catch(error){toast(error.message,true);}
  finally{busy=false;$('submit-button').firstElementChild.textContent='Nộp lời giải';render();}
});
function cell(text,className='') {const td=document.createElement('td');td.textContent=text;td.className=className;return td;}
function buildRow(item) {
  const tr=document.createElement('tr');
  tr.append(cell(String(item.rank).padStart(2,'0'),`rank-number${item.rank<=3?' top':''}`));
  const titleCell=cell(''),title=document.createElement('span'),author=document.createElement('span');
  title.className='entry-title';title.textContent=item.title;author.className='entry-author';author.textContent=`bởi ${item.author}`;titleCell.append(title,author);tr.append(titleCell);
  const previewCell=cell(''),preview=document.createElement('div');preview.className='mini-board';preview.setAttribute('role','img');preview.setAttribute('aria-label',`Bàn cờ ${item.title}`);makeBoard(preview,item.positions,false,true);previewCell.append(preview);tr.append(previewCell);
  const scoreCell=cell(''),badge=document.createElement('span');badge.className=`score-badge${item.score===12?' perfect':''}`;badge.textContent=`${item.score===12?'✦ ':''}${item.score} / 12`;scoreCell.append(badge);tr.append(scoreCell);
  tr.append(cell(dateFormat.format(new Date(item.created_at)),'row-date'));
  const actionCell=cell(''),button=document.createElement('button');button.className='view-button';button.textContent='Xem bàn cờ ↗';button.onclick=()=>openSolution(item.id);actionCell.append(button);tr.append(actionCell);return tr;
}
async function loadLeaderboard(quiet=false) {
  const current=++listRequest;
  if(!quiet){$('list-state').hidden=false;$('list-state').textContent='Đang tải bảng xếp hạng…';}
  try {
    const data=await api(`/api/submissions?page=${page}&q=${encodeURIComponent(search)}`);if(current!==listRequest)return;
    total=data.total;
    if(page>1&&(page-1)*12>=total){page=Math.max(1,Math.ceil(total/12));return loadLeaderboard();}
    $('leaderboard-body').replaceChildren(...data.items.map(buildRow));
    $('total-count').textContent=data.stats.total;$('perfect-count').textContent=data.stats.perfect;
    $('list-state').hidden=data.items.length>0;
    if(!data.items.length){const heading=document.createElement('strong');heading.textContent=search?'Chưa tìm thấy lời giải phù hợp.':'Bảng xếp hạng đang chờ bạn.';$('list-state').replaceChildren(heading,document.createTextNode(search?'Thử một tên người chơi hoặc tên lời giải khác.':'Hãy là người đầu tiên đặt đủ 12 quân và chia sẻ lời giải.'));}
    $('page-label').textContent=`${page} / ${Math.max(1,Math.ceil(total/12))}`;
    $('prev-page').disabled=page<=1;$('next-page').disabled=page*12>=total;
  } catch(error){if(current!==listRequest)return;$('list-state').hidden=false;$('list-state').textContent=`Không tải được bảng xếp hạng. ${error.message} Bấm ↻ để thử lại.`;}
}
$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{search=$('search').value.trim();page=1;loadLeaderboard();},300);};
$('refresh').onclick=()=>loadLeaderboard();$('prev-page').onclick=()=>{if(page>1){page--;loadLeaderboard();}};$('next-page').onclick=()=>{if(page*12<total){page++;loadLeaderboard();}};
async function openSolution(id) {
  try {
    const item=await api(`/api/submissions/${encodeURIComponent(id)}`);activeSolution=item;
    $('detail-rank').textContent=`LỜI GIẢI CỘNG ĐỒNG / HẠNG #${item.rank}`;
    $('detail-title').textContent=item.title;$('detail-author').textContent=`bởi ${item.author} · ${dateFormat.format(new Date(item.created_at))}`;
    $('detail-score').textContent=`${item.score} / 12 điểm`;$('detail-conflicts').textContent=`${item.conflicts} cặp tấn công`;
    makeBoard($('detail-board'),item.positions);$('detail-board').setAttribute('aria-label',`Bàn cờ của ${item.author}: ${item.score} điểm. Tọa độ được ghi bên dưới.`);
    $('detail-coordinates').textContent=`(x, y): ${item.positions.map(p=>`(${p.join(', ')})`).join(' · ')}`;
    if(!$('solution-dialog').open)$('solution-dialog').showModal();
    window.history.replaceState(null,'',`#solution=${item.id}`);
  } catch(error){toast(error.message,true);}
}
$('detail-copy').onclick=async()=>{try{await navigator.clipboard.writeText(`${location.origin}/#solution=${activeSolution.id}`);toast('Đã sao chép liên kết lời giải.');}catch{toast('Không thể sao chép tự động. Bạn có thể sao chép địa chỉ trên trình duyệt.',true);}};
$('detail-download').onclick=()=>{if(activeSolution)download(activeSolution.positions);};
$('solution-close').onclick=()=>$('solution-dialog').close();
$('solution-dialog').addEventListener('close',()=>{window.history.replaceState(null,'','#community');});
$('rules-open').onclick=()=>$('rules-dialog').showModal();$('rules-close').onclick=()=>$('rules-dialog').close();
for(const id of ['rules-dialog','solution-dialog'])$(id).addEventListener('click',e=>{if(e.target===$(id)){const r=$(id).getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$(id).close();}});
for(let i=1;i<=N;i++)for(const id of ['axis-x','axis-y']){const span=document.createElement('span');span.textContent=i;$(id).append(span);}
try {
  const draft=JSON.parse(localStorage.getItem('queens12-draft'));
  if(draft&&Array.isArray(draft.positions)&&draft.positions.length<=12&&draft.positions.every(p=>Array.isArray(p)&&p.length===2&&p.every(v=>Number.isInteger(v)&&v>=1&&v<=12))&&new Set(draft.positions.map(key)).size===draft.positions.length){positions=draft.positions;$('author').value=typeof draft.author==='string'?draft.author.slice(0,40):'';$('title').value=typeof draft.title==='string'?draft.title.slice(0,80):'';}
} catch {}
render();loadLeaderboard();
if(location.hash.startsWith('#solution='))openSolution(location.hash.slice(10));
window.addEventListener('hashchange',()=>{if(location.hash.startsWith('#solution='))openSolution(location.hash.slice(10));});
setInterval(()=>{if(!document.hidden)loadLeaderboard(true);},30000);
