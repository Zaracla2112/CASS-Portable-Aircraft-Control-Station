import math
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "resources" / "tiles"
DEFAULT_HEADERS = {"User-Agent": "CASSControl/1.0 (map-support-script)"}


def deg2tile(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  x_value = int((lon_deg + 180.0) / 360.0 * n)
  y_value = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
  return x_value, y_value


def download_tiles(lat_min, lat_max, lon_min, lon_max, zoom_min, zoom_max, out_dir=None, parity=None):
  output_dir = Path(out_dir) if out_dir else DEFAULT_OUTPUT_DIR

  for zoom in range(zoom_min, zoom_max + 1):
    x_min, y_max = deg2tile(lat_min, lon_min, zoom)
    x_max, y_min = deg2tile(lat_max, lon_max, zoom)

    for x_value in range(min(x_min, x_max), max(x_min, x_max) + 1):
      if parity == "even" and x_value % 2 != 0:
        continue
      if parity == "odd" and x_value % 2 == 0:
        continue

      for y_value in range(min(y_min, y_max), max(y_min, y_max) + 1):
        tile_dir = output_dir / str(zoom) / str(x_value)
        tile_dir.mkdir(parents=True, exist_ok=True)
        tile_path = tile_dir / f"{y_value}.png"

        if tile_path.exists():
          continue

        url = f"https://tile.openstreetmap.org/{zoom}/{x_value}/{y_value}.png"
        label = parity.upper() if parity else "ALL"

        for attempt in range(5):
          try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if response.status_code == 200:
              tile_path.write_bytes(response.content)
              print(f"[{label}] Descargado z{zoom}/{x_value}/{y_value}")
            else:
              print(f"[{label}] Fallo z{zoom}/{x_value}/{y_value}: {response.status_code}")
            break
          except requests.exceptions.RequestException as error:
            wait_seconds = 2 ** attempt
            print(
              f"[{label}] Error de red z{zoom}/{x_value}/{y_value}: {error}. "
              f"Reintentando en {wait_seconds}s ({attempt + 1}/5)"
            )
            time.sleep(wait_seconds)
        else:
          print(f"[{label}] z{zoom}/{x_value}/{y_value} fallo despues de 5 intentos, se salta")

        time.sleep(0.01)