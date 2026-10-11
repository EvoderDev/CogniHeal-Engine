#!/usr/bin/env bash
# =====================================================================
#  CogniHeal-Engine: Episodic Memory Engine - Setup (Linux / macOS)
# =====================================================================
set -e

echo "====================================================================="
echo " CogniHeal-Engine: Episodic Memory Engine - Setup (Linux / macOS)"
echo "====================================================================="

# 1. Check Python installation (prefer python3)
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 is not installed or not in PATH."
    echo "Please install Python 3.11 or higher."
    exit 1
fi

# 2. Check Python version (>= 3.11)
$PYTHON_BIN -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null || {
    echo "[ERROR] Python 3.11 or higher is required for CogniHeal-Engine."
    echo "Current version: $($PYTHON_BIN --version 2>&1)"
    exit 1
}
echo "[OK] Detected $($PYTHON_BIN --version 2>&1)"

# 3. Create virtual environment (.venv) if missing
if [ ! -f ".venv/bin/activate" ]; then
    echo "[*] Creating virtual environment in .venv ..."
    $PYTHON_BIN -m venv .venv
    echo "[OK] Virtual environment created successfully."
else
    echo "[OK] Existing virtual environment found in .venv."
fi

# 4. Activate virtual environment
echo "[*] Activating virtual environment..."
source .venv/bin/activate

# 5. Upgrade pip
echo "[*] Upgrading pip..."
pip install --upgrade pip --quiet

# 6. Install requirements
echo "[*] Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# 7. Install package in editable mode
echo "[*] Installing CogniHeal-Engine in editable mode (pip install -e .)..."
pip install -e .

# 8. Verify installation
echo "[*] Verifying installation..."
cogniheal --help >/dev/null 2>&1 || python -m cogniheal --help >/dev/null 2>&1
echo "[OK] CogniHeal CLI verification succeeded."

echo "====================================================================="
echo " [SUCCESS] CogniHeal-Engine setup completed successfully!"
echo "====================================================================="
echo "To start using CogniHeal-Engine:"
echo "  1. Activate virtual environment: source .venv/bin/activate"
echo "  2. Launch Interactive REPL:      cogniheal  (or 'cogni' / 'cg')"
echo "  3. Run One-Shot Task:            cogniheal run --task \"your task\""
echo "  4. Inspect Episodic Memory:      cogniheal memory stats"
echo "  5. Run Stress Benchmark:         cogniheal benchmark"
echo "====================================================================="
