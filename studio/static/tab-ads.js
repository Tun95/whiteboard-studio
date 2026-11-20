registerPage("ads", {title:"App ads", sub:"Make an advert for your app: a phone, your screenshots, captions and a voice. No files to edit.", icon:"phone", build(el){
  const PHONES = [["black","Black","#0b0b0f"],["white","White","#f4f4f6"],["blue","Blue","#1d3a8a"],["red","Red","#9b1c2e"],["gold","Gold","#8a6a1d"],["green","Green","#14532d"]];
  const LOOKS = [["purple","Purple","#2b1055","#7c3aed"],["ocean","Ocean","#06223f","#0e7490"],["sunset","Sunset","#4a1030","#f97316"],["forest","Forest","#052e1a","#16a34a"],["night","Night","#0b0b12","#2a2f4a"],["light","Light","#e8eefc","#ffffff"]];
  const FX = [["none","Nothing"],["sparkle","Sparkles"],["confetti","Confetti"],["rise","Rising bubbles"],["coins","Coins"]];
  const MOTION = [["none","Stay still"],["zoom","Slowly zoom in"],["pan","Slowly slide sideways"]];
  const STEPS = ["Your ad","Screenshots","Scenes","Voice & music","Make it"];
  const blank = () => ({name:"", phone:"black", look:"purple", size:"1920x1080", music:"", music_volume:0.1, scenes:[
    {headline:"Meet *your app*", sub:"", shot:"", side:"right", box:null, pullout:false, effect:"sparkle", motion:"zoom", voice:"", seconds:5, badge:false},
    {headline:"Show your *best feature*", sub:"Short and simple", shot:"", side:"right", box:null, pullout:true, effect:"none", motion:"zoom", voice:"", seconds:6, badge:false},
    {headline:"Download it *free* today", sub:"", shot:"", side:"left", box:null, pullout:false, effect:"confetti", motion:"zoom", voice:"", seconds:5, badge:true}]});
  const st = ps("ads", {pack:"", step:0, view:"list", makeVoice:true, preview:false, style:"energetic", sel:0});
  const d = App.proj.adDraft = Object.assign(blank(), App.proj.adDraft || {});
  let lib = {images:[], screenshots:[], audio:[], packs:[]};
  el.innerHTML = `<div id="aList"></div><div id="aBuild" class="hidden"></div>`;
  const job = {};

  const imgUrl = n => "/files/" + ((lib.screenshots||[]).some(i=>i.name===n) ? "screenshots" : "images") + "/" + encodeURIComponent(n);
  const save = () => saveProj();
  async function loadLib(){ lib = await api("/api/library"); }

  /* ------------------------------------------------------------ my ads (start page) */
  const draftWorth = ()=> !!((d.name||"").trim() || (d.scenes||[]).some(s=>(s.headline||"").trim()&&!/^(Meet \*your app\*|Show your \*best feature\*|Download it \*free\* today)$/.test(s.headline) || s.shot || (s.voice||"").trim()));
  function renderList(){
    $("#aList",el).classList.remove("hidden"); $("#aBuild",el).classList.add("hidden");
    const packs = lib.packs;
    $("#aList",el).innerHTML = `<div class="grid2"><div>
      ${draftWorth()?`<div class="card" style="border-color:var(--accent)"><h2>Unfinished ad</h2><p class="note" style="margin-top:0">You were making “${esc(d.name||"an ad with no name yet")}”. It was saved automatically.</p>
        <div class="row"><button class="primary" id="aCont" type="button">Continue this ad</button></div></div>`:''}
      <div class="card"><h2>Make a new ad</h2>
        <p class="note" style="margin-top:0">Pick a phone colour, add your screenshots, type a few short lines and the app builds the advert for you. Takes about 5 minutes.</p>
        <button class="primary" id="aNew" type="button">＋ Make a new ad</button></div>
      <div class="card"><h2>Your ads</h2>
        ${packs.map(p=>`<div class="pack ${p.name===st.pack?'sel':''}" data-n="${esc(p.name)}"><b>${esc(p.name)}</b>
          ${p.has_voice?'<span class="tag">voice ready</span>':''}
          ${p.editable?`<button data-edit="${esc(p.name)}" type="button">Change it</button>`:''}<button class="del" data-delpack="${esc(p.name)}" type="button">Delete</button></div>`).join("") || '<div class="note">You have no ads yet. Press “Make a new ad”.</div>'}
        <details style="margin-top:12px"><summary class="note" style="cursor:pointer">I already have a ready-made ad file (.zip)</summary>
          <div class="note" style="margin:8px 0">Only for ads somebody else made for this app. Most people do not need this.</div>
          <button id="aImport" type="button">Add an ad file (.zip)</button><input type="file" id="aFile" accept=".zip" hidden></details>
      </div></div><aside><div class="card"><h2>Make the video</h2><div id="aMakeBox"></div></div><div id="aJob"></div></aside></div>`;
    mountMake($("#aMakeBox",el), false);
    job.panel = new JobPanel($("#aJob",el));
    const ac = $("#aCont",el); if(ac) ac.onclick = ()=>{ st.view = "build"; save(); go2(); };
    $("#aNew",el).onclick = async ()=>{ if(draftWorth() && !await confirmBox("Start a new ad?", "Your unfinished ad “"+(d.name||"no name yet")+"” will be replaced. Press Continue on the start page if you want to keep working on it.", "Start new")) return;
      Object.keys(d).forEach(k=>delete d[k]); Object.assign(d, blank()); st.step = 0; st.sel = 0; st.view = "build"; save(); go2(); };
    $("#aImport",el).onclick = ()=>$("#aFile",el).click();
    $("#aFile",el).onchange = async e=>{ const f=e.target.files[0]; if(!f) return; e.target.value="";
      try{ const r = await upload("adpack", f); st.pack = r.pack; save(); toast("Added: "+r.pack); await loadLib(); renderList(); }catch(err){ reportError(err); } };
    $("#aList",el).onclick = async e=>{
      const dl = e.target.closest("[data-delpack]");
      if(dl){ e.stopPropagation(); const n = dl.dataset.delpack;
        if(await confirmBox("Delete this ad?", `“${n}” and all its files will be removed from your computer. This cannot be undone.`)){
          try{ await post("/api/ads/delete", {name:n}); toast("Deleted "+n); if(st.pack===n) st.pack=""; save(); await loadLib(); renderList(); }catch(err){ reportError(err); } }
        return; }
      const ed = e.target.closest("[data-edit]");
      if(ed){ e.stopPropagation(); try{ const spec = await api("/api/ads/spec?name="+encodeURIComponent(ed.dataset.edit));
          Object.keys(d).forEach(k=>delete d[k]); Object.assign(d, blank(), spec); st.step = 0; st.sel = 0; st.view = "build"; save(); go2(); }catch(err){ reportError(err); } return; }
      const c = e.target.closest(".pack"); if(c){ st.pack = c.dataset.n; save(); renderList(); } };
  }

  /* ------------------------------------------------------------ the "Make" box (used by the start page and the last step) */
  function anyVoice(){ return (d.scenes||[]).some(s=>(s.voice||"").trim()); }
  function mountMake(box, fromWizard){
    box.innerHTML = `<div class="note" id="aSel"></div>
      <div id="aVoiceBox"><label>Voice</label><div id="aVoice"></div><label>How the voice sounds</label><select id="aStyle"></select></div>
      <label class="check"><input type="checkbox" id="aPreview"> Quick preview without the voice (faster)</label>
      <div class="row"><button class="primary grow" id="aMake" type="button">Make the video</button></div><div class="warn hidden" id="aProblem"></div>`;
    const vp = voicePicker($("#aVoice",box), "ads");
    $("#aStyle",box).innerHTML = App.styles.map(s=>`<option ${s===st.style?'selected':''}>${s}</option>`).join("");
    $("#aStyle",box).onchange = e=>{ st.style = e.target.value; save(); };
    const pv = $("#aPreview",box); pv.checked = !!st.preview; pv.onchange = ()=>{ st.preview = pv.checked; save(); check(); };
    function target(){ return fromWizard ? (d.name||"").trim() : st.pack; }
    function check(){
      const p = lib.packs.find(x=>x.name===st.pack); let msg = "";
      if(fromWizard){ if(!(d.scenes||[]).length) msg = "Add at least one scene first."; }
      else if(!p) msg = "Choose one of your ads first.";
      const needVoice = fromWizard ? (anyVoice() && !st.preview) : (p && p.has_script && !p.has_voice && !st.preview);
      if(!msg && needVoice && App.caps && !App.caps.kokoro) msg = "The AI voice is not ready on this computer yet. Tick “Quick preview”, or remove the words in “What the voice says”.";
      if(!msg && !fromWizard && p && !p.has_voice && p.has_script && st.preview === false && !(App.caps && App.caps.kokoro)) msg = "This ad needs the AI voice, which is not ready yet. Tick “Quick preview”.";
      $("#aSel",box).textContent = fromWizard ? "This will make: "+(d.name||"your ad") : (p ? "Selected: "+p.name : "");
      $("#aVoiceBox",box).classList.toggle("hidden", fromWizard ? !anyVoice() : !(p && p.has_script));
      const w=$("#aProblem",box); w.textContent=msg; w.classList.toggle("hidden",!msg);
      $("#aMake",box).disabled = !!msg || $("#aMake",box).dataset.busy==="1";
    }
    $("#aMake",box).onclick = async ()=>{
      const b=$("#aMake",box); b.dataset.busy="1"; b.disabled=true;
      try{
        let name = st.pack;
        if(fromWizard){ name = (await post("/api/ads/save", d)).name; st.pack = name; save(); }
        const p = lib.packs.find(x=>x.name===name);
        const mv = fromWizard ? anyVoice() : !!(p && p.has_script);
        await job.panel.run("/api/ads/render", {pack:name, preview:st.preview, make_voice:mv && !st.preview, voice:vp.get(), style:st.style, size:"", scene:""});
      }catch(err){ reportError(err); }
      b.dataset.busy="0"; await loadLib(); check();
    };
    document.addEventListener("capsready", check);
    check();
    return check;
  }

  /* ------------------------------------------------------------ the guided builder */
  function go2(){ if(st.view==="build") renderBuild(); else renderList(); }
  function renderBuild(){
    $("#aList",el).classList.add("hidden"); const root = $("#aBuild",el); root.classList.remove("hidden");
    root.innerHTML = `<div class="card adsteps"><button id="aBack2List" type="button" class="small">← My ads</button>
      ${STEPS.map((s,i)=>`<button type="button" class="adstep ${i===st.step?'on':''} ${i<st.step?'done':''}" data-step="${i}"><i>${i+1}</i> ${s}</button>`).join("")}</div>
      <div id="aStep"></div>
      <div class="row" style="justify-content:space-between;margin:6px 0 24px"><button id="aPrev" type="button" ${st.step===0?'disabled':''}>← Back</button>
        <button id="aNext" class="primary" type="button" ${st.step===STEPS.length-1?'hidden':''}>Next →</button></div>`;
    $("#aBack2List",root).onclick = async ()=>{ st.view="list"; save(); await loadLib(); renderList(); };
    root.querySelectorAll("[data-step]").forEach(b=>b.onclick=()=>{ st.step=+b.dataset.step; save(); renderBuild(); });
    $("#aPrev",root).onclick = ()=>{ st.step=Math.max(0,st.step-1); save(); renderBuild(); window.scrollTo(0,0); };
    $("#aNext",root).onclick = ()=>{ if(st.step===0 && !(d.name||"").trim()){ toast("Please type a name for your ad first.", true); $("#aName",root).focus(); return; } st.step=Math.min(STEPS.length-1,st.step+1); save(); renderBuild(); window.scrollTo(0,0); };
    [step1,step2,step3,step4,step5][st.step]($("#aStep",root));
  }

  function step1(box){
    box.innerHTML = `<div class="card"><h2>1. About your ad</h2>
      <label style="margin-top:0">Name of the ad</label><input type="text" id="aName" maxlength="60" placeholder="For example: My Game Ad" value="${esc(d.name||"")}">
      <label>Phone colour</label><div class="swatches" id="aPhones">${PHONES.map(([k,n,c])=>`<button type="button" class="sw ${d.phone===k?'on':''}" data-k="${k}" title="${n}"><span style="background:${c}"></span>${n}</button>`).join("")}</div>
      <label>Background colours</label><div class="swatches" id="aLooks">${LOOKS.map(([k,n,a,b])=>`<button type="button" class="sw ${d.look===k?'on':''}" data-k="${k}" title="${n}"><span style="background:linear-gradient(135deg,${a},${b})"></span>${n}</button>`).join("")}</div>
      <label>Video shape</label><div class="swatches" id="aShape">
        <button type="button" class="sw wide ${d.size==="1920x1080"?'on':''}" data-k="1920x1080"><span class="shp w"></span>Wide · YouTube</button>
        <button type="button" class="sw wide ${d.size==="1080x1920"?'on':''}" data-k="1080x1920"><span class="shp t"></span>Tall · Reels, Shorts, TikTok, Status</button></div>
      <div class="note" style="margin-top:8px">You can change all of this later.</div></div>`;
    $("#aName",box).oninput = e=>{ d.name = e.target.value; save(); };
    [["#aPhones","phone"],["#aLooks","look"],["#aShape","size"]].forEach(([s,k])=>$(s,box).onclick = e=>{ const b=e.target.closest("[data-k]"); if(!b) return; d[k]=b.dataset.k; save(); step1(box); });
  }

  function step2(box){
    const imgs = lib.screenshots;
    box.innerHTML = `<div class="card"><h2>2. Your screenshots</h2>
      <p class="note" style="margin-top:0">Add screenshots from your app. Take them on your phone and send them to this computer. Tall pictures look best.</p>
      <div class="shotgrid">${imgs.map(i=>`<div class="shotc"><img src="${imgUrl(i.name)}" alt=""><span>${esc(i.name)}</span><button type="button" class="del" data-del="${esc(i.name)}">Remove</button></div>`).join("") || '<div class="note">No pictures yet.</div>'}</div>
      <div class="row" style="margin-top:12px"><button class="primary" id="aAddShots" type="button">＋ Add screenshots</button><input type="file" id="aShots" accept=".png,.jpg,.jpeg" multiple hidden></div>
      <div class="note" style="margin-top:8px">These screenshots are only used for ads in this project. Your Editor pictures are kept separate.</div></div>`;
    $("#aAddShots",box).onclick = ()=>$("#aShots",box).click();
    $("#aShots",box).onchange = async e=>{ const fs=[...e.target.files]; e.target.value="";
      for(const f of fs){ try{ await upload("shot", f); }catch(err){ reportError(err); } }
      await loadLib(); step2(box); };
    box.onclick = async e=>{ const b=e.target.closest("[data-del]"); if(!b) return;
      if(await deleteMedia("screenshots", b.dataset.del)){ (d.scenes||[]).forEach(s=>{ if(s.shot===b.dataset.del){ s.shot=""; s.box=null; } }); save(); await loadLib(); step2(box); } };
  }

  function step3(box){
    const sc = d.scenes; if(st.sel>=sc.length) st.sel = Math.max(0, sc.length-1);
    const s = sc[st.sel]; const tall = d.size==="1080x1920";
    const opts = (list,cur)=>list.map(([k,n])=>`<option value="${k}" ${k===(cur||list[0][0])?'selected':''}>${n}</option>`).join("");
    box.innerHTML = `<div class="adscenes"><div class="card adlist"><h2>Scenes</h2>
        ${sc.map((x,i)=>`<div class="adsc ${i===st.sel?'on':''}" data-i="${i}" draggable="true" title="Drag to change the order"><span class="grip">⋮⋮</span><i>${i+1}</i><span>${esc((x.headline||"(empty)").replace(/\*/g,""))}</span></div>`).join("")}
        <button type="button" id="aAddSc" class="small" style="margin-top:8px">＋ Add a scene</button></div>
      <div class="card adedit"><h2>Scene ${st.sel+1}</h2>
        <div class="adprev ${tall?'tall':''} look-${d.look}" id="aPrev2"></div>
        <label>Big words on the screen</label><input type="text" id="sHead" maxlength="80" value="${esc(s.headline||"")}" placeholder="For example: Meet *Quiz Master*">
        <div class="note">Put a star on each side of a word to make it stand out in colour: <b>*free*</b></div>
        <label>Smaller words (optional)</label><input type="text" id="sSub" maxlength="80" value="${esc(s.sub||"")}">
        <label>Which screenshot goes on the phone?</label>
        <div class="shotpick"><button type="button" class="${!s.shot?'on':''}" data-shot="">No phone</button>${lib.screenshots.map(i=>`<button type="button" class="${s.shot===i.name?'on':''}" data-shot="${esc(i.name)}" title="${esc(i.name)}"><img src="${imgUrl(i.name)}" alt=""></button>`).join("")}</div>
        ${lib.screenshots.length?'':'<div class="note">Add screenshots in step 2 first.</div>'}
        ${s.shot?`<div class="two"><div><label>Where is the phone?</label><select id="sSide" ${tall?'disabled':''}>${tall?'<option>In the middle (tall videos)</option>':opts([["right","On the right"],["left","On the left"],["center","In the middle"]],s.side)}</select></div>
        <div><label>Pull a part out of the phone?</label><select id="sPull"><option value="0" ${!s.pullout?'selected':''}>No, just glow</option><option value="1" ${s.pullout?'selected':''}>Yes, float it out</option></select></div></div>
        <label>Show off one part of the screen (optional)</label>
        <div class="note" style="margin:0 0 6px">Drag on the picture to draw a box around the part you want people to notice.</div>
        <div class="boxwrap"><div class="shotbox" id="sBox"><img src="${imgUrl(s.shot)}" alt="" draggable="false"><div class="bx ${s.box?'':'hidden'}" id="sBx"></div></div>
          <button type="button" class="small" id="sClearBox" ${s.box?'':'disabled'}>Clear the box</button></div>`:''}
        <div class="two"><div><label>Extra effect</label><select id="sFx">${opts(FX,s.effect)}</select></div><div><label>Camera</label><select id="sMotion">${opts(MOTION,s.motion)}</select></div></div>
        <label>What the voice says (optional)</label><textarea id="sVoice" rows="3" placeholder="Write it like you speak. Leave empty for no voice in this scene.">${esc(s.voice||"")}</textarea>
        <div class="two"><div><label>How many seconds (when there is no voice)</label><input type="number" id="sSecs" min="2" max="30" value="${s.seconds||5}"></div>
          <div><label class="check" style="margin-top:28px"><input type="checkbox" id="sBadge" ${s.badge?'checked':''}> Show “Get it on Google Play”</label></div></div>
        <div class="row" style="margin-top:14px"><button type="button" class="small" id="sUp" ${st.sel===0?'disabled':''}>↑ Move up</button><button type="button" class="small" id="sDown" ${st.sel===sc.length-1?'disabled':''}>↓ Move down</button>
          <button type="button" class="small" id="sDup">⧉ Copy this scene</button><button type="button" class="small del" id="sDel" ${sc.length<2?'disabled':''}>Delete this scene</button></div>
      </div></div>`;
    const prev = ()=>{ // simple picture of how the scene will be laid out
      const pv = $("#aPrev2",box); const L = tall ? "center" : (s.shot ? (s.side||"right") : "center");
      const hd = (s.headline||"").replace(/\*([^*]+)\*/g,"<b>$1</b>"), sb = (s.sub||"").replace(/\*([^*]+)\*/g,"<b>$1</b>");
      const ph = PHONES.find(p=>p[0]===d.phone)||PHONES[0];
      pv.innerHTML = `<div class="pcap ${L}">${hd?`<div class="p1">${hd}</div>`:''}${sb?`<div class="p2">${sb}</div>`:''}${s.badge?'<div class="p3">Get it on Google Play</div>':''}</div>
        ${s.shot?`<div class="pph ${L}" style="border-color:${ph[2]}"><img src="${imgUrl(s.shot)}" alt=""></div>`:''}`;
    };
    prev();
    const set = (k,v)=>{ s[k]=v; save(); };
    $("#sHead",box).oninput = e=>{ set("headline",e.target.value); prev(); box.querySelector(".adsc.on span:not(.grip)").textContent = (e.target.value||"(empty)").replace(/\*/g,""); };
    $("#sSub",box).oninput = e=>{ set("sub",e.target.value); prev(); };
    $("#sVoice",box).oninput = e=>set("voice",e.target.value);
    $("#sSecs",box).oninput = e=>set("seconds",+e.target.value||5);
    $("#sFx",box).onchange = e=>set("effect",e.target.value);
    $("#sMotion",box).onchange = e=>set("motion",e.target.value);
    $("#sBadge",box).onchange = e=>{ set("badge",e.target.checked); prev(); };
    if(s.shot){
      $("#sSide",box).onchange = e=>{ set("side",e.target.value); prev(); };
      $("#sPull",box).onchange = e=>set("pullout",e.target.value==="1");
      const sb = $("#sBox",box), bx = $("#sBx",box), im = sb.querySelector("img");
      const showBox = ()=>{ if(!s.box){ bx.classList.add("hidden"); return; } bx.classList.remove("hidden");
        Object.assign(bx.style,{left:s.box[0]*100+"%",top:s.box[1]*100+"%",width:(s.box[2]-s.box[0])*100+"%",height:(s.box[3]-s.box[1])*100+"%"}); };
      showBox();
      let a=null;
      const pt = e=>{ const r=im.getBoundingClientRect(); return [Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)), Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))]; };
      sb.onpointerdown = e=>{ e.preventDefault(); a=pt(e); sb.setPointerCapture(e.pointerId); };
      sb.onpointermove = e=>{ if(!a) return; const b=pt(e); s.box=[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0]),Math.max(a[1],b[1])]; showBox(); };
      sb.onpointerup = e=>{ if(!a) return; a=null; if(s.box && (s.box[2]-s.box[0]<0.03 || s.box[3]-s.box[1]<0.02)) s.box=null; save(); step3(box); };
      $("#sClearBox",box).onclick = ()=>{ s.box=null; save(); step3(box); };
    }
    box.querySelectorAll("[data-shot]").forEach(b=>b.onclick=()=>{ s.shot=b.dataset.shot; s.box=null; save(); step3(box); });
    box.querySelectorAll(".adsc").forEach(b=>b.onclick=()=>{ st.sel=+b.dataset.i; save(); step3(box); });
    let from = -1;   // drag a scene up or down to change the order
    box.querySelectorAll(".adsc").forEach(b=>{
      b.ondragstart = e=>{ from = +b.dataset.i; b.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; try{ e.dataTransfer.setData("text/plain", String(from)); }catch(_){} };
      b.ondragend = ()=>{ b.classList.remove("drag"); box.querySelectorAll(".adsc.over").forEach(x=>x.classList.remove("over")); };
      b.ondragover = e=>{ if(from<0) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; b.classList.add("over"); };
      b.ondragleave = ()=>b.classList.remove("over");
      b.ondrop = e=>{ e.preventDefault(); const to = +b.dataset.i; if(from<0 || from===to) return;
        const keep = sc[st.sel]; const [m] = sc.splice(from,1); sc.splice(to,0,m); st.sel = sc.indexOf(keep); from = -1; save(); step3(box); };
    });
    $("#aAddSc",box).onclick = ()=>{ sc.push({headline:"", sub:"", shot:"", side:"right", box:null, pullout:false, effect:"none", motion:"zoom", voice:"", seconds:5, badge:false}); st.sel=sc.length-1; save(); step3(box); };
    $("#sUp",box).onclick = ()=>{ [sc[st.sel-1],sc[st.sel]]=[sc[st.sel],sc[st.sel-1]]; st.sel--; save(); step3(box); };
    $("#sDown",box).onclick = ()=>{ [sc[st.sel+1],sc[st.sel]]=[sc[st.sel],sc[st.sel+1]]; st.sel++; save(); step3(box); };
    $("#sDup",box).onclick = ()=>{ sc.splice(st.sel+1,0,JSON.parse(JSON.stringify(s))); st.sel++; save(); step3(box); };
    $("#sDel",box).onclick = async ()=>{ if(await confirmBox("Delete this scene?", "The scene will be removed from your ad.")){ sc.splice(st.sel,1); save(); step3(box); } };
  }

  function step4(box){
    box.innerHTML = `<div class="card"><h2>4. Voice and music</h2>
      <p class="note" style="margin-top:0">The voice is made by a computer (AI voice), not a real person. You choose it in the last step, where you can listen to each voice first.
      ${anyVoice()?'<b>Your scenes have words for the voice.</b>':'None of your scenes has words for the voice yet. Type them under “What the voice says” in step 3, or make the ad with music only.'}</p>
      <label>Background music (optional)</label>
      <select id="aMusic"><option value="">No music</option>${lib.audio.map(a=>`<option value="${esc(a.name)}" ${d.music===a.name?'selected':''}>${esc(a.name)}</option>`).join("")}</select>
      <div class="row" style="margin-top:8px"><button type="button" id="aAddMusic" class="small">＋ Add a music file</button><input type="file" id="aMusicF" accept=".wav,.mp3,.m4a,.ogg,.flac" hidden></div>
      <label>Music loudness</label><div class="row"><input type="range" id="aMVol" min="0" max="40" value="${Math.round((d.music_volume??0.1)*100)}" style="flex:1"><span class="note" id="aMVolT"></span></div>
      <div class="note">Use music you are allowed to use. Quiet music (about 10%) lets the voice be heard.</div></div>`;
    const t=()=>{ $("#aMVolT",box).textContent = Math.round(d.music_volume*100)+"%"; }; t();
    $("#aMusic",box).onchange = e=>{ d.music=e.target.value; save(); };
    $("#aMVol",box).oninput = e=>{ d.music_volume=e.target.value/100; save(); t(); };
    $("#aAddMusic",box).onclick = ()=>$("#aMusicF",box).click();
    $("#aMusicF",box).onchange = async e=>{ const f=e.target.files[0]; if(!f) return; e.target.value="";
      try{ const r = await upload("audio", f); d.music=r.name; save(); await loadLib(); step4(box); }catch(err){ reportError(err); } };
  }

  function step5(box){
    const sc = d.scenes, tall = d.size==="1080x1920";
    const probs = [];
    sc.forEach((s,i)=>{ if(!(s.headline||"").trim() && !s.shot) probs.push(`Scene ${i+1} is empty.`); });
    if(!(d.name||"").trim()) probs.push("Your ad has no name (step 1).");
    box.innerHTML = `<div class="grid2"><div class="card"><h2>5. Ready to make it</h2>
        <div class="note" style="margin-top:0">${esc(d.name||"Your ad")} · ${tall?'Tall video':'Wide video'} · ${sc.length} scene${sc.length===1?'':'s'}${d.music?' · with music':''}${anyVoice()?' · with an AI voice':''}</div>
        <ol class="adsum">${sc.map(s=>`<li>${esc((s.headline||"(no words)").replace(/\*/g,""))}${s.shot?' <span class="tag">phone</span>':''}${s.voice?' <span class="tag">voice</span>':''}</li>`).join("")}</ol>
        ${probs.length?`<div class="warn">${probs.map(esc).join("<br>")}</div>`:''}
        <p class="note">Tip: first make the quick preview (no voice). If it looks right, untick it and make the real video.</p></div>
      <aside><div class="card"><h2>Make the video</h2><div id="aMakeBox"></div></div><div id="aJob"></div></aside></div>`;
    job.panel = new JobPanel($("#aJob",box));
    mountMake($("#aMakeBox",box), true);
    if(probs.length) $("#aMake",box).disabled = true;
  }

  (async()=>{ await loadLib(); if(!lib.packs.find(p=>p.name===st.pack)) st.pack = lib.packs[0] ? lib.packs[0].name : ""; go2(); })();
}, onShow(){}});
