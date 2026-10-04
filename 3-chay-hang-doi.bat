@echo off
chcp 65001 >nul
cd /d "%~dp0"
uv run --no-project python hang_doi.py --max 3
pause
