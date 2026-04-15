@echo off
echo Starting NexClip stack...

set ROOT=c:\Users\Vedsa\Desktop\AI Agents\NexClip
set BACKEND=%ROOT%\backend
set FRONTEND=%ROOT%\frontend
set PY_PATH=%ROOT%;%BACKEND%

start "NexClip Backend" powershell -NoExit -Command "cd '%BACKEND%'; .\venv\Scripts\activate; clear; Write-Host 'Starting Backend...' -ForegroundColor Cyan; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "NexClip Celery Worker" powershell -NoExit -Command "cd '%BACKEND%'; .\venv\Scripts\activate; $env:PYTHONPATH='%PY_PATH%'; clear; Write-Host 'Starting Celery Worker...' -ForegroundColor Cyan; python -m celery -A app.workers.celery_app worker -Q video,captions,nexearch,celery --loglevel=info --pool=threads --concurrency=8"
start "NexClip Frontend" powershell -NoExit -Command "cd '%FRONTEND%'; clear; Write-Host 'Starting Frontend...' -ForegroundColor Cyan; npm run dev"
start "Nex Agent" powershell -NoExit -Command "cd '%ROOT%'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nex Agent...' -ForegroundColor Cyan; python -m nex_agent.server"
start "Nexearch Engine" powershell -NoExit -Command "cd '%ROOT%'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nexearch Engine...' -ForegroundColor Cyan; python -m uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002"
start "Arc Agent" powershell -NoExit -Command "cd '%ROOT%'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Arc Agent...' -ForegroundColor Cyan; python -m nexearch.arc.server"

echo.
echo NexClip services launched:
echo   Backend   http://localhost:8000
echo   Nex Agent http://localhost:8001
echo   Nexearch  http://localhost:8002
echo   Arc Agent http://localhost:8003
echo   Frontend  http://localhost:3000
