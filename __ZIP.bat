@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Pakowanie folderow do ZIP
cd /d "%~dp0"

rem ============================================================
rem  USTAWIENIA
rem ============================================================
rem  Foldery do pominiecia - nazwy oddzielone srednikami,
rem  srednik takze na poczatku i na koncu. Wielkosc liter bez znaczenia.
set "POMIN=;Stare;Robocze;Do sprawdzenia;"

rem  Foldery zaczynajace sie od _ sa pomijane ZAWSZE
rem  (wystarczy zmienic nazwe, np. _Robocze, zeby go nie pakowac)

rem  0 = pomin foldery, ktore juz maja swojego zipa (szybko, tylko nowe)
rem  1 = pakuj wszystko od nowa (nadpisuje stare zipy)
set "NADPISZ=0"
rem ============================================================

echo.
echo  ============================================
echo   PAKOWANIE FOLDEROW DO ZIP
echo  ============================================
echo   Folder: %~dp0
echo.

rem --- 7-Zip jest szybszy i lepiej radzi sobie z nazwami; jak nie ma - tar z Windowsa
set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"
set "SEVENZIP="
if exist "%PF%\7-Zip\7z.exe" set "SEVENZIP=%PF%\7-Zip\7z.exe"
if not defined SEVENZIP if exist "%PF86%\7-Zip\7z.exe" set "SEVENZIP=%PF86%\7-Zip\7z.exe"

if defined SEVENZIP (
    echo   Pakowarka: 7-Zip
) else (
    echo   Pakowarka: tar ^(wbudowany w Windows^)
)
echo.

set /a OK=0, SKIPPED=0, ERR=0
for /d %%D in (*) do call :folder "%%~nxD"

echo.
echo  ============================================
echo   ZAKONCZONO
echo   Spakowano: !OK!   Pominieto: !SKIPPED!   Bledy: !ERR!
echo  ============================================
echo.
pause
exit /b 0

rem ================== funkcje pomocnicze ======================

:folder
set "N=%~1"

if "!N:~0,1!"=="_" (
    echo   [-] pomijam:  !N!
    set /a SKIPPED+=1
    exit /b 0
)

set "TEST=!POMIN:;%~1;=!"
if /i not "!TEST!"=="!POMIN!" (
    echo   [-] pomijam:  !N!
    set /a SKIPPED+=1
    exit /b 0
)

if "%NADPISZ%"=="0" if exist "!N!.zip" (
    echo   [=] juz jest: !N!.zip
    set /a SKIPPED+=1
    exit /b 0
)

if exist "!N!.zip" del "!N!.zip"
echo   [+] pakuje:   !N!

if defined SEVENZIP (
    "!SEVENZIP!" a -tzip -mx=5 "!N!.zip" "!N!" >nul
) else (
    tar -a -c -f "!N!.zip" "!N!"
)

if errorlevel 1 (
    echo       [BLAD] nie udalo sie spakowac: !N!
    set /a ERR+=1
) else (
    set /a OK+=1
)
exit /b 0
