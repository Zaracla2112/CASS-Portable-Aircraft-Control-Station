import math

def deg2tile(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1/math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

import os
import requests
import time

def download_tiles(lat_min, lat_max, lon_min, lon_max, zoom_min, zoom_max, out_dir="tiles"):
    headers = {"User-Agent": "MiAppLocal/1.0 (contacto@ejemplo.com)"}

    for zoom in range(zoom_min, zoom_max + 1):
        x_min, y_max = deg2tile(lat_min, lon_min, zoom)
        x_max, y_min = deg2tile(lat_max, lon_max, zoom)

        for x in range(min(x_min, x_max), max(x_min, x_max) + 1):
            for y in range(min(y_min, y_max), max(y_min, y_max) + 1):
                tile_dir = os.path.join(out_dir, str(zoom), str(x))
                os.makedirs(tile_dir, exist_ok=True)
                tile_path = os.path.join(tile_dir, f"{y}.png")

                if os.path.exists(tile_path):
                    continue

                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"

                for intento in range(5):
                    try:
                        r = requests.get(url, headers=headers, timeout=10)
                        if r.status_code == 200:
                            with open(tile_path, "wb") as f:
                                f.write(r.content)
                            print(f"Descargado z{zoom}/{x}/{y}")
                        else:
                            print(f"Fallo z{zoom}/{x}/{y}: {r.status_code}")
                        break  # salió bien (o con error HTTP, no de red), no reintentar
                    except requests.exceptions.RequestException as e:
                        espera = 2 ** intento  # 1, 2, 4, 8, 16 segundos
                        print(f"Error de red en z{zoom}/{x}/{y}: {e}. Reintentando en {espera}s ({intento+1}/5)")
                        time.sleep(espera)
                else:
                    print(f"z{zoom}/{x}/{y} falló después de 5 intentos, se salta")

                time.sleep(0.01)

download_tiles(32.0, 33.0, -116.0, -115.0, zoom_min=8, zoom_max=16)