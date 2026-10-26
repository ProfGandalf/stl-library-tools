@echo off
rem Uruchamia aplikacje STL Library Tools (okno, bez konsoli).
rem Wymaga Pythona 3 z python.org - tkinter jest w standardzie.
cd /d "%~dp0"

where pyw >nul 2>nul && (start "" pyw -3 "%~dp0stl_tools.py" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0stl_tools.py" & exit /b 0)

echo.
echo  [BLAD] Nie znaleziono Pythona.
echo.
echo   Zainstaluj Pythona 3 ze strony https://www.python.org/downloads/
echo   (zaznacz w instalatorze "Add python.exe to PATH"), potem uruchom ponownie.
echo.
pause
