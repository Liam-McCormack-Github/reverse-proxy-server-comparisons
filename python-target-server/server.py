import time

def server() -> None:
    while True:
        print("Hello World")
        time.sleep(1)

if __name__ == "__main__":
    server()