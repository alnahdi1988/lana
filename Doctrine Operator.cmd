@echo off
setlocal
set "REPO_ROOT=%~dp0"
start "" "%REPO_ROOT%\.venv\Scripts\pythonw.exe" -m doctrine_engine.product.cli launcher
