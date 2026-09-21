from PyQt5.QtWidgets import QApplication

from cass_control.config import ensure_runtime_directories, load_app_config
from cass_control.mapping import build_tile_index, compute_bounds
from cass_control.services.map_server import start_map_server
from cass_control.services.serial_bridge import SerialBridge
from cass_control.state import SharedState
from cass_control.ui.main_window import FlightControlWindow


def main():
  config = load_app_config()
  ensure_runtime_directories(config)

  if not config.paths.tiles_dir.exists():
    raise FileNotFoundError(f"No existe la carpeta de tiles: {config.paths.tiles_dir}")

  tile_index = build_tile_index(config.paths.tiles_dir)
  bounds = compute_bounds(tile_index)
  if bounds is None:
    raise RuntimeError("No se encontraron tiles validos para el mapa local")

  state = SharedState()
  serial_bridge = SerialBridge(state)
  httpd = start_map_server(state, config.paths.tiles_dir, bounds, config.host)

  app = QApplication([])
  window = FlightControlWindow(config, state, serial_bridge, f"http://{config.host}:{httpd.server_port}/")
  window.show()
  window.enter_borderless_fullscreen()
  exit_code = app.exec_()

  serial_bridge.disconnect()
  httpd.shutdown()
  httpd.server_close()
  raise SystemExit(exit_code)