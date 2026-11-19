// Shared helpers for every tab. Loaded first.
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ICONS = {
  home:'<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  pen:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  mic:'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  phone:'<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  book:'<path d="M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6"/><path d="M20 4v14h-6"/>',
  film:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
  folder:'<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  heart:'<path d="M12 21s-8-5-8-11a5 5 0 0 1 8-3 5 5 0 0 1 8 3c0 6-8 11-8 11z"/>',
  play:'<path d="M7 4l13 8-13 8z"/>',
};
const icon = n => `<svg viewBox="0 0 24 24">${ICONS[n]||""}</svg>`;

async function api(path, opts){
  const r = await fetch(path, opts);
  const j = await r.json().catch(()=>({}));
  if(!r.ok){ const e = new Error(j.error || ("Request failed ("+r.status+")")); e.help = j.help; throw e; }
  return j;
}
const post = (path, body) => api(path, {method:"POST", body:JSON.stringify(body||{})});
const upload = (kind, file) => api(`/api/upload?kind=${kind}&name=${encodeURIComponent(file.name)}`, {method:"POST", body:file});
// Friendly problem card: title, what happened, what to do, optional action button, copyable details.
function problemCard(h, fallback){
  const d = document.createElement("div"); d.className = "problem";
  if(!h){ d.innerHTML = `<b>Something went wrong</b><p></p>`; $("p", d).textContent = fallback || "Please try again."; return d; }
  d.innerHTML = `<b></b><p class="ex"></p><p class="fx"></p><div class="row act"></div>
    <details><summary>Technical details (for support)</summary><pre></pre><button type="button" class="small cp">Copy details</button></details>`;
  $("b", d).textContent = h.title; $(".ex", d).textContent = h.explain; $(".fx", d).textContent = h.fix;
  $("pre", d).textContent = h.details || "(none)";
  $(".cp", d).onclick = ()=>{ try{ navigator.clipboard.writeText(h.details||""); toast("Copied."); }catch(e){} };
  if(h.action && h.action.type==="install_lang"){
    const b = document.createElement("button"); b.className = "primary"; b.textContent = h.action.label;
    b.onclick = async ()=>{
      b.disabled = true; b.textContent = "Installing… please wait";
      try{
        const {id} = await post("/api/voice/install-language", {lang:h.action.lang});
        while(true){ await new Promise(r=>setTimeout(r,1500)); const j = await api("/api/job?id="+id);
          if(j.status==="done"){ toast("Installed. Try the voice again."); d.remove(); return; }
          if(j.status==="error"){ b.disabled=false; b.textContent=h.action.label; $(".fx",d).textContent = j.error; if(j.help) $("pre",d).textContent=j.help.details; return; } }
      }catch(e){ b.disabled=false; b.textContent=h.action.label; toast(e.message,true); }
    };
    $(".act", d).appendChild(b);
  }
  return d;
}
function showProblem(e){
  const dlg = document.createElement("dialog"); dlg.className = "problemdlg";
  dlg.appendChild(problemCard(e.help, e.message));
  const r = document.createElement("div"); r.className = "row"; const c = document.createElement("button"); c.textContent = "Close"; c.onclick = ()=>{dlg.close(); dlg.remove();}; r.appendChild(c); dlg.appendChild(r);
  document.body.appendChild(dlg); dlg.showModal();
}
async function confirmDelete(what){
  return new Promise(res=>{
    const dlg = document.createElement("dialog"); dlg.innerHTML = `<h3>Delete this?</h3><p class="note"></p><div class="row"><button class="danger yes">Yes, delete</button><button class="no">Keep it</button></div>`;
    $("p", dlg).textContent = what + " will be removed from this computer. This cannot be undone.";
    $(".yes", dlg).onclick = ()=>{dlg.close(); dlg.remove(); res(true);}; $(".no", dlg).onclick = ()=>{dlg.close(); dlg.remove(); res(false);};
    document.body.appendChild(dlg); dlg.showModal();
  });
}
async function deleteItem(kind, name, label){
  if(!(await confirmDelete(label || name))) return false;
  try{ await post("/api/delete", {kind, name}); toast("Deleted."); return true; }catch(e){ toast(e.message, true); return false; }
}
function toast(msg, err){
  const t = document.createElement("div"); t.className = "toast"+(err?" err":""); t.textContent = msg;
  $("#toasts").appendChild(t); setTimeout(()=>t.remove(), err?7000:3500);
}

