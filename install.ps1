$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Installing MiniCode Harness..."
python -m pip install -e .

$PythonVersion = python -c "import sys; print(f'Python{sys.version_info.major}{sys.version_info.minor}')"
$ScriptsDir = Join-Path $env:APPDATA "Python\$PythonVersion\Scripts"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @($UserPath -split ";" | Where-Object { $_ })

if ($PathEntries -notcontains $ScriptsDir) {
    $NewPath = (($PathEntries + $ScriptsDir) -join ";")
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Added to user PATH: $ScriptsDir"
} else {
    Write-Host "Already in user PATH: $ScriptsDir"
}

if (($env:Path -split ";") -notcontains $ScriptsDir) {
    $env:Path = "$env:Path;$ScriptsDir"
}

$WindowsApps = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$Shim = Join-Path $WindowsApps "minicode.cmd"
$PythonExe = (Get-Command python).Source
$ShimContent = "@echo off`r`n`"$PythonExe`" -m minicode.cli %*`r`n"
[System.IO.File]::WriteAllText($Shim, $ShimContent, [System.Text.Encoding]::ASCII)
Write-Host "Created command shim: $Shim"

Write-Host ""
Write-Host "MiniCode installed. You can run it now:"
Write-Host "  minicode"
Write-Host ""
Write-Host "Open a new terminal if another terminal cannot find the command."
