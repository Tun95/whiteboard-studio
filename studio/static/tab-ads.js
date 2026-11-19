registerPage("ads", {title:"App ads", sub:"Phone adverts with captions, zooms and pull-out effects.", icon:"phone", build(el){
  el.innerHTML = `<div class="grid2"><div>
      <div class="card"><h2>Your ad packs</h2><div id="aPacks"></div>
        <div class="empty" style="margin:10px 0 0;padding:18px"><div class="note" style="margin-bottom:8px">Import an ad pack (.zip) made for this app. It must contain <code>ad.json</code>, your images and screenshots.</div>
          <button class="primary" id="aImport" type="button">Import ad pack (.zip)</button><input type="file" id="aFile" accept=".zip" hidden></div></div>
      <div class="card"><h2>Coming next</h2><p class="note" style="margin:0">A guided ad builder (pick a phone colour, add screenshots, type captions, choose zoom and pull-out effects) so you do not need to edit ad.json by hand.</p></div>
    </div><aside><div class="card"><h2>Make the ad</h2>
      <div class="note" id="aSel">Choose a pack on the left.</div>
      <label>Voice for “Make voice”</label><div id="aVoice"></div>
      <label>Voice style</label><select id="aStyle"></select>
      <label class="check"><input type="checkbox" id="aMakeVoice"> Make the voice from the pack’s script (Kokoro)</label>
      <label class="check"><input type="checkbox" id="aPreview"> Quick silent preview (no voice files needed)</label>
      <label>Video shape</label><select id="aSize"><option value="">As designed in the pack</option><option value="1920x1080">Wide 16:9</option><option value="1080x1920">Tall 9:16 (Shorts, Reels)</option></select>
      <label>Only render one scene (test)</label><input type="number" id="aScene" min="1" placeholder="Leave empty for the whole ad">
      <div class="row"><button class="primary grow" id="aMake" disabled>Make ad</button></div><div class="warn hidden" id="aProblem"></div>
    </div><div id="aJob"></div></aside></div>`;
  const st = ps("ads", {style:"energetic", pack:"", makeVoice:false, preview:false, size:"", scene:""});
  const vp = voicePicker($("#aVoice",el), "ads");
  $("#aStyle",el).innerHTML = App.styles.map(s=>`<option ${s===st.style?'selected':''}>${s}</option>`).join("");
  $("#aStyle",el).onchange = ()=>{ st.style=$("#aStyle",el).value; saveProj(); };
  [["makeVoice","#aMakeVoice"],["preview","#aPreview"]].forEach(([k,s])=>{ const e=$(s,el); e.checked=!!st[k]; e.onchange=()=>{st[k]=e.checked;saveProj();check();}; });
  [["size","#aSize"],["scene","#aScene"]].forEach(([k,s])=>{ const e=$(s,el); e.value=st[k]; e.oninput=e.onchange=()=>{st[k]=e.value;saveProj();}; });
  const job = new JobPanel($("#aJob",el)); let packs = [];
  async function load(){
    packs = (await api("/api/library")).packs;
    if(!packs.find(p=>p.name===st.pack)) st.pack = packs[0] ? packs[0].name : "";
    $("#aPacks",el).innerHTML = packs.map(p=>`<div class="pack ${p.name===st.pack?'sel':''}" data-n="${esc(p.name)}"><b>${esc(p.name)}</b>
      ${p.has_voice?'<span class="tag">voice ready</span>':''}${p.has_preview?'<span class="tag">preview</span>':''} <button class="del small" data-del="${esc(p.name)}" type="button">Delete</button></div>`).join("") || '<div class="note">No ad packs yet. Import one below.</div>';
    check();
  }
  function check(){
    const p = packs.find(x=>x.name===st.pack); let msg = "";
    if(!p) msg = "Import and choose an ad pack first.";
    else if(st.makeVoice && !st.preview && p && !p.has_script) msg = "This pack has no voice script.";
    else if(st.makeVoice && !st.preview && App.caps && !App.caps.kokoro) msg = "Kokoro voice is not installed. Untick “Make the voice” or use the quick preview.";
    else if(!st.makeVoice && !st.preview && p && !p.has_voice) msg = "This pack has no voice files yet. Tick “Make the voice”, or use the quick silent preview.";
    $("#aSel",el).textContent = p ? "Selected: "+p.name : "Choose a pack on the left.";
    const w=$("#aProblem",el); w.textContent=msg; w.classList.toggle("hidden",!msg);
    $("#aMake",el).disabled = !!msg || $("#aMake",el).dataset.busy==="1";
  }
  $("#aPacks",el).addEventListener("click", async e=>{ const d=e.target.closest("[data-del]"); if(!d) return; e.stopImmediatePropagation();
    if(await deleteItem("pack", d.dataset.del, "The ad pack “"+d.dataset.del+"”")){ if(st.pack===d.dataset.del) st.pack=""; saveProj(); load(); } }, true);
  $("#aPacks",el).onclick = e=>{ const c=e.target.closest(".pack"); if(c){ st.pack=c.dataset.n; saveProj(); load(); } };
  $("#aImport",el).onclick = ()=>$("#aFile",el).click();
  $("#aFile",el).onchange = async e=>{
    const f=e.target.files[0]; if(!f) return; e.target.value="";
    try{ const r = await upload("adpack", f); st.pack = r.pack; saveProj(); toast("Imported: "+r.pack); await load(); }catch(err){ toast(err.message,true); }
  };
  $("#aMake",el).onclick = async ()=>{
    const b=$("#aMake",el); b.dataset.busy="1"; b.disabled=true;
    await job.run("/api/ads/render", {pack:st.pack, preview:st.preview, make_voice:st.makeVoice, voice:vp.get(), style:st.style, size:st.size, scene:st.scene});
    b.dataset.busy="0"; load();
  };
  document.addEventListener("capsready", check);
  load();
}, onShow(){}});
