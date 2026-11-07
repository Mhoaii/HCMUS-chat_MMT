"""Simple two-way TCP chat between one server and one client."""

import argparse
import socket
import threading


def receive_messages(connection: socket.socket) -> None:
    buffer = b""
    while True:
        try:
            data = connection.recv(4096)
        except OSError:
            break
        if not data:
            break

        buffer += data
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            print(f"\nPeer: {line.decode('utf-8', errors='replace')}\nYou: ", end="", flush=True)

    if buffer:
        print(f"\nPeer: {buffer.decode('utf-8', errors='replace')}")
    print("\nPeer disconnected.")


def chat(connection: socket.socket) -> None:
    print("Connected. Type /quit to leave.")
    receiver = threading.Thread(target=receive_messages, args=(connection,), daemon=True)
    receiver.start()

    try:
        while True:
            message = input("You: ")
            if message.strip() == "/quit":
                break
            if message:
                connection.sendall((message + "\n").encode("utf-8"))
    except (BrokenPipeError, ConnectionResetError):
        print("\nConnection closed.")
    except KeyboardInterrupt:
        print("\nLeaving chat.")
    finally:
        connection.close()


def run_server(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"Waiting for a connection on {host}:{port}...")
        connection, address = server.accept()
        print(f"Connected to {address[0]}:{address[1]}")
        chat(connection)


def run_client(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.connect((host, port))
        print(f"Connected to {host}:{port}")
        chat(connection)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with another computer over TCP.")
    subparsers = parser.add_subparsers(dest="role", required=True)

    server_parser = subparsers.add_parser("server", help="wait for a client")
    server_parser.add_argument("--host", default="0.0.0.0", help="address to listen on")
    server_parser.add_argument("--port", type=int, default=5000)

    client_parser = subparsers.add_parser("client", help="connect to a server")
    client_parser.add_argument("--host", required=True, help="server IP address or hostname")
    client_parser.add_argument("--port", type=int, default=5000)

    args = parser.parse_args()
    if args.role == "server":
        run_server(args.host, args.port)
    else:
        run_client(args.host, args.port)


if __name__ == "__main__":
    main()
