@echo off
setlocal enabledelayedexpansion
title Render modeli 3D - plansza
cd /d "%~dp0"

echo.
echo  ============================================
echo   RENDER PLANSZY Z MODELAMI 3D
echo  ============================================
echo   Folder: %~dp0
echo.

set "BLENDER="

rem ============================================================
rem  RECZNA SCIEZKA - jesli auto-wykrywanie zawiedzie:
rem  usun "rem " z ponizszej linii i wpisz swoja sciezke
rem ============================================================
set "BLENDER=X:\SteamLibrary\steamapps\common\Blender\blender.exe"

rem --- jesli reczna sciezka wpisana ale plik nie istnieje, wyczysc i szukaj dalej
if defined BLENDER if not exist "!BLENDER!" (
    echo   [i] Wpisana sciezka nie istnieje, szukam automatycznie...
    set "BLENDER="
)

rem --- nawiasy w ProgramFiles(x86) psuja bloki for, wiec kopiujemy do zmiennych
set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"
set "LAP=%LOCALAPPDATA%"

rem --- 1. Blender w PATH?
if not defined BLENDER (
    for /f "delims=" %%i in ('where blender.exe 2^>nul') do (
        if not defined BLENDER set "BLENDER=%%i"
    )
)

rem --- 2. Typowe lokalizacje instalatora (najnowsza wersja pierwsza)
if not defined BLENDER call :scan "%PF%\Blender Foundation"
if not defined BLENDER call :scan "%PF86%\Blender Foundation"
if not defined BLENDER call :scan "%LAP%\Programs\Blender Foundation"
if not defined BLENDER call :scan "D:\Blender Foundation"
if not defined BLENDER call :scan "E:\Blender Foundation"

rem --- 3. Sciezki bezposrednie (Steam, portable)
if not defined BLENDER call :try "%PF86%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "%PF%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "X:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "D:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "E:\SteamLibrary\steamapps\common\Blender\blender.exe"
if not defined BLENDER call :try "%~dp0blender\blender.exe"

if not defined BLENDER goto :notfound

echo   Blender: !BLENDER!
echo.
echo   Renderowanie... (moze potrwac kilka minut)
echo   Nie zamykaj tego okna.
echo.

rem --- zapamietaj czas startu (w setnych sekundy od polnocy)
set "T=%TIME: =0%"
for /f "tokens=1-4 delims=:.," %%a in ("%T%") do (
    set /a "T_START=(((1%%a-100)*60+(1%%b-100))*60+(1%%c-100))*100+(1%%d-100)"
)

"!BLENDER!" --background --python "%~dp0__render_grid.py"

rem --- policz czas trwania
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
    set "T_TXT=!T_H! godz !T_M! min !T_S! s"
) else (
    if !T_M! gtr 0 (
        set "T_TXT=!T_M! min !T_S! s"
    ) else (
        set "T_TXT=!T_S! s"
    )
)

echo.
echo  ============================================
echo   ZAKONCZONO. Sprawdz komunikaty powyzej.
echo   Czas: !T_TXT!
echo   Pliki PNG znajdziesz w tym folderze.
echo  ============================================
echo.
pause
exit /b 0

rem ================== funkcje pomocnicze ======================

:scan
rem skanuje folder w poszukiwaniu podfolderow z blender.exe (od najnowszej nazwy)
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
echo  [BLAD] Nie znaleziono Blendera automatycznie.
echo.
echo   JAK NAPRAWIC:
echo   1. Znajdz swoj blender.exe - najprosciej: kliknij prawym na skrot
echo      Blendera, wybierz Wlasciwosci i zobacz pole "Element docelowy"
echo      (albo "Otworz lokalizacje pliku")
echo   2. Otworz ten plik RENDER.bat w Notatniku
echo   3. Znajdz linie:   rem set "BLENDER=C:\Program Files\..."
echo   4. Usun z niej "rem " na poczatku i wpisz swoja sciezke
echo   5. Zapisz i uruchom ponownie
echo.
pause
exit /b 1
