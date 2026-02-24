#! python run_cors_server.py 8000 D:\MyFolder
from http.server import SimpleHTTPRequestHandler, HTTPServer

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

if __name__ == '__main__':
    import sys
    import os

    # Example: python cors_server.py 8000 D:\\MyFolder
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    directory = sys.argv[2] if len(sys.argv) > 2 else '.'
    os.chdir(directory)
    httpd = HTTPServer(('', port), CORSRequestHandler)
    print(f"Serving {directory} at http://localhost:{port}")
    httpd.serve_forever()