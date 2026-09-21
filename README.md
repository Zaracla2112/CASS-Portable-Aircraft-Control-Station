# CASS Portable Aircraft Control Station

Estacion de control portable para CASS, desarrollada inicialmente para una operacion especifica en Mexicali con el contexto de Baja Rocket 2026. El proyecto hoy esta orientado al hardware, telemetria y mapas offline disponibles para esa mision, pero ya fue reorganizado para facilitar su evolucion hacia una plataforma mas mantenible y reutilizable para distintos tipos de aircraft.

## Alcance actual

El sistema esta pensado para:

- visualizar posicion y telemetria en tiempo real;
- controlar comandos operativos por serial;
- trabajar con tiles offline locales;
- ofrecer un visualizador 3D basico del vehiculo;
- guardar salidas locales de log durante la operacion.

## Estructura del proyecto

```text
cass_control/
  config.py
  main.py
  mapping.py
  parsing.py
  state.py
  services/
  ui/

config/
  app_config.json

resources/
  tiles/
  models/
  images/

outputs/
  logs/local/
  logs/telemetry/

scripts/
  support/
  legacy/

docs/
  notes/
  ARQUITECTURA.md

legacy/
  monolith/
```

## Componentes principales

- `control_vuelo_ui.py`: punto de entrada actual.
- `cass_control/main.py`: arranque de la aplicacion.
- `cass_control/services/serial_bridge.py`: comunicacion serial y envio de comandos.
- `cass_control/services/map_server.py`: servidor local para mapa y posicion.
- `cass_control/ui/main_window.py`: interfaz principal.
- `config/app_config.json`: configuracion editable del despliegue actual.

## Configuracion

La configuracion base vive en `config/app_config.json`.

Actualmente incluye:

- sitio de operacion en Mexicali;
- contexto de mision Baja Rocket 2026;
- puerto y baudrate serial por defecto;
- parametros de seguridad para FIRE;
- rutas para recursos reutilizables y outputs generados.

## Ejecucion

Instala las dependencias necesarias de Python para la interfaz y serial:

```bash
pip install PyQt5 PyQtWebEngine pyserial PyOpenGL requests
```

Luego ejecuta:

```bash
python control_vuelo_ui.py
```

## Scripts de apoyo

En `scripts/support/` se dejaron scripts auxiliares para futuros flujos de descarga y preparacion de mapas:

- `download_tiles_even_columns.py`
- `download_tiles_odd_columns.py`
- `tile_download_common.py`

Los prototipos y pruebas anteriores se conservaron en `scripts/legacy/` y `legacy/monolith/` como referencia historica.

## Estado actual y futuro

Este proyecto sigue siendo especifico al caso de Mexicali y a Baja Rocket 2026 en esta etapa. La meta a futuro es evolucionarlo a una estacion de control mantenible y estandarizable para multiples tipos de aircraft.

Pasos razonables para esa evolucion:

1. Introducir perfiles de vehiculo y mision desde configuracion.
2. Separar la capa de protocolo serial para multiples firmwares o buses.
3. Formalizar un flujo de mapas offline con descarga, cache y validacion.
4. Versionar el modelo de telemetria.
5. Agregar pruebas para parsing, configuracion y servidor local.

## Referencia adicional

Para mas detalle de arquitectura y decisiones, revisa `docs/ARQUITECTURA.md`.