// ---- app state (saved to the project on this computer)
const App = { caps:null, voices:[], styles:[], proj:{}, pages:{}, order:[] };
let _saveT;
function saveProj(){ clearTimeout(_saveT); _saveT = setTimeout(()=>post("/api/project", App.proj).catch(()=>{}), 400); }
const ps = (key, def) => (App.proj[key] = Object.assign({}, def, App.proj[key]||{}));   // per-tab saved settings
function defaultVoice(){ return (App.proj.voice && App.proj.voice.default) || "am_liam"; }

// ---- pages / navigation
function registerPage(id, {title, sub, icon:ic, build, onShow}){ App.pages[id] = {id,title,sub,ic,build,onShow}; App.order.push(id); }
function go(id){
  const pg = App.pages[id]; if(!pg) return;
  $$(".page").forEach(p=>p.classList.toggle("show", p.id==="page-"+id));
  $$("#nav .navbtn").forEach(b=>b.classList.toggle("active", b.dataset.id===id));
  $("#pageTitle").textContent = pg.title; $("#pageSub").textContent = pg.sub;
  if(location.hash !== "#"+id) history.replaceState(null,"","#"+id);
  pg.onShow && pg.onShow();
}

// ---- voices: choose a voice and listen first
function voiceOptions(sel, current){
  const groups = {};
  App.voices.forEach(v => (groups[v.group] = groups[v.group] || []).push(v));
  sel.innerHTML = Object.entries(groups).map(([g,list]) =>
    `<optgroup label="${esc(g)}">${list.map(v=>`<option value="${v.id}">${esc(v.name)} (${v.id})</option>`).join("")}</optgroup>`).join("");
  sel.value = current || defaultVoice();
  if(sel.value !== (current || defaultVoice())) sel.value = "am_liam";
}
const voiceAudio = () => $("#voiceAudio");
let _playingBtn = null;
async function listen(voiceId, btn, text){
  const au = voiceAudio();
  if(_playingBtn === btn && !au.paused){ au.pause(); return; }
  if(_playingBtn){ _playingBtn.classList.remove("on","busy"); _playingBtn.textContent = "▶ Listen"; }
  _playingBtn = btn; btn.classList.add("busy"); btn.textContent = "Loading…";
  try{
    const r = await post("/api/voice/sample", {voice:voiceId, text:text||""});
    au.src = r.url + "?t=" + Date.now(); await au.play();
    btn.classList.remove("busy"); btn.classList.add("on"); btn.textContent = "■ Stop";
    au.onended = au.onpause = ()=>{ btn.classList.remove("on"); btn.textContent = "▶ Listen"; };
  }catch(e){ btn.classList.remove("busy","on"); btn.textContent = "▶ Listen"; if(e.help) showProblem(e); else toast(e.message, true); }
}
// Adds a voice dropdown + Listen button into a container; returns {get(), set(v)}
function voicePicker(mount, key){
  mount.innerHTML = `<div class="row" style="margin-top:0"><select class="grow"></select><button class="play" type="button">▶ Listen</button></div>`;
  const sel = $("select", mount), btn = $(".play", mount);
  const st = ps(key, {voice:defaultVoice()});
  voiceOptions(sel, st.voice);
  sel.onchange = ()=>{ st.voice = sel.value; saveProj(); };
  btn.onclick = ()=>listen(sel.value, btn);
  return { get:()=>sel.value, set:v=>{ sel.value=v; st.voice=v; } };
}

