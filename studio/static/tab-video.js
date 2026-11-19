registerPage("video", {title:"Whiteboard video", sub:"Images that draw themselves, with your voice.", icon:"pen", build(el){
  el.innerHTML = `<div class="grid2"><div id="vScenes"></div><aside>
    <div class="card"><h2>Settings</h2>
      <label style="margin-top:0">Voice (for scenes that “Make voice”)</label><div id="vVoice"></div>
      <label>Voice style</label><select id="vStyle"></select>
      <div class="two"><div><label>Video size</label><select id="vDim"><option value="720">720p (fast)</option><option value="1280">1280 (recommended)</option><option value="1920">1920 (slow)</option></select></div>
        <div><label>Quality</label><select id="vQuality"><option value="low">Low (fast)</option><option value="medium">Medium</option><option value="high">High</option></select></div></div>
      <div class="two"><div><label>Drawing hand</label><select id="vHand"><option value="doodle">Doodle hand</option><option value="brown">Brown hand</option><option value="dark">Dark hand</option><option value="light">Light hand</option><option value="off">No hand</option></select></div>
        <div><label>Camera</label><select id="vCamera"><option value="off">Steady</option><option value="auto">Follow the pen</option></select></div></div>
      <div id="vSecWrap"><label>Seconds per scene (no voice)</label><input type="number" id="vSeconds" min="2" max="120"></div>
      <label>Video name</label><input type="text" id="vName">
      <div class="row"><button class="primary grow" id="vMake">Make video</button></div><div class="warn hidden" id="vProblem"></div>
    </div><div id="vJob"></div></aside></div>`;
  const st = ps("video", {style:"normal", max_dim:"1280", quality:"medium", hand:"doodle", camera:"off", seconds:8, name:"my-video"});
  const ed = sceneEditor({mount:$("#vScenes",el), key:"videoScenes", noun:"scene"});
  const vp = voicePicker($("#vVoice",el), "video");
  const fields = {style:"#vStyle", max_dim:"#vDim", quality:"#vQuality", hand:"#vHand", camera:"#vCamera", seconds:"#vSeconds", name:"#vName"};
  $("#vStyle",el).innerHTML = App.styles.map(s=>`<option>${s}</option>`).join("");
  Object.entries(fields).forEach(([k,sel])=>{ const e=$(sel,el); e.value = st[k]; e.onchange = e.oninput = ()=>{ st[k]=e.value; saveProj(); }; });
  const job = new JobPanel($("#vJob",el));
  function validate(){
    let msg = ed.validate(); if(!msg && App.caps && (!App.caps.animator||!App.caps.ffmpeg)) msg = "The animator or FFmpeg is missing. See the badges on the left.";
    const p = $("#vProblem",el); p.textContent = msg; p.classList.toggle("hidden", !msg);
    $("#vMake",el).disabled = !!msg || $("#vMake",el).dataset.busy==="1";
    $("#vSecWrap",el).classList.toggle("hidden", ed.scenes.some(s=>s.audio_mode!=="none"));
  }
  ed.box.addEventListener("changed", validate); document.addEventListener("capsready", ()=>{ ed.render(); validate(); });
  $("#vMake",el).onclick = async ()=>{
    const b = $("#vMake",el); b.dataset.busy="1"; b.disabled = true;
    await job.run("/api/render", {scenes:ed.scenes, opts:Object.assign({}, st, {voice:vp.get()})});
    b.dataset.busy="0"; validate();
  };
  validate();
}});
