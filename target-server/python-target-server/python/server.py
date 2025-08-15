import http.server
import ssl
import os
import functools
import json
import time
import threading
from database import Database
from simple_logger import log

MASTER_TOKEN = ""
TOKEN_LOCK = threading.Lock()

def reread_token_periodically():
    global MASTER_TOKEN
    while True:
        time.sleep(30)
        try:
            with open('master_token.txt', 'r') as f:
                new_token = f.read().strip()
            
            if new_token:
                with TOKEN_LOCK:
                    if new_token != MASTER_TOKEN:
                        MASTER_TOKEN = new_token
                        log("INFO", "Master token has been updated from file.")
            else:
                log("WARN", "Skipping token update because master_token.txt is empty.")
        except FileNotFoundError:
            log("ERROR", "master_token.txt not found during periodic reread.")
        except Exception as e:
            log("ERROR", "Failed to reread master token in background", extras=f"Error: {e}")


class AuthRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
            if format == '"%s" %s %s':
                try:
                    request_line = str(args[0])
                    code = int(args[1])
                    client_ip = self.address_string()
                    extras = f'Code: {code}, Client IP: {client_ip}, Request: "{request_line}"'
                    if code >= 400:
                        error_messages = {
                            400: "Bad Request received from client",
                            401: "Unauthorized - Authentication failed or is required",
                            403: "Forbidden - Client does not have permission",
                            404: "Not Found - The requested resource does not exist",
                            500: "Internal Server Error - An unhandled exception occurred"
                        }
                        message = error_messages.get(code, "Request failed with other client/server error")
                        log("ERROR", message, extras=extras)
                    else:
                        success_messages = {
                            200: "Request successful",
                        }
                        message = success_messages.get(code, "Request handled successfully")
                        log("INFO", message, extras=extras)
                except (IndexError, ValueError) as e:
                    log("ERROR", "Custom logging failed", extras=f'Format: {format}, Args: {args}, Error: {e}')
                    super().log_message(format, *args)
                return

            if format == 'code %d, message %s':
                try:
                    code = int(args[0])
                    message = str(args[1])
                    log("WARN", "Server sent error response", extras=f"Code: {code}, Message: '{message}'")
                except (IndexError, ValueError) as e:
                    log("ERROR", "Custom logging failed", extras=f'Format: {format}, Args: {args}, Error: {e}')
                return
                
            super().log_message(format, *args)

    def handle_auth(self):
        """Authenticates the request against the in-memory master token in a thread-safe way."""
        received_token = self.headers.get('X-Proxy-Token')
        with TOKEN_LOCK:
            is_valid = received_token == MASTER_TOKEN
        
        if not is_valid:
            msg = "Forbidden: Invalid or missing proxy token."
            log("WARN", msg, extras=f"IP: {self.client_address[0]}")
            self.send_error(403, msg)
            return False
        return True

    def do_GET_stream(self):
        """Handles the /stream endpoint for high-throughput testing."""
        log("INFO", "GET /stream request received", extras=f"Client IP: {self.client_address[0]}")
        if not self.handle_auth():
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'application/octet-stream')
        self.end_headers()

        try:
            chunk = os.urandom(1024)
            while True:
                self.wfile.write(chunk)
                time.sleep(0.01)
        except (BrokenPipeError, ConnectionResetError):
            log("INFO", "Client disconnected from stream.", extras=f"Client IP: {self.client_address[0]}")
        except Exception as e:
            log("ERROR", "Error during streaming", extras=f"Client IP: {self.client_address[0]}, Error: {e}")

    def do_GET(self):
        if self.path == '/stream':
            self.do_GET_stream()
            return
        
        log("INFO", "GET Request received", extras=f"Client IP: {self.client_address[0]}, Path: {self.path}")
        if not self.handle_auth():
            return

        if not os.path.exists(self.translate_path(self.path)):
            if os.path.exists(self.translate_path(self.path) + '.html'):
                self.path += '.html'
        super().do_GET()


    def do_POST(self):
        log("INFO", "POST Request received", extras=f"Client IP: {self.client_address[0]}, Path: {self.path}")
        if self.path == "/api/v1/auth":
            client_id = "N/A"
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                credentials = json.loads(post_data)
                client_id = credentials.get('client_id')
                client_secret = credentials.get('client_secret')
                db = Database()
                is_valid = db.verify_user(client_id, client_secret)
                db.close()
                if is_valid:
                    log("SUCCESS", "Authentication successful", extras=f"client_id: {client_id}")
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    with TOKEN_LOCK:
                        self.wfile.write(json.dumps({'master_token': MASTER_TOKEN}).encode())
                else:
                    log("WARN", "Unauthorized authentication attempt", extras=f"client_id: {client_id}")
                    self.send_error(401, "Unauthorized")
            except Exception as e:
                log("ERROR", "Bad request for client", extras=f"client_id: {client_id}, Error: {e}")
                self.send_error(400, f"Bad Request: {e}")
        else:
            self.send_error(404, "Not Found")

def server():
    TARGET_SERVER_PORT = os.environ.get('TARGET_SERVER_PORT')
    TARGET_SERVER_HOST = os.environ.get('TARGET_SERVER_HOST')
    if not TARGET_SERVER_PORT or not TARGET_SERVER_HOST:
        raise Exception("TARGET_SERVER_PORT and TARGET_SERVER_HOST environment variables must be set")
        
    global MASTER_TOKEN
    try:
        # Read the initial token from the file on startup.
        with TOKEN_LOCK:
            with open('master_token.txt', 'r') as f:
                MASTER_TOKEN = f.read().strip()
        if not MASTER_TOKEN:
            raise ValueError("Master token file is empty on startup.")
        log("INFO", "Initial master token loaded into memory.")
    except (FileNotFoundError, ValueError) as e:
        log("ERROR", f"Could not read initial master token at startup: {e}. The server will not start.")
        return

    # Start the background thread for rereading the token file.
    rereader_thread = threading.Thread(target=reread_token_periodically, daemon=True)
    rereader_thread.start()
    log("INFO", "Started background thread for polling master_token.txt.")

    port = int(TARGET_SERVER_PORT)
    host = f"{TARGET_SERVER_HOST}"
    handler = functools.partial(AuthRequestHandler, directory="website")
    httpd = http.server.HTTPServer((host, port), handler)
    ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    try:
        ssl_context.load_cert_chain(certfile='./cert.pem', keyfile='./key.pem')
    except FileNotFoundError:
        log("ERROR", "SSL certificate or key not found. Ensure 'cert.pem' and 'key.pem' exist.")
        return
    httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)
    log("INFO", f"Starting secure HTTPS server on https://{host}:{port}")
    log("INFO", "Authentication endpoint active at /api/v1/auth")
    log("INFO", "Streaming test endpoint active at /stream")
    httpd.serve_forever()


if __name__ == "__main__":
    server()