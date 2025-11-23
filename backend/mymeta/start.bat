@echo off
echo ========================================
echo    MyMeta Backend Server
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [WARNING] .env file not found!
    echo Please create .env file with your configuration.
    echo See START.md for details.
    echo.
    pause
    exit /b 1
)

REM Check if database is initialized
echo Checking database connection...
python -c "from app.core.database import engine; from sqlalchemy import text; engine.connect().execute(text('SELECT 1'))" 2>nul
if errorlevel 1 (
    echo [INFO] Database not initialized. Running init_db.py...
    python init_db.py
    if errorlevel 1 (
        echo [ERROR] Database initialization failed!
        pause
        exit /b 1
    )
    echo.
)

echo Starting server...
echo.
echo Server will be available at:
echo   - API Docs: http://localhost:8000/docs
echo   - Health: http://localhost:8000/health
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause

