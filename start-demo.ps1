# Pipeline Prophet — Demo Start Script
# Usage: .\start-demo.ps1

Write-Host "=== Pipeline Prophet Demo ===" -ForegroundColor Cyan
Write-Host "Starting backend (FastAPI on port 8000)..." -ForegroundColor Yellow

# Start backend in a new PowerShell window
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd backend; python -m uvicorn app.main:app --reload --port 8000' -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "Starting frontend (Vite on port 5173)..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd frontend; npm run dev' -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== Demo Ready ===" -ForegroundColor Green
Write-Host "Frontend:    http://localhost:5173" -ForegroundColor White
Write-Host "Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "API Docs:    http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "To trigger a demo prediction, run:" -ForegroundColor Yellow
Write-Host "  python backend/scripts/simulate_push.py" -ForegroundColor White
Write-Host ""
Write-Host "To run end-to-end demo simulation:" -ForegroundColor Yellow
Write-Host "  python backend/scripts/simulate_demo_run.py" -ForegroundColor White

# Open browser after a short pause
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
