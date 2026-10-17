"""Simple local/LAN chat server. Messages: one JSON object per line."""
import json
import socket
import sys
import threading
from datetime import datetime

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
users, history, lock = {}, [], threading.RLock()
MAX_LINE = 12000


def pack(kind, **data):
    return (json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n").encode()


def broadcast(kind, **data):
    msg = pack(kind, **data)
    with lock:
        if kind == "chat":
            history.append(json.loads(msg))
            del history[:-60]
        for client in list(users):
            try:
                client.sendall(msg)
            except OSError:
                pass


def refresh():
    with lock:
        names = list(users.values())
    broadcast("users", names=names)


def handle(client):
    name = None
    try:
        with client, client.makefile("r", encoding="utf-8") as stream:
            hello = json.loads(stream.readline(MAX_LINE + 1))
            if hello.get("type") != "join":
                return
            base = str(hello.get("name") or "Guest").strip()[:24] or "Guest"
            with lock:
                name, n = base, 2
                while name in users.values():
                    name, n = f"{base} ({n})", n + 1
                users[client] = name
                client.sendall(pack("welcome", name=name, history=history))
            broadcast("system", text=f"{name} joined the room")
            refresh()
            for line in iter(lambda: stream.readline(MAX_LINE + 1), ""):
                if len(line) > MAX_LINE:
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
        if name:
            with lock:
                users.pop(client, None)
            broadcast("system", text=f"{name} left the room")
            refresh()


if __name__ == "__main__":
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", PORT))
        server.listen()
        print(f"LocalSocketChat listening on 0.0.0.0:{PORT}", flush=True)
        while True:
            threading.Thread(target=handle, args=(server.accept()[0],), daemon=True).start()
