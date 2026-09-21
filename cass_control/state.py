import threading
import time


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