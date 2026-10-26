@echo off
setlocal enabledelayedexpansion
title Render 3D models - contact sheet
cd /d "%~dp0"

echo.
echo  ============================================
echo   RENDER A SHEET OF 3D MODELS
echo  ============================================
echo   Folder: %~dp0
echo.

set "BLENDER="

rem ============================================================
rem  MANUAL PATH - if auto-detection fails:
rem  remove "rem " from the line below and enter your own path
rem ============================================================
set "BLENDER=X:\SteamLibrary\steamapps\common\Blender\blender.exe"

rem --- if a manual path is set but the file does not exist, clear it and search
if defined BLENDER if not exist "!BLENDER!" (
    echo   [i] The given path does not exist, searching automatically...
    set "BLENDER="
)

rem --- the brackets in ProgramFiles(x86) break for blocks, so copy to variables
set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"
set "LAP=%LOCALAPPDATA%"

rem --- 1. Blender in PATH?
if not defined BLENDER (
    for /f "delims=" %%i in ('where blender.exe 2^>nul') do (
        if not defined BLENDER set "BLENDER=%%i"
    )
)

rem --- 2. Typical installer locations (newest version first)
if not defined BLENDER call :scan "%PF%\Blender Foundation"
if not defined BLENDER call :scan "%PF86%\Blender Foundation"
if not defined BLENDER call :scan "%LAP%\Programs\Blender Foundation"
if not defined BLENDER call :scan "D:\Blender Foundation"
if not defined BLENDER call :scan "E:\Blender Foundation"

rem --- 3. Direct paths (Steam, portable)
if not defined BLENDER call :try "%PF86%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "%PF%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "X:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "D:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "E:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "%~dp0blender\blender.exe"

if not defined BLENDER goto :notfound

echo   Blender: !BLENDER!
echo.
echo   Rendering... (may take a few minutes)
echo   Do not close this window.
echo.

rem --- remember the start time (in hundredths of a second since midnight)
set "T=%TIME: =0%"
for /f "tokens=1-4 delims=:.," %%a in ("%T%") do (
    set /a "T_START=(((1%%a-100)*60+(1%%b-100))*60+(1%%c-100))*100+(1%%d-100)"
)

"!BLENDER!" --background --python "%~dp0__render_grid.py"

rem --- compute the duration
set "T=%TIME: =0%"
for /f "tokens=1-4 delims=:.," %%a in ("%T%") do (
    set /a "T_END=(((1%%a-100)*60+(1%%b-100))*60+(1%%c-100))*100+(1%%d-100)"
)
set /a "T_DIFF=T_END-T_START"
if !T_DIFF! lss 0 set /a "T_DIFF=T_DIFF+8640000"
set /a "T_H=T_DIFF/360000"
set /a "T_M=(T_DIFF%%360000)/6000"
set /a "T_S=(T_DIFF%%6000)/100"

if !T_H! gtr 0 (
    set "T_TXT=!T_H! h !T_M! min !T_S! s"
) else (
    if !T_M! gtr 0 (
        set "T_TXT=!T_M! min !T_S! s"
    ) else (
        set "T_TXT=!T_S! s"
    )
)

echo.
echo  ============================================
echo   FINISHED. Check the messages above.
echo   Time: !T_TXT!
echo   The PNG files are in this folder.
echo  ============================================
echo.
pause
exit /b 0

rem ===================== helper functions =====================

:scan
rem scans a folder for subfolders containing blender.exe (newest name first)
if not exist "%~1" exit /b 0
for /f "delims=" %%V in ('dir /b /ad /o-n "%~1" 2^>nul') do (
    if not defined BLENDER (
        if exist "%~1\%%V\blender.exe" set "BLENDER=%~1\%%V\blender.exe"
    )
)
exit /b 0

:try
if not defined BLENDER if exist "%~1" set "BLENDER=%~1"
exit /b 0

:notfound
echo  [ERROR] Blender was not found automatically.
echo.
echo   HOW TO FIX:
echo   1. Find your blender.exe - easiest: right-click the Blender
echo      shortcut, choose Properties and look at the "Target" field
echo      (or "Open file location")
echo   2. Open this __RENDER.bat file in Notepad
echo   3. Find the line:   rem set "BLENDER=C:\Program Files\..."
echo   4. Remove "rem " at its start and enter your own path
echo   5. Save and run again
echo.
pause
exit /b 1
