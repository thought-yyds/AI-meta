#!/bin/bash

echo "========================================"
echo "   MyMeta Backend Server"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "[WARNING] .env file not found!"
    echo "Please create .env file with your configuration."
    echo "See START.md for details."
    echo ""
    exit 1
fi

# Check if database is initialized
echo "Checking database connection..."
python3 -c "from app.core.database import engine; from sqlalchemy import text; engine.connect().execute(text('SELECT 1'))" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[INFO] Database not initialized. Running init_db.py..."
    python3 init_db.py
    if [ $? -ne 0 ]; then
        echo "[ERROR] Database initialization failed!"
        exit 1
    fi
    echo ""
fi

echo "Starting server..."
echo ""
echo "Server will be available at:"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

