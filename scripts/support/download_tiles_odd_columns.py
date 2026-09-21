from tile_download_common import download_tiles


if __name__ == "__main__":
  download_tiles(32.0, 33.0, -116.0, -115.0, zoom_min=8, zoom_max=16, parity="odd")