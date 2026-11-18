# Makes ONE long voice-over file (1 hour or more) from a script file.
# Usage (PowerShell):
#   powershell -ExecutionPolicy Bypass -File "...\long-voice.ps1" -Script "C:\path\client-script.txt" -Name "ClientName" -Voice am_liam -Mode normal
# Result: C:\Users\akand\Desktop\White Board Animation\Client Gigs\<Name>\2-audio\<Name>.wav (and .mp3 if ffmpeg exists)
# If it stops (sleep, closed window), run the SAME command again: it continues. Add -Fresh to start over.
# Voices: am_liam am_onyx am_michael am_eric bm_george bm_lewis | af_sarah af_nicole bf_emma bf_isabella
param(
  [Parameter(Mandatory=$true)][string]$Script,
  [string]$Name = "voiceover",
  [string]$Voice = "am_liam",
  [string]$Mode = "normal",
  [string]$Lang = "",
  [switch]$Fresh
)
$k   = "C:\Users\akand\Desktop\White Board Animation\_Tools\kokoro"
$py  = "$k\kokoro-env\Scripts\python.exe"
$out = "C:\Users\akand\Desktop\White Board Animation\Client Gigs\$Name\2-audio"
if (-not (Test-Path $py))     { Write-Host "Cannot find $py" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $Script)) { Write-Host "Cannot find the script file: $Script" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force $out | Out-Null
$args2 = @("$k\long_voice.py", "--script", $Script, "--out", $out, "--name", $Name, "--voice", $Voice, "--mode", $Mode)
if ($Lang)  { $args2 += @("--lang", $Lang) }
if ($Fresh) { $args2 += "--fresh" }
Set-Location $k
& $py @args2
if ($LASTEXITCODE -eq 0) { Write-Host "Done. Open: $out" -ForegroundColor Green }
