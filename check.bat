@echo off
setlocal
cd /d "%~dp0"

set PYTHONPATH=python_src

python -m unittest discover -s tests
if errorlevel 1 exit /b 1

python -m compileall -q python_src tests
if errorlevel 1 exit /b 1

python -m super_mario_pygamece --doctor
if errorlevel 1 exit /b 1

python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('ruff') else 1)" >nul 2>nul
if not errorlevel 1 (
    python -m ruff check .
    if errorlevel 1 exit /b 1
) else (
    echo Skipping ruff; install dev extras to enable it.
)

python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('mypy') else 1)" >nul 2>nul
if not errorlevel 1 (
    python -m mypy python_src tests
    if errorlevel 1 exit /b 1
) else (
    echo Skipping mypy; install dev extras to enable it.
)

set SDL_VIDEODRIVER=dummy
python -m super_mario_pygamece --no-audio --smoke-test-frames 5
if errorlevel 1 exit /b 1

python -m super_mario_pygamece --level-name 1-1 --no-audio --smoke-test-frames 5
if errorlevel 1 exit /b 1

echo Checks passed.
