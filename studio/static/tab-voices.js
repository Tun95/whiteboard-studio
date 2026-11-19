registerPage("voices", {title:"Voices", sub:"Listen to every AI voice, then pick your favourite.", icon:"mic", build(el){
  el.innerHTML = `<div class="card"><div class="filters">
      <input type="search" id="vqSearch" placeholder="Search voices (name or id)…">
      <select id="vqGroup"><option value="">All languages</option></select>
      <select id="vqGender"><option value="">Any gender</option><option value="female">Female</option><option value="male">Male</option></select></div>
    <label style="margin-top:0">Try your own sentence (optional)</label>
    <input type="text" id="vqText" placeholder="Leave empty to use a standard sample sentence in each voice’s language">
    <div class="row" style="margin-top:8px"><button type="button" id="vqClear" class="del small">Clear saved samples</button><button type="button" id="vqJa" class="small hidden">Install Japanese voice support</button><button type="button" id="vqZh" class="small hidden">Install Mandarin voice support</button></div>
    <p class="note" style="margin:8px 0 0">The first time you listen to a voice it takes a few seconds to make the sample. After that it plays instantly. <b>Default voice:</b> <span id="vqDefault"></span></p>
    <div class="warn hidden" id="vqWarn">Kokoro is not installed here, so previews are off. You can still choose a default voice.</div></div>
    <div class="vgrid" id="vqGrid"></div>`;
  const groups = [...new Set(App.voices.map(v=>v.group))];
  $("#vqGroup",el).innerHTML += groups.map(g=>`<option>${esc(g)}</option>`).join("");
  function draw(){
    const q = $("#vqSearch",el).value.toLowerCase(), g = $("#vqGroup",el).value, gd = $("#vqGender",el).value, def = defaultVoice();
    $("#vqDefault",el).textContent = def;
    $("#vqWarn",el).classList.toggle("hidden", !(App.caps && !App.caps.kokoro));
    $("#vqGrid",el).innerHTML = App.voices.filter(v=>(!q||(v.name+v.id).toLowerCase().includes(q))&&(!g||v.group===g)&&(!gd||v.gender===gd)).map(v=>`
      <div class="vcard ${v.id===def?'def':''}" data-id="${v.id}"><b>${esc(v.name)}</b><div class="meta">${v.id}</div>
        <span class="tag">${v.gender}</span><span class="tag">${esc(v.group.split(",")[0])}</span>
        <div class="row"><button class="play" data-act="listen">▶ Listen</button><button class="small" data-act="use">${v.id===def?'★ Default':'Use'}</button></div></div>`).join("");
  }
  ["input","change"].forEach(ev=>["#vqSearch","#vqGroup","#vqGender"].forEach(s=>$(s,el).addEventListener(ev,draw)));
  $("#vqGrid",el).onclick = e=>{
    const b = e.target.closest("button"); if(!b) return; const id = b.closest(".vcard").dataset.id;
    if(b.dataset.act==="listen") listen(id, b, $("#vqText",el).value);
    if(b.dataset.act==="use"){ App.proj.voice = {default:id}; saveProj(); draw(); toast("Default voice: "+id); }
  };
  document.addEventListener("capsready", draw); draw();
}});

(function(){
  const t = setInterval(async ()=>{
    const el = document.getElementById("page-voices"); const c = el && el.querySelector("#vqClear"); if(!c) return; clearInterval(t);
    c.onclick = async ()=>{ if(await deleteItem("samples","all","All saved voice samples")) toast("Samples cleared. They will be made again when you listen."); };
    const st = await api("/api/voice/languages").catch(()=>null); if(!st) return;
    for(const [code,id,label] of [["j","vqJa","Japanese"],["z","vqZh","Mandarin"]]){
      const b = el.querySelector("#"+id); if(st[code]) continue; b.classList.remove("hidden");
      b.onclick = ()=>{ const h = {title:"", explain:"", fix:"", details:"", action:{type:"install_lang", lang:code, label:"Install "+label+" voice support"}};
        const card = problemCard({title:label+" voice support", explain:"Adds the "+label+" voices. Needs internet, one time only.", fix:"Click the button and wait.", details:"", action:h.action}); b.after(card); b.remove(); };
    }
  }, 500);
})();
