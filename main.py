import threading
import socket
import uvicorn
import webview
import api as api_module

from api import app

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def serve():
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

if __name__ == "__main__":
    port = free_port()
    threading.Thread(target=serve, daemon=True).start()
    window = webview.create_window("Mulsa", f"http://127.0.0.1:{port}", width=1200, height=700, resizable=True, maximized=True)
    api_module.window = window
    webview.start()