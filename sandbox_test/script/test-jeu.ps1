# Test automatique d'Aviassembly - s'execute DANS le Bac a sable Windows
# Lance le jeu, observe son comportement, ecrit un rapport dans le dossier Rapport.
$ErrorActionPreference = 'Continue'
$desk    = 'C:\Users\WDAGUtilityAccount\Desktop'
$game    = "$desk\Aviassembly\Aviassembly.exe"
$out     = "$desk\Rapport"
$dureeS  = 90
$log     = "$out\rapport.txt"
function Write-Log($t) { Add-Content -Path $log -Value $t -Encoding UTF8 }
Set-Content -Path $log -Value "=== Rapport de test Aviassembly ($(Get-Date -Format s)) ===" -Encoding UTF8

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
function Save-Screen($name) {
    try {
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $bmp.Save("$out\$name.png", [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    } catch { Write-Log "capture $name echouee: $_" }
}

# --- Etat initial ---
$runKeys = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run','HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce','HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
function Get-RunState { foreach ($k in $runKeys) { if (Test-Path $k) { (Get-ItemProperty $k).PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { "$k :: $($_.Name) = $($_.Value)" } } } }
$run0   = @(Get-RunState)
$tasks0 = @(Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object { $_.TaskPath + $_.TaskName })
$svc0   = @(Get-Service | ForEach-Object Name)
$proc0  = @(Get-CimInstance Win32_Process | ForEach-Object ProcessId)
$watch  = @("$env:USERPROFILE", "$env:ProgramData", "$env:windir\System32", "$env:windir\SysWOW64")
$start  = Get-Date

# --- Lancement du jeu ---
Write-Log "Lancement: $game"
$p = Start-Process -FilePath $game -WorkingDirectory (Split-Path $game) -PassThru
Write-Log "PID du jeu: $($p.Id)"

$seen = @{}
$net  = @{}
for ($i = 0; $i -lt $dureeS; $i += 2) {
    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process | Where-Object { $proc0 -notcontains $_.ProcessId } | ForEach-Object {
        if (-not $seen[$_.ProcessId]) { $seen[$_.ProcessId] = "t+$($i+2)s  PID=$($_.ProcessId)  parent=$($_.ParentProcessId)  $($_.Name)  |  $($_.CommandLine)" }
    }
    $ids = @($p.Id) + @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $p.Id } | ForEach-Object ProcessId)
    Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess } | ForEach-Object { $net["TCP $($_.LocalAddress):$($_.LocalPort) -> $($_.RemoteAddress):$($_.RemotePort) [$($_.State)]"] = 1 }
    Get-NetUDPEndpoint  -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess } | ForEach-Object { $net["UDP ecoute $($_.LocalAddress):$($_.LocalPort)"] = 1 }
    if ($i -eq 30) { Save-Screen 'capture_30s' }
    if ($i -eq 80) { Save-Screen 'capture_80s' }
}
Write-Log "Jeu toujours en cours apres ${dureeS}s: $(-not $p.HasExited)"

# --- Arret du jeu ---
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
Start-Sleep -Seconds 3

# --- Resultats ---
Write-Log "`n=== Nouveaux processus pendant le test ==="
$seen.Values | Sort-Object | ForEach-Object { Write-Log $_ }
Write-Log "`n=== Activite reseau du jeu (le reseau du bac a sable est coupe) ==="
if ($net.Count) { $net.Keys | Sort-Object | ForEach-Object { Write-Log $_ } } else { Write-Log 'aucune' }

Write-Log "`n=== Demarrage automatique (cles Run) ajoute ==="
$run1 = @(Get-RunState); $d = $run1 | Where-Object { $run0 -notcontains $_ }; if ($d) { $d | ForEach-Object { Write-Log $_ } } else { Write-Log 'aucun' }
Write-Log "`n=== Taches planifiees ajoutees ==="
$d = Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object { $_.TaskPath + $_.TaskName } | Where-Object { $tasks0 -notcontains $_ }; if ($d) { $d | ForEach-Object { Write-Log $_ } } else { Write-Log 'aucune' }
Write-Log "`n=== Services ajoutes ==="
$d = Get-Service | ForEach-Object Name | Where-Object { $svc0 -notcontains $_ }; if ($d) { $d | ForEach-Object { Write-Log $_ } } else { Write-Log 'aucun' }

Write-Log "`n=== Fichiers crees ou modifies pendant le test (hors dossier Rapport) ==="
foreach ($w in $watch) {
    Get-ChildItem $w -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $start -and $_.FullName -notlike "$out*" } |
        ForEach-Object { Write-Log ("{0,10}  {1}" -f $_.Length, $_.FullName) }
}

# Journal Unity du jeu (preuve qu'il a demarre)
$pl = Get-ChildItem "$env:USERPROFILE\AppData\LocalLow" -Recurse -Filter 'Player*.log' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pl) { Copy-Item $pl.FullName "$out\Player.log"; Write-Log "`nJournal Unity copie: $($pl.FullName)" } else { Write-Log "`nAucun journal Unity trouve" }

Write-Log "`n=== FIN ==="
Set-Content -Path "$out\TERMINE.txt" -Value (Get-Date -Format s)
