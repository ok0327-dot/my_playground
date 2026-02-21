# WSL에서 Windows로 파일 복사 스크립트

$sourcePath = "\\wsl$\Ubuntu\home\kang\my_playground\kguide-macro"
$destPath = "C:\Users\dk032\my_playground\kguide-macro"

Write-Host "파일 복사 중..." -ForegroundColor Yellow
Write-Host "소스: $sourcePath" -ForegroundColor Cyan
Write-Host "대상: $destPath" -ForegroundColor Cyan

# 목적 폴더 생성
New-Item -ItemType Directory -Force -Path $destPath | Out-Null

# 파일 복사
Copy-Item -Path "$sourcePath\*" -Destination $destPath -Recurse -Force

Write-Host "`n복사 완료!" -ForegroundColor Green
Write-Host "다음 명령어를 실행하세요:" -ForegroundColor Yellow
Write-Host "cd $destPath" -ForegroundColor White
Write-Host "run_windows.bat" -ForegroundColor White
