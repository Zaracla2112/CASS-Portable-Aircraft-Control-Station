import json
import math
import re
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote

import http.server
import socketserver

try:
  import serial
  from serial.tools import list_ports
except ImportError:
  serial = None
  list_ports = None

try:
  from PyQt5.QtCore import QEvent, QTimer, Qt, QUrl, pyqtSignal
  from PyQt5.QtGui import QColor, QFont, QPainter, QPen
  from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
  )
  from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
except ImportError as error:
  raise SystemExit(
    "Faltan dependencias. Instala: pip install PyQt5 PyQtWebEngine pyserial"
  ) from error

try:
  from PyQt5.QtOpenGL import QGLWidget
  from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_LINES,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_QUADS,
    GL_LINE_LOOP,
    GL_TRIANGLES,
    glBegin,
    glClear,
    glClearColor,
    glColor3f,
    glEnable,
    glEnd,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glVertex3f,
    glViewport,
  )
  from OpenGL.GLU import gluCylinder, gluDeleteQuadric, gluLookAt, gluNewQuadric, gluPerspective
  OPENGL_AVAILABLE = True
except ImportError:
  OPENGL_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
TILES_DIR = BASE_DIR / "tiles"
HOST = "127.0.0.1"
DEFAULT_CENTER = (32.655255, -115.407228)
REFRESH_MS = 250
FIRE_CONFIRM_WINDOW_MS = 10000
VISUALIZER_CARD_HEIGHT = 430
BOTTOM_CARD_MIN_HEIGHT = 430
BOTTOM_CARD_MAX_HEIGHT = 560

BLANK_PNG = (
  b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
  b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\x00\x01"
  b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

STYLE_SHEET = """
QWidget {
  background: #0c1220;
  color: #e6edf7;
  font-family: "Segoe UI";
  font-size: 12px;
}
QMainWindow {
  background: #0a101b;
}
QFrame#HeroCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #17233b, stop:1 #0c1220);
  border: 1px solid #2b4268;
  border-radius: 20px;
}
QFrame#VisualCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121b2e, stop:1 #0d1526);
  border: 1px solid #253a5f;
  border-radius: 18px;
}
QLabel[role="title"] {
  font-size: 24px;
  font-weight: 700;
  color: #f4f7fb;
}
QLabel[role="section"] {
  font-size: 13px;
  font-weight: 700;
  color: #93a8c9;
  letter-spacing: 0.5px;
}
QLabel[role="metricValue"] {
  font-size: 17px;
  font-weight: 700;
  color: #f9fbff;
}
QLabel[role="metricLabel"] {
  font-size: 11px;
  color: #7f93b3;
}
QLabel[role="statusGood"] {
  background: #14311f;
  color: #7ee2a8;
  border: 1px solid #245c3a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="statusWarn"] {
  background: #382814;
  color: #f6c66d;
  border: 1px solid #6f5128;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="placeholderTitle"] {
  font-size: 20px;
  font-weight: 700;
}
QLineEdit, QComboBox, QPlainTextEdit {
  background: #08101d;
  border: 1px solid #263856;
  border-radius: 10px;
  padding: 8px 10px;
}
QComboBox::drop-down {
  border: none;
}
QPushButton {
  background: #1d7df2;
  color: white;
  border: none;
  border-radius: 10px;
  padding: 6px 10px;
  font-weight: 700;
  font-size: 11px;
}
QPushButton:hover {
  background: #3790ff;
}
QPushButton[variant="ghost"] {
  background: #132039;
  border: 1px solid #29426a;
}
QPushButton[variant="danger"] {
  background: #bf3f3f;
}
QPushButton[variant="danger"]:hover {
  background: #db5858;
}
QPlainTextEdit {
  font-family: "Cascadia Mono";
  font-size: 11px;
}
QLabel[role="kvKey"] {
  color: #7f93b3;
  font-size: 11px;
  font-weight: 600;
}
QLabel[role="kvValue"] {
  color: #eef4ff;
  font-size: 13px;
  font-weight: 700;
}
QLabel[role="statusDanger"] {
  background: #3f1010;
  color: #ff8f8f;
  border: 1px solid #7f2a2a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="statusNeutral"] {
  background: #132039;
  color: #b8cae6;
  border: 1px solid #29426a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
"""


def tile_to_latlon(zoom, x_tile, y_tile):
  n = 2.0 ** zoom
  lon_deg = x_tile / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y_tile / n)))
  lat_deg = math.degrees(lat_rad)
  return lat_deg, lon_deg


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

      y_values = []
      for y_file in x_dir.glob("*.png"):
        if y_file.stem.isdigit():
          y_values.append(int(y_file.stem))

      if y_values:
        x_map[int(x_dir.name)] = sorted(y_values)

    if x_map:
      tile_index[zoom] = x_map

  return tile_index


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
    "north": north,
    "south": south,
    "west": west,
    "east": east,
  }


def choose_closest(values, target):
  return min(values, key=lambda value: abs(value - target))


def parse_telemetry_line(raw_line):
  line = raw_line.strip()
  if not line:
    return None

  if line.startswith("ACK:"):
    return {"type": "ack", "value": line}

  parts = [part.strip() for part in line.split(";")]
  if len(parts) < 11:
    return None

  try:
    altitude = float(parts[0])
    latitude = float(parts[1])
    longitude = float(parts[2])
    satellites = int(float(parts[3]))
    threshold = float(parts[4])
    fired = bool(int(float(parts[5])))
    sd_on = bool(int(float(parts[6])))
    sd_ok = bool(int(float(parts[7])))
    bme_ok = bool(int(float(parts[8])))
    gps_ok = bool(int(float(parts[9])))
    uptime_ms = int(float(parts[10]))
  except ValueError:
    return None

  if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
    return None

  rssi = None
  snr = None
  if len(parts) >= 13:
    try:
      rssi = float(parts[11])
      snr = float(parts[12])
    except ValueError:
      rssi = None
      snr = None

  return {
    "type": "telemetry",
    "altitude": altitude,
    "latitude": latitude,
    "longitude": longitude,
    "satellites": satellites,
    "threshold": threshold,
    "fired": fired,
    "sd_on": sd_on,
    "sd_ok": sd_ok,
    "bme_ok": bme_ok,
    "gps_ok": gps_ok,
    "uptime_ms": uptime_ms,
    "rssi": rssi,
    "snr": snr,
    "raw": line,
  }


