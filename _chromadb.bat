@echo off
cd /d "%~dp0"
title HELIX-CHROMADB
chroma run --path chroma_db --host 0.0.0.0 --port 8093
