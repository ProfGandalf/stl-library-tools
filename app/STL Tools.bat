@echo off
rem Launches the STL Library Tools app (window, no console).
rem Needs Python 3 from python.org - tkinter is included.
cd /d "%~dp0"

where pyw >nul 2>nul && (start "" pyw -3 "%~dp0stl_tools.py" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0stl_tools.py" & exit /b 0)

echo.
echo  [ERROR] Python was not found.
echo.
echo   Install Python 3 from https://www.python.org/downloads/
echo   (tick "Add python.exe to PATH" in the installer), then run this again.
echo.
pause
