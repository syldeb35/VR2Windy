import http.client
import json
import queue
import socket
import time
import tkinter as tk
import unittest
from unittest.mock import Mock

from proxy_control import ProxyControlWindow, ProxyProcess


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for proxy")


class ProxyProcessTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.proxy = ProxyProcess(("--port", str(self.port), "--outport", "0"))

    def tearDown(self):
        process = self.proxy.process
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    def wait_until_ready(self):
        def ready():
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                    return True
            except OSError:
                if self.proxy.process.poll() is not None:
                    self.fail(f"Proxy exited with code {self.proxy.process.returncode}")
                return False

        wait_for(ready)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_start_stop_and_restart_real_proxy(self):
        self.proxy.start()
        self.wait_until_ready()
        first_process = self.proxy.process
        self.assertEqual(self.request("GET", "/position/0")[0], 404)
        sentence = b"$GPRMC,120000,A,4800.000,N,00200.000,W,5.0,90.0,010126,,,A"
        self.assertEqual(self.request("POST", "/nmea/0", sentence)[0], 204)
        status, body = self.request("GET", "/position/0")
        self.assertEqual(status, 200)
        self.assertEqual((json.loads(body)["lat"], json.loads(body)["lon"]), (48.0, -2.0))
        with self.assertRaises(RuntimeError):
            self.proxy.start()

        self.proxy.stop()
        first_process.wait(timeout=5)
        self.proxy.start()
        self.wait_until_ready()
        self.assertIsNot(self.proxy.process, first_process)
        self.assertEqual(self.request("GET", "/position/0")[0], 404)
        self.proxy.stop()
        self.proxy.process.wait(timeout=5)

    def test_port_conflict_is_reported_in_log(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", self.port))
            occupied.listen()
            self.proxy.start()
            self.proxy.process.wait(timeout=5)
            self.assertNotEqual(self.proxy.process.returncode, 0)
            lines = []

            def reported():
                try:
                    while True:
                        _, line = self.proxy.messages.get_nowait()
                        lines.append(line)
                except queue.Empty:
                    return any("OSError:" in line for line in lines)

            wait_for(reported)


class ProxyControlWindowTests(unittest.TestCase):
    def setUp(self):
        self.window = ProxyControlWindow.__new__(ProxyControlWindow)
        self.window.root = Mock()
        self.window.proxy = Mock()
        self.window.proxy.messages = queue.Queue()
        self.window.status = Mock()
        self.window.write_log = Mock()
        self.window.update_buttons = Mock()
        self.window.state = "running"
        self.window.stop_action = None
        self.window.stop_deadline = None
        self.window.force_stopped = False
        self.window.proxy.process.poll.return_value = None

    def test_restart_waits_for_exit_before_starting(self):
        self.window.restart()
        self.window.proxy.stop.assert_called_once()
        self.window.poll()
        self.window.proxy.start.assert_not_called()
        self.window.proxy.process.poll.return_value = 0
        self.window.poll()
        self.window.proxy.start.assert_called_once()
        self.assertEqual(self.window.state, "starting")

    def test_unexpected_exit_is_reported(self):
        self.window.proxy.process.poll.return_value = 1
        self.window.poll()
        self.window.status.set.assert_called_with("Proxy arrêté inattendument (code 1)")
        self.assertEqual(self.window.state, "stopped")

    def test_ready_log_changes_starting_to_running(self):
        self.window.state = "starting"
        self.window.proxy.process.pid = 123
        self.window.proxy.messages.put((self.window.proxy.process, "INFO:root:httpd listening on port 8085"))
        self.window.poll()
        self.window.status.set.assert_called_with("En cours (PID 123)")
        self.assertEqual(self.window.state, "running")


class ProxyControlGuiTests(unittest.TestCase):
    def test_footer_stays_at_bottom_when_resized(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Graphical display unavailable: {error}")
        try:
            ProxyControlWindow(root)
            footer = next(
                child for child in root.winfo_children()
                if isinstance(child, tk.ttk.Label) and child.cget("text") == "© Malouce Software 2026"
            )
            for geometry in ("480x300", "700x500"):
                root.geometry(geometry)
                root.update()
                self.assertTrue(footer.winfo_ismapped())
                self.assertEqual(footer.winfo_y() + footer.winfo_height(), root.winfo_height())
                self.assertEqual(footer.winfo_width(), root.winfo_width())
        finally:
            root.destroy()

    def test_graphical_start_restart_stop(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Graphical display unavailable: {error}")
        root.withdraw()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        window = ProxyControlWindow(root)
        window.proxy = ProxyProcess(("--port", str(port)))

        def state_is(expected):
            root.update()
            return window.state == expected

        try:
            window.start()
            wait_for(lambda: state_is("running"))
            first = window.proxy.process
            window.restart()
            wait_for(lambda: state_is("running") and window.proxy.process is not first)
            self.assertIsNotNone(first.poll())
            window.stop()
            wait_for(lambda: state_is("stopped"))
            self.assertIsNotNone(window.proxy.process.poll())
        finally:
            process = window.proxy.process
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            root.destroy()


if __name__ == "__main__":
    unittest.main()
