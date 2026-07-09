$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
while ($true) {
	& $python app.py
	$exitCode = $LASTEXITCODE
	Start-Sleep -Seconds 5
}
