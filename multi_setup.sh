#!/bin/bash

# Function to log messages with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to ping URL with random interval
ping_url() {
    local url="$1"
    log_message "Pinging URL: $url"
    status_code=$(curl -s -o /dev/null -w '%{http_code}' "$url")
    log_message "URL ping status: $status_code"
}

# Function to find available port
find_available_port() {
    log_message "Finding available port..."
    
    # Try using lsof first
    if command -v lsof &> /dev/null; then
        for port in $(seq 5000 65535); do
            if ! lsof -i :$port > /dev/null 2>&1; then
                log_message "Found available port: $port"
                echo $port
                return 0
            fi
        done
    fi
    
    # Fallback to ss
    if command -v ss &> /dev/null; then
        for port in $(seq 5000 65535); do
            if ! ss -tuln | grep -q ":$port "; then
                log_message "Found available port: $port"
                echo $port
                return 0
            fi
        done
    fi
    
    # Default port if no available port found
    log_message "No available port found, using default 8081"
    echo 8081
}

# Upgrade pip
log_message "Upgrading pip..."
python3 -m pip install --upgrade pip

# Install required dependencies
log_message "Installing dependencies..."
pip3 install psutil python-telegram-bot==20.0

# Install C++ compiler and libcurl
log_message "Installing C++ compiler and libcurl..."
sudo apt update && sudo apt install g++ libcurl4-openssl-dev -y

# Clone repositories
log_message "Cloning bin repository..."
cd /workspace
git clone https://github.com/r404nichtgefunden/bin.git

# Compile stxx
log_message "Compiling stxx..."
cd /workspace/bin
g++ -std=c++20 stxx.cpp -o stxx -pthread -lcurl

# Setup root directory
log_message "Setting up root directory..."
sudo chmod 777 /root
sudo cp /workspace/bin/stxx /root
sudo cp -r /workspace/code/bin /root

# Find all Python files in patrick directory
log_message "Finding Python files in patrick directory..."
PYTHON_FILES=()
SCRIPT_PORTS=()

for py_file in $(find /workspace/code/patrick -name "*.py"); do
    PYTHON_FILES+=("$py_file")
    # Find an available port for each file
    PORT=$(find_available_port)
    SCRIPT_PORTS+=("$PORT")
    
    # Save port to file
    script_name=$(basename "$py_file" .py)
    echo "$PORT" > "/root/${script_name}_port.txt"
    
    log_message "Assigned port $PORT to $py_file"
done

# Create supervisor configurations for each Python file
log_message "Creating supervisor configurations..."
for i in "${!PYTHON_FILES[@]}"; do
    py_file="${PYTHON_FILES[$i]}"
    port="${SCRIPT_PORTS[$i]}"
    script_name=$(basename "$py_file" .py)
    script_dir=$(dirname "$py_file")
    
    # Create supervisor config
    cat > "/tmp/${script_name}.conf" << EOF
[program:${script_name}]
directory=${script_dir}
command=/usr/bin/python3 ${py_file} --port ${port}
autostart=true
autorestart=true
stderr_logfile=/var/log/${script_name}.err.log
stdout_logfile=/var/log/${script_name}.out.log
EOF
    
    # Move to supervisor directory
    sudo mv "/tmp/${script_name}.conf" /etc/supervisor/conf.d/
    
    log_message "Created supervisor config for $script_name on port $port"
done

# Enable and restart supervisor
log_message "Enabling and restarting supervisor..."
sudo systemctl enable supervisor
sudo systemctl restart supervisor

# Update supervisor
log_message "Updating supervisor..."
sudo supervisorctl reread
sudo supervisorctl update

# Run each Python file
log_message "Running Python files..."
for i in "${!PYTHON_FILES[@]}"; do
    py_file="${PYTHON_FILES[$i]}"
    port="${SCRIPT_PORTS[$i]}"
    script_name=$(basename "$py_file" .py)
    
    log_message "Running $script_name on port $port..."
    sudo nohup /usr/bin/python3 "$py_file" --port "$port" > "/root/${script_name}.log" 2>&1 &
    
    log_message "Started $script_name with PID: $!"
done

# Start the multi-heartbeat service
log_message "Starting multi-heartbeat service..."
sudo nohup /usr/bin/python3 /workspace/code/multi_heartbeat.py > /root/multi_heartbeat.log 2>&1 &
heartbeat_pid=$!
log_message "Started multi-heartbeat service with PID: $heartbeat_pid"

# Kill all processes except PID 1, binary files, and Python processes
log_message "Killing unnecessary processes..."

for pid in $(ps -eo pid | grep -v "PID\|1\|$$"); do
    # Check if this is the heartbeat process
    if [[ "$pid" == "$heartbeat_pid" ]]; then
        log_message "Keeping heartbeat process with PID: $pid"
        continue
    fi
    
    # Check if this is a Python process
    if ps -p "$pid" -o cmd= | grep -q "python"; then
        log_message "Keeping Python process with PID: $pid"
        continue
    fi
    
    # Check if this is a binary file
    if ps -p "$pid" -o cmd= | grep -q "bin"; then
        log_message "Keeping binary process with PID: $pid"
        continue
    fi
    
    # Kill the process
    log_message "Killing process with PID: $pid"
    sudo kill -9 "$pid" 2>/dev/null || true
done

log_message "All tasks completed successfully!"

# Keep the script running to maintain the session
log_message "Entering maintenance mode to keep session alive..."
while true; do
    # Ping URL with random interval
    sleep_time=$((30 + RANDOM % 60))
    ping_url "https://console.dashwave.io/workspace/8420"
    log_message "Next ping in $sleep_time seconds..."
    sleep $sleep_time
done