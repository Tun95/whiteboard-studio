registerPage("transcribe", {title:"Transcribe", sub:"Turn the speech in a video or audio file into text, then save it as a Word, PDF, text or subtitle file.", icon:"doc", build(el){
  el.innerHTML = `
  <div class="card hidden" id="xSetup"><h2>One-time setup</h2>
    <p class="note" style="margin-top:0">Transcribing uses a free, open-source speech engine (Whisper) that runs on this computer, so your files never leave it. It needs a small add-on (about 250 MB) and, the first time you use each quality level, a speech model download. You only do this once.</p>
    <div class="row"><button class="primary" id="xInstall" type="button">Set up transcription</button></div><div class="note" id="xInstState"></div><div class="bar hidden" id="xInstBar"><i></i></div><div class="perr hidden" id="xInstErr"></div></div>
  <div class="card"><h2>1. Pick a file</h2>
    <div class="row" style="margin-top:0"><select id="xFile" class="grow"></select><button id="xUp" type="button">Upload a file…</button>
      <input type="file" id="xFileIn" accept=".mp4,.mov,.mkv,.webm,.wav,.mp3,.m4a,.ogg,.flac" hidden></div>
    <p class="note" style="margin:6px 0 0">Works with videos and audio files. The sound of a video is used automatically.</p>
    <div class="two"><div><label>Language spoken</label><select id="xLang"></select><p class="note" style="margin:4px 0 0">Leave it on “Detect automatically” if unsure. Whisper does not support Igbo.</p></div>
      <div><label>Quality</label><select id="xModel"></select><p class="note" style="margin:4px 0 0" id="xModelNote"></p></div></div>
    <label class="check" style="margin-top:12px;display:flex;gap:8px;align-items:center"><input type="checkbox" id="xTr"> Translate the speech into English</label>
    <div class="row"><button class="primary" id="xGo" type="button">Turn speech into text</button></div>
    <div class="bar hidden" id="xBar"><i></i></div><div class="note" id="xState"></div><div class="perr hidden" id="xErr"></div></div>
  <div class="card hidden" id="xResult"><h2>2. Check and fix your text</h2>
    <div id="xPlayer" style="margin-bottom:6px"></div><p class="note" style="margin:0">Click a time to hear that part. You can fix any word before saving.</p>
    <div class="seglist" id="xSegs"></div>
    <h2 style="margin-top:14px">3. Save it</h2>
    <div class="two"><div><label style="margin-top:0">File type</label><select id="xFmt"></select></div><div><label style="margin-top:0">Title (optional)</label><input type="text" id="xTitle" placeholder="Interview with …"></div></div>
    <label class="check" style="margin-top:10px;display:flex;gap:8px;align-items:center"><input type="checkbox" id="xStamps"> Show the time before each line</label>
    <div class="row"><button class="primary" id="xSave" type="button">Save file</button><button id="xCopy" type="button">Copy text</button></div>
    <div class="row dlrow hidden" id="xSaved"></div>
    <div class="row" style="margin-top:14px;padding-top:12px;border-top:1px solid var(--line, #e5e9ef)"><button id="xCaps" type="button">Add as captions in the Editor</button><span class="note">Starts at</span><input type="number" id="xOff" value="0" min="0" step="0.5" style="width:84px"><span class="note">seconds</span></div></div>
  <div class="card"><h2>Earlier transcripts</h2><div id="xList"></div></div>`;

  const st = ps("transcribe", {lang:"", model:"small", translate:false, fmt:"docx", stamps:false});
  let info = null, cur = null, curName = "", curFile = null;
  const $x = s => $(s, el), enc = encodeURIComponent;
  const clock = t => { t = Math.max(0, Math.floor(t)); const h = Math.floor(t/3600), m = Math.floor(t%3600/60), s = t%60; return h ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${m}:${String(s).padStart(2,"0")}`; };

  // ---- setup
  async function loadStatus(){
    info = await api("/api/stt/status").catch(()=>null); if(!info) return;
    $x("#xSetup").classList.toggle("hidden", info.installed);
    $x("#xLang").innerHTML = info.languages.map(l=>`<option value="${l.id}">${esc(l.name)}</option>`).join(""); $x("#xLang").value = st.lang;
    $x("#xModel").innerHTML = info.models.map(m=>`<option value="${m.id}">${esc(m.label)} · ${esc(m.size)}${m.downloaded?" ✓ downloaded":""}</option>`).join(""); $x("#xModel").value = st.model;
    $x("#xFmt").innerHTML = Object.entries(info.formats).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join(""); $x("#xFmt").value = st.fmt;
    $x("#xTr").checked = st.translate; $x("#xStamps").checked = st.stamps; modelNote();
  }
  function modelNote(){ const m = info && info.models.find(m=>m.id===$x("#xModel").value); $x("#xModelNote").textContent = m ? m.note + (m.downloaded ? " Already downloaded." : " First use downloads " + m.size + ".") : ""; }
  $x("#xInstall").onclick = async ()=>{
    const b = $x("#xInstall"), bar = $x("#xInstBar"), s = $x("#xInstState"), err = $x("#xInstErr"); b.disabled = true; err.classList.add("hidden"); bar.classList.remove("hidden"); bar.firstChild.style.width = "6%"; s.textContent = "Installing… this needs internet and can take a few minutes.";
    try{ await runJob("/api/stt/install", {}, {onTick:j=>{ bar.firstChild.style.width = Math.max(6, Math.round(100*j.done/j.total))+"%"; s.textContent = "Installing… " + lastLine(j); }, onNote:m=>{ s.textContent = m; }});
      toast("Transcription is ready."); bar.classList.add("hidden"); s.textContent = ""; await loadStatus();
    }catch(e){ bar.classList.add("hidden"); s.textContent = ""; const i = e.info || {title:"Setup failed", what:e.message}; err.innerHTML = problemHTML(i); wireProblem(err, i); err.classList.remove("hidden"); }
    b.disabled = false;
  };
  ["xLang","xModel","xFmt"].forEach(id=>$x("#"+id).onchange = ()=>{ st.lang = $x("#xLang").value; st.model = $x("#xModel").value; st.fmt = $x("#xFmt").value; saveProj(); modelNote(); });
  $x("#xTr").onchange = ()=>{ st.translate = $x("#xTr").checked; saveProj(); }; $x("#xStamps").onchange = ()=>{ st.stamps = $x("#xStamps").checked; saveProj(); };

  // ---- files
  async function loadFiles(keep){
    const lib = await api("/api/library").catch(()=>null); if(!lib) return;
    const opt = (f, folder) => `<option value="${esc(f.name)}" data-folder="${folder}">${esc(f.name)}</option>`;
    const groups = [["Made in this app", lib.videos.map(f=>opt(f,"out"))], ["Uploaded videos", lib.uploads.map(f=>opt(f,"media"))], ["Audio", lib.audio.map(f=>opt(f,"audio"))]].filter(g=>g[1].length);
    const prev = keep || $x("#xFile").value;
    $x("#xFile").innerHTML = groups.length ? groups.map(([t,o])=>`<optgroup label="${t}">${o.join("")}</optgroup>`).join("") : `<option value="">No files yet. Press “Upload a file…”</option>`;
    if(prev) $x("#xFile").value = prev;
  }
  $x("#xUp").onclick = ()=>$x("#xFileIn").click();
  $x("#xFileIn").onchange = async e=>{ const f = e.target.files[0]; if(!f) return; e.target.value = "";
    const kind = /\.(wav|mp3|m4a|ogg|flac)$/i.test(f.name) ? "audio" : "video";
    try{ const r = await upload(kind, f); toast("Uploaded " + f.name); await loadFiles(r.name); }catch(err){ reportError(err); } };

  // ---- transcribe
  $x("#xGo").onclick = async ()=>{
    const sel = $x("#xFile"), file = sel.value; if(!file){ toast("Pick a file first.", true); return; }
    if(info && !info.installed){ toast("Set up transcription first (top of this page).", true); return; }
    const bar = $x("#xBar"), state = $x("#xState"), err = $x("#xErr"), b = $x("#xGo");
    err.classList.add("hidden"); bar.classList.remove("hidden"); bar.firstChild.style.width = "3%"; b.disabled = true; state.textContent = "Starting…";
    try{
      const j = await runJob("/api/stt/transcribe", {file, model:st.model, language:st.lang, task: st.translate ? "translate" : "transcribe"},
        {onTick:j=>{ bar.firstChild.style.width = Math.max(3, Math.round(100*j.done/j.total))+"%"; state.textContent = lastLine(j) || "Working…"; }, onNote:m=>{ state.textContent = m; }});
      bar.firstChild.style.width = "100%"; state.textContent = "Done."; setTimeout(()=>bar.classList.add("hidden"), 800);
      curFile = {name:file, folder: sel.selectedOptions[0] ? sel.selectedOptions[0].dataset.folder : ""};
      await openTranscript(j.output); loadStatus(); loadList();
    }catch(e){ bar.classList.add("hidden"); state.textContent = ""; const i = e.info || {title:"Could not transcribe", what:e.message}; err.innerHTML = problemHTML(i); wireProblem(err, i); err.classList.remove("hidden"); }
    b.disabled = false;
  };

  // ---- result
  async function openTranscript(name){
    cur = await api("/api/stt/get?name=" + enc(name)); curName = name;
    const src = cur.source || ""; if(!curFile || curFile.name !== src){ const lib = await api("/api/library").catch(()=>null); let folder = "";
      if(lib){ if(lib.videos.some(f=>f.name===src)) folder = "out"; else if(lib.uploads.some(f=>f.name===src)) folder = "media"; else if(lib.audio.some(f=>f.name===src)) folder = "audio"; } curFile = {name:src, folder}; }
    const isAudio = /\.(wav|mp3|m4a|ogg|flac)$/i.test(src), url = curFile.folder ? `/files/${curFile.folder}/${enc(src)}` : "";
    $x("#xPlayer").innerHTML = url ? (isAudio ? `<audio controls src="${url}" style="width:100%"></audio>` : `<video controls src="${url}" style="width:100%;max-height:240px;background:#000;border-radius:10px"></video>`) : "";
    $x("#xTitle").value = (src.replace(/\.[^.]+$/,"") || "Transcript");
    drawSegs(); $x("#xResult").classList.remove("hidden"); $x("#xSaved").classList.add("hidden"); $x("#xResult").scrollIntoView({behavior:"smooth", block:"start"});
  }
  function drawSegs(){
    $x("#xSegs").innerHTML = cur.segments.map((s,i)=>`<div class="seg" data-i="${i}"><button class="ts" data-t="${s.start}" type="button" title="Play from here">${clock(s.start)}</button><textarea rows="${Math.max(1, Math.ceil(s.text.length/90))}" data-i="${i}">${esc(s.text)}</textarea></div>`).join("");
  }
  $x("#xSegs").addEventListener("input", e=>{ const t = e.target.closest("textarea"); if(t){ cur.segments[+t.dataset.i].text = t.value; t.rows = Math.max(1, Math.ceil(t.value.length/90)); } });
  $x("#xSegs").addEventListener("click", e=>{ const b = e.target.closest("button.ts"); if(!b) return; const m = $x("#xPlayer").querySelector("video,audio"); if(m){ m.currentTime = +b.dataset.t; m.play().catch(()=>{}); } });
  $x("#xPlayer").addEventListener("timeupdate", e=>{ const t = e.target.currentTime; let on = -1; cur && cur.segments.forEach((s,i)=>{ if(t >= s.start && t < s.end + 0.3) on = i; });
    $$(".seg", el).forEach(d=>d.classList.toggle("on", +d.dataset.i === on)); }, true);
  const plain = ()=>cur.segments.map(s=>($x("#xStamps").checked ? `[${clock(s.start)}] ` : "") + s.text.trim()).join("\n");
  $x("#xCopy").onclick = async ()=>{ try{ await navigator.clipboard.writeText(plain()); toast("Copied. You can paste it anywhere."); }catch(_){ toast("Could not copy. Select the text and copy it by hand.", true); } };
  $x("#xSave").onclick = async ()=>{
    st.fmt = $x("#xFmt").value; const b = $x("#xSave"), box = $x("#xSaved"); b.disabled = true; box.classList.add("hidden");
    try{
      const r = await post("/api/stt/export", {name:curName, format:st.fmt, timestamps:$x("#xStamps").checked, title:$x("#xTitle").value, segments:cur.segments});
      box.innerHTML = `<a class="btn primary" href="${r.url}" download="${esc(r.name)}">Download ${esc(r.name)}</a><span class="note">Also saved in your Library.</span>`; box.classList.remove("hidden");
      const a = document.createElement("a"); a.href = r.url; a.download = r.name; document.body.appendChild(a); a.click(); a.remove();
      document.dispatchEvent(new Event("mediachanged"));
    }catch(e){ reportError(e); }
    b.disabled = false;
  };
  $x("#xCaps").onclick = ()=>{
    const ed = App.proj.editor; if(!ed){ toast("Open the Editor tab once first, then try again.", true); return; }
    const off = Math.max(0, parseFloat($x("#xOff").value) || 0);
    const add = cur.segments.filter(s=>s.text.trim()).map(s=>({text:s.text.trim(), start:Math.round((s.start+off)*100)/100, end:Math.round((s.end+off)*100)/100, position:"bottom", style:"caption"}));
    ed.texts = (ed.texts || []).concat(add); saveProj(); App.pages.editor.refresh && App.pages.editor.refresh();
    toast(`Added ${add.length} captions to the Editor timeline. Open the Editor to see them.`);
  };

  // ---- earlier transcripts
  async function loadList(){
    const r = await api("/api/stt/list").catch(()=>null); if(!r) return;
    $x("#xList").innerHTML = r.transcripts.map(t=>`<div class="row" style="margin:6px 0"><b class="grow">${esc(t.source || t.name)}</b><span class="note">${esc(t.language||"")} · ${t.pieces} pieces · ${esc((t.created||"").replace("T"," "))}</span><button class="small" data-open="${esc(t.name)}" type="button">Open</button><button class="del" data-delt="${esc(t.name)}" type="button">Delete</button></div>`).join("") || '<div class="note">Nothing yet. Your finished transcripts will show here.</div>';
  }
  $x("#xList").onclick = async e=>{ const o = e.target.closest("[data-open]"), d = e.target.closest("[data-delt]");
    if(o){ curFile = null; await openTranscript(o.dataset.open).catch(reportError); }
    if(d){ if(await deleteMedia("transcripts", d.dataset.delt)){ if(curName === d.dataset.delt){ $x("#xResult").classList.add("hidden"); cur = null; } loadList(); } } };
  document.addEventListener("mediachanged", ()=>{ if(el.classList.contains("show")){ loadFiles(); loadList(); } });
  loadStatus(); loadFiles(); loadList();
}, onShow(){ const el = $("#page-transcribe"); api("/api/stt/status").then(s=>el.querySelector("#xSetup").classList.toggle("hidden", s.installed)).catch(()=>{}); }});
