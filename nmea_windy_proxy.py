import http.server
import json
import math
import re
import socketserver
import socket
import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()

parser.add_argument(
    '--bind',
    help='Set the server interface to bind (default 127.0.0.1)')

parser.add_argument(
    '--outport',
    help='Set outbound port base (default 10000)')

parser.add_argument(
    '--port',
    help='Set the HTTP port to bind (default 8085)')

args = parser.parse_args()
HOST = (args.bind if args.bind else '127.0.0.1')
OUTPORT = (int(args.outport) if args.outport else 10000)
PORT = (int(args.port) if args.port else 8085)


connections = dict()
sockets = dict()
last_positions = {}
last_instruments = {}
fleets = {}
WINDY_ORIGINS = {"https://www.windy.com", "https://windy.com"}


def parse_nmea_coordinate(value, hemisphere, degree_digits):
    if len(value) <= degree_digits:
        raise ValueError("Invalid NMEA coordinate")

    degrees = int(value[:degree_digits])
    minutes = float(value[degree_digits:])
    if not 0 <= minutes < 60:
        raise ValueError("Invalid NMEA minutes")

    coordinate = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        coordinate = -coordinate
    elif hemisphere not in ("N", "E"):
        raise ValueError("Invalid NMEA hemisphere")

    return coordinate


def parse_nmea_timestamp(time_field, date_field):
    # RMC: hhmmss[.ss] and ddmmyy, both UTC
    moment = datetime.strptime(
        time_field.split(".")[0] + date_field, "%H%M%S%d%m%y")
    return int(moment.replace(tzinfo=timezone.utc).timestamp() * 1000)


def parse_nmea_position(message):
    try:
        sentence = message.decode("ascii").strip()
        fields = sentence.split("*", 1)[0].split(",")
        if len(fields) < 10 or fields[0] != "$GPRMC" or fields[2] != "A":
            if fields[0].startswith("$IIRPM"):
                #logging.info("Received: %s", sentence)
                return None
            return None

        latitude = parse_nmea_coordinate(fields[3], fields[4], 2)
        longitude = parse_nmea_coordinate(fields[5], fields[6], 3)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return None

        speed = float(fields[7]) if fields[7] else None
        heading = float(fields[8]) if fields[8] else None
        if speed is not None and (not math.isfinite(speed) or speed < 0):
            return None
        if heading is not None and not math.isfinite(heading):
            return None

        return {
            "lat": latitude,
            "lon": longitude,
            "speed": speed,
            "heading": heading,
            "timestamp": parse_nmea_timestamp(fields[1], fields[9]),
        }
    except (UnicodeDecodeError, ValueError):
        return None


def parse_instrument_sentence(message):
    if not message.strip().startswith((b"$IIMWV", b"$IIVWR", b"$IIHDT", b"$IIRPM")):
        return None
    try:
        sentence = message.decode("ascii").strip()
        fields = sentence.split("*", 1)[0].split(",")
        kind = fields[0]
        if kind not in ("$IIMWV", "$IIVWR", "$IIHDT", "$IIRPM"):
            return None

        if "*" in sentence:
            body, checksum = sentence[1:].split("*", 1)
            actual = 0
            for char in body:
                actual ^= ord(char)
            if not re.fullmatch(r"[0-9A-Fa-f]{2}", checksum) or actual != int(checksum, 16):
                raise ValueError("invalid checksum")

        def number(value, minimum, maximum=None):
            result = float(value)
            if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum):
                raise ValueError("value out of range")
            return result

        if kind == "$IIMWV":
            if len(fields) < 6 or fields[2] != "T" or fields[4] != "N" or fields[5] != "A":
                raise ValueError("expected valid true wind in knots")
            return {"true_wind": {
                "angle": number(fields[1], 0, 360),
                "speed": number(fields[3], 0),
            }}
        if kind == "$IIVWR":
            if len(fields) < 5 or fields[2] not in ("L", "R") or fields[4] != "N":
                raise ValueError("expected apparent wind in knots with side L or R")
            return {"apparent_wind": {
                "angle": number(fields[1], 0, 180),
                "side": fields[2],
                "speed": number(fields[3], 0),
            }}
        if kind == "$IIHDT":
            if len(fields) < 3 or fields[2] != "T":
                raise ValueError("expected true heading")
            return {"boat_heading": number(fields[1], 0, 360)}
        if kind == "$IIRPM":
            if len(fields) < 6 or fields[1] != "E" or fields[5] != "A" or not fields[2].isdigit():
                raise ValueError("expected valid ITYC energy and sail")
            return {"sail": int(fields[2]), "energy": number(fields[3], 0), "foil": number(fields[4], 0)}
    except (UnicodeDecodeError, ValueError) as error:
        logging.warning("Invalid instrument sentence: %s", error)
        return None


def decode_ais_payload(payload):
    bits = ""
    for char in payload:
        value = ord(char) - 48
        if value > 40:
            value -= 8
        if not 0 <= value < 64:
            raise ValueError("Invalid AIS payload")
        bits += format(value, "06b")
    return bits


def ais_uint(bits, start, length):
    return int(bits[start:start + length], 2)


def ais_int(bits, start, length):
    value = ais_uint(bits, start, length)
    return value - (1 << length) if value >= 1 << (length - 1) else value