// ---- progress panel for any job (voice + video)
class JobPanel{
  constructor(mount){
    mount.innerHTML = `<div class="card hidden"><h2>Result</h2><div class="bar"><i></i></div><div class="note state">Starting…</div>
      <div class="pslot"></div><pre class="log hidden"></pre><video controls class="hidden"></video>
      <div class="row hidden save"><a class="btn dl">Download MP4</a><span class="note">Also saved in your Whiteboard Wave Studio folder.</span></div></div>`;
    this.box = $(".card", mount); this.bar = $(".bar i", mount); this.state = $(".state", mount);
    this.pslot = $(".pslot", mount); this.log = $(".log", mount); this.video = $("video", mount); this.save = $(".save", mount); this.dl = $(".dl", mount);
  }
  async run(path, body){
    this.pslot.innerHTML = ""; const b = this.box; b.classList.remove("hidden"); this.video.classList.add("hidden"); this.save.classList.add("hidden");
    this.log.classList.remove("hidden"); this.log.textContent = ""; this.bar.style.width = "3%"; this.state.textContent = "Working… this can take a few minutes.";
    let id;
    try{ ({id} = await post(path, body)); }catch(e){ this.state.textContent = ""; this.pslot.appendChild(problemCard(e.help, e.message)); this.log.classList.add("hidden"); return null; }
    while(true){
      await new Promise(r=>setTimeout(r,1200));
      let j; try{ j = await api("/api/job?id="+id); }catch(e){ this.state.textContent = e.message; return null; }
      this.bar.style.width = Math.max(3, Math.round(100*j.done/j.total))+"%";
      this.log.textContent = j.log.join("\n"); this.log.scrollTop = this.log.scrollHeight;
      if(j.status==="done"){
        this.bar.style.width = "100%"; this.state.textContent = "Done! Your video is ready.";
        const url = "/files/out/"+encodeURIComponent(j.output)+"?t="+Date.now();
        this.video.src = url; this.video.classList.remove("hidden");
        this.dl.href = url; this.dl.download = j.output; this.save.classList.remove("hidden");
        return j.output;
      }
      if(j.status==="error"){ this.state.textContent = ""; this.pslot.appendChild(problemCard(j.help, j.error)); this.log.classList.add("hidden"); return null; }
    }
  }
}