class SharedState:
  def __init__(self):
    self.lock = threading.Lock()
    self.connection_status = "Desconectado"
    self.latest_packet = "Sin telemetria"
    self.latest_ack = "Sin ACK"
    self.telemetry = None
    self.logs = []
    self.latest_position = None
    self.logging_enabled = False
    self.log_file_path = ""

  def set_connection_status(self, text):
    with self.lock:
      self.connection_status = text

  def push_log(self, prefix, message):
    stamp = time.strftime("%H:%M:%S")
    log_line = f"[{stamp}] {prefix} {message}"
    with self.lock:
      self.logs.append(log_line)
      if len(self.logs) > 500:
        self.logs = self.logs[-500:]

      should_write_file = self.logging_enabled and bool(self.log_file_path)
      target_path = self.log_file_path

    if should_write_file:
      try:
        with open(target_path, "a", encoding="utf-8") as log_file:
          log_file.write(log_line + "\n")
      except OSError:
        pass

  def pop_logs(self):
    with self.lock:
      pending = self.logs[:]
      self.logs.clear()
      return pending

  def update_telemetry(self, telemetry):
    with self.lock:
      self.telemetry = telemetry
      self.latest_packet = telemetry["raw"]
      latitude = telemetry["latitude"]
      longitude = telemetry["longitude"]
      gps_ok = telemetry["gps_ok"]
      if gps_ok and not (abs(latitude) < 1e-9 and abs(longitude) < 1e-9):
        self.latest_position = (latitude, longitude)
      else:
        self.latest_position = None

  def get_snapshot(self):
    with self.lock:
      return {
        "connection_status": self.connection_status,
        "latest_packet": self.latest_packet,
        "latest_ack": self.latest_ack,
        "telemetry": dict(self.telemetry) if self.telemetry else None,
      }

  def set_latest_ack(self, ack_text):
    with self.lock:
      self.latest_ack = ack_text

  def set_logging_file_path(self, file_path):
    with self.lock:
      self.log_file_path = file_path

  def set_logging_enabled(self, enabled):
    with self.lock:
      self.logging_enabled = enabled

  def get_logging_config(self):
    with self.lock:
      return {
        "enabled": self.logging_enabled,
        "file_path": self.log_file_path,
      }

  def get_position_payload(self):
    with self.lock:
      if self.latest_position is None:
        return {"ok": False}

      latitude, longitude = self.latest_position
      return {
        "ok": True,
        "lat": latitude,
        "lon": longitude,
      }


class SerialBridge:
  def __init__(self, state):
    self.state = state
    self.stop_event = threading.Event()
    self.worker_thread = None
    self.serial_handle = None
    self.lock = threading.Lock()

  def connect(self, port, baudrate):
    self.disconnect()
    self.stop_event.clear()
    self.worker_thread = threading.Thread(
      target=self._reader_loop,
      args=(port, baudrate),
      daemon=True,
    )
    self.worker_thread.start()

  def disconnect(self):
    self.stop_event.set()
    with self.lock:
      if self.serial_handle is not None:
        try:
          self.serial_handle.close()
        except Exception:
          pass
        self.serial_handle = None
    self.state.set_connection_status("Desconectado")

  def send_command(self, command_text):
    command = command_text.strip()
    if not command:
      return False

    if serial is None:
      self.state.push_log("SYS", "pyserial no esta instalado")
      return False

    payload = f"{command}\n".encode("utf-8")
    with self.lock:
      handle = self.serial_handle

    if handle is None:
      self.state.push_log("SYS", "No hay puerto conectado")
      return False

    try:
      handle.write(payload)
      self.state.push_log("TX ", command)
      return True
    except Exception as error:
      self.state.push_log("ERR", f"No se pudo enviar '{command}': {error}")
      return False

  def _reader_loop(self, port, baudrate):
    if serial is None:
      self.state.set_connection_status("Instala pyserial")
      return

    try:
      serial_port = serial.Serial(port, baudrate, timeout=0.25)
    except Exception as error:
      self.state.set_connection_status(f"Error en {port}: {error}")
      self.state.push_log("ERR", f"Fallo al abrir {port}: {error}")
      return

    with self.lock:
      self.serial_handle = serial_port

    self.state.set_connection_status(f"Conectado a {port} @ {baudrate}")
    self.state.push_log("SYS", f"Conexion abierta con {port} @ {baudrate}")

    try:
      while not self.stop_event.is_set():
        try:
          raw_bytes = serial_port.readline()
        except Exception as error:
          self.state.push_log("ERR", f"Lectura serial interrumpida: {error}")
          break

        if not raw_bytes:
          continue

        raw_line = raw_bytes.decode("utf-8", errors="ignore").strip()
        if not raw_line:
          continue

        self.state.push_log("RX ", raw_line)
        parsed = parse_telemetry_line(raw_line)
        if not parsed:
          continue

        if parsed["type"] == "ack":
          self.state.set_latest_ack(parsed["value"])
        elif parsed["type"] == "telemetry":
          self.state.update_telemetry(parsed)
    finally:
      with self.lock:
        if self.serial_handle is serial_port:
          self.serial_handle = None
      try:
        serial_port.close()
      except Exception:
        pass
      if not self.stop_event.is_set():
        self.state.set_connection_status("Conexion cerrada")


class LocalRequestHandler(http.server.BaseHTTPRequestHandler):
  server_version = "CASSControl/1.0"

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
      self._write_png(tile_path.read_bytes())
    except OSError:
      self._write_png(BLANK_PNG)

  def _resolve_tile_path(self, zoom, x_value, y_value):
    direct_path = TILES_DIR / str(zoom) / str(x_value) / f"{y_value}.png"
    if direct_path.exists():
      return direct_path
    return None

  def log_message(self, format_text, *args):
    return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
  daemon_threads = True
  allow_reuse_address = True


class MapBridgePage(QWebEnginePage):
  focusMapRequested = pyqtSignal()

  def javaScriptConsoleMessage(self, _level, message, _line_number, _source_id):
    if message == "__CASS_FOCUS_MAP__":
      self.focusMapRequested.emit()
      return
    super().javaScriptConsoleMessage(_level, message, _line_number, _source_id)


