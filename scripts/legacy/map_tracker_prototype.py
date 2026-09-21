import json
import math
import re
import threading
import time
from pathlib import Path
from urllib.parse import unquote
import http.server
import socketserver

try:
  import serial
except ImportError:
  serial = None

try:
  from PyQt5.QtCore import QTimer, QUrl
  from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
  from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError as error:
  raise SystemExit(
    "Faltan dependencias de PyQt5. Instala: pip install PyQt5 PyQtWebEngine"
  ) from error

BASE_DIR = Path(__file__).resolve().parent
TILES_DIR = BASE_DIR / "tiles"
HOST = "127.0.0.1"
PORT = 8765
CENTER_LAT = 32.5
CENTER_LON = -115.5
SERIAL_PORT = "COM12"
SERIAL_BAUDRATE = 115200
POLL_MS = 200

BLANK_PNG = (
  b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
  b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\x00\x01"
  b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class SharedState:
  def __init__(self):
    self.lock = threading.Lock()
    self.latest_position = None
    self.latest_raw = ""
    self.status = "Iniciando..."

  def set_status(self, status):
    with self.lock:
      self.status = status

  def get_status(self):
    with self.lock:
      return self.status

  def set_position(self, latitude, longitude, raw_line):
    with self.lock:
      self.latest_position = (latitude, longitude)
      self.latest_raw = raw_line

  def get_position_payload(self):
    with self.lock:
      if self.latest_position is None:
        return {
          "ok": False,
          "message": self.status,
        }

      latitude, longitude = self.latest_position
      return {
        "ok": True,
        "lat": latitude,
        "lon": longitude,
        "raw": self.latest_raw,
        "message": self.status,
      }


def parse_lat_lng(raw_line):
  line = raw_line.strip()
  if not line:
    return None

  parts = [part.strip() for part in re.split(r"[;,]", line) if part.strip()]

  # Trama serial esperada: ALT;LAT;LON;...
  if len(parts) >= 3:
    try:
      latitude = float(parts[1])
      longitude = float(parts[2])
      if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    except ValueError:
      pass

  named_match = re.search(r"LAT\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
  named_match_lon = re.search(r"LNG\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
  if named_match and named_match_lon:
    latitude = float(named_match.group(1))
    longitude = float(named_match_lon.group(1))
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
      return latitude, longitude

  return None


def serial_worker(state, stop_event):
  if serial is None:
    state.set_status("Instala pyserial: pip install pyserial")
    return

  while not stop_event.is_set():
    try:
      with serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=1) as serial_port:
        state.set_status(f"Escuchando {SERIAL_PORT} @ {SERIAL_BAUDRATE}")
        while not stop_event.is_set():
          raw_bytes = serial_port.readline()
          if not raw_bytes:
            continue

          raw_line = raw_bytes.decode("utf-8", errors="ignore").strip()
          parsed = parse_lat_lng(raw_line)
          if parsed is None:
            continue

          latitude, longitude = parsed
          state.set_position(latitude, longitude, raw_line)
    except Exception as error:
      state.set_status(f"Sin serial: {error}")
      time.sleep(1)


def build_tile_index():
  tile_index = {}

  if not TILES_DIR.exists():
    return tile_index

  for zoom_dir in TILES_DIR.iterdir():
    if not zoom_dir.is_dir() or not zoom_dir.name.isdigit():
      continue

    zoom = int(zoom_dir.name)
    x_map = {}

    for x_dir in zoom_dir.iterdir():
      if not x_dir.is_dir() or not x_dir.name.isdigit():
        continue

      x_value = int(x_dir.name)
      y_values = []
      for y_file in x_dir.glob("*.png"):
        if y_file.stem.isdigit():
          y_values.append(int(y_file.stem))

      if y_values:
        y_values.sort()
        x_map[x_value] = y_values

    if x_map:
      tile_index[zoom] = x_map

  return tile_index


def tile_to_latlon(zoom, x_tile, y_tile):
  n = 2.0 ** zoom
  lon_deg = x_tile / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y_tile / n)))
  lat_deg = math.degrees(lat_rad)
  return lat_deg, lon_deg


