registerPage("tts", {title:"Text to speech", sub:"Type or paste your own text, pick a voice, and save it as an audio file.", icon:"speaker", build(el){
  el.innerHTML = `
  <div class="card">
    <label style="margin-top:0">Your text</label>
    <textarea id="tText" rows="11" placeholder="Type or paste your text here…"></textarea>
    <div class="row"><button class="small" id="tOpen" type="button">Open a text file (.txt)</button><input type="file" id="tFile" accept=".txt,.md,text/plain" hidden><span class="note" id="tCount"></span></div>
    <details style="margin-top:8px"><summary class="note" style="cursor:pointer">Tips for natural speech</summary>
      <p class="note" style="margin:6px 0 0">• Leave a blank line between paragraphs for a longer pause.<br>• Type <b>[pause 2]</b> on its own line for 2 seconds of silence.<br>• A line that starts with <b>#</b> is a note for you. It is not read aloud.<br>• Use the pronunciation box below for names or words that sound wrong.</p></details>
  </div>
  <div class="card">
    <div class="two"><div><label style="margin-top:0">Voice</label><div id="tVoice"></div></div>
      <div><label style="margin-top:0">Speaking style</label><select id="tStyle"></select>
        <label>Speed</label><select id="tSpeed"><option value="">Automatic (from the style)</option><option value="0.8">Slower (0.8×)</option><option value="0.9">A little slower (0.9×)</option><option value="1">Normal (1×)</option><option value="1.1">A little faster (1.1×)</option><option value="1.2">Faster (1.2×)</option><option value="1.3">Much faster (1.3×)</option></select></div></div>
    <details style="margin-top:10px"><summary class="note" style="cursor:pointer">Fix how a word is pronounced (optional)</summary>
      <textarea id="tFix" rows="3" placeholder="One fix per line, like:&#10;Tunji=Toon-jee&#10;Nginx=engine-ex"></textarea></details>
    <label>File name</label><input type="text" id="tName" placeholder="my-audio">
    <div class="warn hidden" id="tWarn">The AI voice is not ready on this computer yet, so audio cannot be made. Open the app again with internet on, or see the message at the top of the page.</div>
    <div class="row"><button class="primary" id="tMake" type="button">Make audio</button><span class="note">Your audio is saved as WAV, and also as MP3 when the video maker is ready.</span></div>
  </div>
  <div class="card hidden" id="tOut"><h2>Your audio</h2><div class="bar"><i></i></div><div class="note" id="tState"></div><div class="perr hidden" id="tErr"></div>
    <audio controls class="hidden" id="tAudio" style="width:100%;margin-top:10px"></audio><div class="row dlrow hidden" id="tDl"></div>
    <p class="note hidden" id="tSaved">It is also saved in your Library (Audio), and you can use it in the Editor.</p></div>`;

  const st = ps("tts", {text:"", style:"normal", speed:"", name:"my-audio", fixes:""});
  const picker = voicePicker($("#tVoice",el), "ttsVoice");
  $("#tStyle",el).innerHTML = App.styles.map(s=>`<option value="${s}">${s[0].toUpperCase()+s.slice(1)}</option>`).join("");
  const T = $("#tText",el);
  T.value = st.text; $("#tStyle",el).value = st.style; $("#tSpeed",el).value = st.speed; $("#tName",el).value = st.name; $("#tFix",el).value = st.fixes;
  function count(){
    const words = (T.value.replace(/^\s*#.*$/gm,"").match(/\S+/g) || []).length, mins = words / 150;
    $("#tCount",el).textContent = words ? `${words} words · about ${mins < 1 ? Math.max(1, Math.round(mins*60))+" seconds" : mins.toFixed(1)+" minutes"} of audio` : "";
  }
  const keep = ()=>{ st.text = T.value; st.style = $("#tStyle",el).value; st.speed = $("#tSpeed",el).value; st.name = $("#tName",el).value; st.fixes = $("#tFix",el).value; saveProj(); };
  [T,$("#tStyle",el),$("#tSpeed",el),$("#tName",el),$("#tFix",el)].forEach(e=>e.addEventListener("input", ()=>{ keep(); count(); }));
  count();
  $("#tOpen",el).onclick = ()=>$("#tFile",el).click();
  $("#tFile",el).onchange = async e=>{ const f = e.target.files[0]; if(!f) return; e.target.value = "";
    if(f.size > 2_000_000){ toast("That text file is too big (limit 2 MB).", true); return; }
    T.value = await f.text(); if(!$("#tName",el).value || $("#tName",el).value==="my-audio") $("#tName",el).value = f.name.replace(/\.[^.]+$/,""); keep(); count(); };
  const warn = ()=>$("#tWarn",el).classList.toggle("hidden", !(App.caps && !App.caps.kokoro));
  document.addEventListener("capsready", warn); warn();

  const bar = $(".bar i",el), state = $("#tState",el), err = $("#tErr",el);
  $("#tMake",el).onclick = async ()=>{
    keep(); const out = $("#tOut",el), btn = $("#tMake",el);
    if(!T.value.trim()){ toast("Type or paste some text first.", true); return; }
    out.classList.remove("hidden"); err.classList.add("hidden"); $("#tAudio",el).classList.add("hidden"); $("#tDl",el).classList.add("hidden"); $("#tSaved",el).classList.add("hidden");
    bar.style.width = "3%"; state.textContent = "Making your audio… long texts take a few minutes. Keep this window open."; btn.disabled = true;
    try{
      const j = await runJob("/api/tts/make", {text:T.value, voice:picker.get(), style:st.style, speed:st.speed, name:st.name || "my-audio", fixes:st.fixes},
        {onTick:j=>{ bar.style.width = Math.max(3, Math.round(100*j.done/j.total))+"%"; state.textContent = lastLine(j) || "Working…"; }, onNote:m=>{ state.textContent = m; }});
      bar.style.width = "100%"; state.textContent = "Done! Press play to listen.";
      const wav = j.output, stem = wav.replace(/\.wav$/i,""), lib = await api("/api/library").catch(()=>({audio:[]}));
      const hasMp3 = (lib.audio||[]).some(a=>a.name === stem + ".mp3"), url = n => "/files/audio/" + encodeURIComponent(n);
      const au = $("#tAudio",el); au.src = url(hasMp3 ? stem + ".mp3" : wav) + "?t=" + Date.now(); au.classList.remove("hidden");
      $("#tDl",el).innerHTML = `${hasMp3 ? `<a class="btn primary" href="${url(stem+".mp3")}" download="${esc(stem)}.mp3">Download MP3</a>` : ""}<a class="btn" href="${url(wav)}" download="${esc(wav)}">Download WAV</a>`;
      $("#tDl",el).classList.remove("hidden"); $("#tSaved",el).classList.remove("hidden");
      document.dispatchEvent(new Event("mediachanged"));
    }catch(e){ bar.style.width = "0%"; state.textContent = ""; const info = e.info || {title:"Could not make the audio", what:e.message}; err.innerHTML = problemHTML(info); wireProblem(err, info); err.classList.remove("hidden"); }
    btn.disabled = false;
  };
}});
