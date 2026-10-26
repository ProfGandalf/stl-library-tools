#!/bin/sh
# Uruchamia aplikacje STL Library Tools na Linuksie.
# Wymaga python3 z tkinter (Debian/Ubuntu: sudo apt install python3-tk,
# Fedora: sudo dnf install python3-tkinter, Arch: sudo pacman -S tk).
cd "$(dirname "$0")" || exit 1
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Brak tkinter. Zainstaluj pakiet python3-tk (albo python3-tkinter)."
    exit 1
fi
exec python3 stl_tools.py "$@"
