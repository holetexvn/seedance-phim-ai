@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 1. Kiem tra uv ===
where uv >nul 2>nul
if errorlevel 1 (
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
uv --version
echo === 2. Tai ark-mcp (repo cua BytePlus tren GitHub) ===
if not exist ark\pyproject.toml git clone --depth 1 https://github.com/byteplus-sa/ark-mcp.git ark
echo === 3. Cai thu vien ===
cd ark
uv sync
if not exist .env copy ..\cau-hinh\.env.example .env
uv run python -c "import ark_mcp; print('ark-mcp OK')"
echo.
echo Xong. Mo ark\.env, dan API key vao dong BYTEPLUS_MODELARK_API_KEY=
pause
