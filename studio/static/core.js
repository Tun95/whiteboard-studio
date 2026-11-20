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
  speaker:'<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
  doc:'<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
};
const icon = n => `<svg viewBox="0 0 24 24">${ICONS[n]||""}</svg>`;

async function api(path, opts){
  const r = await fetch(path, opts);
  const j = await r.json().catch(()=>({}));
  if(!r.ok){ const e = new Error(j.error || ("Request failed ("+r.status+")")); e.info = j.info || null; e.data = j; throw e; }
  return j;
}
const post = (path, body) => api(path, {method:"POST", body:JSON.stringify(body||{})});
const upload = (kind, file) => api(`/api/upload?kind=${kind}&name=${encodeURIComponent(file.name)}`, {method:"POST", body:file});
function toast(msg, err){
  const t = document.createElement("div"); t.className = "toast"+(err?" err":""); t.textContent = msg;
  $("#toasts").appendChild(t); setTimeout(()=>t.remove(), err?7000:3500);
}

// ---- friendly problem card (used by every tab) ----
function problemHTML(info){
  info = info || {};
  const act = info.action && info.action.type === "install_lang" ? `<button class="primary" data-pa="install">${esc(info.action.label)}</button>` : "";
  return `<div class="problem"><div class="ptitle">${esc(info.title || "Something went wrong")}</div>
    <p>${esc(info.what || "")}</p>${info.fix ? `<p class="pfix"><b>What to do:</b> ${esc(info.fix)}</p>` : ""}
    <div class="row">${act}${info.details ? `<button class="small" data-pa="copy" type="button">Copy details</button>` : ""}</div>
    <div class="pinst note hidden"></div>
    ${info.details ? `<details><summary>Technical details (for the developer)</summary><pre class="log">${esc(info.details)}</pre></details>` : ""}</div>`;
}
function wireProblem(root, info, onFixed){
  root.onclick = async e => {
    const b = e.target.closest("button[data-pa]"); if(!b) return;
    if(b.dataset.pa === "copy"){
      try{ await navigator.clipboard.writeText(info.details || ""); toast("Copied. You can paste it into a message."); }
      catch(_){ toast("Could not copy. Select the text and copy it by hand.", true); }
    }
    if(b.dataset.pa === "install"){
      const box = $(".pinst", root); b.disabled = true; box.classList.remove("hidden"); box.textContent = "Installing… please keep this window open.";
      try{
        let id;
        try{ ({id} = await post("/api/voice/install", {lang: info.action.lang, part: info.action.part || ""})); }
        catch(err){ if(err.data && err.data.running_id){ id = err.data.running_id; box.textContent = "Something else is still installing. Showing its progress…"; } else throw err; }
        while(true){
          await new Promise(r => setTimeout(r, 1500));
          const j = await api("/api/job?id=" + id);
          box.textContent = "Installing… " + (j.log.filter(l => !l.startsWith("$")).slice(-1)[0] || "");
          if(j.status === "done"){ box.textContent = "Installed. You can try again now."; toast("Installed. Try the voice again."); const st = await api("/api/state").catch(()=>null); if(st && st.caps){ App.caps = st.caps; chips && chips(); } onFixed && onFixed(); break; }
          if(j.status === "error"){ root.innerHTML = problemHTML(j.error_info || {title:"Install failed", what:j.error}); wireProblem(root, j.error_info || {}, onFixed); break; }
        }
      }catch(err){ b.disabled = false; box.textContent = err.message; }
    }
  };
}
function showProblem(info){
  let d = $("#problemDlg");
  if(!d){ d = document.createElement("dialog"); d.id = "problemDlg"; d.className = "wide"; document.body.appendChild(d); }
  d.innerHTML = `<div id="problemBody"></div><div class="row" style="justify-content:flex-end"><button id="problemClose" type="button">Close</button></div>`;
  $("#problemBody", d).innerHTML = problemHTML(info); wireProblem($("#problemBody", d), info);
  $("#problemClose", d).onclick = () => d.close(); if(!d.open) d.showModal();
}
function reportError(e){ if(e && e.info) showProblem(e.info); else toast(e && e.message ? e.message : String(e), true); }
function confirmBox(title, text, okLabel){
  return new Promise(res => {
    const d = document.createElement("dialog"); document.body.appendChild(d);
    d.innerHTML = `<h3>${esc(title)}</h3><p class="note">${esc(text)}</p><div class="row" style="justify-content:flex-end"><button data-r="0" type="button">Cancel</button><button class="danger" data-r="1" type="button">${esc(okLabel || "Delete")}</button></div>`;
    d.onclick = e => { const b = e.target.closest("button"); if(b){ d.close(); res(b.dataset.r === "1"); } };
    d.oncancel = () => res(false); d.onclose = () => d.remove(); d.showModal();
  });
}
// Deletes one file after asking, and tidies anything in the app that pointed at it.
async function deleteMedia(folder, name){
  if(!await confirmBox("Delete this file?", `“${name}” will be removed from your computer. This cannot be undone.`)) return false;
  try{ await post("/api/delete", {folder, name}); }catch(e){ reportError(e); return false; }
  const clean = (list, test) => { for(let i = list.length - 1; i >= 0; i--) if(test(list[i])) list.splice(i, 1); };
  if(folder === "images") ["videoScenes","manhwaScenes"].forEach(k => App.proj[k] && clean(App.proj[k].scenes, s => s.image === name));
  if(folder === "audio") ["videoScenes","manhwaScenes"].forEach(k => App.proj[k] && App.proj[k].scenes.forEach(s => { if(s.audio === name){ s.audio = ""; } }));
  const ed = App.proj.editor; if(ed){ clean(ed.clips, c => c.file === name); clean(ed.tracks, t => t.file === name); if(ed.overlays) clean(ed.overlays, o => o.file === name); ed.selK = ""; }
  saveProj(); document.dispatchEvent(new Event("mediachanged")); toast("Deleted " + name); return true;
}