// ---- reusable list of scenes (image + words + voice mode). Used by Video and Manhwa.
function sceneEditor({mount, key, noun, extra}){
  const st = ps(key, {scenes:[]});
  const box = document.createElement("div"); mount.appendChild(box);
  const drop = document.createElement("div"); drop.className = "empty";
  drop.innerHTML = `<div style="font-size:16px;color:var(--ink);font-weight:600">Add your ${noun} images</div>
    <div class="note" style="margin:6px 0 12px">Drop PNG or JPG images here, or choose them. One image = one ${noun}.</div>
    <button class="primary" type="button">Choose images</button><input type="file" accept=".png,.jpg,.jpeg" multiple hidden>`;
  mount.appendChild(drop);
  const input = $("input", drop); $("button", drop).onclick = ()=>input.click();
  const api_ = { get scenes(){ return st.scenes; }, render, validate(){ return check(); } };
  async function add(files){
    for(const f of files){
      try{ const r = await upload("image", f); st.scenes.push(Object.assign({image:r.name,text:"",audio_mode:"none",audio:""}, extra?extra.defaults:{})); }
      catch(e){ toast(f.name+": "+e.message, true); }
    }
    render(); saveProj();
  }
  input.onchange = e=>{ add([...e.target.files]); e.target.value=""; };
  ["dragenter","dragover"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add("drag")}));
  ["dragleave","drop"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove("drag")}));
  drop.addEventListener("drop", e=>add([...e.dataTransfer.files].filter(f=>/\.(png|jpe?g)$/i.test(f.name))));
  function check(){
    const sc = st.scenes, modes = new Set(sc.map(s=>s.audio_mode)); const kokoro = App.caps && App.caps.kokoro;
    if(!sc.length) return `Add at least one ${noun} image.`;
    if(modes.has("none") && modes.size>1) return `Some ${noun}s have a voice and some do not. Give every ${noun} a voice, or none.`;
    if(sc.some(s=>s.audio_mode==="upload" && !s.audio)) return "Choose an audio file for every one set to “my own recording”.";
    if(sc.some(s=>s.audio_mode==="generate" && !(s.text||"").trim())) return "Type the words for every one set to “Make voice”.";
    if(sc.some(s=>s.audio_mode==="generate") && App.caps && !kokoro) return "Kokoro voice is not installed. Use your own recordings, or choose no voice.";
    return "";
  }
  function render(){
    box.innerHTML = st.scenes.map((s,i)=>`
      <div class="card scene" data-i="${i}">
        <div><div class="thumb" style="background-image:url('/files/images/${encodeURIComponent(s.image)}')"></div>
          <div class="row"><button class="small" data-act="up" ${i==0?'disabled':''}>↑</button><button class="small" data-act="down" ${i==st.scenes.length-1?'disabled':''}>↓</button><button class="small ghost" data-act="del">Remove</button></div></div>
        <div><div class="snum">${noun[0].toUpperCase()+noun.slice(1)} ${i+1}</div>
          <label style="margin-top:0">Words spoken here</label>
          <textarea data-f="text" placeholder="Type the words for this ${noun}…">${esc(s.text||"")}</textarea>
          <label>Voice</label>
          <select data-f="audio_mode"><option value="none" ${s.audio_mode=='none'?'selected':''}>No voice</option>
            <option value="generate" ${s.audio_mode=='generate'?'selected':''}>Make voice from the words (Kokoro)</option>
            <option value="upload" ${s.audio_mode=='upload'?'selected':''}>Use my own recording</option></select>
          ${s.audio_mode=='upload' ? `<div class="row"><button class="small" data-act="audio">${s.audio?'Replace audio':'Choose audio file'}</button><span class="note">${esc(s.audio||'No file yet')}</span><input type="file" accept=".wav,.mp3,.m4a,.ogg,.flac" hidden data-aud></div>` : ''}
          ${extra ? extra.render(s,i) : ""}
        </div></div>`).join("");
    box.dispatchEvent(new CustomEvent("changed"));
  }
  box.addEventListener("click", e=>{
    const b = e.target.closest("button"); if(!b || !b.dataset.act) return;
    const i = +b.closest(".scene").dataset.i, a = b.dataset.act;
    if(a==="del") st.scenes.splice(i,1);
    else if(a==="up") [st.scenes[i-1],st.scenes[i]]=[st.scenes[i],st.scenes[i-1]];
    else if(a==="down") [st.scenes[i+1],st.scenes[i]]=[st.scenes[i],st.scenes[i+1]];
    else if(a==="audio"){ b.closest(".scene").querySelector("[data-aud]").click(); return; }
    render(); saveProj();
  });
  box.addEventListener("input", e=>{
    const el = e.target, sc = el.closest(".scene"); if(!sc) return;
    if(el.dataset.f==="text"){ st.scenes[+sc.dataset.i].text = el.value; box.dispatchEvent(new CustomEvent("changed")); saveProj(); }
  });
  box.addEventListener("change", async e=>{
    const el = e.target, sc = el.closest(".scene"); if(!sc) return; const i = +sc.dataset.i;
    if(el.dataset.f==="audio_mode"){ st.scenes[i].audio_mode = el.value; render(); saveProj(); }
    else if(el.dataset.f && el.dataset.f!=="text"){ st.scenes[i][el.dataset.f] = el.value; saveProj(); }
    if(el.hasAttribute("data-aud") && el.files[0]){
      try{ st.scenes[i].audio = (await upload("audio", el.files[0])).name; }catch(err){ toast(err.message,true); }
      render(); saveProj();
    }
  });
  render();
  return Object.assign(api_, {box});
}
