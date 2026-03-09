$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$fallbackPython = "C:\Users\jangn\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue

if ($pythonCmd) {
  $pythonExe = $pythonCmd.Source
} elseif (Test-Path $fallbackPython) {
  $pythonExe = $fallbackPython
} else {
  Write-Error "Python 실행 파일을 찾지 못했습니다. python 설치 후 다시 실행해 주세요."
  exit 1
}

Write-Host "[루멕스 이미지 리프레시] Python: $pythonExe"
Write-Host "[루멕스 이미지 리프레시] 패키지 확인/설치 중..."
& $pythonExe -m pip install -r requirements.txt

Write-Host "[루멕스 이미지 리프레시] 서버 시작: http://127.0.0.1:5000"
& $pythonExe app.py