// ---- app state (saved to the project on this computer)
const App = { caps:null, voices:[], styles:[], proj:{}, pages:{}, order:[] };
let _saveT;
let _dirty = false;
function saveState(t, bad){ const e = $("#saveState"); if(!e) return; e.textContent = t; e.className = "savestate" + (bad ? " bad" : ""); }
function saveProj(){ clearTimeout(_saveT); _dirty = true; saveState("Saving…");
  _saveT = setTimeout(()=>post("/api/project", App.proj).then(()=>{ _dirty = false; saveState("✓ Saved automatically"); }).catch(()=>saveState("Could not save. Is the app still running?", true)), 400); }
// Saves right away when the page is closed or refreshed, so nothing typed in the last moment is lost.
function saveNow(){ if(!_dirty) return; clearTimeout(_saveT); try{ navigator.sendBeacon("/api/project", new Blob([JSON.stringify(App.proj)], {type:"application/json"})); _dirty = false; }catch(_){} }
addEventListener("pagehide", saveNow); document.addEventListener("visibilitychange", ()=>{ if(document.visibilityState === "hidden") saveNow(); });
// Per-tab saved settings. Always hands back the SAME object, so everything that holds it keeps saving (a fresh copy each time made edits get lost).
const ps = (key, def) => { const o = App.proj[key] || (App.proj[key] = {}); for(const k in def) if(!(k in o)) o[k] = def[k]; return o; };   // per-tab saved settings
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
    `<optgroup label="${esc(g)}">${list.map(v=>`<option value="${v.id}">${esc(v.name)}</option>`).join("")}</optgroup>`).join("");
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
  }catch(e){ btn.classList.remove("busy","on"); btn.textContent = "▶ Listen"; reportError(e); }
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
      <div class="perr hidden"></div><pre class="log hidden"></pre><video controls class="hidden"></video>
      <div class="row hidden save"><a class="btn dl">Download MP4</a><span class="note">Also saved in your Whiteboard Wave Studio folder.</span></div></div>`;
    this.box = $(".card", mount); this.bar = $(".bar i", mount); this.state = $(".state", mount);
    this.perr = $(".perr", mount); this.log = $(".log", mount); this.video = $("video", mount); this.save = $(".save", mount); this.dl = $(".dl", mount);
  }
  fail(info){ this.perr.innerHTML = problemHTML(info); wireProblem(this.perr, info); this.perr.classList.remove("hidden"); }
  async run(path, body){
    const b = this.box; this.perr.classList.add("hidden"); b.classList.remove("hidden"); this.video.classList.add("hidden"); this.save.classList.add("hidden");
    this.log.classList.remove("hidden"); this.log.textContent = ""; this.bar.style.width = "3%"; this.state.textContent = "Working… this can take a few minutes.";
    let id;
    try{ ({id} = await post(path, body)); }catch(e){ this.state.textContent = ""; this.log.classList.add("hidden"); this.fail(e.info || {title:"Could not start", what:e.message}); return null; }
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
      if(j.status==="error"){ this.state.textContent = ""; this.bar.style.width = "0%"; this.log.classList.add("hidden"); this.fail(j.error_info || {title:"Something went wrong", what:j.error}); return null; }
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
            <option value="generate" ${s.audio_mode=='generate'?'selected':''}>Make an AI voice from the words</option>
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
  document.addEventListener("mediachanged", render);
  render();
  return Object.assign(api_, {box});
}


// Runs a background job and calls ui.onTick(job) while it works. Resolves with the finished job, throws a friendly error otherwise.
// If another job is still running, it follows that one instead of failing.
async function runJob(path, body, ui){
  ui = ui || {}; let id;
  try{ ({id} = await post(path, body)); }
  catch(e){ if(e.data && e.data.running_id){ id = e.data.running_id; ui.onNote && ui.onNote(e.message); } else throw e; }
  while(true){
    await new Promise(r => setTimeout(r, 1000));
    const j = await api("/api/job?id=" + id);
    ui.onTick && ui.onTick(j);
    if(j.status === "done") return j;
    if(j.status === "error"){ const err = new Error(j.error || "Something went wrong"); err.info = j.error_info; throw err; }
  }
}
const lastLine = j => ((j.log || []).filter(l => !l.startsWith("$")).slice(-1)[0] || "").slice(0, 110);

// ---- projects (like folders in a video editor: each keeps its own files)
async function flushProject(){ clearTimeout(_saveT); try{ await post("/api/project", App.proj); }catch(_){} }
async function projectAction(path, body){
  await flushProject();
  const r = await post(path, body); return r;
}
function initProjects(name){
  $("#projName").textContent = name;
  const dlg = $("#projDlg"), list = $("#projList");
  const when = t => { const d = new Date(t*1000); return d.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"}); };
  async function render(){
    const r = await api("/api/projects");
    $("#projWhere").textContent = "· " + r.folder; if(!$("#projPath").value) $("#projPath").value = r.folder;
    list.innerHTML = r.projects.map(p=>`<div class="pack ${p.name===r.active?'sel':''}" data-n="${esc(p.name)}">
      <div style="flex:1;min-width:0"><b>${esc(p.name)}</b>${p.name===r.active?' <span class="tag">open now</span>':''}
        <div class="note">${p.videos} video${p.videos===1?'':'s'} made · ${p.files} file${p.files===1?'':'s'} · ${p.ads} ad${p.ads===1?'':'s'} · changed ${when(p.modified)}</div></div>
      ${p.name===r.active?'':`<button class="primary small" data-open="${esc(p.name)}" type="button">Open</button>`}
      <button class="small" data-ren="${esc(p.name)}" type="button">Rename</button>
      ${p.name===r.active?'':`<button class="small del" data-delp="${esc(p.name)}" type="button">Delete</button>`}</div>`).join("");
  }
  const reopen = () => { location.hash = location.hash || "#home"; location.reload(); };
  $("#projBtn").onclick = async ()=>{ await render(); dlg.showModal(); };
  $("#projClose").onclick = ()=>dlg.close();
  $("#projBrowse").onclick = async ()=>{ try{ const r = await api("/api/pick-folder"); if(r.path) $("#projPath").value = r.path.replace(/\//g,"\\"); }catch(e){ toast(e.message, true); } };
  $("#projUse").onclick = async ()=>{ const path = $("#projPath").value.trim(); if(!path){ toast("Please choose a folder.", true); return; }
    try{ await flushProject(); const r = await post("/api/projects/folder", {path, move:$("#projMove").checked}); toast("Your projects are now saved in "+r.folder); location.reload(); }catch(e){ reportError(e); } };
  $("#projAdd").onclick = async ()=>{ const n = $("#projNew").value.trim();
    if(!n){ toast("Please type a name for the project.", true); return; }
    try{ await projectAction("/api/projects/create", {name:n}); reopen(); }catch(e){ reportError(e); } };
  $("#projNew").onkeydown = e=>{ if(e.key==="Enter") $("#projAdd").click(); };
  list.onclick = async e=>{
    const o = e.target.closest("[data-open]"), rn = e.target.closest("[data-ren]"), dl = e.target.closest("[data-delp]");
    try{
      if(o){ await projectAction("/api/projects/switch", {name:o.dataset.open}); reopen(); }
      else if(rn){ const v = await askName("Rename project", rn.dataset.ren); if(v && v!==rn.dataset.ren){ await projectAction("/api/projects/rename", {name:rn.dataset.ren, new:v}); const a = await api("/api/projects"); $("#projName").textContent = a.active; await render(); toast("Renamed."); } }
      else if(dl){ const n = dl.dataset.delp;
        if(await confirmBox("Delete this project?", `“${n}” and every picture, video, audio file and ad inside it will be removed from your computer. This cannot be undone.`, "Delete project")){
          await post("/api/projects/delete", {name:n}); await render(); toast("Deleted "+n); } }
    }catch(err){ reportError(err); } };
}
function askName(title, cur){
  return new Promise(res=>{
    const d = document.createElement("dialog"); document.body.appendChild(d);
    d.innerHTML = `<h3>${esc(title)}</h3><input type="text" maxlength="60" value="${esc(cur||"")}" style="margin:8px 0"><div class="row" style="justify-content:flex-end"><button data-r="0" type="button">Cancel</button><button class="primary" data-r="1" type="button">Save</button></div>`;
    const inp = d.querySelector("input"); const done = v => { d.close(); res(v); };
    d.onclick = e=>{ const b = e.target.closest("button"); if(b) done(b.dataset.r==="1" ? inp.value.trim() : null); };
    inp.onkeydown = e=>{ if(e.key==="Enter") done(inp.value.trim()); };
    d.oncancel = ()=>res(null); d.onclose = ()=>d.remove(); d.showModal(); inp.focus(); inp.select();
  });
}
