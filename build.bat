@echo off
title DB Explorer - Build and Package Pipeline
color 0B

echo ==========================================================
echo               DB EXPLORER BUILD PIPELINE                 
echo ==========================================================
echo.

:: 1. Verify virtual environment exists
if not exist ".\dbexplorer_venv\Scripts\pyinstaller.exe" (
    color 0C
    echo [ERROR] Virtual environment or PyInstaller not found in .\dbexplorer_venv.
    echo Please make sure the venv is set up and PyInstaller is installed.
    pause
    exit /b 1
)

:: 2. Re-run PyInstaller to package the latest code changes
echo [STEP 1/2] Compiling Python code and assets with PyInstaller...
echo ----------------------------------------------------------
".\dbexplorer_venv\Scripts\pyinstaller.exe" DB_Explorer.spec
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo [SUCCESS] PyInstaller compiled successfully!
echo.

:: 3. Re-compile installer.iss with Inno Setup Compiler
echo [STEP 2/2] Packaging executable with Inno Setup...
echo ----------------------------------------------------------
set "ISCC_PATH=%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

if not exist "%ISCC_PATH%" (
    color 0E
    echo [WARNING] Inno Setup Compiler ISCC.exe was not found in standard paths.
    echo Skipping Step 2. You can compile installer.iss manually in the Inno Setup GUI.
    pause
    exit /b 0
)

"%ISCC_PATH%" installer.iss
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo [ERROR] Inno Setup compilation failed!
    pause
    exit /b %ERRORLEVEL%
)

color 0A
echo.
echo ==========================================================
echo [SUCCESS] Build pipeline completed successfully!
echo New installer: DB_Explorer_Setup.exe
echo ==========================================================
echo.
pause
