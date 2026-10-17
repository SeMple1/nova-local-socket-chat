"""Minimal CustomTkinter chat client for a local TCP room."""
import json
import queue
import socket
import subprocess
import sys
import threading
from pathlib import Path

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C = {"bg": "#10141C", "side": "#171C26", "panel": "#1C2431", "bubble": "#222C3C",
     "own": "#234DAD", "line": "#2A3444", "text": "#F0F4FC", "muted": "#8F9CAD",
     "accent": "#6D9FFF", "green": "#51D4A0"}
BTN = dict(fg_color=C["own"], hover_color="#3164C9")


def local_ip():
    """IPv4 used by the default route; connect() on UDP sends no data."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("1.1.1.1", 80))
            return probe.getsockname()[0]
    except OSError:
        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                if not item[4][0].startswith(("127.", "169.254.")):
                    return item[4][0]
        except OSError:
            pass
    return "Unavailable"


def encode(**data):
    return (json.dumps(data, ensure_ascii=False) + "\n").encode()


class Chat(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NOVA  |  Local Socket Chat")
        self.geometry("1100x720")
        self.minsize(820, 540)
        self.configure(fg_color=C["bg"])
        self.conn = self.server_process = None
        self.name, self.ip, self.events = "", local_ip(), queue.Queue()
        self.build()
        self.after(80, self.pump)
        self.after(15000, self.poll_ip)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def label(self, parent, text, size=13, color="text", weight="normal", **kw):
        return ctk.CTkLabel(parent, text=text, text_color=C.get(color, color),
                            font=("Segoe UI", size, weight), **kw)

    def entry(self, parent, text="", **kw):
        e = ctk.CTkEntry(parent, height=39, fg_color=C["panel"], border_color=C["line"],
                         corner_radius=10, **kw)
        e.insert(0, text)
        return e

    def build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, width=268, corner_radius=0, fg_color=C["side"])
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(26, 30))
        ctk.CTkLabel(brand, text="✦", width=42, height=42, corner_radius=13,
                     fg_color=C["own"], text_color="white",
                     font=("Segoe UI Symbol", 24)).pack(side="left")
        block = ctk.CTkFrame(brand, fg_color="transparent")
        block.pack(side="left", padx=12)
        self.label(block, "NOVA", 20, weight="bold").pack(anchor="w")
        self.label(block, "LOCAL MESSENGER", 10, "muted").pack(anchor="w")

        self.label(side, "YOUR IDENTITY", 11, "muted", "bold").pack(anchor="w", padx=24)
        self.nick = self.entry(side, "Guest", placeholder_text="Display name")
        self.nick.pack(fill="x", padx=22, pady=(9, 20))

        self.label(side, "CONNECTION", 11, "muted", "bold").pack(anchor="w", padx=24)
        net = ctk.CTkFrame(side, fg_color="transparent")
        net.pack(fill="x", padx=22, pady=(9, 11))
        net.grid_columnconfigure(0, weight=1)
        self.host = self.entry(net, "127.0.0.1")
        self.host.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self.port = self.entry(net, "5050", width=67)
        self.port.grid(row=0, column=1)

        self.connect_button = ctk.CTkButton(side, text="Connect to room", height=40,
                                            corner_radius=11, command=self.connect, **BTN)
        self.connect_button.pack(fill="x", padx=22, pady=(0, 8))
        ctk.CTkButton(side, text="＋  Host a local room", height=38, fg_color=C["panel"],
                      hover_color=C["line"], corner_radius=11,
                      command=self.start_host).pack(fill="x", padx=22)

        self.status = self.label(side, "●  Disconnected", 12, "muted")
        self.status.pack(anchor="w", padx=24, pady=(18, 25))
        ctk.CTkFrame(side, fg_color=C["line"], height=1).pack(fill="x", padx=22)
        self.label(side, "CHANNEL", 11, "muted", "bold").pack(anchor="w", padx=24, pady=(24, 8))
        self.label(side, "#  general", 14, "accent", "bold", anchor="w",
                   fg_color=C["panel"], corner_radius=10, height=41).pack(fill="x", padx=21)

        self.people_title = self.label(side, "ONLINE · 0", 11, "muted", "bold")
        self.people_title.pack(anchor="w", padx=24, pady=(28, 8))
        self.people = ctk.CTkScrollableFrame(side, fg_color="transparent", corner_radius=0)
        self.people.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        self.label(side, "TCP SOCKET   •   PRIVATE LAN", 10, "muted").pack(
            anchor="w", padx=24, pady=(0, 20))

        main = ctk.CTkFrame(self, corner_radius=0, fg_color=C["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, height=89, corner_radius=0, fg_color=C["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=18)
        header.grid_propagate(False)
        share = ctk.CTkFrame(header, fg_color=C["panel"], corner_radius=12,
                             border_width=1, border_color=C["line"])
        share.pack(side="right", pady=11)
        self.label(share, "YOUR LAN IP  ·  SHARE THIS", 10, "muted", "bold").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=(13, 8), pady=(7, 0))
        self.ip_label = self.label(share, self.ip, 17, weight="bold")
        self.ip_label.grid(row=1, column=0, sticky="w", padx=(13, 8), pady=(0, 7))
        ctk.CTkButton(share, text="Copy", width=52, height=28, corner_radius=8,
                      command=self.copy_ip, **BTN).grid(row=1, column=1, padx=(1, 5), pady=(0, 7))
        ctk.CTkButton(share, text="↻", width=29, height=28, corner_radius=8,
                      fg_color=C["line"], hover_color="#36445C",
                      command=self.refresh_ip).grid(row=1, column=2, padx=(0, 8), pady=(0, 7))

        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.pack(side="left", fill="both", expand=True)
        self.label(heading, "#  general", 23, weight="bold").pack(anchor="w", pady=(16, 0))
        self.label(heading, "Realtime chat · private network", 12, "muted").pack(anchor="w")

        self.messages = ctk.CTkScrollableFrame(main, fg_color=C["bg"], corner_radius=0)
        self.messages.grid(row=1, column=0, sticky="nsew", padx=13, pady=10)
        self.notice("Welcome to NOVA. Host a room or connect to an existing server.")

        composer = ctk.CTkFrame(main, fg_color=C["panel"], corner_radius=18, height=74)
        composer.grid(row=2, column=0, sticky="ew", padx=25, pady=(0, 22))
        composer.grid_columnconfigure(0, weight=1)
        self.message = ctk.CTkEntry(composer, placeholder_text="Write a message...", height=46,
                                    fg_color="transparent", border_width=0,
                                    text_color=C["text"], font=("Segoe UI", 14))
        self.message.grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=13)
        self.message.bind("<Return>", lambda e: self.send())
        ctk.CTkButton(composer, text="Send  →", width=96, height=43, corner_radius=12,
                      command=self.send, **BTN).grid(row=0, column=1, padx=(0, 13), pady=13)

    def notice(self, text):
        self.label(self.messages, f"—  {text}  —", 12, "muted",
                   wraplength=580).pack(pady=15, padx=12)

    def bubble(self, event):
        mine = event["name"] == self.name
        row = ctk.CTkFrame(self.messages, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        body = ctk.CTkFrame(row, fg_color=C["own"] if mine else C["bubble"], corner_radius=17)
        body.pack(side="right" if mine else "left", padx=(58, 0) if mine else (0, 58))
        self.label(body, f"{'YOU' if mine else event['name']}   ·   {event.get('time', '')}",
                   11, "#BFD3FF" if mine else "accent", "bold").pack(anchor="w", padx=16, pady=(11, 2))
        self.label(body, event["text"], 14, wraplength=500, justify="left").pack(
            anchor="w", padx=16, pady=(0, 12))
        self.after(30, lambda: self.messages._parent_canvas.yview_moveto(1))

    def update_people(self, names):
        self.people_title.configure(text=f"ONLINE · {len(names)}")
        for child in self.people.winfo_children():
            child.destroy()
        for name in names:
            line = ctk.CTkFrame(self.people, fg_color="transparent")
            line.pack(fill="x", padx=3, pady=3)
            self.label(line, "●", 14, "green").pack(side="left", padx=(2, 10))
            self.label(line, name + ("  (you)" if name == self.name else "")).pack(side="left")

    def refresh_ip(self):
        self.ip = local_ip()
        self.ip_label.configure(text=self.ip)

    def poll_ip(self):
        self.refresh_ip()
        self.after(15000, self.poll_ip)

    def copy_ip(self):
        if self.ip == "Unavailable":
            return self.notice("No LAN IP detected. Check your network connection.")
        address = f"{self.ip}:{self.port.get().strip()}"
        self.clipboard_clear()
        self.clipboard_append(address)
        self.notice(f"Copied {address}")

    def start_host(self):
        if self.conn:
            return self.notice("Disconnect first to start a new room.")
        try:
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError("port must be 1-65535")
            if not self.server_process or self.server_process.poll() is not None:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                self.server_process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).with_name("server.py")), str(port)],
                    cwd=Path(__file__).parent, creationflags=flags)
            self.host.delete(0, "end")
            self.host.insert(0, "127.0.0.1")
            self.after(500, self.connect)
        except (OSError, ValueError) as error:
            self.notice(f"Could not start server: {error}")

    def connect(self):
        if self.conn:
            return self.disconnect()
        try:
            sock = socket.create_connection((self.host.get().strip(), int(self.port.get())),
                                            timeout=1.5)
            sock.settimeout(None)
            sock.sendall(encode(type="join", name=self.nick.get().strip()))
        except (OSError, ValueError) as error:
            self.notice(f"Connection failed: {error}")
            return self.status.configure(text="●  Connection failed", text_color="#F59B9B")
        self.conn = sock
        self.connect_button.configure(text="Disconnect", fg_color="#36445C")
        self.status.configure(text="●  Connected", text_color=C["green"])
        self.nick.configure(state="disabled")
        self.notice("Connected. Messages are shared in real time.")
        threading.Thread(target=self.listen, args=(sock,), daemon=True).start()
        self.message.focus_set()

    def listen(self, sock):
        try:
            with sock.makefile("r", encoding="utf-8") as stream:
                for line in stream:
                    self.events.put((sock, json.loads(line)))
        except (OSError, ValueError, UnicodeError):
            pass
        self.events.put((sock, {"type": "lost"}))

    def send(self):
        text = self.message.get().strip()
        if not text or not self.conn:
            return
        try:
            self.conn.sendall(encode(type="chat", text=text[:1200]))
            self.message.delete(0, "end")
        except OSError:
            self.disconnect()

    def pump(self):
        while not self.events.empty():
            sock, event = self.events.get()
            if sock is not self.conn:
                continue
            kind = event.get("type")
            if kind == "welcome":
                self.name = event["name"]
                for item in event.get("history", []):
                    self.bubble(item)
            elif kind == "chat":
                self.bubble(event)
            elif kind == "system":
                self.notice(event.get("text", ""))
            elif kind == "users":
                self.update_people(event.get("names", []))
            elif kind == "lost":
                self.disconnect()
                self.notice("Server connection closed.")
        self.after(80, self.pump)

    def disconnect(self):
        sock, self.conn = self.conn, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        self.connect_button.configure(text="Connect to room", fg_color=C["own"])
        self.status.configure(text="●  Disconnected", text_color=C["muted"])
        self.nick.configure(state="normal")
        self.update_people([])
        self.name = ""

    def close(self):
        self.disconnect()
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
        self.destroy()


if __name__ == "__main__":
    Chat().mainloop()