def compute_bounds(tile_index):
  if not tile_index:
    return None

  best_zoom = max(tile_index.keys())
  x_values = sorted(tile_index[best_zoom].keys())
  y_values = []
  for x_value in x_values:
    y_values.extend(tile_index[best_zoom][x_value])

  if not x_values or not y_values:
    return None

  x_min = min(x_values)
  x_max = max(x_values)
  y_min = min(y_values)
  y_max = max(y_values)

  north, west = tile_to_latlon(best_zoom, x_min, y_min)
  south, east = tile_to_latlon(best_zoom, x_max + 1, y_max + 1)

  return {
    "min_zoom": min(tile_index.keys()),
    "max_zoom": max(tile_index.keys()),
    "best_zoom": best_zoom,
    "x_min": x_min,
    "x_max": x_max,
    "y_min": y_min,
    "y_max": y_max,
    "north": north,
    "south": south,
    "west": west,
    "east": east,
  }


def choose_closest(values, target):
  return min(values, key=lambda value: abs(value - target))


def make_html(bounds):
  config_json = json.dumps(bounds)
  return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" />
  <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>
  <style>
    html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
    #map {{ background: #f7f5ee; }}
    .small-star {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #ff7b22;
      border: 2px solid #5f2800;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.2);
    }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <script>
    const cfg = {config_json};

    const map = L.map('map', {{
      zoomControl: true,
      minZoom: cfg.min_zoom,
      maxZoom: cfg.max_zoom,
      maxBounds: [[cfg.south, cfg.west], [cfg.north, cfg.east]],
      maxBoundsViscosity: 1.0,
      worldCopyJump: false,
      preferCanvas: true,
    }});

    const tileLayer = L.tileLayer('http://{HOST}:{PORT}/{{z}}/{{x}}/{{y}}.png', {{
      minZoom: cfg.min_zoom,
      maxZoom: cfg.max_zoom,
      noWrap: true,
      attribution: 'Tiles locales'
    }}).addTo(map);

    map.fitBounds([[cfg.south, cfg.west], [cfg.north, cfg.east]]);

    const rocketIcon = L.divIcon({{
      className: 'small-star',
      iconSize: [12, 12],
      iconAnchor: [6, 6]
    }});

    let marker = null;
    let firstFix = true;

    async function refreshPosition() {{
      try {{
        const response = await fetch('http://{HOST}:{PORT}/position', {{ cache: 'no-store' }});
        const data = await response.json();

        if (!data.ok) {{
          return;
        }}

        const latlng = [data.lat, data.lon];

        if (!marker) {{
          marker = L.marker(latlng, {{ icon: rocketIcon }}).addTo(map);
        }} else {{
          marker.setLatLng(latlng);
        }}

        const shortRaw = (data.raw || '').slice(0, 90);
        marker.bindTooltip(`★ Cohete<br>${{data.lat.toFixed(6)}}, ${{data.lon.toFixed(6)}}<br>${{shortRaw}}`, {{
          direction: 'top',
          offset: [0, -8],
          opacity: 0.95
        }});

        if (firstFix) {{
          map.setView(latlng, Math.max(cfg.min_zoom, Math.min(cfg.max_zoom, 13)));
          firstFix = false;
        }}
      }} catch (error) {{
      }}
    }}

    setInterval(refreshPosition, {POLL_MS});
    refreshPosition();
  </script>
