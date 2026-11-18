# Clip system - one-time setup for a new Windows PC (all free tools).
# Run via SETUP.bat (double-click). Safe to run again: it skips what is already done.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Step($t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Winget-Install($id, $name) {
    if (-not (Have "winget")) { Write-Host "   winget not found - install $name manually, then run SETUP.bat again." -ForegroundColor Yellow; return }
    Write-Host "   installing $name with winget ..."
    winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    Refresh-Path
}
function Python-Ok($exe) {
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    $v = & $exe -c "import sys;print(int(sys.version_info>=(3,10)))" 2>$null
    return ($v -eq "1")
}

Write-Host "=============================================" -ForegroundColor Green
Write-Host "   CLIP SYSTEM SETUP (free, CPU only)" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

# 1. system tools ---------------------------------------------------------
Step "System tools (Git, FFmpeg, Node.js, Python)"
if (-not (Have "git"))    { Winget-Install "Git.Git" "Git" }            else { Write-Host "   git OK" }
if (-not (Have "ffmpeg")) { Winget-Install "Gyan.FFmpeg" "FFmpeg" }     else { Write-Host "   ffmpeg OK" }
if (-not (Have "node"))   { Winget-Install "OpenJS.NodeJS.LTS" "Node.js" } else { Write-Host "   node OK" }

# 2. python venv ----------------------------------------------------------
Step "Python environment"
$ParentVenv = Join-Path $Root "..\.venv\Scripts\python.exe"
$OwnVenv    = Join-Path $Root ".venv\Scripts\python.exe"
if (Python-Ok $OwnVenv) {
    $Py = $OwnVenv; Write-Host "   using clipping\.venv"
} elseif (Python-Ok $ParentVenv) {
    $Py = (Resolve-Path $ParentVenv).Path; Write-Host "   using parent OpenMontage .venv"
} else {
    $Base = $null
    $check = "import sys;print(int(sys.version_info>=(3,10)))"
    if (Have "py") {
        foreach ($ver in @("-3.11", "-3.12", "-3.10")) {
            $ok = & py $ver -c $check 2>$null
            if ($ok -eq "1") { $Base = "py $ver"; break }
        }
    }
    if (-not $Base -and (Have "python")) {
        $ok = & python -c $check 2>$null
        if ($ok -eq "1") { $Base = "python" }
    }
    if (-not $Base) {
        Winget-Install "Python.Python.3.11" "Python 3.11"
        $Base = "py -3.11"
    }
    Write-Host "   creating clipping\.venv with: $Base"
    if ($Base -eq "python") { & python -m venv .venv } else { & py $Base.Split(" ")[1] -m venv .venv }
    $Py = $OwnVenv
}
& $Py -m pip install --upgrade pip -q
Write-Host "   installing python packages (requirements.txt) ..."
& $Py -m pip install -r requirements.txt -q

# 3. Claude Code CLI -------------------------------------------------------
Step "Claude Code CLI (the agents' brain)"
if (-not (Have "claude")) {
    if (Have "npm") { npm install -g @anthropic-ai/claude-code | Out-Null; Refresh-Path }
    else { Write-Host "   npm missing - install Node.js, then: npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow }
}
if (Have "claude") { Write-Host "   claude OK  (log in once by running: claude)" }

# 4. vendor engines --------------------------------------------------------
Step "Open-source clipper engines (vendor\)"
$repos = [ordered]@{
    "AI-Youtube-Shorts-Generator" = "https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator.git"
    "ViralCutter" = "https://github.com/RafaelGodoyEbert/ViralCutter.git"
    "autoclip"    = "https://github.com/zhouxiaoka/autoclip.git"
    "openshorts"  = "https://github.com/mutonby/openshorts.git"
    "reelsaw"     = "https://github.com/osbytes/reelsaw.git"
}
if (-not (Test-Path (Join-Path $Root "..\AGENT_GUIDE.md"))) {
    # standalone checkout: also fetch OpenMontage for its pipeline + video skills
    $repos["OpenMontage"] = "https://github.com/calesthio/OpenMontage.git"
} else { Write-Host "   inside OpenMontage already - using ..\skills" }
New-Item -ItemType Directory -Force vendor | Out-Null
foreach ($name in $repos.Keys) {
    $dest = Join-Path "vendor" $name
    if ((Test-Path $dest) -and (Get-ChildItem $dest -Force | Select-Object -First 1)) { Write-Host "   $name OK"; continue }
    Write-Host "   cloning $name ..."
    git clone --depth 1 -q $repos[$name] $dest
}

# 5. whisper model ---------------------------------------------------------
Step "Whisper speech model (local captions, ~145 MB once)"
& $Py tools\doctor.py --get-model base

# 6. config + folders ------------------------------------------------------
Step "Config and folders"
foreach ($d in @("runs", "output", "workspace", "data\streamers", "data\trends", "data\logs")) { New-Item -ItemType Directory -Force $d | Out-Null }
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "   created .env (optional Twitch/Kick keys go here)" }
if (-not (Test-Path ".claude\settings.json")) { Copy-Item "config\permissions.suggested.json" ".claude\settings.json" }

# 7. check -----------------------------------------------------------------
Step "Final check"
& $Py tools\doctor.py
Write-Host ""
Write-Host "Next: 1) run  claude  once and log in   2) double-click RUN_CLIPS.bat" -ForegroundColor Green
