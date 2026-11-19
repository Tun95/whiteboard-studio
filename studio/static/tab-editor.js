registerPage("editor", {title:"Editor", sub:"Cut, arrange and polish your videos. Everything you change plays in the preview straight away.", icon:"film", build(el){
  el.innerHTML = `
  <div class="ed" id="edRoot">
    <div class="ed-bar">
      <div class="grp"><button id="edUndo" title="Undo the last change (Ctrl+Z)" type="button">↶ Undo</button><button id="edRedo" title="Redo (Ctrl+Y)" type="button">↷ Redo</button></div>
      <div class="grp"><button id="edSplit" title="Cut the clip under the playhead into two (S)" type="button">✂ Cut here</button><button id="edDelete" title="Remove the selected item (Delete key)" type="button">🗑 Remove</button></div>
      <div class="grp"><button id="edAddText" title="Put a title or caption on the video at the playhead" type="button">T Add text</button><button id="edAddAudio" title="Add music or a voice recording" type="button">♪ Add music or voice</button></div>
      <div class="grp right"><button id="edZoomOut" title="Zoom the timeline out (-)" type="button">−</button><span class="note">Zoom</span><button id="edZoomIn" title="Zoom the timeline in (+)" type="button">+</button><button id="edFit" title="Fit the whole video on screen" type="button">Fit</button>
        <button class="primary" id="edExportBtn" type="button">Export video</button></div>
    </div>
    <div class="ed-top">
      <section class="ed-pool">
        <div class="ed-tabs"><button class="on" data-pt="v" type="button">Videos</button><button data-pt="a" type="button">Audio</button></div>
        <div class="row" style="margin:6px 0"><button class="small" id="eUpVideo" type="button">Upload video</button><button class="small" id="eUpAudio" type="button">Upload audio</button>
          <input type="file" id="eFileV" accept=".mp4,.mov,.mkv,.webm" hidden><input type="file" id="eFileA" accept=".wav,.mp3,.m4a,.ogg,.flac" hidden></div>
        <div class="ed-list" id="edPool"></div>
      </section>
      <section class="ed-view">
        <div class="ed-stage" id="edStage"><div class="ed-frame" id="edFrame">
          <video id="edV0" playsinline preload="auto"></video><video id="edV1" playsinline preload="auto"></video>
          <div class="ed-texts" id="edTexts"></div><div class="ed-fade" id="edFade"></div>
          <div class="ed-empty" id="edEmpty"><b>Start here</b><span>1. Pick a video on the left and press “+ Add”.<br>2. Add text or music with the buttons on top.<br>3. Press Play to see everything together.</span></div>
        </div></div>
        <div class="ed-transport">
          <button id="edPlay" class="primary" title="Play or pause (Space)" type="button">▶ Play</button>
          <button id="edStart" title="Go to the start" type="button">⏮</button><button id="edBack" title="Back 1 second (←)" type="button">−1s</button><button id="edFwd" title="Forward 1 second (→)" type="button">+1s</button>
          <span class="ed-time" id="edTime">0:00.0 / 0:00.0</span>
          <label class="ed-mute"><input type="checkbox" id="edMute"> Mute preview</label>
        </div>
      </section>
      <section class="ed-insp" id="edInsp"></section>
    </div>
    <section class="ed-tl"><div class="tl-scroll" id="tlScroll"><div class="tl-inner" id="tlInner"></div></div></section>
  </div>
  <dialog id="edExport" class="wide"><h3>Export your video</h3>
    <label style="margin-top:0">Name</label><input type="text" id="eName">
    <label>Video shape</label><select id="eSize"><option value="1920x1080">Wide 1920x1080 (YouTube)</option><option value="1280x720">Wide 1280x720 (smaller file)</option><option value="1080x1920">Tall 1080x1920 (Shorts, Reels, TikTok)</option></select>
    <div class="two"><div><label>Fade in at the start (seconds)</label><input type="number" id="eFi" min="0" step="0.1"></div><div><label>Fade out at the end (seconds)</label><input type="number" id="eFo" min="0" step="0.1"></div></div>
    <div class="note" id="eTotal" style="margin-top:8px"></div><div class="warn hidden" id="eProblem"></div>
    <div id="eJob"></div>
    <div class="row" style="justify-content:flex-end;margin-top:10px"><button id="eClose" type="button">Close</button><button class="primary" id="eMake" type="button">Export video</button></div></dialog>`;

  // ---------------------------------------------------------------- state
  const st = ps("editor", {clips:[], texts:[], tracks:[], fade_in:0, fade_out:0, size:"1920x1080", name:"edited-video", zoom:80, selK:"", selI:0});
  let lib = {videos:[], uploads:[], audio:[]}, poolTab = "v";
  const job = new JobPanel($("#eJob",el));
  const fmt = n => (Math.round(n*10)/10).toString();
  const r1 = n => Math.round(n*10)/10;
  const enc = encodeURIComponent;
  const clamp = (v,a,b) => Math.min(b, Math.max(a, v));
  const clipLen = c => Math.max(0, (c.end - c.start) / (c.speed||1));
  const clipUrl = c => "/files/" + (c.folder||"out") + "/" + enc(c.file);
  const mmss = t => { t = Math.max(0,t); const m = Math.floor(t/60), s = t - m*60; return m + ":" + (s<10?"0":"") + s.toFixed(1); };
  const isShown = () => el.classList.contains("show");

  // ---------------------------------------------------------------- undo / redo
  const undoS = [], redoS = [];
  const snapshot = () => JSON.stringify({clips:st.clips, texts:st.texts, tracks:st.tracks, fade_in:st.fade_in, fade_out:st.fade_out, size:st.size});
  function snap(){ undoS.push(snapshot()); if(undoS.length>80) undoS.shift(); redoS.length = 0; btns(); }
  function restore(js){ Object.assign(st, JSON.parse(js)); st.selK=""; layoutAll(); renderInsp(); saveProj(); }
  function undo(){ if(!undoS.length) return; redoS.push(snapshot()); restore(undoS.pop()); btns(); }
  function redo(){ if(!redoS.length) return; undoS.push(snapshot()); restore(redoS.pop()); btns(); }
  function btns(){ $("#edUndo",el).disabled = !undoS.length; $("#edRedo",el).disabled = !redoS.length; }

  // ---------------------------------------------------------------- selection
  const selItem = () => st.selK==="clip" ? st.clips[st.selI] : st.selK==="text" ? st.texts[st.selI] : st.selK==="track" ? st.tracks[st.selI] : null;
  function select(k, i){ st.selK = k||""; st.selI = i||0; renderTimeline(); renderInsp(); }

  // ---------------------------------------------------------------- player (live preview)
  const frame = $("#edFrame",el), stage = $("#edStage",el), vids = [$("#edV0",el), $("#edV1",el)];
  const P = { t:0, playing:false, w0:0, t0:0, raf:0, starts:[], total:0, cur:-1, act:0, auds:[], textKey:"" };
  P.layout = function(){ let s=0; this.starts = st.clips.map(c=>{ const a=s; s+=clipLen(c); return a; }); this.total = s; if(this.t>this.total) this.t = this.total; };
  P.clipAt = function(t){ for(let i=st.clips.length-1;i>=0;i--) if(t>=this.starts[i]-1e-6) return t<this.starts[i]+clipLen(st.clips[i])-1e-6 || i===st.clips.length-1 ? i : -1; return -1; };
  P.fade = function(t){ let f=1; if(st.fade_in>0) f=Math.min(f,t/st.fade_in); if(st.fade_out>0) f=Math.min(f,(this.total-t)/st.fade_out); return clamp(f,0,1); };
  P.activate = function(i){
    const c = st.clips[i], url = clipUrl(c); let v = vids[this.act];
    if(v.dataset.url !== url){
      const o = vids[1-this.act];
      if(o.dataset.url === url){ v.pause(); this.act = 1-this.act; v = o; }
      else { v.src = url; v.dataset.url = url; v.load(); }
    }
    vids[this.act].classList.add("on"); vids[1-this.act].classList.remove("on");
    this.cur = i; return vids[this.act];
  };
  P.sync = function(play){
    const t = this.t, n = st.clips.length, mute = $("#edMute",el).checked, f = this.fade(t);
    $("#edEmpty",el).classList.toggle("hidden", n>0);
    if(n){
      const i = this.clipAt(t); const c = st.clips[i]; let v = vids[this.act];
      if(i !== this.cur || v.dataset.url !== clipUrl(c)) v = this.activate(i);
      const local = clamp(c.start + (t - this.starts[i]) * (c.speed||1), c.start, Math.max(c.start, c.end - 0.02));
      v.playbackRate = c.speed || 1; v.muted = mute; v.volume = clamp((c.volume==null?1:c.volume) * f, 0, 1);
      if(play){ if(v.paused) v.play().catch(()=>{}); if(Math.abs(v.currentTime - local) > 0.35) v.currentTime = local; }
      else { v.pause(); if(Math.abs(v.currentTime - local) > 0.03) v.currentTime = local; }
      const nx = st.clips[i+1];   // get the next clip ready so the cut is smooth
      if(nx && this.starts[i+1] - t < 1.5){ const o = vids[1-this.act], u = clipUrl(nx); if(o.dataset.url !== u){ o.src = u; o.dataset.url = u; o.load(); } if(o.paused && Math.abs(o.currentTime - nx.start) > 0.05) o.currentTime = nx.start; }
    } else vids.forEach(v=>{ v.pause(); });
    // music and voice tracks
    st.tracks.forEach((tr,k)=>{
      let a = this.auds[k];
      if(!a || a.file !== tr.file){ if(a) a.el.pause(); a = this.auds[k] = {file:tr.file, el:new Audio("/files/audio/" + enc(tr.file))}; a.el.preload = "auto"; }
      const e = a.el, d = e.duration || tr.duration || 0, loop = tr.kind === "music";
      e.loop = loop; e.muted = mute; e.volume = clamp((tr.volume==null?0.3:tr.volume) * f, 0, 1);
      const inside = t >= tr.start && t <= this.total && (loop || !d || t < tr.start + d);
      if(!inside){ if(!e.paused) e.pause(); return; }
      let local = t - tr.start; if(loop && d) local = local % d;
      if(play){ if(e.paused){ try{ e.currentTime = local; }catch(_){} e.play().catch(()=>{}); }
        else if(Math.abs(e.currentTime - local) > 0.4 && !(loop && d && Math.abs(Math.abs(e.currentTime - local) - d) < 0.4)) e.currentTime = local; }
      else { if(!e.paused) e.pause(); try{ if(Math.abs(e.currentTime - local) > 0.05) e.currentTime = local; }catch(_){} }
    });
    while(this.auds.length > st.tracks.length){ this.auds.pop().el.pause(); }
    // text on screen
    const W = +st.size.split("x")[0], H = +st.size.split("x")[1], B = Math.min(W,H);
    const act = st.texts.map((x,i)=>({x,i})).filter(({x})=> (x.text||"").trim() && t >= (x.start||0) - 1e-6 && t <= ((x.end||0) || this.total) + 1e-6);
    const key = act.map(({x,i})=>i+"|"+x.text+"|"+x.style+"|"+x.position).join("¦") + "@" + st.size + (st.selK==="text"?st.selI:"");
    if(key !== this.textKey){ this.textKey = key;
      $("#edTexts",el).innerHTML = act.map(({x,i})=>`<div class="ed-text ${x.style==='title'?'title':'cap'} ${esc(x.position||'bottom')} ${st.selK==='text'&&st.selI===i?'sel':''}">${esc(wrapCaption(x.text, W, Math.floor(B*(x.style==='title'?0.075:0.05))))}</div>`).join(""); }
    $("#edFade",el).style.opacity = String(1 - f);
    this.paint();
  };
  P.paint = function(){
    $("#edTime",el).textContent = mmss(this.t) + " / " + mmss(this.total);
    const ph = $("#tlPh",el); if(ph) ph.style.left = (LAB + this.t * st.zoom) + "px";
    if(this.playing){ const sc = $("#tlScroll",el), x = LAB + this.t*st.zoom; if(x > sc.scrollLeft + sc.clientWidth - 40 || x < sc.scrollLeft + LAB) sc.scrollLeft = Math.max(0, x - LAB - 80); }
  };
  P.seek = function(t){ this.t = clamp(t, 0, this.total); this.w0 = performance.now(); this.t0 = this.t; this.sync(this.playing); };
  P.play = function(){
    if(!st.clips.length){ toast("Add a video clip first.", true); return; }
    if(this.t >= this.total - 0.05) this.t = 0;
    this.playing = true; this.w0 = performance.now(); this.t0 = this.t; $("#edPlay",el).textContent = "❚❚ Pause";
    cancelAnimationFrame(this.raf); const tick = now=>{
      if(!this.playing) return;
      if(!isShown()){ this.pause(); return; }
      this.t = this.t0 + (now - this.w0)/1000;
      if(this.t >= this.total){ this.t = this.total; this.pause(); return; }
      this.sync(true); this.raf = requestAnimationFrame(tick); };
    this.raf = requestAnimationFrame(tick);
  };
  P.pause = function(){ this.playing = false; cancelAnimationFrame(this.raf); $("#edPlay",el).textContent = "▶ Play"; this.sync(false); };
  $("#edPlay",el).onclick = ()=> P.playing ? P.pause() : P.play();
  $("#edStart",el).onclick = ()=>P.seek(0);
  $("#edBack",el).onclick = ()=>P.seek(P.t-1);
  $("#edFwd",el).onclick = ()=>P.seek(P.t+1);
  $("#edMute",el).onchange = ()=>P.sync(P.playing);
  vids.forEach(v=>v.addEventListener("error", ()=>{ if(v.dataset.url && v.classList.contains("on")) toast("This video can’t be previewed here, but it will still export normally.", true); }));

  // captions wrap with the same rule the exporter uses, so the preview matches the final video
  function wrapCaption(text, width, size){
    const cpl = Math.max(8, Math.floor(width*0.88/(size*0.58))), out = [];
    String(text).trim().split("\n").forEach(para=>{ let line = ""; para.split(/\s+/).filter(Boolean).forEach(w=>{ if(line && line.length+1+w.length > cpl){ out.push(line); line = w; } else line = line ? line+" "+w : w; }); out.push(line); });
    return out.join("\n");
  }
  function fitFrame(){
    const r = stage.getBoundingClientRect(); if(r.width < 50 || r.height < 50) return;
    const [W,H] = st.size.split("x").map(Number), k = Math.min((r.width-16)/W, (r.height-16)/H);
    frame.style.width = Math.floor(W*k)+"px"; frame.style.height = Math.floor(H*k)+"px"; frame.style.setProperty("--fb", Math.floor(Math.min(W,H)*k)+"px"); P.textKey = "";
  }
  new ResizeObserver(fitFrame).observe(stage);

  // ---------------------------------------------------------------- media pool
  async function loadLib(){ lib = await api("/api/library"); renderPool(); }
  function renderPool(){
    $$(".ed-tabs button",el).forEach(b=>b.classList.toggle("on", b.dataset.pt===poolTab));
    const box = $("#edPool",el);
    if(poolTab==="v"){
      const v = [...lib.videos.map(f=>({...f,src:"out",tag:"made here"})), ...lib.uploads.map(f=>({...f,src:"media",tag:"uploaded"}))];
      box.innerHTML = v.map(f=>`<div class="pool-item" draggable="true" data-kind="video" data-name="${esc(f.name)}" data-folder="${f.src}">
        <video src="/files/${f.src}/${enc(f.name)}#t=0.4" preload="metadata" muted></video>
        <div class="pi-b"><b title="${esc(f.name)}">${esc(f.name)}</b><span class="note">${f.tag}</span>
        <div class="row"><button class="small" data-add="${esc(f.name)}" data-folder="${f.src}" type="button">+ Add</button><button class="del" data-del="${esc(f.name)}" data-folder="${f.src}" type="button">Delete</button></div></div></div>`).join("")
        || '<div class="note" style="padding:8px">No videos yet. Make one in another tab, or press “Upload video”.</div>';
    } else {
      box.innerHTML = lib.audio.map(f=>`<div class="pool-item aud" draggable="true" data-kind="audio" data-name="${esc(f.name)}">
        <div class="pi-b"><b title="${esc(f.name)}">♪ ${esc(f.name)}</b>
        <div class="row"><button class="small" data-listen="${esc(f.name)}" type="button">▶ Listen</button><button class="small" data-add="${esc(f.name)}" data-audio="1" type="button">+ Add</button><button class="del" data-del="${esc(f.name)}" data-folder="audio" type="button">Delete</button></div></div></div>`).join("")
        || '<div class="note" style="padding:8px">No music or voice files yet. Press “Upload audio”, or make a voice in the Voices tab.</div>';
    }
  }
  const listener = new Audio();
  $(".ed-tabs",el).onclick = e=>{ const b=e.target.closest("button[data-pt]"); if(b){ poolTab=b.dataset.pt; renderPool(); } };
  $("#edPool",el).onclick = async e=>{
    const b = e.target.closest("button"); if(!b) return;
    if(b.dataset.del){ await deleteMedia(b.dataset.folder, b.dataset.del); return; }
    if(b.dataset.listen){ if(!listener.paused && listener.dataset.f===b.dataset.listen){ listener.pause(); b.textContent="▶ Listen"; return; } listener.src="/files/audio/"+enc(b.dataset.listen); listener.dataset.f=b.dataset.listen; listener.play().catch(()=>{}); b.textContent="❚❚ Stop"; listener.onended=()=>{ b.textContent="▶ Listen"; }; return; }
    if(b.dataset.add){ b.dataset.audio ? await addTrack(b.dataset.add) : await addClip(b.dataset.add, b.dataset.folder); }
  };
  [["#eUpVideo","#eFileV","video"],["#eUpAudio","#eFileA","audio"]].forEach(([bt,fi,kind])=>{
    $(bt,el).onclick = ()=>$(fi,el).click();
    $(fi,el).onchange = async e=>{ const f=e.target.files[0]; if(!f) return; e.target.value=""; try{ await upload(kind,f); toast("Uploaded "+f.name); poolTab = kind==="audio"?"a":"v"; loadLib(); }catch(err){ reportError(err); } };
  });
  const infoCache = {};
  async function info(file){ return infoCache[file] || (infoCache[file] = await api("/api/media/info?file="+enc(file))); }

  // ---------------------------------------------------------------- adding things
  async function addClip(file, folder, at){
    try{ const inf = await info(file); snap();
      const c = {file, folder, start:0, end:inf.duration||10, speed:1, volume:1, duration:inf.duration||0};
      const idx = at==null ? st.clips.length : clamp(at,0,st.clips.length); st.clips.splice(idx,0,c); st.selK="clip"; st.selI=idx;
      layoutAll(); renderInsp(); saveProj();
      if(st.clips.length===1) P.seek(0);
    }catch(err){ reportError(err); }
  }
  async function addTrack(file, startAt){
    try{ const inf = await info(file).catch(()=>({duration:0})); snap();
      const voice = /voice|scene-\d|narrat/i.test(file);
      st.tracks.push({file, kind:voice?"voice":"music", volume:voice?1:0.3, start: startAt!=null ? r1(startAt) : (voice? r1(P.t) : 0), duration:inf.duration||0});
      st.selK="track"; st.selI=st.tracks.length-1; layoutAll(); renderInsp(); saveProj();
    }catch(err){ reportError(err); }
  }
  $("#edAddText",el).onclick = ()=>{ snap(); const t0 = r1(P.t), t1 = r1(Math.max(P.total, t0+3)); st.texts.push({text:"Your text here", start:t0, end:Math.min(t1, r1(t0+3)), position:"bottom", style:"caption"});
    st.selK="text"; st.selI=st.texts.length-1; layoutAll(); renderInsp(); saveProj(); const ta=$("#edInsp textarea",el)||$("textarea",$("#edInsp",el)); ta && ta.select(); };
  $("#edAddAudio",el).onclick = ()=>{ poolTab="a"; renderPool(); toast(lib.audio.length ? "Pick a music or voice file on the left and press “+ Add”." : "Upload a music or voice file first (left panel)."); };
  function splitHere(){
    const i = P.clipAt(P.t); const c = st.clips[i];
    if(i<0 || !c){ toast("Move the playhead over a clip first.", true); return; }
    const local = P.t - P.starts[i]; if(local < 0.15 || clipLen(c) - local < 0.15){ toast("Move the playhead further inside the clip to cut it.", true); return; }
    snap(); const s = r1(c.start + local*(c.speed||1));
    const a = {...c, end:s}, b = {...c, start:s}; st.clips.splice(i,1,a,b); st.selK="clip"; st.selI=i+1; layoutAll(); renderInsp(); saveProj();
  }
  function removeSel(){
    if(!st.selK) { toast("Click something on the timeline first."); return; } snap();
    ({clip:st.clips, text:st.texts, track:st.tracks})[st.selK].splice(st.selI,1); st.selK=""; layoutAll(); renderInsp(); saveProj();
  }
  $("#edSplit",el).onclick = splitHere; $("#edDelete",el).onclick = removeSel; $("#edUndo",el).onclick = undo; $("#edRedo",el).onclick = redo;

  // ---------------------------------------------------------------- timeline
  const LAB = 96;
  const lanes = ()=>$(".tl-ruler-lane",el);
  function renderTimeline(){
    const pps = st.zoom, sc = $("#tlScroll",el);
    const W = Math.ceil(Math.max(P.total + 6, (sc.clientWidth - LAB)/pps) * pps);
    const step = pps>=120?1 : pps>=60?2 : pps>=30?5 : pps>=15?10 : 30;
    let ticks = ""; for(let s=0; s*pps<=W; s+=step) ticks += `<i style="left:${s*pps}px"><span>${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}</span></i>`;
    const clips = st.clips.map((c,i)=>`<div class="blk clip ${st.selK==='clip'&&st.selI===i?'sel':''}" data-k="clip" data-i="${i}" style="left:${P.starts[i]*pps}px;width:${Math.max(8,clipLen(c)*pps)}px" title="${esc(c.file)}">
        <span class="hdl l" data-h="l"></span><b>${esc(c.file)}</b><em>${fmt(clipLen(c))}s${(c.speed||1)!==1?` · ${c.speed}×`:''}${c.volume===0?' · muted':''}</em><span class="hdl r" data-h="r"></span></div>`).join("")
      || `<div class="tl-hint">Add a video from the left panel, or drag it here.</div>`;
    const texts = st.texts.map((x,i)=>{ const s0=x.start||0, e0=(x.end||0)||P.total||3; return `<div class="blk text ${st.selK==='text'&&st.selI===i?'sel':''}" data-k="text" data-i="${i}" style="left:${s0*pps}px;width:${Math.max(8,(e0-s0)*pps)}px"><span class="hdl l" data-h="l"></span><b>T ${esc((x.text||"(empty)").split("\n")[0])}</b><span class="hdl r" data-h="r"></span></div>`; }).join("");
    const aud = st.tracks.map((tr,i)=>{ const len = tr.kind==="music" ? Math.max(0,P.total - tr.start) : (tr.duration || 3); return `<div class="tl-row"><div class="tl-lab">${tr.kind==='music'?'Music':'Voice'} ${i+1}</div><div class="tl-lane"><div class="blk ${tr.kind==='music'?'music':'voice'} ${st.selK==='track'&&st.selI===i?'sel':''}" data-k="track" data-i="${i}" style="left:${tr.start*pps}px;width:${Math.max(8,len*pps)}px"><b>♪ ${esc(tr.file)}</b></div></div></div>`; }).join("");
    $("#tlInner",el).style.width = (LAB+W)+"px";
    $("#tlInner",el).innerHTML = `<div class="tl-row"><div class="tl-lab"></div><div class="tl-lane tl-ruler-lane" style="width:${W}px">${ticks}</div></div>
      <div class="tl-row tall"><div class="tl-lab">Video</div><div class="tl-lane" data-lane="v" style="width:${W}px">${clips}<div class="tl-drop hidden" id="tlDrop"></div></div></div>
      <div class="tl-row"><div class="tl-lab">Text</div><div class="tl-lane" data-lane="t" style="width:${W}px">${texts}</div></div>${aud}
      <div class="tl-row"><div class="tl-lab">Music / voice</div><div class="tl-lane" data-lane="a" style="width:${W}px"><div class="tl-hint small">${st.tracks.length?'':'Add music or a voice recording with the ♪ button.'}</div></div></div>
      <div class="tl-ph" id="tlPh" style="left:${LAB + P.t*pps}px"></div>`;
  }
  const xToTime = ev => (ev.clientX - lanes().getBoundingClientRect().left) / st.zoom;
  function scrub(ev){ P.seek(Math.max(0, xToTime(ev))); }
  $("#tlInner",el).addEventListener("pointerdown", e=>{
    if(e.button) return;
    if(e.target.closest(".tl-ruler-lane")){ e.preventDefault(); const was = P.playing; if(was) P.pause(); scrub(e);
      const mv = ev=>scrub(ev), up = ()=>{ document.removeEventListener("pointermove",mv); document.removeEventListener("pointerup",up); if(was) P.play(); };
      document.addEventListener("pointermove",mv); document.addEventListener("pointerup",up); return; }
    const blk = e.target.closest(".blk");
    if(!blk){ if(e.target.closest(".tl-lane")){ select(null); scrub(e); } return; }
    e.preventDefault(); beginDrag(e, blk);
  });
  function beginDrag(e, blk){
    const k = blk.dataset.k, i = +blk.dataset.i, h = e.target.dataset.h || "", x0 = e.clientX, pps = st.zoom;
    const list = k==="clip"?st.clips : k==="text"?st.texts : st.tracks, item = list[i], orig = JSON.parse(JSON.stringify(item));
    let moved = false, dropIdx = i;
    select(k, i);
    const blockEl = ()=>$(`.blk[data-k="${k}"][data-i="${i}"]`, el);
    const mv = ev=>{
      const dx = ev.clientX - x0; if(!moved && Math.abs(dx) < 4) return;
      if(!moved){ moved = true; snap(); if(P.playing) P.pause(); }
      const ds = dx/pps;
      if(k==="clip"){
        const sp = orig.speed||1;
        if(h==="l"){ item.start = r1(clamp(orig.start + ds*sp, 0, orig.end-0.2)); }
        else if(h==="r"){ item.end = r1(clamp(orig.end + ds*sp, orig.start+0.2, orig.duration||1e9)); }
        else { const b = blockEl(); if(b){ b.style.transform = `translateX(${dx}px)`; b.classList.add("drag"); }
          const mid = P.starts[i] + clipLen(orig)/2 + ds; dropIdx = 0; st.clips.forEach((c,j)=>{ if(j!==i && P.starts[j] + clipLen(c)/2 < mid) dropIdx++; });
          const dr = $("#tlDrop",el); let xx = 0; const others = st.clips.filter((_,j)=>j!==i); others.slice(0,dropIdx).forEach(c=>xx+=clipLen(c)); dr.style.left = xx*pps+"px"; dr.classList.remove("hidden"); return; }
      } else if(k==="text"){
        const len = (orig.end||P.total) - (orig.start||0);
        if(h==="l") item.start = r1(clamp((orig.start||0)+ds, 0, (orig.end||P.total)-0.2));
        else if(h==="r") item.end = r1(Math.max((orig.start||0)+0.2, (orig.end||P.total)+ds));
        else { item.start = r1(Math.max(0,(orig.start||0)+ds)); item.end = r1(item.start + len); }
      } else { item.start = r1(Math.max(0, orig.start + ds)); }
      layoutAll(true);
    };
    const up = ev=>{
      document.removeEventListener("pointermove",mv); document.removeEventListener("pointerup",up);
      if(!moved){ P.seek(Math.max(0, xToTime(ev))); renderInsp(); return; }
      if(k==="clip" && !h && dropIdx !== i){ const [c] = st.clips.splice(i,1); st.clips.splice(dropIdx,0,c); st.selI = dropIdx; }
      layoutAll(); renderInsp(); saveProj();
    };
    document.addEventListener("pointermove",mv); document.addEventListener("pointerup",up);
  }
  // drag from the media pool onto the timeline
  const tlIn = $("#tlInner",el);
  $("#edPool",el).addEventListener("dragstart", e=>{ const it = e.target.closest(".pool-item"); if(!it) return; e.dataTransfer.setData("text/plain", JSON.stringify({kind:it.dataset.kind, name:it.dataset.name, folder:it.dataset.folder||""})); });
  tlIn.addEventListener("dragover", e=>{ e.preventDefault(); });
  tlIn.addEventListener("drop", async e=>{
    e.preventDefault(); let d; try{ d = JSON.parse(e.dataTransfer.getData("text/plain")); }catch(_){ return; }
    const t = Math.max(0, xToTime(e));
    if(d.kind==="video"){ let idx = 0; st.clips.forEach((c,j)=>{ if(P.starts[j] + clipLen(c)/2 < t) idx++; }); await addClip(d.name, d.folder, idx); }
    else if(d.kind==="audio") await addTrack(d.name, t);
  });

  // ---------------------------------------------------------------- inspector
  function renderInsp(){
    const box = $("#edInsp",el), it = selItem();
    const row = (label, html)=>`<label>${label}</label>${html}`;
    if(!it){
      box.innerHTML = `<h2>Your video</h2><p class="note">Click a clip, text or sound on the timeline to change it here.</p>
        ${row("Video shape",`<select data-p="size"><option value="1920x1080">Wide 1920x1080</option><option value="1280x720">Wide 1280x720</option><option value="1080x1920">Tall 1080x1920 (Shorts / Reels)</option></select>`)}
        <div class="two"><div>${row("Fade in (s)",`<input type="number" data-p="fade_in" min="0" step="0.1" value="${st.fade_in}">`)}</div><div>${row("Fade out (s)",`<input type="number" data-p="fade_out" min="0" step="0.1" value="${st.fade_out}">`)}</div></div>
        <p class="note" style="margin-top:14px"><b>Shortcuts</b><br>Space: play / pause · S: cut here · Delete: remove<br>← →: step 0.1s (Shift: 1s) · + −: zoom · Ctrl+Z: undo</p>`;
      $("select[data-p=size]",box).value = st.size; return;
    }
    if(st.selK==="clip"){
      const c = it, i = P.clipAt(P.t), here = i===st.selI;
      box.innerHTML = `<h2>Video clip</h2><b class="ellip" title="${esc(c.file)}">${esc(c.file)}</b><div class="note">Plays for ${fmt(clipLen(c))} s</div>
        <div class="two"><div>${row("Play from (s)",`<input type="number" data-f="start" min="0" step="0.1" value="${fmt(c.start)}">`)}</div><div>${row("Play until (s)",`<input type="number" data-f="end" min="0" step="0.1" value="${fmt(c.end)}">`)}</div></div>
        <div class="row"><button class="small" data-a="setstart" ${here?'':'disabled'} type="button" title="Cut off everything before the playhead">Start at playhead</button><button class="small" data-a="setend" ${here?'':'disabled'} type="button" title="Cut off everything after the playhead">End at playhead</button></div>
        ${row("Speed",`<select data-f="speed">${[0.5,0.75,1,1.25,1.5,2,3].map(s=>`<option ${s==(c.speed||1)?'selected':''}>${s}</option>`).join("")}</select>`)}
        ${row(`Sound of this clip: <b id="vl">${Math.round((c.volume==null?1:c.volume)*100)}%</b>`,`<input type="range" data-f="volume" min="0" max="1.5" step="0.05" value="${c.volume==null?1:c.volume}">`)}
        <div class="row" style="margin-top:12px"><button class="small" data-a="left" ${st.selI==0?'disabled':''} type="button">← Move earlier</button><button class="small" data-a="right" ${st.selI==st.clips.length-1?'disabled':''} type="button">Move later →</button><button class="small ghost" data-a="del" type="button">Remove</button></div>`;
    } else if(st.selK==="text"){
      const x = it;
      box.innerHTML = `<h2>Text on screen</h2>${row("What it says",`<textarea data-f="text" rows="3" placeholder="Type here">${esc(x.text||"")}</textarea>`)}
        <p class="note" style="margin:4px 0 0">Long text is split into lines automatically. Press Enter to start a new line yourself.</p>
        ${row("Look",`<select data-f="style"><option value="caption" ${x.style!=='title'?'selected':''}>Caption (dark box)</option><option value="title" ${x.style==='title'?'selected':''}>Big title</option></select>`)}
        ${row("Where",`<select data-f="position">${[["top","Top"],["center","Middle"],["bottom","Bottom"]].map(([v,l])=>`<option value="${v}" ${v===(x.position||'bottom')?'selected':''}>${l}</option>`).join("")}</select>`)}
        <div class="two"><div>${row("Shows from (s)",`<input type="number" data-f="start" min="0" step="0.1" value="${fmt(x.start||0)}">`)}</div><div>${row("Shows until (s)",`<input type="number" data-f="end" min="0" step="0.1" value="${fmt(x.end||0)}">`)}</div></div>
        <div class="row"><button class="small" data-a="tstart" type="button">From playhead</button><button class="small" data-a="tend" type="button">Until playhead</button><button class="small ghost" data-a="del" type="button">Remove</button></div>`;
    } else {
      const tr = it, files = lib.audio.map(f=>f.name);
      box.innerHTML = `<h2>${tr.kind==='music'?'Music':'Voice'}</h2>${row("File",`<select data-f="file">${(files.includes(tr.file)?files:[tr.file,...files]).map(f=>`<option ${f===tr.file?'selected':''}>${esc(f)}</option>`).join("")}</select>`)}
        ${row("Type",`<select data-f="kind"><option value="music" ${tr.kind==='music'?'selected':''}>Music (repeats until the end)</option><option value="voice" ${tr.kind==='voice'?'selected':''}>Voice (plays once)</option></select>`)}
        ${row(`Volume: <b id="vl">${Math.round(tr.volume*100)}%</b>`,`<input type="range" data-f="volume" min="0" max="1.5" step="0.05" value="${tr.volume}">`)}
        <p class="note" style="margin:2px 0 0">The preview plays up to 100%. Above that is only heard in the exported video.</p>
        ${row("Starts at (s)",`<input type="number" data-f="start" min="0" step="0.1" value="${fmt(tr.start||0)}">`)}
        <div class="row"><button class="small" data-a="astart" type="button">Start at playhead</button><button class="small ghost" data-a="del" type="button">Remove</button></div>`;
    }
  }
  const insp = $("#edInsp",el);
  insp.addEventListener("focusin", e=>{ if(e.target.matches("input,textarea,select") && !insp._snapped){ insp._snapped = true; snap(); } });
  insp.addEventListener("focusout", ()=>{ insp._snapped = false; });
  function field(e){
    const f = e.target.dataset.f, p = e.target.dataset.p; if(!f && !p) return;
    if(p){ st[p] = e.target.type==="number" ? Math.max(0,parseFloat(e.target.value)||0) : e.target.value; if(p==="size") fitFrame(); layoutAll(true); saveProj(); return; }
    const it = selItem(); if(!it) return; let v = e.target.value;
    if(["start","end","volume"].includes(f) || (f==="speed")) v = parseFloat(v); if(Number.isNaN(v)) v = 0;
    if(st.selK==="clip"){ it[f] = f==="speed" ? (v||1) : v; if(f==="start") it.start = Math.max(0, Math.min(it.start, it.end-0.1)); if(f==="end"){ it.end = Math.max(it.start+0.1, it.duration ? Math.min(it.end, it.duration) : it.end); } }
    else if(st.selK==="text"){ it[f] = v; }
    else { it[f] = v; if(f==="file"){ infoCache[v] ? it.duration = infoCache[v].duration : info(v).then(i=>{ it.duration = i.duration; layoutAll(true); }).catch(()=>{}); } }
    if(f==="volume"){ const vl=$("#vl",insp); if(vl) vl.textContent = Math.round(v*100)+"%"; }
    P.textKey = ""; layoutAll(true); saveProj();
    if(e.type==="change" && ["kind","speed","style","position"].includes(f)) renderInsp();
  }
  insp.addEventListener("input", e=>{ if(e.target.matches("textarea,input[type=range]")) field(e); });
  insp.addEventListener("change", field);
  insp.addEventListener("click", e=>{
    const b = e.target.closest("button[data-a]"); if(!b) return; const a = b.dataset.a, it = selItem(); snap();
    if(a==="del"){ snapDone(); removeSelNoSnap(); return; }
    if(a==="left" || a==="right"){ const j = st.selI + (a==="left"?-1:1); [st.clips[st.selI], st.clips[j]] = [st.clips[j], st.clips[st.selI]]; st.selI = j; }
    if(a==="setstart" || a==="setend"){ const i = P.clipAt(P.t); if(i===st.selI){ const s = r1(it.start + (P.t - P.starts[i])*(it.speed||1)); if(a==="setstart") it.start = Math.min(s, it.end-0.1); else it.end = Math.max(s, it.start+0.1); } }
    if(a==="tstart") it.start = r1(P.t); if(a==="tend") it.end = r1(P.t);
    if(a==="astart") it.start = r1(P.t);
    layoutAll(); renderInsp(); saveProj();
  });
  const snapDone = ()=>{};
  function removeSelNoSnap(){ ({clip:st.clips, text:st.texts, track:st.tracks})[st.selK].splice(st.selI,1); st.selK=""; layoutAll(); renderInsp(); saveProj(); }

  // ---------------------------------------------------------------- zoom, layout, keys
  function layoutAll(keepInsp){ P.layout(); renderTimeline(); P.textKey = ""; P.sync(P.playing); btns(); check(); }
  function zoom(f){ const c = clamp(Math.round(st.zoom*f), 8, 400); if(c===st.zoom) return; st.zoom = c; layoutAll(); saveProj(); }
  $("#edZoomIn",el).onclick = ()=>zoom(1.4); $("#edZoomOut",el).onclick = ()=>zoom(1/1.4);
  $("#edFit",el).onclick = ()=>{ const w = $("#tlScroll",el).clientWidth - LAB - 30; st.zoom = clamp(Math.floor(w / Math.max(5, P.total+1)), 8, 400); layoutAll(); saveProj(); };
  document.addEventListener("keydown", e=>{
    if(!isShown() || e.target.matches("input,textarea,select")) return;
    const k = e.key, ctrl = e.ctrlKey || e.metaKey;
    if(k===" "){ e.preventDefault(); $("#edPlay",el).click(); }
    else if(ctrl && k.toLowerCase()==="z"){ e.preventDefault(); e.shiftKey ? redo() : undo(); }
    else if(ctrl && k.toLowerCase()==="y"){ e.preventDefault(); redo(); }
    else if(k==="s" || k==="S"){ splitHere(); }
    else if(k==="Delete" || k==="Backspace"){ e.preventDefault(); removeSel(); }
    else if(k==="ArrowLeft"){ e.preventDefault(); P.seek(P.t - (e.shiftKey?1:0.1)); }
    else if(k==="ArrowRight"){ e.preventDefault(); P.seek(P.t + (e.shiftKey?1:0.1)); }
    else if(k==="+" || k==="="){ zoom(1.4); } else if(k==="-"){ zoom(1/1.4); }
  });

  // ---------------------------------------------------------------- export dialog
  const dlg = $("#edExport",el);
  [["fade_in","#eFi"],["fade_out","#eFo"],["size","#eSize"],["name","#eName"]].forEach(([k,s])=>{ const e=$(s,el); e.value=st[k]; e.oninput=e.onchange=()=>{ st[k] = e.type==="number" ? Math.max(0,parseFloat(e.value)||0) : e.value; if(k==="size") fitFrame(); P.sync(P.playing); saveProj(); }; });
  $("#edExportBtn",el).onclick = ()=>{ P.pause(); ["fade_in","fade_out","size","name"].forEach(k=>{}); $("#eFi",el).value=st.fade_in; $("#eFo",el).value=st.fade_out; $("#eSize",el).value=st.size; $("#eName",el).value=st.name; check(); dlg.showModal(); };
  $("#eClose",el).onclick = ()=>dlg.close();
  function check(){
    const msg = !st.clips.length ? "Add at least one video clip to the timeline first." : (App.caps && !App.caps.ffmpeg ? "FFmpeg is missing. See the badges on the left." : "");
    const w = $("#eProblem",el); w.textContent = msg; w.classList.toggle("hidden", !msg); $("#eMake",el).disabled = !!msg || $("#eMake",el).dataset.busy==="1";
    $("#eTotal",el).textContent = st.clips.length ? `Total length: about ${fmt(P.total)} seconds` : "";
  }
  $("#eMake",el).onclick = async ()=>{
    const b = $("#eMake",el); b.dataset.busy = "1"; b.disabled = true;
    const out = await job.run("/api/edit/render", {clips:st.clips.map(c=>({file:c.file,start:c.start,end:c.end,speed:c.speed,volume:c.volume==null?1:c.volume})), texts:st.texts, tracks:st.tracks,
      fade_in:st.fade_in, fade_out:st.fade_out, size:st.size, name:st.name});
    b.dataset.busy = "0"; check(); if(out) loadLib();
  };
  document.addEventListener("capsready", check);
  document.addEventListener("mediachanged", ()=>{ loadLib().then(()=>{ layoutAll(); renderInsp(); }); });
  window.addEventListener("resize", ()=>{ fitFrame(); renderTimeline(); P.paint(); });

  App.pages.editor.refresh = ()=>loadLib().then(()=>{ fitFrame(); layoutAll(); renderInsp(); });
  App.pages.editor._player = P; App.pages.editor._state = st;
  P.layout(); btns(); renderTimeline(); renderInsp(); loadLib().then(()=>{ renderInsp(); });
}, onShow(){ App.pages.editor.refresh && App.pages.editor.refresh(); }});
