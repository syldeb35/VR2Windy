import http.client
import json
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path


PROXY = Path(__file__).resolve().parents[1] / "nmea_windy_proxy.py"
RMC = b"$GPRMC,120000,A,4800.000,N,00200.000,W,5.0,90.0,010126,,,A"
SENTENCES = [
    b"$IIMWV,125,T,7.80234,N,A*29",
    b"$IIVWR,42.11247,R,9.53089,N,,,,,1*6B",
    b"$IIHDT,205.66065,T*26",
    b"$IIRPM,E,7,100,0,A*51",
]


class InstrumentIntegrationTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.http_port = sock.getsockname()[1]
        for port in range(20000, 60000):
            sockets = [socket.socket(), socket.socket()]
            try:
                sockets[0].bind(("127.0.0.1", port))
                sockets[1].bind(("127.0.0.1", port + 1))
                self.outport = port
                break
            except OSError:
                continue
            finally:
                for sock in sockets:
                    sock.close()
        else:
            self.fail("No two available forwarding ports")
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(PROXY), "--port", str(self.http_port),
             "--outport", str(self.outport)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop_proxy)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.http_port), timeout=0.1):
                    return
            except OSError:
                if self.process.poll() is not None:
                    self.fail(f"Proxy exited with code {self.process.returncode}")
                time.sleep(0.02)
        self.fail("Proxy failed to start")

    def stop_proxy(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=5)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http_port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, race, sentence):
        status, _, _ = self.request("POST", f"/nmea/{race}", sentence)
        self.assertEqual(status, 204)

    def position(self, race):
        status, _, body = self.request("GET", f"/position/{race}")
        return status, json.loads(body)

    def test_instruments_are_retransmitted_and_attached_per_race(self):
        self.post("0", SENTENCES[0])
        self.assertEqual(self.position("0")[0], 404)
        with socket.create_connection(("127.0.0.1", self.outport), timeout=2) as receiver:
            receiver.settimeout(2)
            for sentence in SENTENCES:
                self.post("0", sentence)
                self.assertEqual(receiver.recv(1024), sentence + b"\r\n")
        self.post("0", RMC)
        self.post("1", RMC)
        status, position = self.position("0")
        self.assertEqual(status, 200)
        self.assertEqual(position["heading"], 90)
        self.assertEqual(position["speed"], 5)
        self.assertEqual(position["instruments"], {
            "true_wind": {"angle": 125, "speed": 7.80234},
            "apparent_wind": {"angle": 42.11247, "side": "R", "speed": 9.53089},
            "boat_heading": 205.66065,
            "sail": 7,
            "energy": 100,
        })
        self.assertEqual(self.position("1")[1]["instruments"], {})
        self.post("1", b"$IIVWR,10,L,12,N")
        self.assertEqual(self.position("1")[1]["instruments"]["apparent_wind"]["side"], "L")
        self.assertEqual(self.position("0")[1]["instruments"]["apparent_wind"]["side"], "R")
        self.post("0", RMC)
        self.assertEqual(self.position("0")[1]["instruments"]["energy"], 100)

    def test_invalid_values_do_not_replace_last_valid_measurements(self):
        self.post("0", RMC)
        for sentence in SENTENCES:
            self.post("0", sentence)
        original = self.position("0")[1]["instruments"]
        for sentence in (
            b"$IIMWV,125,R,7,N,A",
            b"$IIMWV,125,T,nan,N,A",
            b"$IIMWV,125,T,7,M,A",
            b"$IIMWV,125,T,7,N,V",
            b"$IIMWV,125,T,7,N,A*00",
            b"$IIVWR,10,X,12,N",
            b"$IIHDT,361,T",
            b"$IIRPM,E,7,inf,0,A",
            b"$IIRPM,E,7,50,0,V",
        ):
            self.post("0", sentence)
        self.assertEqual(self.position("0")[1]["instruments"], original)
        self.post("0", b"$IIRPM,E,5,0,0,A")
        self.assertEqual(self.position("0")[1]["instruments"]["energy"], 0)
        self.assertEqual(self.position("0")[1]["instruments"]["sail"], 5)

    def test_position_cors_is_unchanged(self):
        self.post("0", RMC)
        status, headers, _ = self.request(
            "OPTIONS", "/position/0", headers={
                "Origin": "https://www.windy.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://www.windy.com")
        self.assertEqual(headers["Access-Control-Allow-Private-Network"], "true")
        status, headers, _ = self.request(
            "GET", "/position/0", headers={"Origin": "https://www.windy.com"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://www.windy.com")


if __name__ == "__main__":
    unittest.main()
