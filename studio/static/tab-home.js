registerPage("home", {title:"Home", sub:"Pick what you want to make.", icon:"home", build(el){
  el.innerHTML = `<div class="tools">
    ${[["video","pen","Whiteboard video","Images that draw themselves, with your script and voice."],
       ["ads","phone","App ads","Phone adverts with captions, zooms and pull-out effects."],
       ["manhwa","book","Manhwa recap","Panels with motion, blurred background and voice."],
       ["voices","mic","Voices","Listen to every AI voice before you choose."],
       ["editor","film","Editor","Join clips, trim, add music, titles and captions."],
       ["library","folder","Library","Your videos, uploads and ad packs."]]
      .map(([id,ic,t,d])=>`<button class="tool" data-go="${id}"><span class="ico">${icon(ic)}</span><b>${t}</b><span>${d}</span></button>`).join("")}
  </div>
  <div class="card" style="margin-top:18px"><h2>How it works</h2>
    <p class="note" style="margin:0">1. Make your pictures (for example with Gemini). 2. Add them in a tool, write or record the words, choose a voice. 3. Click Make video. 4. Polish in the Editor if you want: music, titles, trims. Your work is saved on this computer.</p></div>
  <div class="card" id="homeRecent"><h2>Latest videos</h2><div class="lib"></div></div>`;
  el.onclick = e=>{ const b=e.target.closest("[data-go]"); if(b) go(b.dataset.go); };
}, async onShow(){
  const lib = await api("/api/library").catch(()=>null); if(!lib) return;
  const box = $("#homeRecent .lib");
  box.innerHTML = lib.videos.slice(0,6).map(v=>`<div class="libitem"><b>${esc(v.name)}</b><video controls preload="metadata" src="/files/out/${encodeURIComponent(v.name)}#t=0.4"></video></div>`).join("") || '<div class="note">Nothing yet. Make your first video!</div>';
}});
