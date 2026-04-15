Write-Host "Starting NexClip stack..." -ForegroundColor Cyan

$root = "c:\Users\Vedsa\Desktop\AI Agents\NexClip"
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$pythonPath = "$root;$backend"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='NexClip Backend'; cd '$backend'; .\venv\Scripts\activate; clear; Write-Host 'Starting Backend...' -ForegroundColor Cyan; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='NexClip Celery Worker'; cd '$backend'; .\venv\Scripts\activate; `$env:PYTHONPATH='$pythonPath'; clear; Write-Host 'Starting Celery Worker...' -ForegroundColor Cyan; python -m celery -A app.workers.celery_app worker -Q video,captions,nexearch,celery --loglevel=info --pool=threads --concurrency=8"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='NexClip Frontend'; cd '$frontend'; clear; Write-Host 'Starting Frontend...' -ForegroundColor Cyan; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='Nex Agent'; cd '$root'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nex Agent...' -ForegroundColor Cyan; python -m nex_agent.server"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='Nexearch Engine'; cd '$root'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nexearch Engine...' -ForegroundColor Cyan; python -m uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle='Arc Agent'; cd '$root'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Arc Agent...' -ForegroundColor Cyan; python -m nexearch.arc.server"

Write-Host ""
Write-Host "NexClip services launched:" -ForegroundColor Magenta
Write-Host "  Backend   http://localhost:8000" -ForegroundColor DarkGray
Write-Host "  Nex Agent http://localhost:8001" -ForegroundColor DarkGray
Write-Host "  Nexearch  http://localhost:8002" -ForegroundColor DarkGray
Write-Host "  Arc Agent http://localhost:8003" -ForegroundColor DarkGray
Write-Host "  Frontend  http://localhost:3000" -ForegroundColor DarkGray
