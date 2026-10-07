#!/bin/zsh
# Build MatrixLab.app (a double-clickable macOS app) with PyInstaller.
#
#   ./build_app.sh            -> dist/MatrixLab.app
#
# One-time setup if PyInstaller is missing:
#   python3 -m pip install --user pyinstaller
#
# The bundle carries its own Python, numpy, matplotlib and Tk, so it runs
# without a terminal and without the system python.  Expect a few hundred MB.
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller --noconfirm --clean --windowed \
    --name "MatrixLab" \
    --osx-bundle-identifier "com.joehammon.matrixlab" \
    --exclude-module PyQt5 --exclude-module PyQt6 \
    --exclude-module PySide2 --exclude-module PySide6 \
    --exclude-module IPython --exclude-module jupyter \
    --exclude-module pandas --exclude-module scipy \
    --exclude-module cv2 --exclude-module PIL.ImageQt \
    app.py

echo
echo "Built: $(pwd)/dist/MatrixLab.app"
echo "Drag it to /Applications, or run:  open dist/MatrixLab.app"
