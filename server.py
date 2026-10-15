"""Simple local/LAN chat server. Messages: one JSON object per line."""
import json
import socket
import sys
import threading
from datetime import datetime

HOST, PORT = "0.0.0.0", int(sys.argv[1]) if len(sys.argv) > 1 else 5050
users, history = {}, []
lock = threading.RLock()


def pack(kind, **data):
    return (json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n").encode("utf-8")


def broadcast(kind, **data):
    message = pack(kind, **data)
    with lock:
        if kind == "chat":
            history.append(json.loads(message))
            del history[:-60]
        for client in list(users):
            try:
                client.sendall(message)
            except OSError:
                pass


def refresh():
    with lock:
        names = list(users.values())
    broadcast("users", names=names)


def handle(client, address):
    name = None
    try:
        with client, client.makefile("r", encoding="utf-8") as stream:
            hello = json.loads(stream.readline())
            if hello.get("type") != "join":
                return
            base = str(hello.get("name") or "Guest").strip()[:24] or "Guest"
            with lock:
                name = base
                n = 2
                while name in users.values():
                    name, n = f"{base} ({n})", n + 1
                users[client] = name
                client.sendall(pack("welcome", name=name, history=history[-60:]))
            broadcast("system", text=f"{name} joined the room")
            refresh()
            for line in stream:
                if len(line) > 12000:
                    break
                try:
                    data = json.loads(line)
                    text = str(data.get("text", "")).strip()[:1200]
                except (ValueError, AttributeError):
                    continue
                if data.get("type") == "chat" and text:
                    broadcast("chat", name=name, text=text,
                              time=datetime.now().strftime("%H:%M"))
    except (OSError, ValueError, UnicodeError):
        pass
    finally:
        with lock:
            if name:
                users.pop(client, None)
        if name:
            broadcast("system", text=f"{name} left the room")
            refresh()


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"LocalSocketChat listening on {HOST}:{PORT}", flush=True)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
