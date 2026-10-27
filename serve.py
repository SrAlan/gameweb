"""Servidor local para ver la página como se verá subida.

Uso (en esta carpeta):   python serve.py        -> http://localhost:8000
                          python serve.py 9000   -> otro puerto

También se puede abrir index.html con doble clic; con el servidor, además, la página
comprueba que el .rar está en game/ y muestra su tamaño.
"""
import http.server
import os
import socketserver
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

os.chdir(os.path.dirname(os.path.abspath(__file__)))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Sirviendo en http://localhost:{PORT}  (Ctrl+C para parar)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
