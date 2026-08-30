@echo off
echo Building STORM PS4 PKG SENDER...

rmdir /s /q build
rmdir /s /q dist

pyinstaller --noconfirm --onefile --windowed --clean ^
    --name "STORM PS4 PKG SENDER" ^
    --icon "stormps4pkgsender.ico" ^
    --add-data "stormps4pkgsender.ico;." ^
    --add-data "tools;tools" ^
    stormps4pkgsender.py

echo.
echo Build Complete. Executable is in the 'dist' folder.
pause
