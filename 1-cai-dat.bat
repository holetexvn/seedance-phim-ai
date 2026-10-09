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
echo === 2. Tai ark-mcp (ma nguon mo ben thu ba, khong phai san pham chinh thuc cua BytePlus) ===
rem Ghim dung ban ark-mcp da kiem tra (commit a802fd3, 09/10/2026), khong lay ban moi nhat
set "ARK_COMMIT=a802fd39fd06752290e6c7d92475428044d48777"
if not exist ark\pyproject.toml (
  git clone https://github.com/byteplus-sa/ark-mcp.git ark
  git -C ark checkout %ARK_COMMIT% || (echo Khong checkout duoc ark-mcp & pause & exit /b 1)
)
echo === 3. Cai thu vien ===
cd ark
uv sync --locked
if not exist .env copy ..\cau-hinh\.env.example .env
uv run python -c "import ark_mcp; print('ark-mcp OK')"
echo.
echo Xong. Mo ark\.env, dan API key vao dong BYTEPLUS_MODELARK_API_KEY=
pause