</body>
</html>
"""


class LocalRequestHandler(http.server.BaseHTTPRequestHandler):
  server_version = "SeafoxLocal/1.0"

  def _write_json(self, payload):
    body = json.dumps(payload).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)

  def _write_html(self, html_text):
    body = html_text.encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _write_png(self, png_bytes):
    self.send_response(200)
    self.send_header("Content-Type", "image/png")
    self.send_header("Content-Length", str(len(png_bytes)))
    self.send_header("Cache-Control", "public, max-age=3600")
    self.end_headers()
    self.wfile.write(png_bytes)

  def do_GET(self):
    if self.path == "/" or self.path.startswith("/?"):
      self._write_html(self.server.html_text)
      return

    if self.path.startswith("/position"):
      self._write_json(self.server.state.get_position_payload())
      return

    match = re.match(r"^/(\d+)/(\d+)/(\d+)\.png$", unquote(self.path))
    if not match:
      self.send_error(404, "File not found")
      return

    zoom = int(match.group(1))
    x_value = int(match.group(2))
    y_value = int(match.group(3))

    tile_path = self._resolve_tile_path(zoom, x_value, y_value)
    if tile_path is None:
      self._write_png(BLANK_PNG)
      return

    try:
      tile_bytes = tile_path.read_bytes()
    except OSError:
      self._write_png(BLANK_PNG)
      return

    self._write_png(tile_bytes)

  def _resolve_tile_path(self, zoom, x_value, y_value):
    direct = TILES_DIR / str(zoom) / str(x_value) / f"{y_value}.png"
    if direct.exists():
      return direct

    tile_index = self.server.tile_index
    if zoom not in tile_index:
      return None

    x_candidates = sorted(tile_index[zoom].keys())
    if not x_candidates:
      return None

    closest_x = choose_closest(x_candidates, x_value)
    y_candidates = tile_index[zoom].get(closest_x, [])
    if not y_candidates:
      return None

    closest_y = choose_closest(y_candidates, y_value)
    fallback = TILES_DIR / str(zoom) / str(closest_x) / f"{closest_y}.png"
    return fallback if fallback.exists() else None

  def log_message(self, format_text, *args):
    return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
  daemon_threads = True
  allow_reuse_address = True


class SeafoxWindow(QMainWindow):
  def __init__(self, server):
    super().__init__()
    self.server = server
    self.setWindowTitle("Seafox Control")
    self.resize(1000, 760)

    container = QWidget(self)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    self.status_label = QLabel("Iniciando...")
    self.status_label.setContentsMargins(8, 6, 8, 6)
    layout.addWidget(self.status_label)

    self.web_view = QWebEngineView(self)
    self.web_view.setUrl(QUrl(f"http://{HOST}:{PORT}/"))
    layout.addWidget(self.web_view)

    self.setCentralWidget(container)

    self.status_timer = QTimer(self)
    self.status_timer.timeout.connect(self.refresh_status)
    self.status_timer.start(300)

  def refresh_status(self):
    self.status_label.setText(self.server.state.get_status())

  def closeEvent(self, event):
    self.status_timer.stop()
    super().closeEvent(event)


def main():
  if not TILES_DIR.exists():
    raise FileNotFoundError(f"No existe la carpeta de tiles: {TILES_DIR}")

  tile_index = build_tile_index()
  bounds = compute_bounds(tile_index)
  if not bounds:
    raise RuntimeError("No hay tiles validos en la carpeta local")

  state = SharedState()
  state.set_status("Mapa local listo")

  html_text = make_html(bounds)

  httpd = ThreadedHTTPServer((HOST, PORT), LocalRequestHandler)
  httpd.state = state
  httpd.tile_index = tile_index
  httpd.html_text = html_text

  server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
  server_thread.start()

  stop_event = threading.Event()
  serial_thread = threading.Thread(target=serial_worker, args=(state, stop_event), daemon=True)
  serial_thread.start()

  app = QApplication([])
  window = SeafoxWindow(httpd)
  window.show()
  exit_code = app.exec_()

  stop_event.set()
  httpd.shutdown()
  httpd.server_close()

  raise SystemExit(exit_code)


if __name__ == "__main__":
  main()
