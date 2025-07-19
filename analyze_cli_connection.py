#!/usr/bin/env python3
"""
Analyze how the SpacetimeDB CLI connects in v1.1.2
"""
import subprocess
import time
import threading
import socket
import sys

def monitor_port(port=3000, duration=10):
    """Monitor connections to a port"""
    print(f"Monitoring port {port} for {duration} seconds...")
    
    start_time = time.time()
    connections = []
    
    while time.time() - start_time < duration:
        try:
            # Try to see what's connecting
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if line and line not in connections:
                        connections.append(line)
                        print(f"Connection detected: {line}")
        except Exception as e:
            print(f"Error monitoring: {e}")
        
        time.sleep(0.5)
    
    return connections

def test_cli_connection():
    """Test SpacetimeDB CLI connection and monitor it"""
    print("Starting connection monitoring...")
    
    # Start monitoring in background
    monitor_thread = threading.Thread(
        target=monitor_port,
        args=(3000, 15)
    )
    monitor_thread.start()
    
    # Give monitor time to start
    time.sleep(1)
    
    # Run CLI command
    print("\nRunning spacetime subscribe...")
    try:
        # Run in Docker
        proc = subprocess.Popen(
            [
                "docker", "exec", "spacetimedb-blackholio",
                "spacetime", "subscribe", 
                "c200790a25c83d93389b2bd36bc7c7b76a3036c80797b4be7dc40f47f7a851e7",
                "SELECT * FROM *"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit to see output
        time.sleep(5)
        
        # Check if still running
        if proc.poll() is None:
            print("CLI is connected and running!")
            stdout, stderr = proc.communicate(timeout=5)
            if stdout:
                print(f"STDOUT: {stdout}")
            if stderr:
                print(f"STDERR: {stderr}")
        else:
            stdout, stderr = proc.communicate()
            print(f"CLI exited with code: {proc.returncode}")
            if stdout:
                print(f"STDOUT: {stdout}")
            if stderr:
                print(f"STDERR: {stderr}")
            
    except subprocess.TimeoutExpired:
        print("CLI is still running (good sign!)")
        proc.kill()
    except Exception as e:
        print(f"Error running CLI: {e}")
    
    # Wait for monitor to finish
    monitor_thread.join()
    
    print("\nConnection analysis complete!")

if __name__ == "__main__":
    test_cli_connection()
