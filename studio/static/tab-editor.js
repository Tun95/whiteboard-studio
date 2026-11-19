registerPage("editor", {title:"Editor", sub:"Cut, arrange and polish your videos. Everything you change plays in the preview straight away.", icon:"film", build(el){
  el.innerHTML = `
  <div class="ed" id="edRoot">
    <div class="ed-bar">
      <div class="grp"><button id="edUndo" title="Undo the last change (Ctrl+Z)" type="button">↶ Undo</button><button id="edRedo" title="Redo (Ctrl+Y)" type="button">↷ Redo</button></div>
      <div class="grp"><button id="edCopy" title="Copy the selected items (Ctrl+C)" type="button">⧉ Copy</button><button id="edPaste" title="Paste at the red line (Ctrl+V)" type="button">📋 Paste</button></div>
      <div class="grp"><button id="edSplit" title="Cut the clip under the playhead into two (S)" type="button">✂ Cut</button><button id="edDelete" title="Remove the selected items (Delete key)" type="button">🗑 Remove</button></div>
      <div class="grp"><button id="edAddText" title="Put a title or caption on the video at the playhead" type="button">T Text</button><button id="edAddPic" title="Put a picture, logo, GIF or watermark on the video" type="button">🖼 Picture</button><button id="edAddAudio" title="Add music or a voice recording" type="button">♪ Music / voice</button></div>
      <div class="grp"><button id="edZoomOut" title="Zoom the timeline out (-)" type="button">−</button><span class="zl">Zoom</span><button id="edZoomIn" title="Zoom the timeline in (+)" type="button">+</button><button id="edFit" title="Fit the whole video on screen" type="button">Fit</button></div>
      <button class="primary expo" id="edExportBtn" type="button">⬇ Export video</button>
    </div>
    <div class="ed-top">
      <section class="ed-pool">
        <div class="ed-tabs"><button class="on" data-pt="v" type="button">Videos</button><button data-pt="i" type="button">Pictures</button><button data-pt="a" type="button">Audio</button></div>
        <div class="row" style="margin:6px 0"><button class="small" id="eUpVideo" type="button">Upload video</button><button class="small" id="eUpImage" type="button">Upload picture</button><button class="small" id="eUpAudio" type="button">Upload audio</button>
          <input type="file" id="eFileI" accept=".png,.jpg,.jpeg,.gif,.webp" hidden><input type="file" id="eFileV" accept=".mp4,.mov,.mkv,.webm" hidden><input type="file" id="eFileA" accept=".wav,.mp3,.m4a,.ogg,.flac" hidden></div>
        <div class="ed-list" id="edPool"></div>
      </section>
      <section class="ed-view">
        <div class="ed-stage" id="edStage"><div class="ed-frame" id="edFrame">
          <video id="edV0" playsinline preload="auto"></video><video id="edV1" playsinline preload="auto"></video>
          <div class="ed-over" id="edOver"></div><div class="ed-texts" id="edTexts"></div><div class="ed-fade" id="edFade"></div>
          <div class="ed-empty" id="edEmpty"><b>Start here</b><span>1. Pick a video on the left and press “+ Add”.<br>2. Add text, pictures or music with the buttons on top.<br>3. Press Play to see everything together.</span></div>
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
  const st = ps("editor", {clips:[], texts:[], tracks:[], overlays:[], fade_in:0, fade_out:0, size:"1920x1080", name:"edited-video", zoom:80, selK:"", selI:0});
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
  const snapshot = () => JSON.stringify({clips:st.clips, texts:st.texts, tracks:st.tracks, overlays:st.overlays, fade_in:st.fade_in, fade_out:st.fade_out, size:st.size});
  function snap(){ undoS.push(snapshot()); if(undoS.length>80) undoS.shift(); redoS.length = 0; btns(); }
  function restore(js){ Object.assign(st, JSON.parse(js)); st.selK=""; M.clear(); layoutAll(); renderInsp(); saveProj(); }
  function undo(){ if(!undoS.length) return; redoS.push(snapshot()); restore(undoS.pop()); btns(); }
  function redo(){ if(!redoS.length) return; undoS.push(snapshot()); restore(redoS.pop()); btns(); }
  function btns(){ $("#edUndo",el).disabled = !undoS.length; $("#edRedo",el).disabled = !redoS.length; $("#edPaste",el).disabled = !(typeof CB !== "undefined" && CB && CB.length); $("#edCopy",el).disabled = !st.selK; }

  // ---------------------------------------------------------------- selection
  st.overlays = st.overlays || [];
  const LIST = k => ({clip:st.clips, text:st.texts, track:st.tracks, ov:st.overlays})[k];
  const selItem = () => st.selK ? (LIST(st.selK)||[])[st.selI] || null : null;
  const M = new Set();                                   // everything that is selected, as "kind:index" (Ctrl+click adds more)
  const mk = (k,i) => k+":"+i, inSel = (k,i) => M.has(mk(k,i));
  const group = () => [...M].map(x=>{ const [k,i] = x.split(":"); return {k, i:+i}; });
  function select(k, i, add){
    if(!k){ M.clear(); st.selK = ""; st.selI = 0; }
    else if(add){ const key = mk(k,i); if(M.has(key)){ M.delete(key); const g = group().pop(); st.selK = g ? g.k : ""; st.selI = g ? g.i : 0; } else { M.add(key); st.selK = k; st.selI = i; } }
    else { M.clear(); M.add(mk(k,i)); st.selK = k; st.selI = i; }
    renderTimeline(); renderInsp(); P.textKey = ""; P.sync(P.playing); btns();
  }

  // ---------------------------------------------------------------- player (live preview)
  const frame = $("#edFrame",el), stage = $("#edStage",el), vids = [$("#edV0",el), $("#edV1",el)];
  const P = { t:0, playing:false, w0:0, t0:0, raf:0, starts:[], total:0, cur:-1, act:0, auds:[], textKey:"" };
  P.layout = function(){ let s=0; this.starts = st.clips.map(c=>{ const a=s; s+=clipLen(c); return a; }); this.total = s; if(this.t>this.total) this.t = this.total; };
  P.clipAt = function(t){ const n = st.clips.length; if(!n) return -1; for(let i=n-1;i>=0;i--) if(t >= this.starts[i] - 1e-6) return i; return 0; };
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
      const i = this.clipAt(t); const c = st.clips[i]; let v = vids[this.act]; if(!c) return;
      if(i !== this.cur || v.dataset.url !== clipUrl(c)) v = this.activate(i);
      const local = clamp(c.start + (t - this.starts[i]) * (c.speed||1), c.start, Math.max(c.start, c.end - 0.02));
      v.playbackRate = c.speed || 1; v.muted = mute; v.volume = clamp((c.volume==null?1:c.volume) * f, 0, 1);
      if(play){ if(v.paused) v.play().catch(e=>{ if(e && e.name==="NotAllowedError" && this.playing){ this.pause(); toast("Your browser blocked the preview. Click ▶ Play once more.", true); } }); if(Math.abs(v.currentTime - local) > 0.35) v.currentTime = local; }
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
    const act = st.texts.map((x,i)=>({x,i,on: t >= (x.start||0) - 1e-6 && t <= ((x.end||0) || this.total) + 1e-6})).filter(({x,i,on})=> (x.text||"").trim() && (on || inSel("text",i)));
    const key = act.map(({x,i,on})=>i+"|"+x.text+"|"+x.style+"|"+x.position+"|"+x.x+"|"+x.y+"|"+on).join("¦") + "@" + st.size + (st.selK==="text"?st.selI:"") + M.size;
    if(key !== this.textKey){ this.textKey = key;
      $("#edTexts",el).innerHTML = act.map(({x,i,on})=>{ const free = x.x!=null && x.y!=null;
        return `<div class="ed-text ${x.style==='title'?'title':'cap'} ${free?'free':esc(x.position||'bottom')} ${on?'':'ghost'} ${inSel('text',i)?'sel':''}" data-i="${i}" ${free?`style="left:${x.x*100}%;top:${x.y*100}%"`:''}>${esc(wrapCaption(x.text, W, Math.floor(B*(x.style==='title'?0.075:0.05))))}</div>`; }).join(""); }
    $("#edFade",el).style.opacity = String(1 - f);
    this.over(t);
    this.paint();
  };
  // pictures / logos / GIFs on the screen (drag them to move, drag the corners to resize)
  P.over = function(t){
    const box = $("#edOver",el), total = this.total;
    const vis = st.overlays.map((o,i)=>{ const on = t >= (o.start||0) - 1e-6 && t <= ((o.end||0) || total || 1e9) + 1e-6; return {o,i,on, sel:inSel("ov",i)}; }).filter(x=>x.on || x.sel);
    const key = vis.map(x=>x.i+"|"+x.o.file+"|"+x.on+"|"+x.sel).join("¦") + (M.size>1?"m":"");
    if(key !== this.ovKey){ this.ovKey = key;
      box.innerHTML = vis.map(x=>`<div class="ed-ov ${x.on?'':'ghost'} ${x.sel?'sel':''}" data-i="${x.i}"><img src="/files/images/${enc(x.o.file)}" draggable="false" alt="">${x.sel && M.size===1 ? '<i class="rh tl" data-c="tl"></i><i class="rh tr" data-c="tr"></i><i class="rh bl" data-c="bl"></i><i class="rh br" data-c="br"></i>' : ''}</div>`).join(""); }
    box.querySelectorAll(".ed-ov").forEach(d=>{ const o = st.overlays[+d.dataset.i]; if(!o) return;
      d.style.left = (o.x*100)+"%"; d.style.top = (o.y*100)+"%"; d.style.width = (o.w*100)+"%"; d.style.opacity = d.classList.contains("ghost") ? "" : String(o.opacity==null?1:o.opacity); });
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
    this.playing = true; this.w0 = performance.now(); this.t0 = this.t; this.hold = performance.now(); $("#edPlay",el).textContent = "❚❚ Pause";
    try{ this.sync(true); }catch(err){ console.error(err); }   // start picture and sound right now, while the click still counts (browsers block it otherwise)
    cancelAnimationFrame(this.raf); const tick = now=>{
      if(!this.playing) return;
      if(!isShown()){ this.pause(); return; }
      const cv = vids[this.act];
      if(this.hold){   // only at the very start: wait (up to 6 s) for the first picture so the beginning is never skipped
        if((cv.readyState < 3 || cv.seeking) && performance.now() - this.hold < 6000){
          this.t0 = this.t; this.w0 = now; this.auds.forEach(a=>{ if(!a.el.paused) a.el.pause(); }); if(cv.paused) cv.play().catch(()=>{});
          this.raf = requestAnimationFrame(tick); return; }
        this.hold = 0; this.w0 = now; this.t0 = this.t;
      }
      this.t = Math.max(0, this.t0 + (now - this.w0)/1000);
      if(this.t >= this.total){ this.t = this.total; this.pause(); return; }
      try{ this.sync(true); }catch(err){ console.error(err); }   // one hiccup must never freeze the playhead
      this.raf = requestAnimationFrame(tick); };
    this.raf = requestAnimationFrame(tick);
  };
  P.pause = function(){
    this.playing = false; this.hold = 0; cancelAnimationFrame(this.raf); $("#edPlay",el).textContent = "▶ Play";
    vids.forEach(v=>{ try{ v.pause(); }catch(_){} }); this.auds.forEach(a=>{ try{ a.el.pause(); }catch(_){} });   // stop every sound first, whatever happens next
    try{ this.sync(false); }catch(err){ console.error(err); }
  };
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
    } else if(poolTab==="i"){
      box.innerHTML = lib.images.map(f=>`<div class="pool-item" draggable="true" data-kind="image" data-name="${esc(f.name)}">
        <img class="pi-img" src="/files/images/${enc(f.name)}" alt="" draggable="false">
        <div class="pi-b"><b title="${esc(f.name)}">${esc(f.name)}</b>
        <div class="row"><button class="small" data-addpic="${esc(f.name)}" type="button">+ Add to screen</button><button class="del" data-del="${esc(f.name)}" data-folder="images" type="button">Delete</button></div></div></div>`).join("")
        || '<div class="note" style="padding:8px">No pictures yet. Press “Upload picture” (PNG, JPG or GIF). A PNG with a see-through background is best for a logo or watermark.</div>';
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
    if(b.dataset.addpic){ await addOverlay(b.dataset.addpic); return; }
    if(b.dataset.add){ b.dataset.audio ? await addTrack(b.dataset.add) : await addClip(b.dataset.add, b.dataset.folder); }
  };
  [["#eUpVideo","#eFileV","video"],["#eUpAudio","#eFileA","audio"],["#eUpImage","#eFileI","overlay"]].forEach(([bt,fi,kind])=>{
    $(bt,el).onclick = ()=>$(fi,el).click();
    $(fi,el).onchange = async e=>{ const f=e.target.files[0]; if(!f) return; e.target.value=""; try{ await upload(kind,f); toast("Uploaded "+f.name); poolTab = kind==="audio"?"a":kind==="overlay"?"i":"v"; loadLib(); }catch(err){ reportError(err); } };
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
  async function addOverlay(file, at, cx, cy){
    try{
      const dim = await new Promise(res=>{ const im = new Image(); im.onload = ()=>res({w:im.naturalWidth, h:im.naturalHeight}); im.onerror = ()=>res({w:400,h:400}); im.src = "/files/images/"+enc(file); });
      snap(); const [W,H] = st.size.split("x").map(Number), s0 = r1(at==null ? P.t : at);
      let w = Math.min(0.3, Math.max(0.08, (dim.w/ W) < 0.3 ? dim.w/W : 0.3)); if(dim.h/dim.w * w * W > H*0.8) w = (H*0.8) / (dim.h/dim.w) / W;
      st.overlays.push({file, start:s0, end:r1(Math.min(s0+5, P.total > s0 ? P.total : s0+5)), x:cx==null?0.5:cx, y:cy==null?0.5:cy, w:r1(w*100)/100, opacity:1, ar:r2(dim.h/dim.w)});
      select("ov", st.overlays.length-1); layoutAll(); saveProj();
    }catch(err){ reportError(err); }
  }
  $("#edAddPic",el).onclick = ()=>{ poolTab="i"; renderPool(); if(lib.images.length) toast("Pick a picture on the left and press “+ Add to screen”."); else $("#eFileI",el).click(); };
  $("#edAddAudio",el).onclick = ()=>{ poolTab="a"; renderPool(); toast(lib.audio.length ? "Pick a music or voice file on the left and press “+ Add”." : "Upload a music or voice file first (left panel)."); };
  function splitHere(){
    const i = P.clipAt(P.t); const c = st.clips[i];
    if(i<0 || !c){ toast("Move the playhead over a clip first.", true); return; }
    const local = P.t - P.starts[i]; if(local < 0.15 || clipLen(c) - local < 0.15){ toast("Move the playhead further inside the clip to cut it.", true); return; }
    snap(); const s = r1(c.start + local*(c.speed||1));
    const a = {...c, end:s}, b = {...c, start:s}; st.clips.splice(i,1,a,b); st.selK="clip"; st.selI=i+1; layoutAll(); renderInsp(); saveProj();
  }
  // ---- copy / cut / paste on the timeline
  let CB = null;
  function copySel(quiet){
    const g = group(); if(!g.length && st.selK) g.push({k:st.selK, i:st.selI});
    if(!g.length){ toast("Click something on the timeline first, then copy it."); return false; }
    CB = g.map(x=>({k:x.k, i:x.i, item:JSON.parse(JSON.stringify(LIST(x.k)[x.i]))})); btns();
    if(!quiet) toast(`Copied ${g.length} item${g.length>1?"s":""}. Move the red line where you want it, then press Paste.`); return true;
  }
  function pasteCB(){
    if(!CB || !CB.length){ toast("Nothing copied yet. Select something on the timeline and press Copy."); return; }
    snap(); const t = r1(P.t), made = [];
    const clips = CB.filter(c=>c.k==="clip").sort((a,b)=>a.i-b.i);
    if(clips.length){
      let idx = st.clips.length;
      for(let j=0;j<st.clips.length;j++){ const s0 = P.starts[j], e0 = s0 + clipLen(st.clips[j]); if(t < e0 - 0.05){ idx = t <= s0 + 0.05 ? j : j + 1; break; } }
      clips.forEach((c,n)=>st.clips.splice(idx+n, 0, JSON.parse(JSON.stringify(c.item))));
      clips.forEach((_,n)=>made.push(["clip", idx+n]));
    }
    const timed = CB.filter(c=>c.k!=="clip");
    if(timed.length){
      const minStart = Math.min(...timed.map(c=>c.item.start||0)), d = t - minStart;
      timed.forEach(c=>{ const it = JSON.parse(JSON.stringify(c.item)); it.start = r1(Math.max(0,(it.start||0)+d)); if(c.k!=="track" && it.end) it.end = r1(it.end+d);
        if(Math.abs(d) < 0.05 && it.x!=null && it.y!=null){ it.x = clamp(r2(it.x+0.04),0,1); it.y = clamp(r2(it.y+0.04),0,1); }   // so a copy at the same time is not hidden behind the original
        const arr = LIST(c.k); arr.push(it); made.push([c.k, arr.length-1]); });
    }
    M.clear(); made.forEach(([k,i])=>M.add(mk(k,i))); const last = made[made.length-1]; st.selK = last[0]; st.selI = last[1];
    P.ovKey = ""; layoutAll(); renderInsp(); saveProj(); toast(`Pasted ${made.length} item${made.length>1?"s":""} at ${mmss(t)}.`);
  }
  function removeSel(){
    if(!st.selK) { toast("Click something on the timeline first."); return; } snap();
    const g = group(); if(!g.length) g.push({k:st.selK, i:st.selI});
    ["clip","text","track","ov"].forEach(k=>{ g.filter(x=>x.k===k).map(x=>x.i).sort((a,b)=>b-a).forEach(i=>LIST(k).splice(i,1)); });
    M.clear(); st.selK=""; P.ovKey = ""; layoutAll(); renderInsp(); saveProj();
  }
  $("#edCopy",el).onclick = ()=>copySel(); $("#edPaste",el).onclick = pasteCB; $("#edSplit",el).onclick = splitHere; $("#edDelete",el).onclick = removeSel; $("#edUndo",el).onclick = undo; $("#edRedo",el).onclick = redo;

  // ---------------------------------------------------------------- timeline
  const LAB = 96;
  const lanes = ()=>$(".tl-ruler-lane",el);
  function renderTimeline(){
    if(M.size <= 1){ M.clear(); if(st.selK && selItem()) M.add(mk(st.selK, st.selI)); else st.selK = ""; }
    const pps = st.zoom, sc = $("#tlScroll",el);
    const W = Math.ceil(Math.max(P.total + 6, (sc.clientWidth - LAB)/pps) * pps);
    const step = pps>=120?1 : pps>=60?2 : pps>=30?5 : pps>=15?10 : 30;
    let ticks = ""; for(let s=0; s*pps<=W; s+=step) ticks += `<i style="left:${s*pps}px"><span>${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}</span></i>`;
    const clips = st.clips.map((c,i)=>`<div class="blk clip ${inSel('clip',i)?'sel':''}" data-k="clip" data-i="${i}" style="left:${P.starts[i]*pps}px;width:${Math.max(8,clipLen(c)*pps)}px" title="${esc(c.file)}">
        <span class="hdl l" data-h="l"></span><b>${esc(c.file)}</b><em>${fmt(clipLen(c))}s${(c.speed||1)!==1?` · ${c.speed}×`:''}${c.volume===0?' · muted':''}</em><span class="hdl r" data-h="r"></span></div>`).join("")
      || `<div class="tl-hint">Add a video from the left panel, or drag it here.</div>`;
    const texts = st.texts.map((x,i)=>{ const s0=x.start||0, e0=(x.end||0)||P.total||3; return `<div class="blk text ${inSel('text',i)?'sel':''}" data-k="text" data-i="${i}" style="left:${s0*pps}px;width:${Math.max(8,(e0-s0)*pps)}px"><span class="hdl l" data-h="l"></span><b>T ${esc((x.text||"(empty)").split("\n")[0])}</b><span class="hdl r" data-h="r"></span></div>`; }).join("");
    const pics = st.overlays.map((o,i)=>{ const s0=o.start||0, e0=(o.end||0)||P.total||3; return `<div class="blk ov ${inSel('ov',i)?'sel':''}" data-k="ov" data-i="${i}" style="left:${s0*pps}px;width:${Math.max(8,(e0-s0)*pps)}px" title="${esc(o.file)}"><span class="hdl l" data-h="l"></span><b>🖼 ${esc(o.file)}</b><span class="hdl r" data-h="r"></span></div>`; }).join("");
    const aud = st.tracks.map((tr,i)=>{ const len = tr.kind==="music" ? Math.max(0,P.total - tr.start) : (tr.duration || 3); return `<div class="tl-row"><div class="tl-lab">${tr.kind==='music'?'Music':'Voice'} ${i+1}</div><div class="tl-lane"><div class="blk ${tr.kind==='music'?'music':'voice'} ${inSel('track',i)?'sel':''}" data-k="track" data-i="${i}" style="left:${tr.start*pps}px;width:${Math.max(8,len*pps)}px"><b>♪ ${esc(tr.file)}</b></div></div></div>`; }).join("");
    $("#tlInner",el).style.width = (LAB+W)+"px";
    $("#tlInner",el).innerHTML = `<div class="tl-row"><div class="tl-lab"></div><div class="tl-lane tl-ruler-lane" style="width:${W}px">${ticks}</div></div>
      <div class="tl-row tall"><div class="tl-lab">Video</div><div class="tl-lane" data-lane="v" style="width:${W}px">${clips}<div class="tl-drop hidden" id="tlDrop"></div></div></div>
      <div class="tl-row"><div class="tl-lab">Pictures</div><div class="tl-lane" data-lane="p" style="width:${W}px">${pics}</div></div>
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
    if(e.ctrlKey || e.metaKey){ select(k, i, true); return; }          // Ctrl + click: add to / remove from the selection
    if(h || !inSel(k,i)) select(k, i); else { st.selK = k; st.selI = i; renderInsp(); }   // dragging one of several selected keeps them all
    const grp = group().filter(g=> k==="clip" ? g.k==="clip" : g.k!=="clip");
    const orig = new Map(grp.map(g=>[mk(g.k,g.i), JSON.parse(JSON.stringify(LIST(g.k)[g.i]))]));
    const item = LIST(k)[i], o0 = orig.get(mk(k,i));
    let moved = false, dropIdx = i;
    const selClips = grp.map(g=>g.i).sort((a,b)=>a-b);
    const mv = ev=>{
      const dx = ev.clientX - x0; if(!moved && Math.abs(dx) < 4) return;
      if(!moved){ moved = true; snap(); if(P.playing) P.pause(); }
      const ds = dx/pps;
      if(k==="clip"){
        const sp = o0.speed||1;
        if(h==="l"){ item.start = r1(clamp(o0.start + ds*sp, 0, o0.end-0.2)); }
        else if(h==="r"){ item.end = r1(clamp(o0.end + ds*sp, o0.start+0.2, o0.duration||1e9)); }
        else {
          selClips.forEach(j=>{ const b = $(`.blk[data-k="clip"][data-i="${j}"]`, el); if(b){ b.style.transform = `translateX(${dx}px)`; b.classList.add("drag"); } });
          const mid = P.starts[i] + clipLen(o0)/2 + ds; dropIdx = 0; st.clips.forEach((c,j)=>{ if(!selClips.includes(j) && P.starts[j] + clipLen(c)/2 < mid) dropIdx++; });
          const dr = $("#tlDrop",el); let xx = 0; st.clips.filter((_,j)=>!selClips.includes(j)).slice(0,dropIdx).forEach(c=>xx+=clipLen(c)); dr.style.left = xx*pps+"px"; dr.classList.remove("hidden"); return; }
      } else {
        const timed = k==="track" ? false : true;
        if(h && timed){
          const s0 = o0.start||0, e0 = o0.end||P.total;
          if(h==="l") item.start = r1(clamp(s0+ds, 0, e0-0.2)); else item.end = r1(Math.max(s0+0.2, e0+ds));
        } else {
          const minStart = Math.min(...grp.map(g=>orig.get(mk(g.k,g.i)).start||0)); const d = Math.max(ds, -minStart);
          grp.forEach(g=>{ const it = LIST(g.k)[g.i], o = orig.get(mk(g.k,g.i)); it.start = r1((o.start||0) + d); if(g.k!=="track" && o.end) it.end = r1(o.end + d); });
        }
      }
      layoutAll(true);
    };
    const up = ev=>{
      document.removeEventListener("pointermove",mv); document.removeEventListener("pointerup",up);
      if(!moved){ if(M.size>1 && !(e.ctrlKey||e.metaKey)) select(k,i); P.seek(Math.max(0, xToTime(ev))); renderInsp(); return; }
      if(k==="clip" && !h && selClips.length){
        const moving = selClips.map(j=>st.clips[j]), rest = st.clips.filter((_,j)=>!selClips.includes(j));
        rest.splice(dropIdx, 0, ...moving); st.clips.length = 0; st.clips.push(...rest);
        M.clear(); moving.forEach((_,n)=>M.add(mk("clip", dropIdx+n))); st.selI = dropIdx + Math.max(0, selClips.indexOf(i));
      }
      layoutAll(); renderInsp(); saveProj();
    };
    document.addEventListener("pointermove",mv); document.addEventListener("pointerup",up);
  }
  // drag / resize a picture right on the preview
  $("#edOver",el).addEventListener("pointerdown", e=>{
    const d = e.target.closest(".ed-ov"); if(!d || e.button) return; e.preventDefault();
    const i = +d.dataset.i, o = st.overlays[i]; if(!o) return;
    if(e.ctrlKey || e.metaKey){ select("ov", i, true); return; }
    if(!inSel("ov",i) || M.size>1) select("ov", i);
    const rect = frame.getBoundingClientRect(), handle = e.target.dataset.c || "", o0 = {x:o.x, y:o.y, w:o.w}, px0 = e.clientX, py0 = e.clientY;
    let moved = false;
    const mv = ev=>{
      if(!moved && Math.hypot(ev.clientX-px0, ev.clientY-py0) < 3) return; if(!moved){ moved = true; snap(); }
      if(handle){ const cx = rect.left + o0.x*rect.width, dxp = Math.abs(ev.clientX - cx); o.w = r2(clamp(2*dxp/rect.width, 0.03, 1.5)); }
      else { let nx = o0.x + (ev.clientX-px0)/rect.width, ny = o0.y + (ev.clientY-py0)/rect.height;
        if(Math.abs(nx-0.5) < 0.015) nx = 0.5; if(Math.abs(ny-0.5) < 0.015) ny = 0.5;     // snaps to the middle
        o.x = r2(clamp(nx, 0, 1)); o.y = r2(clamp(ny, 0, 1)); }
      P.over(P.t); const ins = $("#edInsp",el); const sl = $("input[data-f=wpct]",ins); if(sl){ sl.value = Math.round(o.w*100); const vw = $("#vw",ins); if(vw) vw.textContent = Math.round(o.w*100)+"%"; }
    };
    const up = ()=>{ document.removeEventListener("pointermove",mv); document.removeEventListener("pointerup",up); if(moved) saveProj(); };
    document.addEventListener("pointermove",mv); document.addEventListener("pointerup",up);
  });
  const r2 = n => Math.round(n*1000)/1000;
  $("#edTexts",el).addEventListener("pointerdown", e=>{
    const d = e.target.closest(".ed-text"); if(!d || e.button) return; e.preventDefault();
    const i = +d.dataset.i, x = st.texts[i]; if(!x) return;
    if(e.ctrlKey || e.metaKey){ select("text", i, true); return; }
    if(!inSel("text",i) || M.size>1) select("text", i);
    if(P.playing) P.pause();
    const rect = frame.getBoundingClientRect(), dr = d.getBoundingClientRect(), startC = {x:(dr.left+dr.width/2-rect.left)/rect.width, y:(dr.top+dr.height/2-rect.top)/rect.height}, px0 = e.clientX, py0 = e.clientY;
    let moved = false;
    const mv = ev=>{
      if(!moved && Math.hypot(ev.clientX-px0, ev.clientY-py0) < 3) return; if(!moved){ moved = true; snap(); }
      let nx = startC.x + (ev.clientX-px0)/rect.width, ny = startC.y + (ev.clientY-py0)/rect.height;
      if(Math.abs(nx-0.5) < 0.015) nx = 0.5; if(Math.abs(ny-0.5) < 0.015) ny = 0.5;
      x.x = r2(clamp(nx, 0.02, 0.98)); x.y = r2(clamp(ny, 0.02, 0.98)); P.textKey = ""; P.sync(false);
    };
    const up = ()=>{ document.removeEventListener("pointermove",mv); document.removeEventListener("pointerup",up); if(moved){ renderInsp(); saveProj(); } };
    document.addEventListener("pointermove",mv); document.addEventListener("pointerup",up);
  });
  // drag from the media pool onto the timeline
  const tlIn = $("#tlInner",el);
  $("#edPool",el).addEventListener("dragstart", e=>{ const it = e.target.closest(".pool-item"); if(!it) return; e.dataTransfer.setData("text/plain", JSON.stringify({kind:it.dataset.kind, name:it.dataset.name, folder:it.dataset.folder||""})); });
  frame.addEventListener("dragover", e=>e.preventDefault());
  frame.addEventListener("drop", async e=>{ e.preventDefault(); let d; try{ d = JSON.parse(e.dataTransfer.getData("text/plain")); }catch(_){ return; }
    if(d.kind!=="image") return; const r = frame.getBoundingClientRect(); await addOverlay(d.name, P.t, r2((e.clientX-r.left)/r.width), r2((e.clientY-r.top)/r.height)); });
  tlIn.addEventListener("dragover", e=>{ e.preventDefault(); });
  tlIn.addEventListener("drop", async e=>{
    e.preventDefault(); let d; try{ d = JSON.parse(e.dataTransfer.getData("text/plain")); }catch(_){ return; }
    const t = Math.max(0, xToTime(e));
    if(d.kind==="video"){ let idx = 0; st.clips.forEach((c,j)=>{ if(P.starts[j] + clipLen(c)/2 < t) idx++; }); await addClip(d.name, d.folder, idx); }
    else if(d.kind==="audio") await addTrack(d.name, t);
    else if(d.kind==="image") await addOverlay(d.name, t);
  });

  // ---------------------------------------------------------------- inspector
  function renderInsp(){
    const box = $("#edInsp",el), it = selItem();
    const row = (label, html)=>`<label>${label}</label>${html}`;
    if(!it){
      box.innerHTML = `<h2>Your video</h2><p class="note">Click a clip, text or sound on the timeline to change it here.</p>
        ${row("Video shape",`<select data-p="size"><option value="1920x1080">Wide 1920x1080</option><option value="1280x720">Wide 1280x720</option><option value="1080x1920">Tall 1080x1920 (Shorts / Reels)</option></select>`)}
        <div class="two"><div>${row("Fade in (s)",`<input type="number" data-p="fade_in" min="0" step="0.1" value="${st.fade_in}">`)}</div><div>${row("Fade out (s)",`<input type="number" data-p="fade_out" min="0" step="0.1" value="${st.fade_out}">`)}</div></div>
        <p class="note" style="margin-top:14px"><b>Shortcuts</b><br>Space: play / pause · S: cut here · Delete: remove<br>← →: step 0.1s (Shift: 1s) · Ctrl+Z: undo<br>Mouse wheel on the timeline: zoom · Shift + wheel: slide sideways<br>Ctrl + click: select several · Ctrl + A: select all<br>Ctrl + C / X / V: copy, cut, paste at the red line</p>`;
      $("select[data-p=size]",box).value = st.size; return;
    }
    if(M.size > 1){
      box.innerHTML = `<h2>${M.size} items selected</h2><p class="note">Drag any selected block on the timeline to move them all together. Ctrl + click adds or removes one.</p>
        <div class="row"><button class="del" data-a="delall" type="button">🗑 Remove all ${M.size}</button><button class="small" data-a="desel" type="button">Clear selection</button></div>`;
    } else if(st.selK==="ov"){
      const o = it, grid = [["tl","↖"],["tc","↑"],["tr","↗"],["ml","←"],["mc","●"],["mr","→"],["bl","↙"],["bc","↓"],["br","↘"]];
      box.innerHTML = `<h2>Picture on screen</h2><img class="pi-prev" src="/files/images/${enc(o.file)}" alt=""><b class="ellip" title="${esc(o.file)}">${esc(o.file)}</b>
        <p class="note" style="margin:4px 0">Drag the picture on the preview to move it. Drag a corner to make it bigger or smaller.</p>
        <button class="primary" data-a="watermark" type="button" title="Small, see-through, bottom right, for the whole video">Make it a watermark</button>
        ${row(`Size: <b id="vw">${Math.round(o.w*100)}%</b>`,`<input type="range" data-f="wpct" min="3" max="100" step="1" value="${Math.round(o.w*100)}">`)}
        ${row(`See-through: <b id="vo">${Math.round((o.opacity==null?1:o.opacity)*100)}%</b>`,`<input type="range" data-f="opacity" min="0.1" max="1" step="0.05" value="${o.opacity==null?1:o.opacity}">`)}
        <label>Quick place</label><div class="grid9">${grid.map(([c,a])=>`<button type="button" data-a="place" data-c="${c}">${a}</button>`).join("")}</div>
        <div class="two"><div>${row("Shows from (s)",`<input type="number" data-f="start" min="0" step="0.1" value="${fmt(o.start||0)}">`)}</div><div>${row("Shows until (s)",`<input type="number" data-f="end" min="0" step="0.1" value="${fmt(o.end||0)}">`)}</div></div>
        <div class="row"><button class="small" data-a="tstart" type="button">From playhead</button><button class="small" data-a="tend" type="button">Until playhead</button><button class="small" data-a="whole" type="button">Whole video</button></div>
        <div class="row" style="margin-top:8px"><button class="small" data-a="dupov" type="button">Duplicate</button><button class="small ghost" data-a="del" type="button">Remove</button></div>`;
    } else if(st.selK==="clip"){
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
        ${row("Where",`<select data-f="position">${x.x!=null&&x.y!=null?'<option value="custom" selected>Where you dragged it</option>':''}${[["top","Top"],["center","Middle"],["bottom","Bottom"]].map(([v,l])=>`<option value="${v}" ${x.x==null&&v===(x.position||'bottom')?'selected':''}>${l}</option>`).join("")}</select>`)}
        <p class="note" style="margin:2px 0 0">Tip: drag the words on the preview to put them anywhere.</p>
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
    else if(st.selK==="ov"){ if(f==="wpct"){ it.w = clamp(v/100, 0.03, 1.5); const vw=$("#vw",insp); if(vw) vw.textContent = Math.round(v)+"%"; } else { it[f] = v; const vo=$("#vo",insp); if(f==="opacity" && vo) vo.textContent = Math.round(v*100)+"%"; } }
    else if(st.selK==="text"){ if(f==="position"){ if(v==="custom") return; delete it.x; delete it.y; } it[f] = v; }
    else { it[f] = v; if(f==="file"){ infoCache[v] ? it.duration = infoCache[v].duration : info(v).then(i=>{ it.duration = i.duration; layoutAll(true); }).catch(()=>{}); } }
    if(f==="volume"){ const vl=$("#vl",insp); if(vl) vl.textContent = Math.round(v*100)+"%"; }
    P.textKey = ""; layoutAll(true); saveProj();
    if(e.type==="change" && ["kind","speed","style","position"].includes(f)) renderInsp();
  }
  insp.addEventListener("input", e=>{ if(e.target.matches("textarea,input[type=range]")) field(e); });
  insp.addEventListener("change", field);
  insp.addEventListener("click", e=>{
    const b = e.target.closest("button[data-a]"); if(!b) return; const a = b.dataset.a;
    if(a==="delall"){ removeSel(); return; }
    if(a==="desel"){ select(null); return; }
    const it = selItem(); snap();
    if(a==="watermark"){ Object.assign(it, {w:0.16, opacity:0.7, start:0, end:0}); const [W,H] = st.size.split("x").map(Number); it.x = r2(1 - 0.04 - it.w/2); it.y = r2(1 - 0.04 - (it.w*W*(it.ar||0.5))/H/2); }
    if(a==="place"){ const c = b.dataset.c, m = 0.03 + it.w/2; const [W,H] = st.size.split("x").map(Number); const mh = 0.03 + (it.w*W*(it.ar||0.5))/H/2;
      it.x = c[1]==="l" ? m : c[1]==="r" ? 1-m : 0.5; it.y = c[0]==="t" ? mh : c[0]==="b" ? 1-mh : 0.5; }
    if(a==="whole"){ it.start = 0; it.end = 0; }
    if(a==="dupov"){ const copy = JSON.parse(JSON.stringify(it)); copy.x = clamp(copy.x+0.05,0,1); copy.y = clamp(copy.y+0.05,0,1); st.overlays.splice(st.selI+1,0,copy); st.selI += 1; M.clear(); M.add(mk("ov",st.selI)); P.ovKey = ""; }
    if(a==="del"){ snapDone(); removeSelNoSnap(); return; }
    if(a==="left" || a==="right"){ const j = st.selI + (a==="left"?-1:1); [st.clips[st.selI], st.clips[j]] = [st.clips[j], st.clips[st.selI]]; st.selI = j; }
    if(a==="setstart" || a==="setend"){ const i = P.clipAt(P.t); if(i===st.selI){ const s = r1(it.start + (P.t - P.starts[i])*(it.speed||1)); if(a==="setstart") it.start = Math.min(s, it.end-0.1); else it.end = Math.max(s, it.start+0.1); } }
    if(a==="tstart") it.start = r1(P.t); if(a==="tend") it.end = r1(P.t);
    if(a==="astart") it.start = r1(P.t);
    layoutAll(); renderInsp(); saveProj();
  });
  const snapDone = ()=>{};
  function removeSelNoSnap(){ LIST(st.selK).splice(st.selI,1); M.clear(); st.selK=""; P.ovKey = ""; layoutAll(); renderInsp(); saveProj(); }

  // ---------------------------------------------------------------- zoom, layout, keys
  function layoutAll(keepInsp){ P.layout(); renderTimeline(); P.textKey = ""; P.sync(P.playing); btns(); check(); }
  function zoom(f){ const c = clamp(Math.round(st.zoom*f), 8, 400); if(c===st.zoom) return; st.zoom = c; layoutAll(); saveProj(); }
  $("#tlScroll",el).addEventListener("wheel", e=>{
    const sc = $("#tlScroll",el);
    if(e.shiftKey){ sc.scrollLeft += e.deltaY || e.deltaX; e.preventDefault(); return; }     // Shift + wheel: slide sideways
    if(e.altKey) return;                                                                      // Alt + wheel: scroll up/down through tracks
    e.preventDefault();
    const xIn = e.clientX - sc.getBoundingClientRect().left, tAt = (sc.scrollLeft + xIn - LAB) / st.zoom;
    let nz = Math.round(st.zoom * Math.exp(-clamp(e.deltaY,-240,240) * 0.0016)); if(nz === st.zoom) nz += e.deltaY < 0 ? 1 : -1;
    nz = clamp(nz, 8, 400); if(nz === st.zoom) return; st.zoom = nz; layoutAll();
    sc.scrollLeft = Math.max(0, LAB + tAt*nz - xIn); saveProj();
  }, {passive:false});
  $("#edZoomIn",el).onclick = ()=>zoom(1.4); $("#edZoomOut",el).onclick = ()=>zoom(1/1.4);
  $("#edFit",el).onclick = ()=>{ const w = $("#tlScroll",el).clientWidth - LAB - 30; st.zoom = clamp(Math.floor(w / Math.max(5, P.total+1)), 8, 400); layoutAll(); saveProj(); };
  document.addEventListener("keydown", e=>{
    if(!isShown() || e.target.matches("input,textarea,select")) return;
    const k = e.key, ctrl = e.ctrlKey || e.metaKey;
    if(k===" "){ e.preventDefault(); $("#edPlay",el).click(); }
    else if(ctrl && k.toLowerCase()==="z"){ e.preventDefault(); e.shiftKey ? redo() : undo(); }
    else if(ctrl && k.toLowerCase()==="y"){ e.preventDefault(); redo(); }
    else if(ctrl && k.toLowerCase()==="c"){ e.preventDefault(); copySel(); }
    else if(ctrl && k.toLowerCase()==="x"){ e.preventDefault(); if(copySel(true)) removeSel(); }
    else if(ctrl && k.toLowerCase()==="v"){ e.preventDefault(); pasteCB(); }
    else if(ctrl && k.toLowerCase()==="a"){ e.preventDefault(); M.clear(); [["clip",st.clips],["text",st.texts],["track",st.tracks],["ov",st.overlays]].forEach(([kk,l])=>l.forEach((_,i)=>M.add(mk(kk,i)))); const g = group()[0]; if(g){ st.selK = g.k; st.selI = g.i; } renderTimeline(); renderInsp(); P.ovKey=""; P.sync(P.playing); }
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
    const out = await job.run("/api/edit/render", {clips:st.clips.map(c=>({file:c.file,start:c.start,end:c.end,speed:c.speed,volume:c.volume==null?1:c.volume})), texts:st.texts, tracks:st.tracks, overlays:st.overlays,
      fade_in:st.fade_in, fade_out:st.fade_out, size:st.size, name:st.name});
    b.dataset.busy = "0"; check(); if(out) loadLib();
  };
  document.addEventListener("capsready", check);
  document.addEventListener("mediachanged", ()=>{ loadLib().then(()=>{ layoutAll(); renderInsp(); }); });
  window.addEventListener("resize", ()=>{ fitFrame(); renderTimeline(); P.paint(); });

  App.pages.editor.refresh = ()=>loadLib().then(()=>{ fitFrame(); layoutAll(); renderInsp(); });
  App.pages.editor._player = P; App.pages.editor._state = st;
  P.layout(); btns(); renderTimeline(); renderInsp(); loadLib().then(()=>{ renderInsp(); layoutAll(); });
}, onShow(){ App.pages.editor.refresh && App.pages.editor.refresh(); }});
