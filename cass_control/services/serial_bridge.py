import threading

from cass_control.parsing import parse_telemetry_line

try:
  import serial
  from serial.tools import list_ports
except ImportError:
  serial = None
  list_ports = None


def list_serial_ports(default_port):
  if list_ports is None:
    return [default_port]

  ports = [port.device for port in list_ports.comports()]
  return ports or [default_port]


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