import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


PROXY_SCRIPT = Path(__file__).resolve().with_name("nmea_windy_proxy.py")
STOP_TIMEOUT_SECONDS = 5


class ProxyProcess:
    def __init__(self, arguments=()):
        self.arguments = tuple(arguments)
        self.process = None
        self.messages = queue.Queue()

    def start(self):
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("Le proxy est déjà démarré.")
        options = {}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(PROXY_SCRIPT), *self.arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **options,
        )
        process = self.process
        threading.Thread(target=self._read_output, args=(process,), daemon=True).start()

    def _read_output(self, process):
        try:
            for line in process.stdout:
                self.messages.put((process, line.rstrip()))
        finally:
            process.stdout.close()

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def kill(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()


class ProxyControlWindow:
    def __init__(self, root):
        self.root = root
        self.proxy = ProxyProcess()
        self.state = "stopped"
        self.stop_action = None
        self.stop_deadline = None
        self.force_stopped = False
        
        root.title("VR2Windy - Contrôle du proxy")
        root.minsize(480, 300)
        root.protocol("WM_DELETE_WINDOW", self.close)

        footer = ttk.Label(root, text="© Malouce Software 2026", anchor="e", padding=(12, 4))
        footer.pack(side="bottom", fill="x")

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Proxy NMEA local (127.0.0.1:8085)").pack(anchor="w")
        self.status = tk.StringVar(value="Arrêté")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=(6, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Démarrer", command=self.start)
        self.start_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(buttons, text="Arrêter", command=self.stop)
        self.stop_button.pack(side="left", padx=(0, 6))
        self.restart_button = ttk.Button(buttons, text="Redémarrer", command=self.restart)
        self.restart_button.pack(side="left")

        ttk.Label(frame, text="Journal").pack(anchor="w", pady=(12, 4))
        self.log = scrolledtext.ScrolledText(frame, height=10, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        
        self.update_buttons()
        root.after(100, self.poll)

    def write_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def update_buttons(self):
        self.start_button.configure(state="normal" if self.state == "stopped" else "disabled")
        self.stop_button.configure(state="normal" if self.state in ("starting", "running") else "disabled")
        self.restart_button.configure(state="normal" if self.state in ("starting", "running") else "disabled")

    def start(self):
        try:
            self.proxy.start()
        except (OSError, RuntimeError) as error:
            self.status.set("Erreur de démarrage")
            self.write_log(f"Impossible de démarrer le proxy : {error}")
            self.update_buttons()
            return
        self.state = "starting"
        self.status.set("Démarrage…")
        self.write_log("Démarrage du proxy.")
        self.update_buttons()

    def request_stop(self, action):
        self.stop_action = action
        self.stop_deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
        self.force_stopped = False
        self.state = "stopping"
        self.status.set("Arrêt en cours…")
        try:
            self.proxy.stop()
        except OSError as error:
            self.write_log(f"Impossible d'arrêter le proxy : {error}")
        self.update_buttons()

    def stop(self):
        self.request_stop("stop")

    def restart(self):
        self.request_stop("restart")

    def close(self):
        process = self.proxy.process
        if process is not None and process.poll() is None:
            if not messagebox.askyesno(
                "Fermer le contrôle du proxy",
                "Fermer cette fenêtre arrêtera le proxy. Continuer ?",
                parent=self.root,
            ):
                return
            self.request_stop("close")
        else:
            self.root.destroy()

    def poll(self):
        while True:
            try:
                process, line = self.proxy.messages.get_nowait()
            except queue.Empty:
                break
            self.write_log(line)
            if (process is self.proxy.process and self.state == "starting"
                    and "httpd listening on port " in line):
                self.state = "running"
                self.status.set(f"En cours (PID {process.pid})")
                self.update_buttons()

        process = self.proxy.process
        if process is not None:
            exit_code = process.poll()
            if exit_code is not None and self.state != "stopped":
                previous_state = self.state
                self.state = "stopped"
                action = self.stop_action
                self.stop_action = None
                if previous_state == "stopping":
                    self.write_log(f"Proxy arrêté (code {exit_code}).")
                    self.status.set("Arrêté")
                    self.update_buttons()
                    if action == "close":
                        self.root.destroy()
                        return
                    if action == "restart":
                        self.start()
                else:
                    self.status.set(f"Proxy arrêté inopinément (code {exit_code})")
                    self.write_log(f"Le proxy s'est arrêté inopinément (code {exit_code}).")
                    self.update_buttons()
            elif (self.state == "stopping" and self.stop_deadline is not None
                  and not self.force_stopped
                  and time.monotonic() >= self.stop_deadline):
                self.force_stopped = True
                try:
                    self.proxy.kill()
                    self.write_log("Arrêt forcé du proxy après expiration du délai.")
                except OSError as error:
                    self.write_log(f"Impossible de forcer l'arrêt du proxy : {error}")

        self.root.after(100, self.poll)


def main():
    root = tk.Tk(className="VR2Windy Proxy")
    chemin_icone = Path(__file__).resolve().with_name("proxy_icon.png")
    icone = tk.PhotoImage(file=str(chemin_icone))
    root.iconphoto(False, icone)
    ProxyControlWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
