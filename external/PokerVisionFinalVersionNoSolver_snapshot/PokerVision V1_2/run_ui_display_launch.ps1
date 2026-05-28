$ErrorActionPreference = "Stop"

$PythonExe = "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
$ProjectDir = "C:\PokerVision\PokerVision V0.5"
$MainFile = Join-Path $ProjectDir "main.py"

Write-Host "PokerVision Core V0.5 batch UI launch" -ForegroundColor Cyan
Write-Host "Python: $PythonExe" -ForegroundColor Gray
Write-Host "Main:   $MainFile" -ForegroundColor Gray

& $PythonExe $MainFile
