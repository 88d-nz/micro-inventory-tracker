#!/bin/bash
# Micro Inventory Tracker - Startup Script

cd "$(dirname "$0")"

# Install requirements if needed
if ! python3 -c "from flask import Flask" 2>/dev/null; then
    echo "Installing Flask..."
    pip3 install -r requirements.txt
fi

# Run the app
echo "Starting Micro Inventory Tracker..."
echo "Access at: http://localhost:5000"
echo "Press Ctrl+C to stop"
python3 app.py