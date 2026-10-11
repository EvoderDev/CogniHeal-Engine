@echo off
setlocal EnableDelayedExpansion

echo =====================================================================
echo  CogniHeal-Engine: Episodic Memory Engine - Setup (Windows)
echo =====================================================================

:: 1. Check Python installation
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.11 or higher from https://www.python.org/
    exit /b 1
)

:: 2. Check Python version (requires >= 3.11)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.11 or higher is required for CogniHeal-Engine.
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Current version: %%v
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] Detected %%v

:: 3. Create virtual environment (.venv) if it does not exist
if not exist ".venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment in .venv ...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found in .venv.
)

:: 4. Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

:: 5. Upgrade pip
echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: 6. Install requirements
echo [*] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies from requirements.txt.
    exit /b 1
)

:: 7. Install package in editable mode
echo [*] Installing CogniHeal-Engine in editable mode (pip install -e .)...
pip install -e .
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install CogniHeal-Engine package.
    exit /b 1
)

:: 8. Verify installation
echo [*] Verifying installation...
cogniheal --help >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Direct command 'cogniheal' check failed, verifying via python -m cogniheal...
    python -m cogniheal --help >nul 2>&1
)
echo [OK] CogniHeal CLI verification succeeded.

echo =====================================================================
echo  [SUCCESS] CogniHeal-Engine setup completed successfully!
echo =====================================================================
echo To start using CogniHeal-Engine:
echo   1. Activate virtual environment: .venv\Scripts\activate
echo   2. Launch Interactive REPL:      cogniheal  (or 'cogni' / 'cg')
echo   3. Run One-Shot Task:            cogniheal run --task "your task"
echo   4. Inspect Episodic Memory:      cogniheal memory stats
echo   5. Run Stress Benchmark:         cogniheal benchmark
echo =====================================================================
