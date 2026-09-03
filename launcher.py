import os
import sys
import threading
import time
import webbrowser
import streamlit.web.cli as stcli

def open_browser(port):
    """Espera a que el servidor inicie y abre el navegador."""
    time.sleep(2)
    webbrowser.open(f"http://localhost:{port}")

if __name__ == "__main__":
    # Si ejecutamos como binario congelado por PyInstaller
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "app.py")
    
    port = 8501

    # Sobrescribimos sys.argv para engañar a Streamlit y ejecutar nuestra app internamente
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--global.developmentMode=false"
    ]

    # Iniciar un hilo para abrir el navegador
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Ceder el control a Streamlit
    sys.exit(stcli.main())