def parse_ais_sentence(message):
    # Single-fragment AIVDM types 1 (position) and 5 (static data) sent by ITYC
    try:
        sentence = message.decode("ascii").strip()
        fields = sentence.split("*", 1)[0].split(",")
        if len(fields) < 7 or fields[0] != "!AIVDM":
            return None
        bits = decode_ais_payload(fields[5])
        msg_type = ais_uint(bits, 0, 6)
        mmsi = ais_uint(bits, 8, 30)

        if msg_type == 1 and len(bits) >= 137:
            longitude = ais_int(bits, 61, 28) / 600000
            latitude = ais_int(bits, 89, 27) / 600000
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                return None
            return mmsi, {
                "lat": latitude,
                "lon": longitude,
                "speed": ais_uint(bits, 50, 10) / 10,
                "heading": ais_uint(bits, 116, 12) / 10,
            }
        if msg_type == 5 and len(bits) >= 232:
            name = "".join(
                chr(v + 64) if v < 32 else chr(v)
                for v in (ais_uint(bits, 112 + i * 6, 6) for i in range(20)))
            return mmsi, {"name": name.replace("@", " ").strip()}
    except (UnicodeDecodeError, ValueError):
        return None
    return None


def store_ais(race_id, message):
    parsed = parse_ais_sentence(message)
    if parsed is None:
        return
    mmsi, data = parsed
    boat = fleets.setdefault(race_id, {}).setdefault(str(mmsi), {})
    boat.update(data)
    if "lat" in data:
        boat["timestamp"] = int(time.time() * 1000)


class NMEAHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        match = re.fullmatch(r"/nmea/(\d{1,5})", urlsplit(self.path).path)
        if not match:
            self.send_error(404)
            return

        try:
            content_len = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.send_error(400)
            return
        post_body = self.rfile.read(content_len)
        race_number = int(match.group(1))
        race_id = str(race_number)
        if not 0 <= OUTPORT + race_number <= 65535:
            self.send_error(400)
            return
        position = parse_nmea_position(post_body)
        if position:
            last_positions[race_id] = position
        else:
            store_ais(race_id, post_body)
            instruments = parse_instrument_sentence(post_body)
            if instruments is not None:
                last_instruments.setdefault(race_id, {}).update(instruments)
        forward_message(int(race_id), post_body)
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        fleet_match = re.fullmatch(r"/fleet/(\d{1,5})", path)
        if fleet_match:
            race_id = str(int(fleet_match.group(1)))
            boats = [b for b in fleets.get(race_id, {}).values() if "lat" in b]
            self.send_json_response(200, boats)
            return
        match = re.fullmatch(r"/position/(\d{1,5})", path)
        if not match:
            self.send_error(404)
            return

        race_id = str(int(match.group(1)))
        position = last_positions.get(race_id)
        if position is None:
            self.send_json_response(404, {"error": "No position received for this race"})
            return
        self.send_json_response(200, {
            **position,
            "instruments": last_instruments.get(race_id, {}),
        })

    def do_OPTIONS(self):
        match = re.fullmatch(r"/(?:position|fleet)/(\d{1,5})", urlsplit(self.path).path)
        origin = self.headers.get('Origin')
        if not match or origin not in WINDY_ORIGINS:
            self.send_error(403)
            return

        self.send_response(204)
        self.send_windy_cors_headers(origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if self.headers.get('Access-Control-Request-Private-Network') == 'true':
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '600')
        self.end_headers()

    def send_json_response(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        origin = self.headers.get('Origin')
        if origin in WINDY_ORIGINS:
            self.send_windy_cors_headers(origin)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_windy_cors_headers(self, origin):
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Vary', 'Origin')

    def log_message(self, format, *args):
        pass


def forward_message(conn_id, message):
    conn = find_or_create_connection(conn_id)
    if conn:
        try:
            conn.send(message + '\r\n'.encode('ascii'))
        except Exception:
            logging.info('Connection lost on port ' + str(conn_id)
                         + ', closing.')
            conn.close()
            connections.pop(conn_id, None)


def find_or_create_connection(conn_id):
    if conn_id in connections:
        return connections[conn_id]
    else:
        conn = None
        if conn_id not in sockets:
            sockets[conn_id] = create_socket(conn_id)
        conn = accept_connection(sockets[conn_id])
        if conn:
            connections[conn_id] = conn
        return conn


def create_socket(conn_id):
    logging.info('Creating socket for race ID ' + str(conn_id))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    sock.bind((HOST, OUTPORT + conn_id))
    sock.listen(0)
    return sock


def accept_connection(sock):
    try:
        (conn, address) = sock.accept()
        logging.info('Accepted connection on port '
                     + str(sock.getsockname()[1]))
        return conn
    except IOError:
        return None


class NMEAServer(socketserver.TCPServer):
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self):
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


logging.basicConfig(level=logging.INFO)

logging.info("Creating Server")
server = NMEAServer((HOST, PORT), NMEAHandler)
logging.info("httpd listening on port " + str(PORT))

try:
    server.serve_forever()
except KeyboardInterrupt:
    pass

finally:
    logging.info('Cleaning up')
    server.server_close()
    logging.info('Stopping httpd\n')
