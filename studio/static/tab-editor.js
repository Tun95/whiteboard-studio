registerPage("editor", {title:"Editor", sub:"Join clips, trim, add music, titles and captions.", icon:"film", build(el){
  el.innerHTML = `<div class="grid2"><div>
    <div class="card"><h2>Your media</h2><div class="row" style="margin:0 0 8px">
        <button class="small" id="eUpVideo" type="button">Upload video</button><button class="small" id="eUpAudio" type="button">Upload music or voice</button>
        <input type="file" id="eFileV" accept=".mp4,.mov,.mkv,.webm" hidden><input type="file" id="eFileA" accept=".wav,.mp3,.m4a,.ogg,.flac" hidden></div>
      <div class="lib" id="eMedia"></div></div>
    <div class="card"><h2>Timeline</h2><div class="tl" id="eTl"></div><div id="eClips"></div>
      <div class="note" id="eEmpty">Add clips from “Your media” above. They play in the order shown here.</div></div>
    <div class="card"><h2>Preview of the selected clip</h2><video id="ePrev" controls preload="metadata"></video>
      <div class="row"><button class="small" id="eSetStart" type="button">Set start = now</button><button class="small" id="eSetEnd" type="button">Set end = now</button><span class="note" id="eNow"></span></div></div>
  </div><aside>
    <div class="card"><h2>Titles and captions</h2><div id="eTexts"></div><button class="small" id="eAddText" type="button">+ Add text</button></div>
    <div class="card"><h2>Music and voice tracks</h2><div id="eTracks"></div><button class="small" id="eAddTrack" type="button">+ Add track</button>
      <p class="note" style="margin:8px 0 0">Music repeats to fill the video. Voice plays once from its start time.</p></div>
    <div class="card"><h2>Export</h2>
      <div class="two"><div><label style="margin-top:0">Fade in (s)</label><input type="number" id="eFi" min="0" step="0.1"></div><div><label style="margin-top:0">Fade out (s)</label><input type="number" id="eFo" min="0" step="0.1"></div></div>
      <label>Video shape</label><select id="eSize"><option value="1920x1080">Wide 1920x1080</option><option value="1280x720">Wide 1280x720</option><option value="1080x1920">Tall 1080x1920</option></select>
      <label>Name</label><input type="text" id="eName">
      <div class="row"><button class="primary grow" id="eMake">Export video</button></div><div class="warn hidden" id="eProblem"></div>
      <div class="note" id="eTotal" style="margin-top:8px"></div></div>
    <div id="eJob"></div></aside></div>`;
  const st = ps("editor", {clips:[], texts:[], tracks:[], fade_in:0, fade_out:0, size:"1920x1080", name:"edited-video", sel:0});
  let lib = {videos:[], uploads:[], audio:[]};
  const fmt = n => (Math.round(n*10)/10).toString();
  const job = new JobPanel($("#eJob",el));

  async function loadLib(){
    lib = await api("/api/library");
    const v = [...lib.videos.map(f=>({...f,kind:"video"})), ...lib.uploads.map(f=>({...f,kind:"video"}))];
    $("#eMedia",el).innerHTML = v.map(f=>`<div class="libitem"><b title="${esc(f.name)}">${esc(f.name)}</b><button class="small" data-add="${esc(f.name)}" data-folder="${f.folder}">+ Add to timeline</button></div>`).join("")
      + lib.audio.map(f=>`<div class="libitem"><b title="${esc(f.name)}">♪ ${esc(f.name)}</b><button class="small" data-track="${esc(f.name)}">+ Add as track</button></div>`).join("")
      || '<div class="note">Nothing here yet. Make a video in another tab, or upload one.</div>';
  }
  $("#eMedia",el).onclick = async e=>{
    const b = e.target.closest("button"); if(!b) return;
    if(b.dataset.add){
      try{ const info = await api("/api/media/info?file="+encodeURIComponent(b.dataset.add));
        st.clips.push({file:b.dataset.add, folder:b.dataset.folder, start:0, end:info.duration, speed:1, duration:info.duration}); st.sel = st.clips.length-1; draw(); saveProj();
      }catch(err){ toast(err.message,true); }
    }
    if(b.dataset.track){ st.tracks.push({file:b.dataset.track, kind:"music", volume:0.3, start:0}); drawTracks(); saveProj(); }
  };
  [["#eUpVideo","#eFileV","video"],["#eUpAudio","#eFileA","audio"]].forEach(([bt,fi,kind])=>{
    $(bt,el).onclick = ()=>$(fi,el).click();
    $(fi,el).onchange = async e=>{ const f=e.target.files[0]; if(!f) return; e.target.value=""; try{ await upload(kind,f); toast("Uploaded "+f.name); loadLib(); }catch(err){ toast(err.message,true); } };
  });

  function clipLen(c){ return Math.max(0, (c.end - c.start) / (c.speed||1)); }
  function total(){ return st.clips.reduce((a,c)=>a+clipLen(c),0); }
  function draw(){
    $("#eEmpty",el).classList.toggle("hidden", st.clips.length>0);
    const T = total() || 1;
    $("#eTl",el).innerHTML = st.clips.map((c,i)=>`<div class="${i===st.sel?'sel':''}" data-i="${i}" style="flex:${Math.max(0.05,clipLen(c)/T)}" title="${esc(c.file)}">${i+1}. ${esc(c.file)}</div>`).join("");
    $("#eClips",el).innerHTML = st.clips.map((c,i)=>`<div class="clip ${i===st.sel?'sel':''}" data-i="${i}">
      <div class="top"><b>${i+1}. ${esc(c.file)}</b><span class="note">${fmt(clipLen(c))}s</span>
        <button class="small" data-a="up" ${i==0?'disabled':''}>↑</button><button class="small" data-a="down" ${i==st.clips.length-1?'disabled':''}>↓</button><button class="small ghost" data-a="del">Remove</button></div>
      <div class="fields"><div><label>Start (s)</label><input type="number" data-f="start" min="0" step="0.1" value="${fmt(c.start)}"></div>
        <div><label>End (s)</label><input type="number" data-f="end" min="0" step="0.1" value="${fmt(c.end)}"></div>
        <div><label>Speed</label><select data-f="speed">${[0.5,0.75,1,1.25,1.5,2,3].map(s=>`<option ${s==(c.speed||1)?'selected':''}>${s}</option>`).join("")}</select></div></div></div>`).join("");
    $("#eTotal",el).textContent = st.clips.length ? `Total length: about ${fmt(total())} seconds` : "";
    const c = st.clips[st.sel]; const pv = $("#ePrev",el);
    if(c){ const url = "/files/"+(c.folder||"out")+"/"+encodeURIComponent(c.file); if(!pv.src.endsWith(url)) pv.src = url; }
    check();
  }
  $("#eTl",el).onclick = e=>{ const d=e.target.closest("[data-i]"); if(d){ st.sel=+d.dataset.i; draw(); } };
  $("#eClips",el).onclick = e=>{
    const card = e.target.closest(".clip"); if(!card) return; const i=+card.dataset.i, b=e.target.closest("button");
    if(b && b.dataset.a){
      if(b.dataset.a==="del"){ st.clips.splice(i,1); st.sel=Math.max(0,Math.min(st.sel,st.clips.length-1)); }
      if(b.dataset.a==="up"){ [st.clips[i-1],st.clips[i]]=[st.clips[i],st.clips[i-1]]; st.sel=i-1; }
      if(b.dataset.a==="down"){ [st.clips[i+1],st.clips[i]]=[st.clips[i],st.clips[i+1]]; st.sel=i+1; }
    } else if(!e.target.closest("input,select")) st.sel=i;
    draw(); saveProj();
  };
  $("#eClips",el).onchange = e=>{
    const card = e.target.closest(".clip"); if(!card || !e.target.dataset.f) return;
    const c = st.clips[+card.dataset.i], f = e.target.dataset.f; c[f] = parseFloat(e.target.value) || 0; if(f==="speed") c.speed = c[f] || 1;
    c.start = Math.max(0, c.start); if(c.duration) c.end = Math.min(c.end, c.duration);
    draw(); saveProj();
  };
  const pv = $("#ePrev",el);
  pv.ontimeupdate = ()=>$("#eNow",el).textContent = "Now: "+fmt(pv.currentTime)+" s";
  $("#eSetStart",el).onclick = ()=>{ const c=st.clips[st.sel]; if(c){ c.start = Math.round(pv.currentTime*10)/10; draw(); saveProj(); } };
  $("#eSetEnd",el).onclick = ()=>{ const c=st.clips[st.sel]; if(c){ c.end = Math.round(pv.currentTime*10)/10; draw(); saveProj(); } };

  // texts
  function drawTexts(){
    $("#eTexts",el).innerHTML = st.texts.map((t,i)=>`<div class="clip" data-i="${i}"><input type="text" data-f="text" placeholder="Text on screen" value="${esc(t.text)}">
      <div class="fields"><div><label>From (s)</label><input type="number" data-f="start" min="0" step="0.1" value="${fmt(t.start||0)}"></div>
        <div><label>To (s)</label><input type="number" data-f="end" min="0" step="0.1" value="${fmt(t.end||0)}"></div>
        <div><label>Place</label><select data-f="position">${["bottom","center","top"].map(p=>`<option ${p===t.position?'selected':''}>${p}</option>`).join("")}</select></div></div>
      <div class="row"><select data-f="style" class="grow"><option value="caption" ${t.style!=='title'?'selected':''}>Caption (dark box)</option><option value="title" ${t.style==='title'?'selected':''}>Big title</option></select><button class="small ghost" data-a="del">Remove</button></div></div>`).join("");
  }
  $("#eAddText",el).onclick = ()=>{ st.texts.push({text:"",start:0,end:Math.round(total()*10)/10||3,position:"bottom",style:"caption"}); drawTexts(); saveProj(); };
  $("#eTexts",el).onchange = $("#eTexts",el).oninput = e=>{ const c=e.target.closest(".clip"); if(!c||!e.target.dataset.f) return; const f=e.target.dataset.f; st.texts[+c.dataset.i][f] = ["start","end"].includes(f)? parseFloat(e.target.value)||0 : e.target.value; saveProj(); };
  $("#eTexts",el).onclick = e=>{ const b=e.target.closest("[data-a=del]"); if(b){ st.texts.splice(+b.closest(".clip").dataset.i,1); drawTexts(); saveProj(); } };

  // tracks
  function drawTracks(){
    const files = lib.audio.map(f=>f.name);
    $("#eTracks",el).innerHTML = st.tracks.map((t,i)=>`<div class="clip" data-i="${i}">
      <select data-f="file">${files.map(f=>`<option ${f===t.file?'selected':''}>${esc(f)}</option>`).join("")||`<option>${esc(t.file)}</option>`}</select>
      <div class="fields"><div><label>Type</label><select data-f="kind"><option value="music" ${t.kind==='music'?'selected':''}>Music (repeats)</option><option value="voice" ${t.kind==='voice'?'selected':''}>Voice (once)</option></select></div>
        <div><label>Volume</label><input type="range" data-f="volume" min="0" max="1.5" step="0.05" value="${t.volume}"></div>
        <div><label>Starts at (s)</label><input type="number" data-f="start" min="0" step="0.1" value="${fmt(t.start||0)}"></div></div>
      <div class="row"><button class="small ghost" data-a="del">Remove</button></div></div>`).join("");
  }
  $("#eAddTrack",el).onclick = ()=>{ if(!lib.audio.length){ toast("Upload a music or voice file first.", true); return; } st.tracks.push({file:lib.audio[0].name, kind:"music", volume:0.3, start:0}); drawTracks(); saveProj(); };
  $("#eTracks",el).onchange = $("#eTracks",el).oninput = e=>{ const c=e.target.closest(".clip"); if(!c||!e.target.dataset.f) return; const f=e.target.dataset.f; st.tracks[+c.dataset.i][f] = ["volume","start"].includes(f)? parseFloat(e.target.value)||0 : e.target.value; saveProj(); };
  $("#eTracks",el).onclick = e=>{ const b=e.target.closest("[data-a=del]"); if(b){ st.tracks.splice(+b.closest(".clip").dataset.i,1); drawTracks(); saveProj(); } };

  [["fade_in","#eFi"],["fade_out","#eFo"],["size","#eSize"],["name","#eName"]].forEach(([k,s])=>{ const e=$(s,el); e.value=st[k]; e.oninput=e.onchange=()=>{ st[k]= e.type==="number"? parseFloat(e.value)||0 : e.value; saveProj(); }; });
  function check(){
    const msg = !st.clips.length ? "Add at least one clip to the timeline." : (App.caps && !App.caps.ffmpeg ? "FFmpeg is missing. See the badges on the left." : "");
    const w=$("#eProblem",el); w.textContent=msg; w.classList.toggle("hidden",!msg); $("#eMake",el).disabled = !!msg || $("#eMake",el).dataset.busy==="1";
  }
  $("#eMake",el).onclick = async ()=>{
    const b=$("#eMake",el); b.dataset.busy="1"; b.disabled=true;
    const out = await job.run("/api/edit/render", {clips:st.clips.map(c=>({file:c.file,start:c.start,end:c.end,speed:c.speed})), texts:st.texts, tracks:st.tracks,
      fade_in:st.fade_in, fade_out:st.fade_out, size:st.size, name:st.name});
    b.dataset.busy="0"; check(); if(out) loadLib();
  };
  document.addEventListener("capsready", check);
  loadLib().then(()=>{ draw(); drawTexts(); drawTracks(); });
  App.pages.editor.refresh = ()=>loadLib().then(()=>{ draw(); drawTracks(); });
}, onShow(){ App.pages.editor.refresh && App.pages.editor.refresh(); }});
