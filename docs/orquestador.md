# Orquestador único (10-11)

## Problema
La aplicación y el ciclo del PC crecieron por separado: cada uno con su lista de partidos (índice de la aplicación /
`config/matches.yaml`), su cola (tabla `jobs` / `config/peticion_pc.txt`) y su forma de ejecutar. Resultado: un partido
repetido, fotos de una carpeta antigua, un clic guardado donde el análisis no lo leía, la cola de la aplicación queriendo
rehacer partidos que el ciclo ya había hecho, y dos procesos pesados a la vez.

## Diseño (contrastado con el estado del arte)
- **Grafo de etapas con cachés por huella** (como Dagster/Prefect): ya existe (`pipeline`, huellas por etapa).
- **Cola persistente en SQLite con un único ejecutor** (como Huey/RQ en una máquina): la base de datos de la
  aplicación (`datos/tennisbio.db`, WAL) es la única fuente de verdad de partidos, trabajos y eventos.
- **Plano de control**: enviar, pausar, reanudar, cancelar y estado, con las mismas órdenes desde la aplicación y desde
  el chat (por la cola del PC). Sin Celery/Prefect/Dagster: piden servidor o broker, encajan mal en un PC Windows
  sin conexión y no resuelven nada que no resuelva unificar lo que hay.

| Pieza | Qué es |
|---|---|
| Registro de partidos | `tennisbio.registry`: `config/matches.yaml` y las carpetas son *fuentes* que `sync` lleva al registro; `catalog.load_matches` lee el registro (todas las entradas: ciclo, CLI, auditoría, aplicación) |
| Ejecutor | `tennisbio worker`: uno por PC (bloqueo exclusivo); el único que ejecuta trabajos pesados |
| Trabajos | Flujos configurables (`config/flujos.yaml`): listas de pasos idempotentes (etapas, informe, auditoría, medida, exportar) |
| Órdenes | `tennisbio jobs submit/pause/resume/cancel/status`; la aplicación las llama por su API; el chat por la cola del PC |
| Monitorización | Tabla de eventos; `estado_trabajos.json` subido a pc-logs en cada cambio; pantalla «Cola» de la aplicación |

## Fases
| Fase | Qué | Estado |
|---|---|---|
| A | Registro único de partidos (`tennisbio registry sync/list`, `registry.source: db`) | hecho (10-11) |
| B | Ejecutor único con bloqueo y `tennisbio jobs` (`tennisbio worker`; `tennisbio/orchestrator.py`) | hecho (10-11) |
| C | Flujos en `config/flujos.yaml` (completo, informe, prevision, prueba); trabajo «flujo» que sigue en el paso donde se quedó | hecho en código (11-11); falta verlo en el PC (petición 187) |
| D | Ciclo del PC y chat por B: peticiones `trabajo` y `control`; en cada ciclo registro al día, ejecutor vivo y `estado_trabajos.json` a pc-logs cuando cambia su firma; código nuevo = el ejecutor se reinicia entre dos trabajos; una parada pausa la cola ya | hecho (11-11), falta verlo en el PC |
| E | La aplicación por B (su «Cola» lee los mismos trabajos y eventos) | pendiente |
| F | Prueba de extremo a extremo en el PC (enviar aquí, pausar en la app, reanudar aquí) | pendiente |

Nada se borra: lo antiguo queda desactivado por configuración (`registry.source: yaml` vuelve al catálogo solo).
