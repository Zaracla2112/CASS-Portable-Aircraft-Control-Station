# Arquitectura del proyecto

## Alcance actual

Este proyecto nacio como una estacion de control portable para CASS, enfocada en una operacion concreta en Mexicali para Baja Rocket 2026. La aplicacion actual esta hecha a la medida del hardware, de la telemetria serial y del mapa offline disponible hoy.

Su objetivo inmediato es:

- visualizar posicion y telemetria en tiempo real;
- controlar comandos operativos por serial;
- trabajar con tiles offline locales;
- ofrecer un visualizador 3D basico del vehiculo;
- guardar salidas locales de log para la operacion.

## Estructura actual

La estructura se reorganizo para separar responsabilidades:

```text
cass_control/
  config.py              -> carga configuracion y rutas
  main.py                -> arranque de la aplicacion
  mapping.py             -> utilidades para tiles y limites del mapa
  parsing.py             -> parsing de tramas de telemetria
  state.py               -> estado compartido en memoria
  services/
    map_server.py        -> servidor HTTP local para tiles y posicion
    serial_bridge.py     -> conexion serial y envio de comandos
  ui/
    main_window.py       -> ventana principal y wiring de la interfaz
    styles.py            -> hoja de estilos Qt
    widgets.py           -> widgets reutilizables (graficas, visor 3D, pagina mapa)

config/
  app_config.json        -> configuracion editable del despliegue actual

resources/
  tiles/                 -> tiles offline reutilizables
  models/                -> modelos 3D y assets de geometria
  images/                -> imagenes auxiliares

outputs/
  logs/local/            -> logs .txt generados por la app
  logs/telemetry/        -> exportaciones y trazas CSV

scripts/
  support/               -> scripts de apoyo reutilizables
  legacy/                -> prototipos o pruebas historicas

docs/
  notes/                 -> notas operativas vigentes
  ARQUITECTURA.md        -> este documento

legacy/
  monolith/              -> respaldo del archivo original monolitico
```

## Decisiones de diseno

- Se mantuvo `control_vuelo_ui.py` como punto de entrada para no romper el uso actual.
- La configuracion editable se saco a `config/app_config.json` para que sitio, mision, puertos y rutas no queden hardcodeados en la UI.
- Los recursos y outputs ahora viven en carpetas distintas para separar insumos reutilizables de artefactos generados.
- El archivo monolitico original se conservo como referencia historica en `legacy/monolith/`.

## Futuro deseado

La direccion del proyecto deberia ser una estacion de control mantenible y estandarizable para varios tipos de aircraft, no solo este cohete ni este hardware puntual.

Siguientes pasos razonables:

1. Introducir perfiles de vehiculo y mision desde configuracion.
2. Separar la capa de protocolo serial para soportar multiples firmwares o buses.
3. Formalizar un modulo de mapas offline con pipeline de descarga, cache y validacion.
4. Definir un modelo de telemetria versionado para evitar parsing fragil.
5. Agregar pruebas para parsing, configuracion y servidor local.
6. Estandarizar nombres de comandos y capacidades entre tipos de aircraft.

## Notas de alcance

- El sistema sigue siendo especifico a Mexicali y al caso Baja Rocket 2026 en esta fase.
- La arquitectura ya esta preparada para empezar a generalizar sin reescribir todo otra vez.