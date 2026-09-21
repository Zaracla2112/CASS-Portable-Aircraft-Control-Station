import math
import os
import time

import requests


def deg2tile(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def download_tiles(lat_min, lat_max, lon_min, lon_max, zoom_min, zoom_max, out_dir="tiles"):
    headers = {"User-Agent": "MiAppLocal/1.0 (contacto@ejemplo.com)"}

    for zoom in range(zoom_min, zoom_max + 1):
        x_min, y_max = deg2tile(lat_min, lon_min, zoom)
        x_max, y_min = deg2tile(lat_max, lon_max, zoom)

        for x in range(min(x_min, x_max), max(x_min, x_max) + 1):
            if x % 2 == 0:
                continue

            for y in range(min(y_min, y_max), max(y_min, y_max) + 1):
                tile_dir = os.path.join(out_dir, str(zoom), str(x))
                os.makedirs(tile_dir, exist_ok=True)
                tile_path = os.path.join(tile_dir, f"{y}.png")

                if os.path.exists(tile_path):
                    continue

                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"

                for intento in range(5):
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            with open(tile_path, "wb") as file_handle:
                                file_handle.write(response.content)
                            print(f"[IMPAR] Descargado z{zoom}/{x}/{y}")
                        else:
                            print(f"[IMPAR] Fallo z{zoom}/{x}/{y}: {response.status_code}")
                        break
                    except requests.exceptions.RequestException as error:
                        espera = 2 ** intento
                        print(
                            f"[IMPAR] Error de red z{zoom}/{x}/{y}: {error}. "
                            f"Reintentando en {espera}s ({intento + 1}/5)"
                        )
                        time.sleep(espera)
                else:
                    print(f"[IMPAR] z{zoom}/{x}/{y} fallo despues de 5 intentos, se salta")

                time.sleep(0.01)


if __name__ == "__main__":
    download_tiles(32.0, 33.0, -116.0, -115.0, zoom_min=8, zoom_max=16)
