import socket
import os
import threading

def handle_client(connection, address):
    print(f"New connection from {address}")
    try:
        while True:
            data_received = connection.recv(1024)
            if not data_received:
                print(f"[{address}] Client disconnected.")
                break
            connection.sendall(data_received)
    except ConnectionResetError:
        print(f"[{address}] Connection reset by peer.")
    except Exception as e:
        print(f"An error occurred with {address}: {e}")
    finally:
        connection.close()
        print(f"Connection closed for {address}")

def server() -> None:
    TARGET_SERVER_PORT = os.environ.get('TARGET_SERVER_PORT')
    TARGET_SERVER_HOST = os.environ.get('TARGET_SERVER_HOST')

    if not TARGET_SERVER_PORT:
        raise Exception("TARGET_SERVER_PORT is not set")
    if not TARGET_SERVER_HOST:
        raise Exception("TARGET_SERVER_HOST is not set")


    port = int(TARGET_SERVER_PORT)
    host = f"{TARGET_SERVER_HOST}"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            print(f"Listening on {host}:{port}")
            print("Ready for connections...")

            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                client_thread.start()

if __name__ == "__main__":
    server()