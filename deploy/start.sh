#!/bin/bash
set -e

echo "Starting Aeon Cascade..."

# Start backend API in background
echo "Starting backend API on port 8000..."
cd /app
python -m indra_agent.main &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 5

# Start frontend
echo "Starting frontend on port 3000..."
cd /app/frontend
PORT=3000 node build &
FRONTEND_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap shutdown SIGTERM SIGINT

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
