registerPage("doodle", {title:"Doodle pictures", sub:"Describe a picture in your own words and the app draws it as a whiteboard doodle. Free, private, and works without internet after set-up.", icon:"spark", build(el){
  el.innerHTML = `
  <div class="card hidden" id="dSetup"><h2>One-time set-up</h2>
    <p class="note" style="margin-top:0">The picture maker is free, open-source AI (Z-Image Turbo, Apache-2.0) that runs on this computer. Nothing is sent anywhere and there is nothing to sign up for. It needs a one-time download. After that it works without internet.</p>
    <div class="two"><div><label style="margin-top:0">Version</label><select id="dQual"></select></div>
      <div><label style="margin-top:0">Good to know</label><p class="note" style="margin:0">Needs about <b>8 GB of free memory</b>. On a normal computer a picture takes a few minutes. A computer with a graphics card is quicker.</p></div></div>
    <div class="row"><button class="primary" id="dInstall" type="button">Set up the picture maker</button><button id="dInstCancel" type="button" class="hidden">✕ Cancel</button></div>
    <div class="note" id="dInstState"></div><div class="bar hidden" id="dInstBar"><i></i></div><div class="perr hidden" id="dInstErr"></div></div>
  <div class="card" id="dMain"><label style="margin-top:0">What should the picture show?</label>
    <textarea id="dPrompt" rows="3" maxlength="600" placeholder="For example: a happy family eating together at a table"></textarea>
    <div class="chips" id="dEx"></div>
    <div class="two"><div><label>Style</label><select id="dStyle"></select></div><div><label>Shape</label><select id="dShape"></select></div></div>
    <div class="two"><div><label>How many pictures</label><select id="dCount"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></div><div></div></div>
    <div class="row"><button class="primary" id="dMake" type="button">Draw the picture</button><button id="dCancel" type="button" class="hidden">✕ Cancel</button></div>
    <div class="note" id="dState"></div><div class="bar hidden" id="dBar"><i></i></div><div class="perr hidden" id="dErr"></div>
    <p class="note" style="margin:8px 0 0">Tip: describe one clear thing, in simple words. Pictures are saved in <b>Pictures</b> of this project, so you can use them in Whiteboard video, the Editor and App ads.</p></div>
  <div class="card"><h2>Your doodles</h2><div class="lib" id="dGrid"></div></div>`;
  const st = ps("doodle", {prompt:"", style:"whiteboard", shape:"square", count:"1", quality:"standard"});
  const $d = s => $(s, el); let info = null;
  const EX = ["a lighthouse on a hill", "a happy family eating together", "a person climbing stairs to success", "a light bulb with an idea", "a farmer planting seeds"];
  $d("#dEx").innerHTML = EX.map(e=>`<button type="button" class="exchip" data-e="${esc(e)}">${esc(e)}</button>`).join("");
  $d("#dEx").onclick = e=>{ const b = e.target.closest("[data-e]"); if(b){ $d("#dPrompt").value = b.dataset.e; keep(); } };
  const keep = ()=>{ st.prompt = $d("#dPrompt").value; st.style = $d("#dStyle").value; st.shape = $d("#dShape").value; st.count = $d("#dCount").value; st.quality = $d("#dQual").value; saveProj(); };
  async function loadStatus(){
    try{ info = await api("/api/pic/status"); }catch(e){ return; }
    $d("#dQual").innerHTML = info.qualities.map(q=>`<option value="${q.id}">${esc(q.label)} · ${esc(q.size)}</option>`).join("");
    $d("#dStyle").innerHTML = info.styles.map(s=>`<option value="${s.id}">${esc(s.label)}</option>`).join("");
    $d("#dShape").innerHTML = info.shapes.map(s=>`<option value="${s.id}">${esc(s.label)}</option>`).join("");
    $d("#dQual").value = st.quality; $d("#dStyle").value = st.style; $d("#dShape").value = st.shape; $d("#dCount").value = st.count; $d("#dPrompt").value = st.prompt;
    $d("#dSetup").classList.toggle("hidden", info.ready); $d("#dMake").disabled = !info.ready;
    $d("#dMake").title = info.ready ? "" : "Set up the picture maker first (the card above).";
  }
  async function loadGrid(){
    let r; try{ r = await api("/api/pic/list"); }catch(e){ return; }
    $d("#dGrid").innerHTML = r.pictures.length ? r.pictures.map(p=>`<div class="libitem"><img src="/files/images/${encodeURIComponent(p.name)}" alt="" loading="lazy" style="width:100%;height:220px;object-fit:contain;background:#fff;border-radius:8px">
      <div class="meta"><span title="${esc(p.name)}">${esc(p.name.replace(/^doodle-/,"").replace(/\.png$/,""))}</span>
      <a class="btn small" href="/files/images/${encodeURIComponent(p.name)}" download="${esc(p.name)}">Download</a><button class="small del" data-del="${esc(p.name)}" type="button">Delete</button></div></div>`).join("")
      : `<p class="note">Nothing yet. Your doodles will show here.</p>`;
  }
  $d("#dGrid").onclick = async e=>{ const b = e.target.closest("[data-del]"); if(b && await deleteMedia("images", b.dataset.del)) loadGrid(); };
  ["dPrompt","dStyle","dShape","dCount","dQual"].forEach(id=>$d("#"+id).addEventListener("input", keep));
  $d("#dInstall").onclick = async ()=>{
    const b = $d("#dInstall"), bar = $d("#dInstBar"), s = $d("#dInstState"), err = $d("#dInstErr"); keep();
    b.disabled = true; err.classList.add("hidden"); bar.classList.remove("hidden"); bar.firstChild.style.width = "4%"; s.textContent = "Starting… this is a big one-time download (about 5 to 7 GB). You can leave it running.";
    try{ await runJob("/api/pic/install", {quality:st.quality}, {cancel:$d("#dInstCancel"), onTick:j=>{ bar.firstChild.style.width = Math.max(4, Math.round(100*j.done/j.total))+"%"; s.textContent = lastLine(j) || "Working…"; }, onNote:m=>{ s.textContent = m; }});
      toast("The picture maker is ready."); bar.classList.add("hidden"); s.textContent = ""; await loadStatus();
    }catch(e){ bar.classList.add("hidden"); s.textContent = ""; if(e.cancelled){ s.textContent = "Cancelled. What was downloaded is kept, so next time it continues."; b.disabled = false; return; }
      const i = e.info || {title:"Set-up failed", what:e.message}; err.innerHTML = problemHTML(i); wireProblem(err, i); err.classList.remove("hidden"); }
    b.disabled = false;
  };
  $d("#dMake").onclick = async ()=>{
    keep(); const prompt = $d("#dPrompt").value.trim();
    if(!prompt){ toast("Please describe the picture first.", true); return; }
    const b = $d("#dMake"), bar = $d("#dBar"), s = $d("#dState"), err = $d("#dErr");
    b.disabled = true; err.classList.add("hidden"); bar.classList.remove("hidden"); bar.firstChild.style.width = "3%"; s.textContent = "Drawing… a picture takes a few minutes. Keep this window open.";
    try{ await runJob("/api/pic/make", {prompt, style:st.style, shape:st.shape, count:+st.count}, {cancel:$d("#dCancel"), onTick:j=>{ bar.firstChild.style.width = Math.max(3, Math.round(100*j.done/j.total))+"%"; s.textContent = lastLine(j) || "Drawing…"; }, onNote:m=>{ s.textContent = m; }});
      bar.firstChild.style.width = "100%"; s.textContent = "Done! Your doodle is below and saved in Pictures."; document.dispatchEvent(new Event("mediachanged")); await loadGrid();
    }catch(e){ bar.classList.add("hidden"); s.textContent = ""; if(e.cancelled){ s.textContent = "Cancelled. Nothing was saved."; b.disabled = false; return; }
      const i = e.info || {title:"Could not draw the picture", what:e.message}; err.innerHTML = problemHTML(i); wireProblem(err, i); err.classList.remove("hidden"); }
    b.disabled = false; await loadStatus();
  };
  loadStatus(); loadGrid();
  App.pages.doodle.onShow = ()=>{ loadStatus(); loadGrid(); };
}});
