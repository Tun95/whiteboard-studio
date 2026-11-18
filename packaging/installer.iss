; Inno Setup script for Whiteboard Wave Studio
[Setup]
AppName=Whiteboard Wave Studio
AppVersion=0.1.0
AppPublisher=Whiteboard Wave Studio
DefaultDirName={autopf}\WhiteboardWaveStudio
DefaultGroupName=Whiteboard Wave Studio
OutputBaseFilename=WhiteboardWaveStudio-Setup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
[Files]
Source: "..\dist\WhiteboardWaveStudio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\Whiteboard Wave Studio"; Filename: "{app}\WhiteboardWaveStudio.exe"
Name: "{autodesktop}\Whiteboard Wave Studio"; Filename: "{app}\WhiteboardWaveStudio.exe"
[Run]
Filename: "{app}\WhiteboardWaveStudio.exe"; Description: "Start Whiteboard Wave Studio"; Flags: nowait postinstall skipifsilent
