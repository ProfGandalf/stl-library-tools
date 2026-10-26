@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Packing folders into ZIP
cd /d "%~dp0"

rem ============================================================
rem  SETTINGS
rem ============================================================
rem  Folders to skip - names separated by semicolons,
rem  with a semicolon at the start and the end too. Case-insensitive.
set "SKIP=;Stare;Robocze;Do sprawdzenia;"

rem  Folders starting with _ are ALWAYS skipped
rem  (just rename one, e.g. _Robocze, to stop it from being packed)

rem  0 = skip folders that already have their zip (fast, only new ones)
rem  1 = pack everything again (overwrites old zips)
set "OVERWRITE=0"
rem ============================================================

echo.
echo  ============================================
echo   PACKING FOLDERS INTO ZIP
echo  ============================================
echo   Folder: %~dp0
echo.

rem --- 7-Zip is faster and handles names better; if missing - tar from Windows
set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"
set "SEVENZIP="
if exist "%PF%\7-Zip\7z.exe" set "SEVENZIP=%PF%\7-Zip\7z.exe"
if not defined SEVENZIP if exist "%PF86%\7-Zip\7z.exe" set "SEVENZIP=%PF86%\7-Zip\7z.exe"

if defined SEVENZIP (
    echo   Packer: 7-Zip
) else (
    echo   Packer: tar ^(built into Windows^)
)
echo.

set /a OK=0, SKIPPED=0, ERR=0
for /d %%D in (*) do call :folder "%%~nxD"

echo.
echo  ============================================
echo   FINISHED
echo   Packed: !OK!   Skipped: !SKIPPED!   Errors: !ERR!
echo  ============================================
echo.
pause
exit /b 0

rem ===================== helper functions =====================

:folder
set "N=%~1"

if "!N:~0,1!"=="_" (
    echo   [-] skipping:  !N!
    set /a SKIPPED+=1
    exit /b 0
)

set "TEST=!SKIP:;%~1;=!"
if /i not "!TEST!"=="!SKIP!" (
    echo   [-] skipping:  !N!
    set /a SKIPPED+=1
    exit /b 0
)

if "%OVERWRITE%"=="0" if exist "!N!.zip" (
    echo   [=] exists:    !N!.zip
    set /a SKIPPED+=1
    exit /b 0
)

if exist "!N!.zip" del "!N!.zip"
echo   [+] packing:   !N!

if defined SEVENZIP (
    "!SEVENZIP!" a -tzip -mx=5 "!N!.zip" "!N!" >nul
) else (
    tar -a -c -f "!N!.zip" "!N!"
)

if errorlevel 1 (
    echo       [ERROR] could not pack: !N!
    set /a ERR+=1
) else (
    set /a OK+=1
)
exit /b 0
