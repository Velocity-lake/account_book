@echo off
setlocal enabledelayedexpansion
set "APP_DIR=%~dp0"
pushd "%APP_DIR%"
set "VENV_DIR=%APP_DIR%.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 -m venv "%VENV_DIR%"
  ) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
      python -m venv "%VENV_DIR%"
    ) else (
      echo 请先安装 Python 3
      goto :end
    )
  )
)
call "%VENV_DIR%\Scripts\activate.bat"
set "PYTHONIOENCODING=utf-8"
if exist "%APP_DIR%requirements.txt" (
  pip install -r "%APP_DIR%requirements.txt"
)
"%VENV_DIR%\Scripts\python.exe" "%APP_DIR%app.py" %*
:end
popd
endlocal