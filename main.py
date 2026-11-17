import threading
import socket
import time
import uvicorn
import webview
import api as api_module

from api import app

# Puerto 0 = "el que este libre". Lo abrimos, miramos cual nos ha tocado y lo soltamos.
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def serve(port):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

# Espera a que uvicorn acepte conexiones; si no, la ventana carga antes y sale "connection refused".
def wait_for(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)

if __name__ == "__main__":
    port = free_port()
    threading.Thread(target=serve, args=(port,), daemon=True).start()
    wait_for(port)
    # marco nativo (snap, maximizar y redimensionar de Windows) con el titulo vacio: el nombre ya va dentro
    window = webview.create_window("", f"http://127.0.0.1:{port}", width=1200, height=700, resizable=True, maximized=True)
    api_module.window = window
    webview.start()
