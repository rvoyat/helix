@echo off
cd /d "%~dp0"
title HELIX — Arresto

echo.
echo  Arresto di HELIX in corso...
echo.

REM Kill backend window
taskkill /FI "WINDOWTITLE eq HELIX-BACKEND" /F /T >nul 2>&1

REM Kill chromadb window
taskkill /FI "WINDOWTITLE eq HELIX-CHROMADB" /F /T >nul 2>&1

REM Kill by port as fallback
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8092 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%p /T >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8093 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%p /T >nul 2>&1
)

echo  HELIX fermato.
echo.
timeout /t 2 /nobreak >nul
