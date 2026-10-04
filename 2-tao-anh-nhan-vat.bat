@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Sinh anh tham chieu nhan vat bang Seedream (1-3 phut moi anh) ...
uv run --no-project python hang_doi.py --anh
pause
