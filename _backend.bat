@echo off
cd /d "%~dp0"
title HELIX-BACKEND
python -m uvicorn backend.main:app --port 8092
