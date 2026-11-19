// Builds the sidebar and every page, then starts the app.
function chips(){
  const c = App.caps, box = $("#chips");
  if(!c){ box.innerHTML = '<span class="chip">Checking tools…</span>'; return; }
  const item = (ok,t)=>`<span class="chip ${ok?'ok':'bad'}">${ok?'✓':'✗'} ${t}</span>`;
  box.innerHTML = item(c.animator,"Animator")+item(c.ffmpeg,"FFmpeg")+item(c.kokoro,"Voice (Kokoro)");
}
async function boot(){
  const s = await api("/api/state");
  Object.assign(App, {caps:s.caps, voices:s.voices, styles:s.styles});
  App.proj = await api("/api/project");
  $("#ver").textContent = "v"+s.version; $("#dataDir").textContent = s.data_dir; $("#donateText").textContent = s.donate_text;
  if(s.donate_url){ $("#donateLink").href = s.donate_url; $("#donateLink").classList.remove("hidden"); } else $("#donateSoon").classList.remove("hidden");
  $("#nav").innerHTML = App.order.map(id=>`<button class="navbtn" data-id="${id}"><span class="ico">${icon(App.pages[id].ic)}</span>${esc(App.pages[id].title)}</button>`).join("");
  $("#nav").onclick = e=>{ const b=e.target.closest(".navbtn"); if(b) go(b.dataset.id); };
  $$(".ico[data-i]").forEach(el=>el.innerHTML = icon(el.dataset.i));
  const host = $("#pages");
  App.order.forEach(id=>{ const d=document.createElement("section"); d.className="page"; d.id="page-"+id; host.appendChild(d); App.pages[id].build(d); });
  $("#donateBtn").onclick = ()=>$("#donateDlg").showModal(); $("#donateClose").onclick = ()=>$("#donateDlg").close();
  $("#aboutBtn").onclick = ()=>$("#aboutDlg").showModal(); $("#aboutClose").onclick = ()=>$("#aboutDlg").close();
  chips(); go(App.pages[location.hash.slice(1)] ? location.hash.slice(1) : "home");
  const t = setInterval(async ()=>{
    const st = await api("/api/state").catch(()=>null);
    if(st && st.caps){ App.caps = st.caps; clearInterval(t); chips(); document.dispatchEvent(new Event("capsready")); }
  }, 1500);
}
// One-time voice setup runs by itself in the background; show calm progress, never a scary error.
async function watchSetup(){
  const box = $("#setupBanner"); let last = "";
  const tick = async ()=>{
    const st = await api("/api/setup").catch(()=>null); if(!st) return setTimeout(tick, 3000);
    if(st.state === "checking" || st.state === "needed"){ box.classList.remove("hidden"); box.innerHTML = "<b>Checking your voices…</b> This only takes a moment."; return setTimeout(tick, 2000); }
    if(st.state === "installing"){
      let line = ""; try{ const j = await api("/api/job?id="+st.job); line = (j.log.filter(l=>!l.startsWith("$")).slice(-1)[0]||""); }catch(_){}
      box.classList.remove("hidden"); box.innerHTML = "<b>Getting your voices ready (one time only).</b> Japanese and Mandarin voices are being added. You can keep working; this needs internet and may take a few minutes.";
      last = "installing"; return setTimeout(tick, 2000);
    }
    if(st.state === "failed"){ box.classList.remove("hidden"); box.innerHTML = problemHTML(st.info || {title:"Some voices could not be set up", what:"", fix:"Restart the app with internet on; it will try again."}); return; }
    if(last === "installing"){ toast("Your voices are ready."); const s2 = await api("/api/state").catch(()=>null); if(s2 && s2.caps){ App.caps = s2.caps; chips(); } }
    box.classList.add("hidden");
  };
  tick();
}
boot().then(watchSetup).catch(e=>{ document.body.innerHTML = "<pre style='padding:24px'>The app could not start: "+esc(e.message)+"</pre>"; });
