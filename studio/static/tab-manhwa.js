registerPage("manhwa", {title:"Manhwa recap", sub:"Panels with motion and a blurred background, with your voice.", icon:"book", build(el){
  const MOTION = ["auto","zoom_in","zoom_out","pan_left","pan_right","pan_up","pan_down","scroll","none"];
  const ENTER = ["auto","swipe_left","swipe_right","swipe_up","swipe_down","drop","zoom","fade","none"];
  const opt = (list, cur)=>list.map(o=>`<option ${o===cur?'selected':''}>${o}</option>`).join("");
  el.innerHTML = `<div class="grid2"><div id="mScenes"></div><aside>
    <div class="card"><h2>Settings</h2>
      <label style="margin-top:0">Voice (for panels that “Make voice”)</label><div id="mVoice"></div>
      <label>Voice style</label><select id="mStyle"></select>
      <label>Video shape</label><select id="mSize"><option value="1920x1080">Wide 16:9 (YouTube)</option><option value="1080x1920">Tall 9:16 (Shorts, Reels, TikTok)</option><option value="1280x720">Wide 720p (fast)</option></select>
      <div id="mSecWrap"><label>Seconds per panel (no voice)</label><input type="number" id="mSeconds" min="1" max="60"></div>
      <label>Video name</label><input type="text" id="mName">
      <div class="row"><button class="primary grow" id="mMake">Make video</button></div><div class="warn hidden" id="mProblem"></div>
    </div><div id="mJob"></div></aside></div>`;
  const st = ps("manhwa", {style:"normal", size:"1920x1080", seconds:4, name:"manhwa-video"});
  const ed = sceneEditor({mount:$("#mScenes",el), key:"manhwaScenes", noun:"panel", extra:{
    defaults:{motion:"auto", enter:"auto"},
    render:(s)=>`<div class="two"><div><label>Panel motion</label><select data-f="motion">${opt(MOTION,s.motion||"auto")}</select></div>
      <div><label>Entrance</label><select data-f="enter">${opt(ENTER,s.enter||"auto")}</select></div></div>`}});
  const vp = voicePicker($("#mVoice",el), "manhwa");
  $("#mStyle",el).innerHTML = App.styles.map(s=>`<option>${s}</option>`).join("");
  [["style","#mStyle"],["size","#mSize"],["seconds","#mSeconds"],["name","#mName"]].forEach(([k,sel])=>{ const e=$(sel,el); e.value=st[k]; e.onchange=e.oninput=()=>{st[k]=e.value;saveProj();}; });
  const job = new JobPanel($("#mJob",el));
  function validate(){
    let msg = ed.validate(); if(!msg && App.caps && !App.caps.ffmpeg) msg = "FFmpeg is missing. See the badges on the left.";
    const p=$("#mProblem",el); p.textContent=msg; p.classList.toggle("hidden",!msg);
    $("#mMake",el).disabled = !!msg || $("#mMake",el).dataset.busy==="1";
    $("#mSecWrap",el).classList.toggle("hidden", ed.scenes.some(s=>s.audio_mode!=="none"));
  }
  ed.box.addEventListener("changed", validate); document.addEventListener("capsready", ()=>{ ed.render(); validate(); });
  $("#mMake",el).onclick = async ()=>{
    const b=$("#mMake",el); b.dataset.busy="1"; b.disabled=true;
    await job.run("/api/manhwa/render", {panels:ed.scenes, opts:Object.assign({}, st, {voice:vp.get()})});
    b.dataset.busy="0"; validate();
  };
  validate();
}});
