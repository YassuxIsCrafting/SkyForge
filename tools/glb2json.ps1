# Convertit chaque modeles\*.glb en glTF texte (.json) avec tampon integre en base64.
# Les Artifacts ne servent pas les .glb ; le jeu decode lui-meme le base64 (voir loadGLB dans index.html).
param([string]$Dir = (Join-Path $PSScriptRoot '..\models'))
$enc = New-Object Text.UTF8Encoding($false)
Get-ChildItem $Dir -Filter *.glb | ForEach-Object {
  $b = [IO.File]::ReadAllBytes($_.FullName)
  $jl = [BitConverter]::ToUInt32($b, 12)
  $json = [Text.Encoding]::UTF8.GetString($b, 20, $jl)
  $o = 20 + $jl; $bl = [BitConverter]::ToUInt32($b, $o)
  $bin = New-Object byte[] $bl; [Array]::Copy($b, $o + 8, $bin, 0, $bl)
  $j = $json | ConvertFrom-Json
  $j.buffers[0] | Add-Member -NotePropertyName uri -NotePropertyValue ("data:application/octet-stream;base64," + [Convert]::ToBase64String($bin)) -Force
  [IO.File]::WriteAllText((Join-Path $Dir "$($_.BaseName).json"), ($j | ConvertTo-Json -Depth 64 -Compress), $enc)
  "{0,-16} {1,8} Ko" -f "$($_.BaseName).json", [int]((Get-Item (Join-Path $Dir "$($_.BaseName).json")).Length / 1KB)
}
