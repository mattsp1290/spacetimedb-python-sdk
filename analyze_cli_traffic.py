#!/usr/bin/env python3
"""
Network traffic analyzer for SpacetimeDB CLI
This script helps capture and analyze the network traffic from the working CLI tool.
"""
import subprocess
import time
import threading
import sys
import os
import signal
import json
import re
from typing import List, Dict, Optional

class CLITrafficAnalyzer:
    def __init__(self):
        self.capture_file = "spacetime_traffic.txt"
        self.tcpdump_process = None
        self.is_macos = sys.platform == "darwin"
        
    def start_tcpdump(self, port: int = 3000) -> subprocess.Popen:
        """Start tcpdump to capture network traffic."""
        interface = "lo0" if self.is_macos else "lo"
        
        # Build tcpdump command
        cmd = [
            "sudo", "tcpdump",
            "-i", interface,
            "-A",  # Print packet contents in ASCII
            "-s", "0",  # Capture full packets
            f"port {port}",
            "-w", "spacetime.pcap"  # Also save to pcap file
        ]
        
        print(f"Starting tcpdump on interface {interface} for port {port}...")
        print(f"Command: {' '.join(cmd)}")
        
        # Start tcpdump
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Give it time to start
        time.sleep(1)
        
        return process
    
    def stop_tcpdump(self, process: subprocess.Popen):
        """Stop tcpdump gracefully."""
        if process:
            print("\nStopping tcpdump...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    def analyze_pcap_file(self):
        """Analyze the captured pcap file for WebSocket connections."""
        print("\nAnalyzing captured traffic...")
        
        # Use tcpdump to read and analyze the pcap file
        cmd = ["sudo", "tcpdump", "-r", "spacetime.pcap", "-A"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout
            
            # Look for WebSocket upgrade requests
            ws_pattern = re.compile(r'GET\s+(/[^\s]*)\s+HTTP.*?Upgrade:\s*websocket', re.IGNORECASE | re.DOTALL)
            matches = ws_pattern.findall(output)
            
            if matches:
                print("\n✓ Found WebSocket endpoints:")
                for endpoint in set(matches):
                    print(f"  - {endpoint}")
            else:
                print("\n✗ No WebSocket upgrade requests found")
            
            # Look for interesting headers
            auth_pattern = re.compile(r'Authorization:\s*([^\r\n]+)', re.IGNORECASE)
            auth_matches = auth_pattern.findall(output)
            
            if auth_matches:
                print("\n✓ Found Authorization headers:")
                for auth in set(auth_matches):
                    print(f"  - {auth[:50]}...")
            
            # Save full analysis
            with open("traffic_analysis.txt", "w") as f:
                f.write(output)
            print(f"\nFull analysis saved to traffic_analysis.txt")
            
        except subprocess.CalledProcessError as e:
            print(f"Error analyzing pcap: {e}")
    
    def run_cli_command(self, module_name: str = "test_module"):
        """Run the SpacetimeDB CLI subscribe command."""
        print(f"\nRunning SpacetimeDB CLI command: spacetime subscribe {module_name}")
        
        cmd = ["spacetime", "subscribe", module_name]
        
        try:
            # Run the command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Let it run for a few seconds to establish connection
            print("Letting CLI run for 5 seconds to capture traffic...")
            time.sleep(5)
            
            # Terminate the CLI
            process.terminate()
            
            # Get any output
            stdout, stderr = process.communicate(timeout=2)
            
            if stdout:
                print(f"\nCLI stdout:\n{stdout}")
            if stderr:
                print(f"\nCLI stderr:\n{stderr}")
                
        except Exception as e:
            print(f"Error running CLI command: {e}")
    
    def use_netstat_alternative(self, module_name: str = "test_module"):
        """Use netstat/lsof to find connections made by the CLI."""
        print("\nUsing netstat/lsof to find SpacetimeDB connections...")
        
        # Start the CLI in background
        cmd = ["spacetime", "subscribe", module_name]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it time to connect
        time.sleep(2)
        
        try:
            if self.is_macos:
                # Use lsof on macOS
                netstat_cmd = ["sudo", "lsof", "-i", ":3000", "-n", "-P"]
            else:
                # Use netstat on Linux
                netstat_cmd = ["sudo", "netstat", "-anp", "|", "grep", ":3000"]
            
            result = subprocess.run(netstat_cmd, capture_output=True, text=True, shell=True)
            
            print("\nActive connections to port 3000:")
            print(result.stdout)
            
            # Also check what files/sockets the spacetime process has open
            if process.pid:
                lsof_cmd = ["sudo", "lsof", "-p", str(process.pid)]
                lsof_result = subprocess.run(lsof_cmd, capture_output=True, text=True)
                
                print(f"\nFiles/sockets opened by spacetime CLI (PID {process.pid}):")
                print(lsof_result.stdout)
                
        finally:
            # Clean up
            process.terminate()
            process.wait()
    
    def intercept_with_proxy(self):
        """Instructions for using an HTTP proxy to intercept traffic."""
        print("\n" + "="*80)
        print("Alternative: Use HTTP Proxy Interception")
        print("="*80)
        
        print("\n1. Install mitmproxy:")
        print("   pip install mitmproxy")
        
        print("\n2. Start mitmproxy:")
        print("   mitmproxy --listen-port 8080")
        
        print("\n3. Configure spacetime CLI to use proxy:")
        print("   export HTTP_PROXY=http://localhost:8080")
        print("   export HTTPS_PROXY=http://localhost:8080")
        print("   export WS_PROXY=http://localhost:8080")
        
        print("\n4. Run spacetime CLI:")
        print("   spacetime subscribe test_module")
        
        print("\n5. Check mitmproxy interface for captured requests")
        print("="*80)

def main():
    analyzer = CLITrafficAnalyzer()
    
    print("SpacetimeDB CLI Traffic Analyzer")
    print("="*60)
    
    # Check if running as root (needed for tcpdump)
    if os.geteuid() != 0 and not sys.platform == "darwin":
        print("\n⚠️  This script needs sudo privileges for network capture.")
        print("Please run: sudo python3 analyze_cli_traffic.py")
        print("\nAlternatively, trying non-root methods...")
        
        # Try alternative methods
        analyzer.use_netstat_alternative()
        analyzer.intercept_with_proxy()
        return
    
    try:
        # Method 1: tcpdump capture
        print("\nMethod 1: Using tcpdump to capture traffic")
        print("-"*40)
        
        # Start packet capture
        tcpdump = analyzer.start_tcpdump()
        
        # Run the CLI command
        analyzer.run_cli_command()
        
        # Stop capture
        analyzer.stop_tcpdump(tcpdump)
        
        # Analyze the capture
        analyzer.analyze_pcap_file()
        
        # Method 2: Alternative analysis
        print("\nMethod 2: Using system tools")
        print("-"*40)
        analyzer.use_netstat_alternative()
        
        # Show proxy instructions
        analyzer.intercept_with_proxy()
        
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        if analyzer.tcpdump_process:
            analyzer.stop_tcpdump(analyzer.tcpdump_process)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
