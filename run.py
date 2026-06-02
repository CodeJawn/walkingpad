import subprocess
import sys
import time
import webbrowser

HOST = "0.0.0.0"
PORT = 5000

def open_browser():
    """Opens the web browser to the application."""
    print(f"Opening browser to http://127.0.0.1:{PORT}")
    webbrowser.open_new(f"http://127.0.0.1:{PORT}")

if __name__ == "__main__":
    print("Starting production server with Waitress...")
    
    # Start the Waitress server as a subprocess
    server_process = subprocess.Popen(
        [sys.executable, "-m", "waitress", f"--host={HOST}", f"--port={PORT}", "app:app"]
    )
    
    # Give the server a moment to start up
    time.sleep(2)
    
    # Open the web browser
    open_browser()
    
    try:
        # Wait for the server process to complete.
        # You can press Ctrl+C in this window to stop the server.
        server_process.wait()
    except KeyboardInterrupt:
        print("Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")