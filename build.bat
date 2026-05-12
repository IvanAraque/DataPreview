@echo off
echo Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DataPreview.spec del DataPreview.spec

echo Generando el ejecutable con PyInstaller...
call .venv\Scripts\activate
pyinstaller --name DataPreview --windowed --onefile src/app.py

echo.
echo Proceso completado. Tu ejecutable esta en la carpeta 'dist'.
pause
