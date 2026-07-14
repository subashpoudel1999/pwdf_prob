@echo off
setlocal
cd /d "%~dp0"

REM --- Locate Git Bash (needed to run run.sh) ---
set "BASH_EXE="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH_EXE=C:\Program Files\Git\bin\bash.exe"
if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "BASH_EXE=C:\Program Files (x86)\Git\bin\bash.exe"
where bash >nul 2>nul
if "%BASH_EXE%"=="" if %ERRORLEVEL%==0 set "BASH_EXE=bash"

if "%BASH_EXE%"=="" (
  echo ERROR: Could not find Git Bash ^(bash.exe^).
  echo Please install Git for Windows from https://git-scm.com/download/win
  echo then run this file again.
  echo.
  pause
  exit /b 1
)

REM --- Make sure Flutter is reachable ---
where flutter >nul 2>nul
if not %ERRORLEVEL%==0 (
  if exist "C:\flutter\bin\flutter.bat" (
    set "PATH=C:\flutter\bin;%PATH%"
  ) else (
    echo ERROR: Could not find Flutter on PATH or at C:\flutter\bin.
    echo Please install Flutter ^(see instructions.html, Step 2^) and make sure
    echo "flutter" works from a normal Command Prompt window before retrying.
    echo.
    pause
    exit /b 1
  )
)

"%BASH_EXE%" run.sh
echo.
echo App stopped. Press any key to close this window.
pause >nul