class TimeSeriesChart(QWidget):
  def __init__(self, title, color_hex, parent=None):
    super().__init__(parent)
    self.title = title
    self.color = QColor(color_hex)
    self.values = []
    self.setMinimumHeight(74)

  def set_values(self, values):
    self.values = values
    self.update()

  def paintEvent(self, _event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = self.rect().adjusted(8, 8, -8, -8)

    painter.fillRect(rect, QColor("#0a1324"))
    painter.setPen(QPen(QColor("#203454"), 1))
    painter.drawRoundedRect(rect, 10, 10)

    painter.setPen(QPen(QColor("#91a8cc"), 1))
    painter.drawText(rect.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignLeft, self.title)

    plot_rect = rect.adjusted(8, 26, -8, -8)
    if len(self.values) < 2:
      painter.setPen(QPen(QColor("#5e7497"), 1))
      painter.drawText(plot_rect, Qt.AlignCenter, "Sin datos")
      return

    min_value = min(self.values)
    max_value = max(self.values)
    if abs(max_value - min_value) < 1e-6:
      min_value -= 1
      max_value += 1

    painter.setPen(QPen(QColor("#1d2f4a"), 1))
    for step in range(1, 4):
      y = plot_rect.top() + step * plot_rect.height() / 4
      painter.drawLine(int(plot_rect.left()), int(y), int(plot_rect.right()), int(y))

    points = []
    count = len(self.values)
    for index, value in enumerate(self.values):
      x = plot_rect.left() + (plot_rect.width() * index / (count - 1))
      ratio = (value - min_value) / (max_value - min_value)
      y = plot_rect.bottom() - ratio * plot_rect.height()
      points.append((x, y))

    painter.setPen(QPen(self.color, 2))
    for index in range(len(points) - 1):
      x1, y1 = points[index]
      x2, y2 = points[index + 1]
      painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    painter.setPen(QPen(QColor("#bcd0ed"), 1))
    painter.drawText(plot_rect.adjusted(0, 0, 0, -2), Qt.AlignBottom | Qt.AlignRight, f"{self.values[-1]:.2f}")


if OPENGL_AVAILABLE:
  class RocketViewer(QGLWidget):
    def __init__(self):
      super().__init__()
      self.lat0 = 32.603000
      self.lon0 = -115.387000
      self.alt0 = 0.0

      self.x = 0.0
      self.y = 0.0
      self.z = 0.0

      self.camera_x = 0.0
      self.camera_y = -10.0
      self.camera_z = 1.7
      self.yaw = 90.0
      self.pitch = -10.0

      self.last_mouse_x = 0
      self.last_mouse_y = 0
      self.mouse_pressed = False
      self.camera_locked = False

      self.setMinimumSize(420, 300)

    def initializeGL(self):
      glEnable(GL_DEPTH_TEST)
      glClearColor(0.05, 0.05, 0.08, 1)

    def resizeGL(self, width, height):
      if height == 0:
        height = 1
      glViewport(0, 0, width, height)
      glMatrixMode(GL_PROJECTION)
      glLoadIdentity()
      gluPerspective(60, width / height, 0.1, 1000)
      glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
      glLoadIdentity()

      if self.camera_locked:
        dx = self.x - self.camera_x
        dy = self.y - self.camera_y
        dz = self.z - self.camera_z
        horizontal_distance = math.sqrt(dx * dx + dy * dy)
        self.yaw = math.degrees(math.atan2(dy, dx))
        self.pitch = math.degrees(math.atan2(dz, horizontal_distance))

      yaw_rad = math.radians(self.yaw)
      pitch_rad = math.radians(self.pitch)
      direction_x = math.cos(pitch_rad) * math.cos(yaw_rad)
      direction_y = math.cos(pitch_rad) * math.sin(yaw_rad)
      direction_z = math.sin(pitch_rad)

      look_x = self.camera_x + direction_x
      look_y = self.camera_y + direction_y
      look_z = self.camera_z + direction_z
      gluLookAt(self.camera_x, self.camera_y, self.camera_z, look_x, look_y, look_z, 0, 0, 1)

      self.draw_grid()
      self.draw_axes()
      self.draw_rocket()

    def mousePressEvent(self, event):
      self.last_mouse_x = event.x()
      self.last_mouse_y = event.y()
      self.mouse_pressed = True

    def mouseReleaseEvent(self, _event):
      self.mouse_pressed = False

    def mouseMoveEvent(self, event):
      if not self.mouse_pressed or self.camera_locked:
        return

      dx = event.x() - self.last_mouse_x
      dy = event.y() - self.last_mouse_y
      self.yaw += dx * 0.4
      self.pitch -= dy * 0.4
      self.pitch = max(-89, min(89, self.pitch))
      self.last_mouse_x = event.x()
      self.last_mouse_y = event.y()
      self.update()

    def wheelEvent(self, event):
      delta = event.angleDelta().y()
      yaw_rad = math.radians(self.yaw)
      pitch_rad = math.radians(self.pitch)
      direction_x = math.cos(pitch_rad) * math.cos(yaw_rad)
      direction_y = math.cos(pitch_rad) * math.sin(yaw_rad)
      direction_z = math.sin(pitch_rad)
      distance = delta / 120

      self.camera_x += direction_x * distance
      self.camera_y += direction_y * distance
      self.camera_z += direction_z * distance
      self.update()

    def set_gps(self, lat, lon, altitude):
      lat0_rad = math.radians(self.lat0)
      self.y = (lat - self.lat0) * 111320
      self.x = (lon - self.lon0) * 111320 * math.cos(lat0_rad)
      self.z = altitude - self.alt0
      self.update()

    def reset_position(self, lat, lon, altitude):
      self.lat0 = lat
      self.lon0 = lon
      self.alt0 = altitude
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0
      self.camera_x = 0.0
      self.camera_y = -10.0
      self.camera_z = 1.7
      self.yaw = 90.0
      self.pitch = -10.0
      self.camera_locked = False
      self.update()

    def toggle_camera_lock(self):
      self.camera_locked = not self.camera_locked
      self.update()

    def set_camera_original(self):
      self.camera_x = self.x
      self.camera_y = self.y - 10.0
      self.camera_z = self.z + 1.7
      self.camera_locked = True
      self.update()

    def set_camera_topdown(self):
      self.camera_x = self.x
      self.camera_y = self.y
      self.camera_z = self.z + 12.0
      self.camera_locked = True
      self.update()

    def set_camera_side_lock(self):
      self.camera_x = self.x + 50.0
      self.camera_y = self.y
      self.camera_z = self.z + 10.0
      self.camera_locked = True
      self.update()

    def draw_grid(self):
      self.draw_ground()
      glColor3f(0.25, 0.25, 0.25)
      glLineWidth(1)
      glBegin(GL_LINES)
      size = 100
      for i in range(-size, size + 1):
        glVertex3f(i, -size, 0)
        glVertex3f(i, size, 0)
        glVertex3f(-size, i, 0)
        glVertex3f(size, i, 0)
      glEnd()

      half = 2.5
      glColor3f(1.0, 0.9, 0.1)
      glLineWidth(2)
      glBegin(GL_LINE_LOOP)
      glVertex3f(-half, -half, 0.01)
      glVertex3f(half, -half, 0.01)
      glVertex3f(half, half, 0.01)
      glVertex3f(-half, half, 0.01)
      glEnd()

    def draw_ground(self):
      size = 120
      glColor3f(0.10, 0.32, 0.12)
      glBegin(GL_QUADS)
      glVertex3f(-size, -size, -0.001)
      glVertex3f(size, -size, -0.001)
      glVertex3f(size, size, -0.001)
      glVertex3f(-size, size, -0.001)
      glEnd()

    def draw_axes(self):
      glLineWidth(3)
      glBegin(GL_LINES)
      glColor3f(1, 0, 0)
      glVertex3f(0, 0, 0)
      glVertex3f(10, 0, 0)
      glColor3f(0, 1, 0)
      glVertex3f(0, 0, 0)
      glVertex3f(0, 10, 0)
      glColor3f(0, 0, 1)
      glVertex3f(0, 0, 0)
      glVertex3f(0, 0, 10)
      glEnd()

    def draw_rocket(self):
      glPushMatrix()
      glTranslatef(self.x, self.y, self.z)
      glColor3f(0.8, 0.8, 0.8)
      quadric = gluNewQuadric()
      gluCylinder(quadric, 0.5, 0.5, 3, 20, 10)
      glTranslatef(0, 0, 3)
      glColor3f(0.9, 0.1, 0.1)
      gluCylinder(quadric, 0.5, 0, 1, 20, 10)
      gluDeleteQuadric(quadric)
      glTranslatef(0, 0, -3)
      glColor3f(0.7, 0.1, 0.1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glPopMatrix()

    def draw_fin(self):
      glBegin(GL_TRIANGLES)
      glVertex3f(0.4, 0, 0)
      glVertex3f(1.2, 0, 0)
      glVertex3f(0.4, 0, 1.2)
      glEnd()
else:
  class RocketViewer(QWidget):
    def __init__(self):
      super().__init__()
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0
      self.camera_locked = False
      self._status = QLabel("OpenGL no disponible: instala PyOpenGL")
      self._status.setAlignment(Qt.AlignCenter)
      self._status.setStyleSheet("color: #f6c66d;")
      layout = QVBoxLayout(self)
      layout.addWidget(self._status)

    def set_gps(self, lat, lon, altitude):
      self.x = lon
      self.y = lat
      self.z = altitude

    def reset_position(self, _lat, _lon, _altitude):
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0

    def toggle_camera_lock(self):
      self.camera_locked = not self.camera_locked

    def set_camera_original(self):
      self.camera_locked = True

    def set_camera_topdown(self):
      self.camera_locked = True

    def set_camera_side_lock(self):
      self.camera_locked = True


def make_map_html(bounds, port):
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
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ background: #e5ecf4; }}
    #map {{ background: linear-gradient(180deg, #dce7f3 0%, #f4f6fb 100%); }}
    .rocket-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #ff6a3d;
      border: 1px solid #80230b;
      box-shadow: 0 0 0 2px rgba(255, 106, 61, 0.18);
    }}
    .leaflet-control-zoom a {{
      color: #0d1526;
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
      doubleClickZoom: false,
      worldCopyJump: false,
      preferCanvas: true,
    }});

    L.tileLayer('http://{HOST}:{port}/{{z}}/{{x}}/{{y}}.png', {{
      minZoom: cfg.min_zoom,
      maxZoom: cfg.max_zoom,
      noWrap: true,
      attribution: 'Tiles locales CASS'
    }}).addTo(map);

    map.fitBounds([[cfg.south, cfg.west], [cfg.north, cfg.east]], {{ padding: [24, 24] }});
    map.on('dblclick', () => {{
      console.log('__CASS_FOCUS_MAP__');
    }});

    const rocketIcon = L.divIcon({{
      className: 'rocket-dot',
      iconSize: [10, 10],
      iconAnchor: [5, 5]
    }});

    let marker = null;
    let followMode = false;

    function activateFollowMode() {{
      followMode = true;
      if (marker) {{
        map.setView(marker.getLatLng(), cfg.max_zoom);
      }}
    }}

    function deactivateFollowMode() {{
      followMode = false;
    }}

    function showFollowMenu(latlng) {{
      const popup = L.popup({{ closeButton: true, autoClose: true, closeOnClick: true }})
        .setLatLng(latlng)
        .setContent(`
          <div style="display:flex;flex-direction:column;gap:6px;min-width:120px;">
            <div style="font-weight:700;color:#0d1526;">Cohete</div>
            <button id="follow-rocket-btn" style="cursor:pointer;border:none;border-radius:8px;padding:8px 10px;background:#1d7df2;color:#fff;font-weight:700;">
              Seguirlo
            </button>
            <button id="unfollow-rocket-btn" style="cursor:pointer;border:none;border-radius:8px;padding:8px 10px;background:#2f415f;color:#fff;font-weight:700;">
              Dejar de seguirlo
            </button>
          </div>
        `);

      popup.openOn(map);
      window.setTimeout(() => {{
        const button = document.getElementById('follow-rocket-btn');
        const unfollowButton = document.getElementById('unfollow-rocket-btn');
        if (button) {{
          button.onclick = () => {{
            activateFollowMode();
            map.closePopup();
          }};
        }}
        if (unfollowButton) {{
          unfollowButton.onclick = () => {{
            deactivateFollowMode();
            map.closePopup();
          }};
        }}
      }}, 0);
    }}

    async function refreshPosition() {{
      try {{
        const response = await fetch('http://{HOST}:{port}/position', {{ cache: 'no-store' }});
        const data = await response.json();
        if (!data.ok) {{
          if (marker) {{
            map.removeLayer(marker);
            marker = null;
          }}
          return;
        }}

        const latLng = [data.lat, data.lon];
        if (!marker) {{
          marker = L.marker(latLng, {{ icon: rocketIcon }}).addTo(map);
          map.setView(latLng, cfg.max_zoom);
          marker.on('contextmenu', (event) => {{
            showFollowMenu(event.latlng);
          }});
        }} else {{
          marker.setLatLng(latLng);
          if (followMode) {{
            map.setView(latLng, cfg.max_zoom);
          }}
        }}
      }} catch (error) {{
      }}
    }}

    setInterval(refreshPosition, 300);
    refreshPosition();
  </script>
