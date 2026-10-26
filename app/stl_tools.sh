#!/bin/sh
# Launches the STL Library Tools app on Linux.
# Needs python3 with tkinter (Debian/Ubuntu: sudo apt install python3-tk,
# Fedora: sudo dnf install python3-tkinter, Arch: sudo pacman -S tk).
cd "$(dirname "$0")" || exit 1
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "tkinter is missing. Install the python3-tk (or python3-tkinter) package."
    exit 1
fi
exec python3 stl_tools.py "$@"
