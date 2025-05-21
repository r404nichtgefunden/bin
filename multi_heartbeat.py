#!/usr/bin/env python3
import os
import time
import random
import subprocess
import logging
import signal
import sys
import json
import socket
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/root/multi_heartbeat.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MultiHeartbeat")

def ping_url():
    """Ping URL with random intervals to avoid fixed timing patterns"""
    url = "https://console.dashwave.io/workspace/8420"
    
    try:
        logger.info(f"Pinging URL: {url}")
        result = subprocess.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' {url}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        status_code = result.stdout.strip()
        logger.info(f"URL ping status: {status_code}")
        return status_code
    except Exception as e:
        logger.error(f"Error pinging URL: {e}")
        return "error"

def simulate_activity():
    """Simulate minimal activity to keep the session alive"""
    try:
        # Perform a minimal activity (e.g., list files)
        subprocess.run("ls -la /root > /dev/null 2>&1", shell=True)
        logger.info("Simulated activity: ls command in root directory")
        
        # Check system load
        load = subprocess.run(
            "uptime",
            shell=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        logger.info(f"System load: {load}")
    except Exception as e:
        loggerdef simulate_activity():
    """Simulate minimal activity to keep the session alive"""
    try:
        # Perform a minimal activity (e.g., list files)
        subprocess.run("ls -la /root > /dev/null 2>&1", shell=True)
        logger.info("Simulated activity: ls command in root directory")
        
        # Check system load
        load = subprocess.run(
            "uptime",
            shell=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        logger.info(f"System load: {load}")
    except Exception as e:
        logger.error(f"Error in activity simulation: {e}")

def find_available_port(start_port=5000, end_port=65535):
    """Find an available port in the given range"""
    # Try using lsof command first
    try:
        used_ports_str = subprocess.run(
            "lsof -i -P -n | grep LISTEN | awk '{print $9}' | cut -d ':' -f 2 | sort -u",
            shell=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        used_ports = set()
        if used_ports_str:
            for port_str in used_ports_str.split('\n'):
                try:
                    used_ports.add(int(port_str))
                except ValueError:
                    pass
        
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                return port
    except Exception:
        pass
    
    # Fallback to socket method
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    
    # If no port is available, return a default
    return 8081

def check_and_restart_python_scripts():
    """Check if Python scripts are running and restart them if needed"""
    try:
        # Load script ports from file
        script_ports = {}
        if os.path.exists("/root/script_ports.json"):
            with open("/root/script_ports.json", "r") as f:
                script_ports = json.load(f)
        
        # Check each script
        for script_path, port in script_ports.items():
            script_name = os.path.basename(script_path)
            
            # Check if the script is running
            check_cmd = f"ps aux | grep '{script_path} --port {port}' | grep -v grep"
            process_check = subprocess.run(
                check_cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if process_check.stdout.strip():
                logger.info(f"{script_name} is running on port {port}")
            else:
                logger.warning(f"{script_name} is not running! Attempting to restart...")
                
                # Try to restart using supervisor first
                program_name = script_name.split('.')[0]
                subprocess.run(
                    f"sudo supervisorctl restart {program_name}",
                    shell=True
                )
                
                # If supervisor fails or isn't available, try direct restart
                subprocess.run(
                    f"sudo nohup /usr/bin/python3 {script_path} --port {port} > /root/{program_name}.log 2>&1 &",
                    shell=True
                )
                
                logger.info(f"Restarted {script_name} on port {port}")
        
        # Check for Python files in /root/bin that might not be in the script_ports file
        for py_file in glob.glob("/root/bin/*.py"):
            script_name = os.path.basename(py_file)
            if py_file not in script_ports:
                logger.info(f"Found new Python file: {script_name}")
                
                # Find an available port
                port = find_available_port()
                
                # Run the script
                program_name = script_name.split('.')[0]
                subprocess.run(
                    f"sudo nohup /usr/bin/python3 {py_file} --port {port} > /root/{program_name}.log 2>&1 &",
                    shell=True
                )
                
                # Save the port to a file
                with open(f"/root/{program_name}_port.txt", "w") as f:
                    f.write(str(port))
                
                # Add to script_ports
                script_ports[py_file] = port
                
                # Setup supervisor
                setup_supervisor_for_script(py_file, port)
                
                logger.info(f"Started {script_name} on port {port}")
        
        # Save updated script_ports
        with open("/root/script_ports.json", "w") as f:
            json.dump(script_ports, f, indent=4)
    
    except Exception as e:
        logger.error(f"Error checking and restarting Python scripts: {e}")

def setup_supervisor_for_script(script_path, port):
    """Setup supervisor for a Python script"""
    try:
        script_name = os.path.basename(script_path)
        script_dir = os.path.dirname(script_path)
        program_name = script_name.split('.')[0]
        
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
        config_path = f"/tmp/{program_name}.conf"
        with open(config_path, "w") as f:
            f.write(supervisor_config)
        
        # Move to supervisor directory
        subprocess.run(
            f"sudo mv {config_path} /etc/supervisor/conf.d/",
            shell=True
        )
        
        # Update supervisor
        subprocess.run(
            "sudo supervisorctl reread && sudo supervisorctl update",
            shell=True
        )
        
        logger.info(f"Setup supervisor for {script_name} on port {port}")
        return True
    except Exception as e:
        logger.error(f"Error setting up supervisor for {script_path}: {e}")
        return False

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)

def main():
    """Main function"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Multi-heartbeat service started")
    
    try:
        while True:
            # Ping URL
            ping_url()
            
            # Simulate activity
            simulate_activity()
            
            # Check and restart Python scripts
            check_and_restart_python_scripts()
            
            # Sleep for a random interval between 30 and 90 seconds
            interval = random.randint(30, 90)
            logger.info(f"Sleeping for {interval} seconds before next heartbeat")
            time.sleep(interval)
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()