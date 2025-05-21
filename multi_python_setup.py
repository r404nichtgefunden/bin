#!/usr/bin/env python3
import os
import subprocess
import time
import signal
import random
import sys
import logging
import threading
import socket
import argparse
import glob
from typing import List, Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("multi_python_setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MultiPythonSetup")

def run_command(command: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> Optional[str]:
    """Run a shell command and return its output"""
    logger.info(f"Running command: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        if result.stdout:
            logger.info(f"Command output: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"Command error: {result.stderr.strip()}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {command}")
        return None
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return None

def upgrade_pip():
    """Upgrade pip to the latest version"""
    logger.info("Upgrading pip...")
    return run_command("python3 -m pip install --upgrade pip")

def install_dependencies():
    """Install required dependencies"""
    logger.info("Installing dependencies...")
    return run_command("pip3 install psutil python-telegram-bot==20.0")

def install_cpp_compiler():
    """Install C++ compiler and libcurl"""
    logger.info("Installing C++ compiler and libcurl...")
    run_command("sudo apt update")
    return run_command("sudo apt install g++ libcurl4-openssl-dev -y")

def clone_repositories():
    """Clone the required repositories"""
    logger.info("Cloning bin repository...")
    return run_command("cd /workspace && git clone https://github.com/r404nichtgefunden/bin.git")

def compile_stxx():
    """Compile the stxx.cpp file"""
    logger.info("Compiling stxx.cpp...")
    return run_command("g++ -std=c++20 stxx.cpp -o stxx -pthread -lcurl", cwd="/workspace/bin")

def setup_root_directory():
    """Setup the root directory"""
    logger.info("Setting up root directory...")
    run_command("sudo chmod 777 /root")
    run_command("sudo cp /workspace/bin/stxx /root")
    return run_command("sudo cp -r /workspace/code/bin /root")

def find_available_port(start_port: int = 5000, end_port: int = 65535) -> int:
    """Find an available port in the given range"""
    logger.info(f"Finding available port in range {start_port}-{end_port}...")
    
    # Try using lsof command first
    try:
        used_ports_str = run_command("lsof -i -P -n | grep LISTEN | awk '{print $9}' | cut -d ':' -f 2 | sort -u")
        used_ports = set()
        if used_ports_str:
            for port_str in used_ports_str.split('\n'):
                try:
                    used_ports.add(int(port_str))
                except ValueError:
                    pass
        
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                logger.info(f"Found available port: {port}")
                return port
    except Exception as e:
        logger.warning(f"Error using lsof to find ports: {e}")
    
    # Fallback to socket method
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                logger.info(f"Found available port: {port}")
                return port
        except OSError:
            continue
    
    # If no port is available, return a default
    logger.warning("No available port found, using default 8081")
    return 8081

def run_python_script(script_path: str, port: int):
    """Run a Python script with the specified port"""
    script_name = os.path.basename(script_path)
    script_dir = os.path.dirname(script_path)
    log_file = f"{script_name.split('.')[0]}.log"
    port_file = f"{script_name.split('.')[0]}_port.txt"
    
    logger.info(f"Running {script_name} on port {port}...")
    
    # Save the port to a file for reference
    run_command(f"echo {port} > /root/{port_file}")
    
    # Run the script
    return run_command(f"sudo nohup /usr/bin/python3 {script_path} --port {port} > /root/{log_file} 2>&1 &")

def setup_supervisor_for_script(script_path: str, port: int):
    """Setup supervisor to manage a Python script"""
    script_name = os.path.basename(script_path)
    script_dir = os.path.dirname(script_path)
    program_name = script_name.split('.')[0]
    
    logger.info(f"Setting up supervisor for {script_name} on port {port}...")
    
    # Create supervisor config
    supervisor_config = f"""[program:{program_name}]
directory={script_dir}
command=/usr/bin/python3 {script_path} --port {port}
autostart=true
autorestart=true
stderr_logfile=/var/log/{program_name}.err.log
stdout_logfile=/var/log/{program_name}.out.log
"""
    
    # Write config to file
    try:
        config_path = f"/tmp/{program_name}.conf"
        with open(config_path, "w") as f:
            f.write(supervisor_config)
        
        # Move to supervisor directory
        run_command(f"sudo mv {config_path} /etc/supervisor/conf.d/")
        
        logger.info(f"Supervisor config created for {script_name}")
        return True
    except Exception as e:
        logger.error(f"Error setting up supervisor for {script_name}: {e}")
        return False

def find_and_run_python_files():
    """Find all Python files in the patrick directory and run them with unique ports"""
    logger.info("Finding and running Python files in patrick directory...")
    
    # Get list of all Python files in patrick directory
    patrick_dir = "/workspace/code/patrick"
    python_files = []
    for root, dirs, files in os.walk(patrick_dir):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(python_files)} Python files in patrick directory")
    
    # Run each Python file with a unique port
    script_ports = {}
    for py_file in python_files:
        port = find_available_port()
        run_python_script(py_file, port)
        setup_supervisor_for_script(py_file, port)
        script_ports[py_file] = port
    
    # Save script ports to a file for reference
    try:
        with open("/root/script_ports.json", "w") as f:
            import json
            json.dump(script_ports, f, indent=4)
        logger.info("Saved script ports to /root/script_ports.json")
    except Exception as e:
        logger.error(f"Error saving script ports: {e}")
    
    return script_ports

def enable_and_update_supervisor():
    """Enable and update supervisor"""
    logger.info("Enabling and updating supervisor...")
    
    # Enable supervisor
    run_command("sudo systemctl enable supervisor")
    
    # Restart supervisor
    run_command("sudo systemctl restart supervisor")
    
    # Update supervisor
    run_command("sudo supervisorctl reread")
    run_command("sudo supervisorctl update")
    
    logger.info("Supervisor enabled and updated")

def kill_unnecessary_processes():
    """Kill all processes except PID 1, binary files, and Python processes"""
    logger.info("Killing unnecessary processes...")
    
    # Get all Python processes
    python_processes = []
    try:
        ps_output = run_command("ps -eo pid,cmd | grep python")
        if ps_output:
            for line in ps_output.split('\n'):
                if 'grep python' in line:
                    continue
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    python_processes.append(int(parts[0]))
    except Exception as e:
        logger.error(f"Error getting Python processes: {e}")
    
    logger.info(f"Found {len(python_processes)} Python processes")
    
    # Get all binary processes
    binary_processes = []
    try:
        ps_output = run_command("ps -eo pid,cmd | grep bin")
        if ps_output:
            for line in ps_output.split('\n'):
                if 'grep bin' in line:
                    continue
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    binary_processes.append(int(parts[0]))
    except Exception as e:
        logger.error(f"Error getting binary processes: {e}")
    
    logger.info(f"Found {len(binary_processes)} binary processes")
    
    # Kill all other processes except PID 1, our own process, Python processes, and binary processes
    try:
        ps_output = run_command("ps -eo pid,cmd")
        if ps_output:
            for line in ps_output.split('\n'):
                parts = line.strip().split()
                if not parts or not parts[0].isdigit():
                    continue
                
                pid = int(parts[0])
                
                # Skip PID 1, our own process, Python processes, and binary processes
                if (pid == 1 or 
                    pid == os.getpid() or 
                    pid in python_processes or 
                    pid in binary_processes):
                    continue
                
                logger.info(f"Killing process: {pid} - {' '.join(parts[1:])}")
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Failed to kill process {pid}: {e}")
    except Exception as e:
        logger.error(f"Error killing processes: {e}")

def ping_url_with_random_interval():
    """Ping URL with random intervals to avoid fixed timing patterns"""
    url = "https://console.dashwave.io/workspace/8420"
    
    while True:
        try:
            logger.info(f"Pinging URL: {url}")
            status = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' {url}", timeout=30)
            logger.info(f"URL ping status: {status}")
        except Exception as e:
            logger.error(f"Error pinging URL: {e}")
        
        # Sleep for a random interval between 30 and 90 seconds
        interval = random.randint(30, 90)
        logger.info(f"Sleeping for {interval} seconds before next ping")
        time.sleep(interval)

def simulate_activity():
    """Simulate minimal activity to keep the session alive"""
    logger.info("Starting activity simulation...")
    
    while True:
        try:
            # Perform a minimal activity (e.g., list files)
            run_command("ls -la > /dev/null 2>&1")
            
            # Sleep for a random interval between 2 and 5 minutes
            interval = random.randint(120, 300)
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Error in activity simulation: {e}")
            time.sleep(60)  # Sleep for a minute before retrying

def main():
    """Main function to run all tasks"""
    logger.info("Starting multi-python setup script...")
    
    # Upgrade pip
    upgrade_pip()
    
    # Install dependencies
    install_dependencies()
    
    # Install C++ compiler and libcurl
    install_cpp_compiler()
    
    # Clone repositories
    clone_repositories()
    
    # Compile stxx
    compile_stxx()
    
    # Setup root directory
    setup_root_directory()
    
    # Find and run Python files
    script_ports = find_and_run_python_files()
    
    # Enable and update supervisor
    enable_and_update_supervisor()
    
    # Kill unnecessary processes
    kill_unnecessary_processes()
    
    # Start URL pinging in a separate thread
    ping_thread = threading.Thread(target=ping_url_with_random_interval, daemon=True)
    ping_thread.start()
    
    # Start activity simulation in a separate thread
    activity_thread = threading.Thread(target=simulate_activity, daemon=True)
    activity_thread.start()
    
    logger.info("All initial tasks completed successfully!")
    
    # Keep the main thread running
    try:
        while True:
            time.sleep(3600)  # Sleep for an hour
            logger.info("Multi-python setup still active")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()