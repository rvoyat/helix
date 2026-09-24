@echo off
cd /d "%~dp0"
title HELIX — IE Health Delivery Assistant

echo.
echo  ============================================================
echo   HELIX — Assistente Virtuale IE Health Delivery
echo   Industry Enterprise - Health Accenture
echo   Powered by Gemini + ChromaDB + LangChain
echo  ============================================================
echo.

REM ── [1/4] Check / install dependencies ───────────────────────────
pip show uvicorn >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Installazione dipendenze...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo  ERRORE: installazione dipendenze fallita.
        pause & exit /b 1
    )
) else (
    echo [1/4] Dipendenze OK.
)

REM ── [2/4] Start ChromaDB on port 8093 ────────────────────────────
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8093 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%p /T >nul 2>&1
)
echo [2/4] Avvio ChromaDB su http://localhost:8093 ...
start "HELIX-CHROMADB" /MIN "%~dp0_chromadb.bat"

echo [2/4] Verifica avvio ChromaDB...
set ATTEMPTS=0

:CHROMA_LOOP
set /a ATTEMPTS+=1
if %ATTEMPTS% gtr 20 goto CHROMA_FAILED
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try{$t=New-Object System.Net.Sockets.TcpClient;$t.Connect('localhost',8093);$t.Close();exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel% equ 0 goto CHROMA_DONE
goto CHROMA_LOOP

:CHROMA_FAILED
echo.
echo  ATTENZIONE: ChromaDB non risponde dopo 20 secondi.
echo  Controlla la finestra HELIX-CHROMADB per i dettagli.
echo.
pause
exit /b 1

:CHROMA_DONE
echo [2/4] ChromaDB attivo.

REM ── [3/4] Start backend on port 8092 ─────────────────────────────
echo [3/4] Avvio backend su http://localhost:8092 ...
start "HELIX-BACKEND" /MIN "%~dp0_backend.bat"

REM ── [4/4] Health check — poll up to 180 times (1s each) ──────────
echo [4/4] Verifica avvio backend (primo avvio: download modello + indicizzazione)...
set ATTEMPTS=0

:CHECK_LOOP
set /a ATTEMPTS+=1
if %ATTEMPTS% gtr 180 goto CHECK_FAILED
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try{Invoke-WebRequest http://localhost:8092/health -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel% equ 0 goto CHECK_DONE
goto CHECK_LOOP

:CHECK_FAILED
echo.
echo  ATTENZIONE: il backend non risponde dopo 180 secondi.
echo  Controlla la finestra HELIX-BACKEND per i dettagli.
echo.
pause
exit /b 1

:CHECK_DONE
echo.
echo  ============================================================
echo   Backend attivo  -- http://localhost:8092
echo   ChromaDB attivo -- http://localhost:8093
echo  ============================================================
echo.

REM ── Open chatbot ──────────────────────────────────────────────────
start "" "%~dp0frontend\index.html"

echo  HELIX e' in esecuzione.
echo  Backend : http://localhost:8092
echo  ChromaDB: http://localhost:8093
echo  Chatbot : frontend\index.html
echo  Documenti: frontend\docs.html
echo.
echo  Per fermare il server esegui stop.bat
echo.
pause
