#!/bin/bash
# filepath: \\wsl$\Ubuntu\home\simon\code\goose-on-aca\app\ollama\start-ollama.sh

set -e

# Default model if none specified
DEFAULT_MODEL="qwen2.5:14b"
PLANNER_PORT="${PLANNER_PORT:-8801}"

# Function to start ollama and pull model (keeps running)
start_with_model() {
    local model="${1:-$DEFAULT_MODEL}"
    echo "Starting Ollama server..."
    ollama serve &
    
    # Wait for server to be ready
    echo "Waiting for Ollama server to be ready..."
    sleep 5
    
    # Try to pull the model
    echo "Pulling required model: $model"
    if ollama pull "$model"; then
        echo "Successfully pulled model: $model"
    else
        echo "Failed to pull model: $model, but server is running"
    fi
    
    echo "Ollama server is ready with model: $model"
    echo "Server will keep running... (Press Ctrl+C to stop)"
    wait
}

run_planner() {
    local model="${1:-$DEFAULT_MODEL}"
    echo "Starting Ollama server for planner mode..."
    ollama serve &
    local ollama_pid=$!

    cleanup() {
        echo "Shutting down Ollama server..."
        kill $ollama_pid 2>/dev/null || true
        wait $ollama_pid 2>/dev/null || true
    }
    trap cleanup EXIT

    echo "Waiting for Ollama server to be ready..."
    sleep 5
    echo "Ensuring model $model is available..."
    if ! ollama pull "$model"; then
        echo "Warning: unable to pull model $model; planner will still start."
    fi

    export OLLAMA_MODEL="$model"
    echo "Launching FastAPI planner on port $PLANNER_PORT"
    exec python -m uvicorn app.ollama_service.service:app --host 0.0.0.0 --port "$PLANNER_PORT"
}

# Function to pull model and quit with timeout/retry mechanism
pull_and_quit() {
    local model="${1:-$DEFAULT_MODEL}"
    local timeout=60  # 1 minute timeout
    local max_attempts=10  # Maximum retry attempts
    local attempt=1
    
    echo "Starting Ollama server temporarily..."
    ollama serve &
    local server_pid=$!
    
    # Wait for server to be ready
    echo "Waiting for Ollama server to be ready..."
    sleep 5
    
    # Retry loop with timeout
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt/$max_attempts: Pulling model $model (timeout: ${timeout}s)"
        
        # Start the pull command in background
        timeout $timeout ollama pull "$model" &
        local pull_pid=$!
        
        # Wait for the pull command to complete or timeout
        if wait $pull_pid 2>/dev/null; then
            echo "Successfully pulled model: $model"
            break
        else
            local exit_code=$?
            if [ $exit_code -eq 124 ]; then
                echo "Pull attempt $attempt timed out after ${timeout}s, retrying..."
            else
                echo "Pull attempt $attempt failed with exit code $exit_code, retrying..."
            fi
            
            # Kill any remaining ollama pull processes
            pkill -f "ollama pull" 2>/dev/null || true
            sleep 2
            
            attempt=$((attempt + 1))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        echo "Failed to pull model $model after $max_attempts attempts"
    fi
    
    echo "Shutting down Ollama server..."
    kill $server_pid
    wait $server_pid 2>/dev/null || true
    echo "Model pull process complete. Container will exit."
}

# Parse command line arguments
case "$1" in
    "serve")
        # Just start the server without pulling any model
        echo "Starting Ollama server only..."
        exec /bin/ollama serve
        ;;
    "start")
        # Start server and pull model (keeps running)
        model="${2:-$DEFAULT_MODEL}"
        start_with_model "$model"
        ;;
    "pull")
        # Pull model and quit
        model="${2:-$DEFAULT_MODEL}"
        pull_and_quit "$model"
        ;;
    "planner")
        model="${2:-$DEFAULT_MODEL}"
        run_planner "$model"
        ;;
    "interactive"|"bash"|"shell")
        # Interactive bash shell
        exec /bin/bash
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [COMMAND] [MODEL]"
        echo ""
        echo "Commands:"
        echo "  serve              Start Ollama server only"
        echo "  start [MODEL]      Start server and pull model (keeps running)"
        echo "  pull [MODEL]       Pull model and exit (default: $DEFAULT_MODEL)"
        echo "  interactive        Start interactive bash shell"
        echo "  bash               Same as interactive"
        echo "  shell              Same as interactive"
        echo "  help               Show this help"
        echo "  [other]            Pass command directly to ollama"
        echo ""
        echo "Examples:"
        echo "  $0 start llama2:7b    # Start server with model"
        echo "  $0 pull qwen2.5:32b   # Pull model and exit"
        echo "  $0 serve              # Just run server"
        echo "  $0 interactive        # Debug shell"
        ;;
    "")
        # Default behavior: start planner mode with default model
        run_planner "$DEFAULT_MODEL"
        ;;
    *)
        # Pass through any other ollama commands
        exec /bin/ollama "$@"
        ;;
esac