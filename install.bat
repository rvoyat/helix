@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title HELIX — Installazione

echo.
echo  ============================================================
echo   HELIX — Installazione e Verifica Dipendenze
echo   Industry Enterprise - Health Accenture
echo  ============================================================
echo.

set ERRORS=0

REM ── [1/5] Verifica Python ──────────────────────────────────────────────
echo [1/5] Verifica Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERRORE: Python non trovato nel PATH.
    echo  Scarica e installa Python 3.10+ da https://www.python.org/downloads/
    echo  Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    echo.
    set ERRORS=1
    goto SUMMARY
)

REM Verifica versione minima Python 3.10
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if !PYMAJ! LSS 3 (
    echo  ERRORE: Python !PYVER! non supportato. Richiesto Python 3.10+.
    set ERRORS=1
    goto SUMMARY
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 10 (
    echo  ERRORE: Python !PYVER! non supportato. Richiesto Python 3.10+.
    set ERRORS=1
    goto SUMMARY
)
echo  OK — Python !PYVER!

REM ── [2/5] Verifica pip ─────────────────────────────────────────────────
echo [2/5] Verifica pip...

pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  pip non trovato. Installazione in corso...
    python -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo  ERRORE: impossibile installare pip.
        set ERRORS=1
        goto SUMMARY
    )
)
echo  OK — pip disponibile.

REM ── [3/5] Installazione dipendenze Python ─────────────────────────────
echo [3/5] Installazione dipendenze da requirements.txt...
echo  (prima installazione: puo' richiedere 5-10 minuti)
echo.

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  ERRORE: installazione dipendenze fallita.
    echo  Controlla la connessione internet e riprova.
    set ERRORS=1
    goto SUMMARY
)
echo.
echo  OK — dipendenze installate.

REM ── [4/5] Verifica pacchetti critici ──────────────────────────────────
echo [4/5] Verifica pacchetti critici...

set MISSING=

python -c "import uvicorn" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! uvicorn

python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! fastapi

python -c "import chromadb" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! chromadb

python -c "import langchain" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! langchain

python -c "import sentence_transformers" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! sentence-transformers

python -c "import dotenv" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! python-dotenv

python -c "import google.generativeai" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! google-generativeai

python -c "import fitz" >nul 2>&1
if %errorlevel% neq 0 set MISSING=!MISSING! PyMuPDF

if not "!MISSING!"=="" (
    echo.
    echo  ATTENZIONE: pacchetti non importabili:!MISSING!
    echo  Tentativo reinstallazione...
    pip install !MISSING!
    if %errorlevel% neq 0 (
        echo  ERRORE: reinstallazione fallita per:!MISSING!
        set ERRORS=1
    )
) else (
    echo  OK — tutti i pacchetti critici sono disponibili.
)

REM Verifica comando chroma CLI
chroma --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ATTENZIONE: comando 'chroma' non trovato nel PATH.
    echo  Provo a individuare il percorso degli script Python...
    for /f "delims=" %%s in ('python -c "import sysconfig; print(sysconfig.get_path(\"scripts\"))"') do set PYBIN=%%s
    if exist "!PYBIN!\chroma.exe" (
        echo  Trovato in !PYBIN!
        echo  Aggiungi questo percorso al PATH di sistema:
        echo    !PYBIN!
        echo  oppure usa il percorso completo in _chromadb.bat.
        REM Aggiorna _chromadb.bat per usare percorso completo
        echo @echo off > "%~dp0_chromadb.bat"
        echo cd /d "%%~dp0" >> "%~dp0_chromadb.bat"
        echo title HELIX-CHROMADB >> "%~dp0_chromadb.bat"
        echo "!PYBIN!\chroma.exe" run --path chroma_db --host 0.0.0.0 --port 8093 >> "%~dp0_chromadb.bat"
        echo  _chromadb.bat aggiornato con percorso completo.
    ) else (
        echo  ERRORE: chroma.exe non trovato. Verifica l'installazione di chromadb.
        set ERRORS=1
    )
) else (
    echo  OK — comando 'chroma' disponibile.
)

REM ── [5/5] Verifica configurazione ─────────────────────────────────────
echo [5/5] Verifica configurazione...

if not exist "%~dp0.env" (
    echo.
    echo  ATTENZIONE: file .env non trovato.
    echo  Crea il file .env con il seguente contenuto:
    echo.
    echo    GEMINI_API_KEY=la_tua_chiave_api
    echo    GEMINI_MODEL=gemini-2.5-flash
    echo    DOCS_FOLDER=./docs
    echo    INGESTION_PROVIDER=langchain
    echo.
    echo  Ottieni la chiave API su https://aistudio.google.com/apikey
    set ERRORS=1
) else (
    REM Verifica che GEMINI_API_KEY sia impostata e non vuota
    set KEY_OK=0
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
        if "%%a"=="GEMINI_API_KEY" if not "%%b"=="" set KEY_OK=1
    )
    if !KEY_OK! EQU 0 (
        echo  ATTENZIONE: GEMINI_API_KEY non impostata nel file .env
        echo  Ottieni la chiave API su https://aistudio.google.com/apikey
        set ERRORS=1
    ) else (
        echo  OK — file .env presente e GEMINI_API_KEY configurata.
    )
)

REM Crea cartella docs se non esiste
if not exist "%~dp0docs" (
    mkdir "%~dp0docs"
    echo  OK — cartella 'docs' creata.
) else (
    echo  OK — cartella 'docs' esistente.
)

REM ── Riepilogo ──────────────────────────────────────────────────────────
:SUMMARY
echo.
echo  ============================================================
if %ERRORS% EQU 0 (
    echo   INSTALLAZIONE COMPLETATA CON SUCCESSO
    echo.
    echo   Avvia HELIX con:  start.bat
) else (
    echo   INSTALLAZIONE COMPLETATA CON ERRORI
    echo.
    echo   Risolvi gli errori sopra riportati, poi riesegui install.bat
    echo   o avvia direttamente start.bat.
)
echo  ============================================================
echo.
pause
endlocal
