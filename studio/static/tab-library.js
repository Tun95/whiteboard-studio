registerPage("library", {title:"Library", sub:"Everything you have made or uploaded.", icon:"folder", build(el){
  el.innerHTML = `<div class="card"><h2>Finished videos</h2><div class="lib" id="lVideos"></div></div>
    <div class="card"><h2>Uploaded videos</h2><div class="lib" id="lUploads"></div></div>
    <div class="card"><h2>Audio</h2><div class="lib" id="lAudio"></div></div>
    <div class="card"><h2>Images</h2><div class="lib" id="lImages"></div></div>
    <p class="note">All files live in <code id="lPath"></code></p>`;
}, async onShow(){
  const el = $("#page-library");
  if(!el.dataset.wired){ el.dataset.wired = "1";
    el.addEventListener("click", async e=>{ const b = e.target.closest("[data-del]"); if(!b) return;
      if(await deleteMedia(b.dataset.folder, b.dataset.del)) App.pages.library.onShow(); });
    document.addEventListener("mediachanged", ()=>{ if(el.classList.contains("show")) App.pages.library.onShow(); }); } const lib = await api("/api/library").catch(()=>null); if(!lib) return;
  $("#lPath",el).textContent = $("#dataDir").textContent + "\\current-project";
  const empty = '<div class="note">Nothing here yet.</div>';
  $("#lVideos",el).innerHTML = lib.videos.map(f=>`<div class="libitem"><div class="top"><b>${esc(f.name)}</b><button class="del" data-folder="out" data-del="${esc(f.name)}" title="Delete">Delete</button></div><video controls preload="metadata" src="/files/out/${encodeURIComponent(f.name)}"></video><a class="btn small" download href="/files/out/${encodeURIComponent(f.name)}">Download</a></div>`).join("") || empty;
  $("#lUploads",el).innerHTML = lib.uploads.map(f=>`<div class="libitem"><div class="top"><b>${esc(f.name)}</b><button class="del" data-folder="media" data-del="${esc(f.name)}" title="Delete">Delete</button></div><video controls preload="metadata" src="/files/media/${encodeURIComponent(f.name)}"></video></div>`).join("") || empty;
  $("#lAudio",el).innerHTML = lib.audio.map(f=>`<div class="libitem"><div class="top"><b>${esc(f.name)}</b><button class="del" data-folder="audio" data-del="${esc(f.name)}" title="Delete">Delete</button></div><audio controls preload="none" style="width:100%" src="/files/audio/${encodeURIComponent(f.name)}"></audio></div>`).join("") || empty;
  $("#lImages",el).innerHTML = lib.images.map(f=>`<div class="libitem"><div class="top"><b>${esc(f.name)}</b><button class="del" data-folder="images" data-del="${esc(f.name)}" title="Delete">Delete</button></div><div class="thumb" style="width:100%;margin-top:6px;background-image:url('/files/images/${encodeURIComponent(f.name)}')"></div></div>`).join("") || empty;
}});
