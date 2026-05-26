#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=================================================="
echo "   AIuthor - Premium Agentic Book Writer Startup   "
echo "=================================================="

# Check for Python & Poetry
if ! command -v poetry &> /dev/null; then
    echo "ERROR: Poetry is not installed on this system."
    echo "Please make sure /usr/bin/poetry is in your PATH."
    exit 1
fi

# Check for Node & NPM
if ! command -v npm &> /dev/null; then
    echo "ERROR: NPM is not installed on this system."
    echo "Please make sure node and npm are available."
    exit 1
fi

# 1. Install & Setup Backend
echo "--> Setting up Python Backend dependencies..."
cd backend
poetry install
cd ..

# 2. Install & Build Frontend
echo "--> Setting up React Frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "node_modules not found. Running npm install..."
    npm install
fi

echo "--> Compiling React Frontend (Vite production build)..."
npm run build
cd ..

# 3. Launch FastAPI Server
echo "=================================================="
echo "   Server starting on http://localhost:8000        "
echo "   API Docs available on http://localhost:8000/docs "
echo "=================================================="

cd backend
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
