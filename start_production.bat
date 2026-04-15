@echo off
echo Starting NexClip PRODUCTION MODE (750 simultaneous tasks)...
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  WARNING: This requires a production server.                ║
echo ║  128+ CPU cores, 512 GB RAM, PostgreSQL, NVMe storage.     ║
echo ║  DO NOT run this on your local PC.                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Terminal 1 - Backend
start "NexClip Backend" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; clear; Write-Host 'Starting Backend...' -ForegroundColor Cyan; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"

:: Terminal 2 - Celery Worker: VIDEO PROCESSING (100 simultaneous)
start "Celery: Video" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; clear; Write-Host 'Video Worker (100 slots)...' -ForegroundColor Yellow; .\venv\Scripts\python.exe -m celery -A app.workers.celery_app worker -Q video --loglevel=info --pool=threads --concurrency=100 -n video@%%h"

:: Terminal 3 - Celery Worker: CAPTION RENDERING (600 simultaneous)
start "Celery: Captions" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; clear; Write-Host 'Caption Worker (600 slots)...' -ForegroundColor Yellow; .\venv\Scripts\python.exe -m celery -A app.workers.celery_app worker -Q captions --loglevel=info --pool=threads --concurrency=600 -n captions@%%h"

:: Terminal 4 - Celery Worker: NEXEARCH PIPELINES (50 simultaneous)
start "Celery: Nexearch" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\backend'; .\venv\Scripts\activate; clear; Write-Host 'Nexearch Worker (50 slots)...' -ForegroundColor Yellow; .\venv\Scripts\python.exe -m celery -A app.workers.celery_app worker -Q nexearch --loglevel=info --pool=threads --concurrency=50 -n nexearch@%%h"

:: Terminal 5 - Frontend
start "NexClip Frontend" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip\frontend'; clear; Write-Host 'Starting Frontend...' -ForegroundColor Cyan; npm run dev"

:: Terminal 6 - Nex Agent
start "Nex Agent" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nex Agent...' -ForegroundColor Cyan; python -m nex_agent.server"

:: Terminal 7 - Nexearch Intelligence Engine
start "Nexearch Engine" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Nexearch Engine...' -ForegroundColor Cyan; python -m uvicorn nexearch.main:app --host 0.0.0.0 --port 8002 --workers 2"

:: Terminal 8 - Arc Agent
start "Arc Agent" powershell -NoExit -Command "cd 'c:\Users\Vedsa\Desktop\AI Agents\NexClip'; .\backend\venv\Scripts\activate; clear; Write-Host 'Starting Arc Agent...' -ForegroundColor Cyan; python -m nexearch.arc.server"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  PRODUCTION MODE — All Services Started                     ║
echo ║                                                              ║
echo ║  Backend      :  http://localhost:8000  (4 workers)          ║
echo ║  Nex Agent    :  http://localhost:8001                       ║
echo ║  Nexearch     :  http://localhost:8002  (2 workers)          ║
echo ║  Arc Agent    :  http://localhost:8003                       ║
echo ║  Frontend     :  http://localhost:3000                       ║
echo ║                                                              ║
echo ║  Celery Workers (3 dedicated queues):                        ║
echo ║    Video      :  100 simultaneous pipelines                  ║
echo ║    Captions   :  600 simultaneous renders                    ║
echo ║    Nexearch   :   50 simultaneous pipelines                  ║
echo ║                                                              ║
echo ║  TOTAL        :  750 simultaneous tasks, ZERO queuing        ║
echo ╚══════════════════════════════════════════════════════════════╝

