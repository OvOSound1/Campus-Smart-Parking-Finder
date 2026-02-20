#!/bin/bash
# Quick Start Script for Campus Smart Parking Finder

echo "==================================="
echo "Campus Smart Parking Finder"
echo "==================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "To start the server:"
echo "  python parking_server.py"
echo ""
echo "To run the RPC client:"
echo "  python rpc_client.py"
echo ""
echo "To run load tests:"
echo "  python load_test.py --baseline"
echo ""
echo "To simulate sensors:"
echo "  python sensor_simulator.py --duration 30"
echo ""
echo "To subscribe to events:"
echo "  python pubsub_client.py --lot LOT-A"
echo ""