</body>
</html>
"""


def make_card(title_text):
  card = QFrame()
  card.setObjectName("Card")
  layout = QVBoxLayout(card)
  layout.setContentsMargins(18, 16, 18, 16)
  layout.setSpacing(12)
  return card, layout


class FlightControlWindow(QMainWindow):
  def __init__(self, state, serial_bridge, map_url):
    super().__init__()
    self.state = state
    self.serial_bridge = serial_bridge
    self.telemetry_labels = {}
    self.altitude_history = deque(maxlen=180)
    self.rssi_history = deque(maxlen=180)
    self.snr_history = deque(maxlen=180)
    self.fire_arm_enabled = False
    self.fire_press_count = 0
    self.first_fire_press_ms = 0
    self.is_borderless_fullscreen = False
    self.focus_mode = None
    self.camera_mode = 0

    self.setWindowTitle("CASS Flight Control")
    self.resize(1600, 920)
    self.setStyleSheet(STYLE_SHEET)

    root = QWidget(self)
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(16, 16, 16, 16)
    root_layout.setSpacing(14)

    root_layout.addWidget(self._build_visualizers_row())
    root_layout.addWidget(self._build_bottom_dashboard(), stretch=1)

    self.setCentralWidget(root)

    self.ui_timer = QTimer(self)
    self.ui_timer.timeout.connect(self.refresh_ui)
    self.ui_timer.start(REFRESH_MS)

    self.web_view.setUrl(QUrl(map_url))
    self.refresh_ports()
    self.refresh_ui()

  def enter_borderless_fullscreen(self):
    if self.is_borderless_fullscreen:
      return
    self.setWindowFlag(Qt.FramelessWindowHint, True)
    self.showFullScreen()
    self.is_borderless_fullscreen = True

  def exit_borderless_fullscreen(self):
    if not self.is_borderless_fullscreen:
      return
    self.setWindowFlag(Qt.FramelessWindowHint, False)
    self.showMaximized()
    self.is_borderless_fullscreen = False

  def keyPressEvent(self, event):
    if event.key() == Qt.Key_Escape and self.is_borderless_fullscreen:
      self.exit_borderless_fullscreen()
      event.accept()
      return
    super().keyPressEvent(event)

  def _build_visualizers_row(self):
    self.visualizers_container = QWidget()
    layout = QHBoxLayout(self.visualizers_container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    self.map_card = self._build_map_card()
    self.placeholder_card = self._build_placeholder_3d()

    for card in [self.map_card, self.placeholder_card]:
      card.setObjectName("VisualCard")
      card.setFixedHeight(VISUALIZER_CARD_HEIGHT)
      card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    layout.addWidget(self.map_card, stretch=1)
    layout.addWidget(self.placeholder_card, stretch=1)
    return self.visualizers_container

  def _build_bottom_dashboard(self):
    self.bottom_dashboard = QWidget()
    layout = QHBoxLayout(self.bottom_dashboard)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    self.status_card = self._build_status_card()
    self.connection_card = self._build_connection_card()
    self.status_card.setMinimumHeight(BOTTOM_CARD_MIN_HEIGHT)
    self.connection_card.setMinimumHeight(BOTTOM_CARD_MIN_HEIGHT)
    self.status_card.setMaximumHeight(BOTTOM_CARD_MAX_HEIGHT)
    self.connection_card.setMaximumHeight(BOTTOM_CARD_MAX_HEIGHT)

    layout.addWidget(self.status_card, stretch=3)
    layout.addWidget(self.connection_card, stretch=3)
    layout.addWidget(self._build_terminal_and_charts_card(), stretch=4)
    return self.bottom_dashboard

  def _build_map_card(self):
    card, layout = make_card("Mapa de vuelo")
    title = QLabel("Mapa de vuelo")
    title.setProperty("role", "section")
    layout.addWidget(title)

    self.web_view = QWebEngineView(self)
    self.map_page = MapBridgePage(self.web_view)
    self.map_page.focusMapRequested.connect(lambda: self.toggle_focus_mode("map"))
    self.web_view.setPage(self.map_page)
    self.web_view.setMinimumHeight(320)
    self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.web_view.setStyleSheet("border-radius: 14px; background: #dfe7f2;")
    layout.addWidget(self.web_view, stretch=1)
    return card

  def _build_placeholder_3d(self):
    card, layout = make_card("Visualizador 3D")
    title = QLabel("Visualizador 3D")
    title.setProperty("role", "section")
    layout.addWidget(title)

    content_row = QHBoxLayout()
    content_row.setSpacing(10)

    panel = QFrame()
    panel.setStyleSheet("background: #0b1323; border: 1px solid #1f314d; border-radius: 12px;")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(10, 10, 10, 10)
    panel_layout.setSpacing(6)

    update_button = QPushButton("Actualizar")
    update_button.setProperty("variant", "ghost")
    update_button.clicked.connect(self.update_rocket_viewer_from_inputs)
    reset_button = QPushButton("Reset")
    reset_button.setProperty("variant", "ghost")
    reset_button.clicked.connect(self.reset_rocket_viewer)
    self.viewer_lock_button = QPushButton("Lock camara")
    self.viewer_lock_button.setCheckable(True)
    self.viewer_lock_button.setProperty("variant", "ghost")
    self.viewer_lock_button.clicked.connect(self.toggle_rocket_camera_lock)
    self.viewer_camera_button = QPushButton("Cambiar camara")
    self.viewer_camera_button.setProperty("variant", "ghost")
    self.viewer_camera_button.clicked.connect(self.cycle_rocket_camera)

    panel_layout.addWidget(update_button)
    panel_layout.addWidget(reset_button)
    panel_layout.addWidget(self.viewer_lock_button)
    panel_layout.addWidget(self.viewer_camera_button)

    self.viewer_camera_mode_label = QLabel("Camara: Original")
    self.viewer_camera_mode_label.setProperty("role", "metricLabel")
    panel_layout.addWidget(self.viewer_camera_mode_label)

    self.viewer_x_label = QLabel("X: 0.00 m")
    self.viewer_y_label = QLabel("Y: 0.00 m")
    self.viewer_z_label = QLabel("Z: 0.00 m")
    self.viewer_x_label.setProperty("role", "kvValue")
    self.viewer_y_label.setProperty("role", "kvValue")
    self.viewer_z_label.setProperty("role", "kvValue")
    panel_layout.addWidget(self.viewer_x_label)
    panel_layout.addWidget(self.viewer_y_label)
    panel_layout.addWidget(self.viewer_z_label)
    panel_layout.addStretch(1)

    self.rocket_viewer = RocketViewer()
    self.rocket_viewer.setStyleSheet("background: #0a1324; border: 1px solid #1f314d; border-radius: 12px;")
    self.rocket_viewer.installEventFilter(self)

    content_row.addWidget(panel, stretch=1)
    content_row.addWidget(self.rocket_viewer, stretch=3)
    layout.addLayout(content_row, stretch=1)
    return card

  def _build_status_card(self):
    card, layout = make_card("Estado y telemetria")

    top_row = QHBoxLayout()
    title = QLabel("Estado y telemetria")
    title.setProperty("role", "section")
    self.packet_badge = QLabel("Sin telemetria")
    self.packet_badge.setProperty("role", "statusWarn")
    top_row.addWidget(title)
    top_row.addWidget(self.packet_badge)
    layout.addLayout(top_row)

    mission_row = QHBoxLayout()
    self.mission_phase_badge = QLabel("Sin telemetria")
    self.mission_phase_badge.setProperty("role", "statusWarn")
    self.fire_state_badge = QLabel("FIRE sin ejecutar")
    self.fire_state_badge.setProperty("role", "statusNeutral")
    mission_row.addWidget(self.mission_phase_badge)
    mission_row.addWidget(self.fire_state_badge)
    layout.addLayout(mission_row)

    modules = QGridLayout()
    self.sd_badge = QLabel("SD --")
    self.bme_badge = QLabel("BME --")
    self.gps_badge = QLabel("GPS --")
    self.lora_badge = QLabel("LoRa --")
    for widget in [self.sd_badge, self.bme_badge, self.gps_badge, self.lora_badge]:
      widget.setProperty("role", "statusWarn")
    modules.addWidget(self.sd_badge, 0, 0)
    modules.addWidget(self.bme_badge, 0, 1)
    modules.addWidget(self.gps_badge, 1, 0)
    modules.addWidget(self.lora_badge, 1, 1)
    layout.addLayout(modules)

    metrics = QGridLayout()
    metrics.setHorizontalSpacing(12)
    metrics.setVerticalSpacing(4)
    fields = [
      ("ALT", "Altitud", "0.00 m"),
      ("LAT", "Latitud", "--"),
      ("LON", "Longitud", "--"),
      ("SAT", "Satelites", "0"),
      ("THR", "Threshold", "0 m"),
      ("FIR", "Disparo", "NO"),
      ("SDO", "SD Guardando", "OFF"),
      ("SDK", "SD Estado", "NO OK"),
      ("BME", "BME280", "NO OK"),
      ("GPS", "GPS", "NO OK"),
      ("TIM", "Uptime", "0 s"),
      ("RF ", "RSSI / SNR", "-- / --"),
    ]

    for index, (key, label_text, default_text) in enumerate(fields):
      key_label = QLabel(label_text)
      key_label.setProperty("role", "kvKey")
      value_label = QLabel(default_text)
      value_label.setProperty("role", "kvValue")
      self.telemetry_labels[key] = value_label
      row = index // 2
      column = (index % 2) * 2
      metrics.addWidget(key_label, row, column)
      metrics.addWidget(value_label, row, column + 1)

    layout.addLayout(metrics)
    return card

  def _build_terminal_and_charts_card(self):
    card, layout = make_card("Terminal y graficas")
    title_row = QHBoxLayout()
    title = QLabel("Terminal y graficas")
    title.setProperty("role", "section")
    self.latest_packet_badge = QLabel("Sin ACK")
    self.latest_packet_badge.setProperty("role", "statusWarn")
    title_row.addWidget(title)
    title_row.addWidget(self.latest_packet_badge)
    layout.addLayout(title_row)

    self.terminal = QPlainTextEdit()
    self.terminal.setReadOnly(True)
    self.terminal.setMinimumHeight(130)
    self.terminal.setFont(QFont("Cascadia Mono", 10))
    layout.addWidget(self.terminal, stretch=1)

    command_row = QHBoxLayout()
    self.custom_command_edit = QLineEdit()
    self.custom_command_edit.setPlaceholderText("Comando manual, por ejemplo: STATUS o THR:150")
    send_button = QPushButton("Enviar")
    send_button.clicked.connect(self.send_custom_command)
    command_row.addWidget(self.custom_command_edit, stretch=1)
    command_row.addWidget(send_button)
    layout.addLayout(command_row)

    charts_row = QHBoxLayout()
    charts_row.setSpacing(10)
    self.altitude_chart = TimeSeriesChart("Altitud (m)", "#42d6a4")
    self.rssi_chart = TimeSeriesChart("RSSI (dBm)", "#61a0ff")
    self.snr_chart = TimeSeriesChart("SNR (dB)", "#ffb44f")
    charts_row.addWidget(self.altitude_chart)
    charts_row.addWidget(self.rssi_chart)
    charts_row.addWidget(self.snr_chart)
    layout.addLayout(charts_row)
    return card

  def _build_connection_card(self):
    card, layout = make_card("Conexion y control")

    status_row = QHBoxLayout()
    title = QLabel("Conexion y control")
    title.setProperty("role", "section")
    self.connection_badge = QLabel("Desconectado")
    self.connection_badge.setProperty("role", "statusWarn")
    status_row.addWidget(title)
    status_row.addWidget(self.connection_badge)
    layout.addLayout(status_row)

    form = QGridLayout()
    form.setHorizontalSpacing(8)
    form.setVerticalSpacing(4)

    form.addWidget(QLabel("Puerto"), 0, 0)
    self.port_combo = QComboBox()
    form.addWidget(self.port_combo, 0, 1)

    refresh_ports_button = QPushButton("Refrescar")
    refresh_ports_button.setProperty("variant", "ghost")
    refresh_ports_button.clicked.connect(self.refresh_ports)
    form.addWidget(refresh_ports_button, 0, 2)

    form.addWidget(QLabel("Baudrate"), 1, 0)
    self.baud_edit = QLineEdit("115200")
    form.addWidget(self.baud_edit, 1, 1, 1, 2)

    self.connect_button = QPushButton("Conectar")
    self.connect_button.clicked.connect(self.toggle_connection)
    self.disconnect_button = QPushButton("Desconectar")
    self.disconnect_button.setProperty("variant", "ghost")
    self.disconnect_button.clicked.connect(self.disconnect_serial)
    form.addWidget(self.connect_button, 2, 1)
    form.addWidget(self.disconnect_button, 2, 2)

    layout.addLayout(form)

    logging_frame = QFrame()
    logging_frame.setStyleSheet("background: #0f192c; border: 1px solid #29426a; border-radius: 12px;")
    logging_layout = QVBoxLayout(logging_frame)
    logging_layout.setContentsMargins(10, 10, 10, 10)
    logging_layout.setSpacing(6)

    logging_header = QHBoxLayout()
    logging_label = QLabel("Logging local (.txt)")
    logging_label.setProperty("role", "metricLabel")
    self.logging_switch = QCheckBox("OFF")
    self.logging_switch.stateChanged.connect(self.toggle_local_logging)
    logging_header.addWidget(logging_label)
    logging_header.addStretch(1)
    logging_header.addWidget(self.logging_switch)
    logging_layout.addLayout(logging_header)

    self.log_file_edit = QLineEdit()
    self.log_file_edit.setPlaceholderText("Ruta del archivo .txt para logs")
    logging_layout.addWidget(self.log_file_edit)

    log_buttons_row = QHBoxLayout()
    self.select_log_button = QPushButton("Seleccionar")
    self.select_log_button.setProperty("variant", "ghost")
    self.select_log_button.clicked.connect(self.select_log_file)
    self.create_log_button = QPushButton("Crear .txt")
    self.create_log_button.setProperty("variant", "ghost")
    self.create_log_button.clicked.connect(self.create_log_file)
    self.apply_log_button = QPushButton("Aplicar")
    self.apply_log_button.clicked.connect(self.apply_log_file_path)
    log_buttons_row.addWidget(self.select_log_button)
    log_buttons_row.addWidget(self.create_log_button)
    log_buttons_row.addWidget(self.apply_log_button)
    logging_layout.addLayout(log_buttons_row)

    layout.addWidget(logging_frame)

    fire_guard = QFrame()
    fire_guard.setStyleSheet("background: #120d15; border: 1px solid #4b2b58; border-radius: 12px;")
    fire_guard_layout = QVBoxLayout(fire_guard)
    fire_guard_layout.setContentsMargins(10, 10, 10, 10)
    fire_guard_layout.setSpacing(6)

    self.fire_arm_checkbox = QCheckBox("Habilitar envio FIRE")
    self.fire_arm_checkbox.stateChanged.connect(self.toggle_fire_arm)
    self.fire_arm_checkbox.setStyleSheet("color: #f2d0ff;")
    fire_guard_layout.addWidget(self.fire_arm_checkbox)

    fire_row = QHBoxLayout()
    self.fire_progress_badge = QLabel("Confirmacion FIRE: 0/3")
    self.fire_progress_badge.setProperty("role", "statusNeutral")
    self.fire_send_button = QPushButton("Enviar FIRE")
    self.fire_send_button.setProperty("variant", "danger")
    self.fire_send_button.clicked.connect(self.send_fire)
    self.fire_send_button.setEnabled(False)
    fire_row.addWidget(self.fire_progress_badge)
    fire_row.addWidget(self.fire_send_button)
    fire_guard_layout.addLayout(fire_row)
    layout.addWidget(fire_guard)

    threshold_row = QHBoxLayout()
    self.threshold_edit = QLineEdit("1000")
    self.threshold_edit.setPlaceholderText("Threshold")
    threshold_button = QPushButton("Enviar THR")
    threshold_button.clicked.connect(self.send_threshold)
    threshold_row.addWidget(self.threshold_edit)
    threshold_row.addWidget(threshold_button)
    layout.addLayout(threshold_row)

    commands_grid = QGridLayout()
    commands_grid.setHorizontalSpacing(8)
    commands_grid.setVerticalSpacing(4)

    buttons = [
      ("STATUS", self.send_status, "ghost"),
      ("PAUSE", self.send_pause, "ghost"),
      ("RESUME", self.send_resume, "ghost"),
      ("PRUEBA", self.send_prueba, "ghost"),
      ("RFIRE", self.send_rfire, "ghost"),
      ("RESET", self.send_reset, "danger"),
    ]

    for index, (text, handler, variant) in enumerate(buttons):
      button = QPushButton(text)
      button.setProperty("variant", variant)
      button.clicked.connect(handler)
      commands_grid.addWidget(button, index // 2, index % 2)

    layout.addLayout(commands_grid)
    return card

  def refresh_ports(self):
    current = self.port_combo.currentText()
    self.port_combo.clear()
    if list_ports is None:
      self.port_combo.addItem("COM12")
      return

    ports = [port.device for port in list_ports.comports()]
    if not ports:
      ports = ["COM12"]
    self.port_combo.addItems(ports)

    if current and current in ports:
      self.port_combo.setCurrentText(current)
    elif "COM12" in ports:
      self.port_combo.setCurrentText("COM12")

  def select_log_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
      self,
      "Seleccionar archivo de log",
      str(BASE_DIR),
      "Text files (*.txt);;All files (*.*)",
    )
    if file_path:
      self.log_file_edit.setText(file_path)
      self.state.set_logging_file_path(file_path)
      self.state.push_log("SYS", f"Archivo de log seleccionado: {file_path}")

  def create_log_file(self):
    default_name = f"cass_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    default_path = str(BASE_DIR / default_name)
    file_path, _ = QFileDialog.getSaveFileName(
      self,
      "Crear archivo de log",
      default_path,
      "Text files (*.txt);;All files (*.*)",
    )
    if file_path:
      try:
        with open(file_path, "a", encoding="utf-8"):
          pass
      except OSError as error:
        self.state.push_log("ERR", f"No se pudo crear archivo de log: {error}")
        return

      self.log_file_edit.setText(file_path)
      self.state.set_logging_file_path(file_path)
      self.state.push_log("SYS", f"Archivo de log creado: {file_path}")

  def apply_log_file_path(self):
    file_path = self.log_file_edit.text().strip()
    if not file_path:
      self.state.push_log("ERR", "Ruta de log vacia")
      return

    if not file_path.lower().endswith(".txt"):
      file_path += ".txt"
      self.log_file_edit.setText(file_path)

    try:
      with open(file_path, "a", encoding="utf-8"):
        pass
    except OSError as error:
      self.state.push_log("ERR", f"No se pudo abrir archivo de log: {error}")
      return

    self.state.set_logging_file_path(file_path)
    self.state.push_log("SYS", f"Ruta de log aplicada: {file_path}")

  def toggle_local_logging(self, state):
    enabled = state == Qt.Checked

    if enabled:
      file_path = self.log_file_edit.text().strip()
      if not file_path:
        file_path = str(BASE_DIR / f"cass_log_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        self.log_file_edit.setText(file_path)

      if not file_path.lower().endswith(".txt"):
        file_path += ".txt"
        self.log_file_edit.setText(file_path)

      try:
        with open(file_path, "a", encoding="utf-8"):
          pass
      except OSError as error:
        self.logging_switch.blockSignals(True)
        self.logging_switch.setChecked(False)
        self.logging_switch.setText("OFF")
        self.logging_switch.blockSignals(False)
        self.state.push_log("ERR", f"No se pudo activar logging: {error}")
        return

      self.state.set_logging_file_path(file_path)

    self.state.set_logging_enabled(enabled)
    self.logging_switch.setText("ON" if enabled else "OFF")
    self.state.push_log("SYS", "Logging local activado" if enabled else "Logging local desactivado")

  def toggle_connection(self):
    port = self.port_combo.currentText().strip()
    try:
      baudrate = int(self.baud_edit.text().strip())
    except ValueError:
      self.state.push_log("ERR", "Baudrate invalido")
      return

    self.serial_bridge.connect(port, baudrate)

  def disconnect_serial(self):
    self.serial_bridge.disconnect()
    self.state.push_log("SYS", "Conexion serial cerrada por usuario")

  def send_custom_command(self):
    if self.serial_bridge.send_command(self.custom_command_edit.text()):
      self.custom_command_edit.clear()

  def send_threshold(self):
    value = self.threshold_edit.text().strip()
    self.serial_bridge.send_command(f"THR:{value}")

  def send_status(self):
    self.serial_bridge.send_command("STATUS")

  def send_pause(self):
    self.serial_bridge.send_command("PAUSE")

  def send_resume(self):
    self.serial_bridge.send_command("RESUME")

  def send_prueba(self):
    self.serial_bridge.send_command("PRUEBA")

  def send_fire(self):
    if not self.fire_arm_enabled:
      self.state.push_log("SAFE", "Bloqueado: habilita FIRE antes de enviar")
      return

    now_ms = int(time.time() * 1000)
    if self.fire_press_count == 0 or (now_ms - self.first_fire_press_ms) > FIRE_CONFIRM_WINDOW_MS:
      self.first_fire_press_ms = now_ms
      self.fire_press_count = 0

    if self.serial_bridge.send_command("FIRE"):
      self.fire_press_count += 1
      if self.fire_press_count >= 3:
        self.fire_press_count = 0
      self._update_fire_progress_badge()

  def send_rfire(self):
    self.serial_bridge.send_command("RFIRE")
    self.fire_press_count = 0
    self._update_fire_progress_badge()

  def send_reset(self):
    self.serial_bridge.send_command("RESET")

  def refresh_ui(self):
    snapshot = self.state.get_snapshot()
    connection_text = snapshot["connection_status"]
    self.connection_badge.setText(connection_text)
    self.connection_badge.setProperty(
      "role",
      "statusGood" if connection_text.startswith("Conectado") else "statusWarn",
    )
    self.connection_badge.style().unpolish(self.connection_badge)
    self.connection_badge.style().polish(self.connection_badge)

    has_telemetry = snapshot["telemetry"] is not None
    self.packet_badge.setText("Telemetria viva" if has_telemetry else "Sin telemetria")
    self.packet_badge.setProperty("role", "statusGood" if has_telemetry else "statusWarn")
    self.packet_badge.style().unpolish(self.packet_badge)
    self.packet_badge.style().polish(self.packet_badge)

    ack_text = snapshot["latest_ack"]
    self.latest_packet_badge.setText(ack_text)
    self.latest_packet_badge.setProperty("role", "statusWarn" if ack_text != "Sin ACK" else "statusNeutral")
    self.latest_packet_badge.style().unpolish(self.latest_packet_badge)
    self.latest_packet_badge.style().polish(self.latest_packet_badge)
    self._flush_logs()
    self._refresh_telemetry(snapshot["telemetry"])
    self._refresh_fire_progress_window()

  def eventFilter(self, watched, event):
    if event.type() == QEvent.MouseButtonDblClick:
      if watched is self.rocket_viewer:
        self.toggle_focus_mode("3d")
        return True
    return super().eventFilter(watched, event)

  def toggle_focus_mode(self, target):
    if self.focus_mode == target:
      self.focus_mode = None
      self.bottom_dashboard.show()
      self.map_card.show()
      self.placeholder_card.show()
      for card in [self.map_card, self.placeholder_card]:
        card.setFixedHeight(VISUALIZER_CARD_HEIGHT)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
      self.status_card.setMinimumHeight(BOTTOM_CARD_MIN_HEIGHT)
      self.connection_card.setMinimumHeight(BOTTOM_CARD_MIN_HEIGHT)
      self.status_card.setMaximumHeight(BOTTOM_CARD_MAX_HEIGHT)
      self.connection_card.setMaximumHeight(BOTTOM_CARD_MAX_HEIGHT)
      self.state.push_log("SYS", "Modo enfoque desactivado")
      return

    self.focus_mode = target
    self.bottom_dashboard.hide()
    if target == "map":
      self.placeholder_card.hide()
      self.map_card.show()
      self.map_card.setMinimumHeight(600)
      self.map_card.setMaximumHeight(16777215)
      self.map_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
      self.state.push_log("SYS", "Modo enfoque: mapa")
    else:
      self.map_card.hide()
      self.placeholder_card.show()
      self.placeholder_card.setMinimumHeight(600)
      self.placeholder_card.setMaximumHeight(16777215)
      self.placeholder_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
      self.state.push_log("SYS", "Modo enfoque: visualizador 3D")

  def _flush_logs(self):
    for line in self.state.pop_logs():
      self.terminal.appendPlainText(line)
    self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

  def _refresh_telemetry(self, telemetry):
    if telemetry is None:
      return

    self.telemetry_labels["ALT"].setText(f"{telemetry['altitude']:.2f} m")
    self.telemetry_labels["LAT"].setText(f"{telemetry['latitude']:.6f}")
    self.telemetry_labels["LON"].setText(f"{telemetry['longitude']:.6f}")
    self.telemetry_labels["SAT"].setText(str(telemetry["satellites"]))
    self.telemetry_labels["THR"].setText(f"{telemetry['threshold']:.0f} m")
    self.telemetry_labels["FIR"].setText("SI" if telemetry["fired"] else "NO")
    self.telemetry_labels["SDO"].setText("ON" if telemetry["sd_on"] else "OFF")
    self.telemetry_labels["SDK"].setText("OK" if telemetry["sd_ok"] else "NO OK")
    self.telemetry_labels["BME"].setText("OK" if telemetry["bme_ok"] else "NO OK")
    self.telemetry_labels["GPS"].setText("OK" if telemetry["gps_ok"] else "NO OK")
    self.telemetry_labels["TIM"].setText(f"{telemetry['uptime_ms'] / 1000:.0f} s")

    if telemetry["rssi"] is None or telemetry["snr"] is None:
      self.telemetry_labels["RF "].setText("-- / --")
    else:
      self.telemetry_labels["RF "].setText(f"{telemetry['rssi']:.0f} / {telemetry['snr']:.2f}")

    self.altitude_history.append(telemetry["altitude"])
    if telemetry["rssi"] is not None:
      self.rssi_history.append(telemetry["rssi"])
    if telemetry["snr"] is not None:
      self.snr_history.append(telemetry["snr"])

    self.altitude_chart.set_values(list(self.altitude_history))
    self.rssi_chart.set_values(list(self.rssi_history))
    self.snr_chart.set_values(list(self.snr_history))

    self._sync_rocket_viewer_with_telemetry(telemetry)
    self._refresh_mission_state(telemetry)

  def update_rocket_viewer_from_inputs(self):
    snapshot = self.state.get_snapshot()
    telemetry = snapshot["telemetry"]
    if telemetry is None:
      self.state.push_log("ERR", "No hay telemetria para actualizar visualizador 3D")
      return

    latitude = telemetry["latitude"]
    longitude = telemetry["longitude"]
    altitude = telemetry["altitude"]
    self.rocket_viewer.set_gps(latitude, longitude, altitude)
    self._update_rocket_local_labels()

  def reset_rocket_viewer(self):
    snapshot = self.state.get_snapshot()
    telemetry = snapshot["telemetry"]
    if telemetry is None:
      self.state.push_log("ERR", "No hay telemetria para reset del visualizador 3D")
      return

    latitude = telemetry["latitude"]
    longitude = telemetry["longitude"]
    altitude = telemetry["altitude"]

    self.rocket_viewer.reset_position(latitude, longitude, altitude)
    self.viewer_lock_button.setChecked(False)
    self.viewer_lock_button.setText("Lock camara")
    self._update_rocket_local_labels()

  def toggle_rocket_camera_lock(self):
    self.rocket_viewer.toggle_camera_lock()
    if getattr(self.rocket_viewer, "camera_locked", False):
      self.viewer_lock_button.setText("Unlock camara")
    else:
      self.viewer_lock_button.setText("Lock camara")

  def _sync_rocket_viewer_with_telemetry(self, telemetry):
    latitude = telemetry["latitude"]
    longitude = telemetry["longitude"]
    altitude = telemetry["altitude"]

    self.rocket_viewer.set_gps(latitude, longitude, altitude)
    self._update_rocket_local_labels()

  def cycle_rocket_camera(self):
    self.camera_mode = (self.camera_mode + 1) % 3
    if self.camera_mode == 0:
      self.rocket_viewer.set_camera_original()
      self.viewer_camera_mode_label.setText("Camara: Original")
    elif self.camera_mode == 1:
      self.rocket_viewer.set_camera_topdown()
      self.viewer_camera_mode_label.setText("Camara: Cohete hacia abajo")
    else:
      self.rocket_viewer.set_camera_side_lock()
      self.viewer_camera_mode_label.setText("Camara: Lateral +50m X")

    self.viewer_lock_button.setChecked(True)
    self.viewer_lock_button.setText("Unlock camara")

  def _update_rocket_local_labels(self):
    self.viewer_x_label.setText(f"X: {getattr(self.rocket_viewer, 'x', 0.0):.2f} m")
    self.viewer_y_label.setText(f"Y: {getattr(self.rocket_viewer, 'y', 0.0):.2f} m")
    self.viewer_z_label.setText(f"Z: {getattr(self.rocket_viewer, 'z', 0.0):.2f} m")

  def _refresh_mission_state(self, telemetry):
    if telemetry["fired"]:
      self.fire_state_badge.setText("FIRE ejecutado")
      self.fire_state_badge.setProperty("role", "statusDanger")
    else:
      self.fire_state_badge.setText("FIRE sin ejecutar")
      self.fire_state_badge.setProperty("role", "statusNeutral")
    self.fire_state_badge.style().unpolish(self.fire_state_badge)
    self.fire_state_badge.style().polish(self.fire_state_badge)

    if telemetry["sd_on"]:
      phase_text = "Fase SD_WRITE"
      phase_role = "statusWarn"
    else:
      phase_text = "Fase RF_PHASE"
      phase_role = "statusGood"
    self.mission_phase_badge.setText(phase_text)
    self.mission_phase_badge.setProperty("role", phase_role)
    self.mission_phase_badge.style().unpolish(self.mission_phase_badge)
    self.mission_phase_badge.style().polish(self.mission_phase_badge)

    self._set_module_badge(self.sd_badge, "SD", telemetry["sd_ok"])
    self._set_module_badge(self.bme_badge, "BME", telemetry["bme_ok"])
    self._set_module_badge(self.gps_badge, "GPS", telemetry["gps_ok"])
    lora_ok = telemetry["rssi"] is not None and telemetry["snr"] is not None
    self._set_module_badge(self.lora_badge, "LoRa", lora_ok)

  def _set_module_badge(self, label, name, is_ok):
    label.setText(f"{name} {'OK' if is_ok else 'NO OK'}")
    label.setProperty("role", "statusGood" if is_ok else "statusWarn")
    label.style().unpolish(label)
    label.style().polish(label)

  def toggle_fire_arm(self, state):
    self.fire_arm_enabled = state == Qt.Checked
    self.fire_send_button.setEnabled(self.fire_arm_enabled)
    if self.fire_arm_enabled:
      self.state.push_log("SAFE", "FIRE habilitado por operador")
    else:
      self.state.push_log("SAFE", "FIRE bloqueado")
      self.fire_press_count = 0
    self._update_fire_progress_badge()

  def _refresh_fire_progress_window(self):
    if self.fire_press_count == 0:
      return
    now_ms = int(time.time() * 1000)
    if (now_ms - self.first_fire_press_ms) > FIRE_CONFIRM_WINDOW_MS:
      self.fire_press_count = 0
      self._update_fire_progress_badge()

  def _update_fire_progress_badge(self):
    self.fire_progress_badge.setText(f"Confirmacion FIRE: {self.fire_press_count}/3")
    if not self.fire_arm_enabled:
      role = "statusWarn"
    elif self.fire_press_count == 0:
      role = "statusNeutral"
    elif self.fire_press_count < 3:
      role = "statusDanger"
    else:
      role = "statusDanger"
    self.fire_progress_badge.setProperty("role", role)
    self.fire_progress_badge.style().unpolish(self.fire_progress_badge)
    self.fire_progress_badge.style().polish(self.fire_progress_badge)

  def closeEvent(self, event):
    self.ui_timer.stop()
    super().closeEvent(event)


def main():
  if not TILES_DIR.exists():
    raise FileNotFoundError(f"No existe la carpeta de tiles: {TILES_DIR}")

  tile_index = build_tile_index()
  bounds = compute_bounds(tile_index)
  if bounds is None:
    raise RuntimeError("No se encontraron tiles validos para el mapa local")

  state = SharedState()
  serial_bridge = SerialBridge(state)

  httpd = ThreadedHTTPServer((HOST, 0), LocalRequestHandler)
  httpd.tile_index = tile_index
  httpd.state = state
  httpd.html_text = make_map_html(bounds, httpd.server_port)

  server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
  server_thread.start()

  app = QApplication([])
  window = FlightControlWindow(state, serial_bridge, f"http://{HOST}:{httpd.server_port}/")
  window.show()
  window.enter_borderless_fullscreen()
  exit_code = app.exec_()

  serial_bridge.disconnect()
  httpd.shutdown()
  httpd.server_close()
  raise SystemExit(exit_code)


if __name__ == "__main__":
  main()