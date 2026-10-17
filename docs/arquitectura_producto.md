# Arquitectura de producto: de prototipo a aplicación profesional

> Documento de diseño. Está pensado para guardarse en `docs/arquitectura_producto.md`. No cambia nada del plan vigente de `CLAUDE.md`: lo ordena y le da forma de producto. La parte de móvil y nube sigue al final.

---

## 0. Resumen

- **Situación actual.** El motor de análisis ya es bueno: etapas idempotentes, huellas por etapa, cachés por ventana, escritura atómica y paralelismo iGPU/CPU. Lo que falta es todo lo que lo rodea:
  - un catálogo que el usuario no tenga que editar;
  - una cola de trabajos;
  - un panel de estado;
  - una política de almacenamiento y copias;
  - CI y versiones publicadas.
- **Recomendación: opción A, «local primero».** Una aplicación local en el PC, con interfaz web en `127.0.0.1` dentro de una ventana de escritorio, base de datos SQLite, cola con dos carriles (iGPU y CPU) y panel. Más adelante (fase 8 del plan) se publican solo los informes estáticos en Cloudflare R2/Pages detrás de Cloudflare Access. Coste en la nube: **0 a 2 € al mes**. El PC no se expone a Internet.
- **Opción complementaria, no sustitutiva: GPU en la nube bajo demanda.** Solo para procesar lotes grandes de partidos. Coste estimado: **0,5 a 1,5 € por partido** y unos 45 a 75 min en lugar de 4,5 a 5 h. Antes hay que portar el motor a CUDA y validarlo con pruebas de referencia.
- **Arreglos baratos antes de tocar nada más:**
  1. La huella del vídeo usa tamaño + fecha. Mover o copiar un vídeo relanza las 4,5 h del partido. Hay que cambiarla por un hash del contenido.
  2. Solo `fine` lleva la huella del código. El resto de etapas dependen de que alguien suba la versión a mano.
  3. Las carpetas de prueba `_poc*` ocupan unos 20 GB que se pueden recuperar.
  4. No hay CI.

---

## 1. Punto de partida (datos medidos en el repo y en `pc-logs`)

### 1.1 Pipeline y tiempos reales

Datos de `pc-logs:prueba_poc9_largo.log` y del manifiesto de `_poc9_largo`. Se trata de un partido entero: 210 min, 1080p50 y pasada fina v16.

| Etapa (versión) | Depende de | Tiempo real | Ritmo (para la ETA) | Recurso |
|---|---|---|---|---|
| probe (2) | — | 24 s | — | CPU |
| scenes (3) | probe | 27,7 min | 7,9 s por min de vídeo | CPU + TransNetV2 |
| audio (2) | probe | 2,0 min | 0,6 s por min | CPU |
| court (4) | scenes | 9,6 min | 2,7 s por min | CPU |
| score (6) | scenes, court | 19,1 min (en paralelo con players) | 5,5 s por min | CPU (OCR) |
| players (4) | scenes, court | 33,4 min (19,1 en paralelo) | 48 s por min de pista (41,9 min de pista) | iGPU |
| identity (4) | players, score, court, audio | 45 s | — | CPU |
| candidates (7) | players, audio, identity, court, score | 20 s | — | CPU |
| **Pasada barata (total)** | | **≈ 74 min** | | |
| fine (16) | candidates, court, score | **193 min** | 20,6 s por candidato; 245 ms por fotograma | iGPU + CPU |
| fine_opponent (9) | ídem | 0 (apagada) | — | iGPU |
| Informe, auditoría y capturas | todas | ≈ 27 min | — | CPU |
| **Total** | | **4 h 55 min** | | |

Desglose de `fine` (193 min):

| Componente | Tiempo |
|---|---|
| Pose | 95 min (híbrido 51, YOLO 41) |
| Bola en la iGPU | 41 min, más 124 min de bola en la CPU en paralelo |
| Raqueta | 27 min |
| Cuerdas y 3D | 12 min |
| Jugadora lejana | 10 min |
| Recorte de ventanas | 3,6 min |

Volumen procesado: 562 candidatos de la jugadora, 226 ventanas, 47 386 fotogramas (≈ 16 min de vídeo) y **129 golpes confirmados**:

| Golpe | Lado cercano | Lado lejano |
|---|---|---|
| Derecha | 55 | 14 |
| Revés | 19 | 16 |
| Saque o remate | 25 | — |

**Recalcular las medidas desde las cachés** (petición 10) costó **25,6 min**.

### 1.2 Disco

Datos de `pc-logs:tamanos.txt` (17-10).

- `_poc9_largo` ocupa 7,8 GB. **Hipótesis por verificar:** unos 5 GB son la copia del tramo que hace `smoke_test.py` (`ffmpeg -c copy` de 600 min, que es el vídeo entero) y solo unos 2,5 a 3 GB son salidas reales. En producción (`run --all` sobre `C:\tenis\videos`) esa copia no existe.
- Las salidas reales se reparten así:
  - ventanas `windows/*.mp4` en x264 CRF 16 (≈ 16 min de vídeo a 1080p50);
  - cachés de pose, bola y raqueta (`*_<ph>.npz`, `*_ball.npy`);
  - `players.npz`;
  - `series/`, informe y exportación.
- Las carpetas de prueba `_poc`, `_poc3…_poc9_largo` y `_smoke` suman **≈ 20 GB**.
- Disco libre: 267 GB.

### 1.3 Huecos de producto

| Área | Hoy | Hueco |
|---|---|---|
| Catálogo | `config/matches.yaml` generado por `auto_catalog.py` con un solo `player` | Cambiar de jugadora, añadir la rival o corregir el torneo obliga a editar YAML. El rival se activa con `analyze_opponent` en la configuración. |
| Lanzamiento | `.bat` de doble clic y `git pull` de la rama de desarrollo cada 10 min | No hay versiones publicadas. El PC ejecuta código a medio hacer. |
| Estado | `progreso.json`, `registro.log` y rama `pc-logs` | No hay panel ni histórico de errores, y no se distingue un error transitorio de uno permanente. |
| Huella del vídeo | `tamaño-mtime` (`pipeline.video_fingerprint`) | Copiar o mover el vídeo cambia el mtime y relanza las 4,5 h. |
| Huella del código | Solo `fine` usa `code=FINE_CODE` | Las demás etapas dependen de subir la versión a mano. |
| Informe | Enlaza `../<partido>/windows/*.mp4` por ruta relativa | No es autocontenido, así que no se puede publicar tal cual. |
| CI | No hay `.github/`. Hay 42 ficheros de test (≈ 314 tests) y la revisión automática en el PC. | Nada se comprueba antes de llegar al PC. |
| Versión | `pyproject` 0.0.1 | Sin etiquetas, sin registro de cambios y sin esquema de datos versionado. |
| Licencias | YOLO11 (Ultralytics, **AGPL-3.0**) | Sin problema para uso personal. Habría que revisarlo si algún día se distribuye la app o se ofrece como servicio. |

---

## 2. Arquitectura propuesta (opción A, recomendada)

### 2.1 Componentes

```
┌──────────────────────────── PC Windows (Ryzen 7 8745HS, 780M, 20 GB) ───────────────────────────┐
│                                                                                                   │
│  Ventana «Tennisbio» (pywebview / Edge WebView2)  ──►  http://127.0.0.1:8765 (solo localhost)     │
│        │                                                                                          │
│  ┌─────▼───────────── tennisbio-app (proceso «servidor local») ──────────────┐                    │
│  │ API (FastAPI)   · Partidos · Jugadores · Análisis · Cola · Panel · Ajustes │                    │
│  │ Planificador    · decide qué falta (pipeline.status) y encola trabajos    │                    │
│  │ Ingesta         · fichero local / carpeta vigilada / URL (yt-dlp)          │                    │
│  │ Notificador     · toast de Windows · ntfy/Telegram (opcional)              │                    │
│  └─────┬───────────────────────┬─────────────────────────────────────────────┘                    │
│        │ SQLite (WAL)          │ eventos (progreso, logs JSONL)                                   │
│  ┌─────▼──────────┐   ┌────────▼─────────┐   ┌──────────────────┐                                 │
│  │ Trabajador GPU │   │ Trabajador CPU   │   │ Mantenimiento    │                                 │
│  │ (1 a la vez)   │   │ (1-2 a la vez)   │   │ retención, copias│                                 │
│  │ etapas pesadas │   │ informe, auditoría│  │ espacio, salud   │                                 │
│  │ pipeline.run() │   │ export, publicar │   │                  │                                 │
│  └─────┬──────────┘   └────────┬─────────┘   └────────┬─────────┘                                 │
│        └──────────── C:\tenis\datos\ (vídeos, partidos, informes, cachés) ─┘                      │
└───────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                │ solo salida (rclone/wrangler) — fase 8
                          ┌─────────────────────▼──────────────────────┐
                          │ Cloudflare R2 + Pages  ·  Cloudflare Access │  ← móvil / compartir
                          │ informes estáticos + clips 720p             │
                          └─────────────────────────────────────────────┘
               Copias: disco USB (semanal, restic) + B2/R2 cifrado (datos permanentes)
```

**Decisiones**

- **El PC no es servidor.** La interfaz escucha solo en `127.0.0.1` y no se abre ningún puerto. La nube recibe ficheros que el PC sube, nunca le pide nada al PC.
- **Las etapas no se reescriben.** El trabajador llama a `pipeline.run(ctx, stages)` igual que hoy `cli.py`. `Context.progress` y `Context.log` se conectan a la base de datos (además de `progreso.json`, que se mantiene).
- **Los ficheros siguen siendo la fuente de verdad** de los resultados: `manifest.json`, `strokes.json`, `series/` y las cachés. SQLite es el **índice, el catálogo y la cola**, y se puede reconstruir recorriendo las carpetas con `tennisbio db rebuild`. Así se evita una migración arriesgada y se conservan las cachés actuales, incluidas las de `_poc9_largo`.
- **Dos carriles** de trabajo:
  - GPU: una etapa pesada a la vez, porque la 780M es una sola;
  - CPU: informe, auditoría, exportación y publicación.
  
  Es el mismo criterio que `Stage.resource` y `pipeline.parallel`, llevado al nivel de la cola.
- **Sin YAML para el usuario.** `matches.yaml` y `local.yaml` pasan a ser **exportaciones** generadas desde la base de datos para que el CLI y los scripts de Claude sigan funcionando. `load_matches` lee la base de datos si existe y, si no, el YAML.

### 2.2 Flujos principales

**A. Añadir un partido**

1. Arrastrar un fichero, elegir uno de `C:\tenis\videos\entrada\` o pegar una URL.
2. **Ingesta.** `ffprobe` (duración, fps, entrelazado, pistas de audio) y hash del contenido (SHA-256, ≈ 20 a 30 s para 5 GB en NVMe). Si el hash ya existe en la base de datos, el partido está duplicado y se ofrece reutilizarlo.
3. **Propuesta automática del formulario.** Torneo y superficie salen del nombre (`catalog.surface_of`). Las jugadoras salen de los nombres del marcador por OCR, en una lectura rápida de unos 2 min sobre muestras. La fecha, del nombre o de los metadatos.
4. El usuario solo **confirma**. Lo único que puede tener que elegir es quién es «la jugadora» si el OCR no lo decide, y lo hace pulsando su nombre, no escribiéndolo.
5. Se encola un trabajo «análisis completo» con su ETA, por ejemplo «≈ 4 h 50 min · termina hoy a las 03:10».

**B. Añadir o activar un jugador**

- Ficha con nombre, mano, revés a una o dos manos y altura. La altura es obligatoria porque escala todas las medidas (`body_scale`). La rival sin ficha usa 1,80 m (±5 %) y el panel lo avisa.
- Interruptor «analizar a esta jugadora en sus partidos». Encola `fine[jugador]` en cada partido donde aparece (ver sección 3).

**C. Relanzar o actualizar** (sección 4). El planificador compara las huellas y muestra **antes de lanzar** qué se repite y cuánto tarda.

**D. Publicar el informe** (fase 8). Empaqueta el informe autocontenido, convierte los clips a 720p, lo sube a R2 y avisa con el enlace.

---

## 3. Más jugadores y más golpes: qué se reutiliza y qué se recalcula

### 3.1 Qué es de cada cosa

| Nivel | Etapas y ficheros | Por qué |
|---|---|---|
| **Del vídeo** (una vez por partido, no depende de quién se analice) | probe, scenes, audio, court, score, players | La pasada barata ya registra **todos los impactos de ambas jugadoras** (1 128 candidatos en el vídeo entero: 843 lejanos y 130 tramos de la rival). |
| **Del partido** (ambas personas) | identity, candidates | Identidad = quién es quién en cada tramo, para las dos. |
| **De la jugadora** | fine[jugadora] → `strokes.json`, `series/` | Pose, bola y raqueta en sus ventanas, y sus medidas. |
| **Del golpe** | informe, auditoría, exportación | `strokes.json` ya contiene **todos** los golpes de la jugadora (derecha, revés y saque), no solo derechas. |

### 3.2 Coste de cada ampliación (partido de 210 min)

| Ampliación | Qué se reutiliza | Qué se calcula | Tiempo |
|---|---|---|---|
| **Revés de Rybakina** (ya está en `strokes.json`: 35 golpes en `_poc9_largo`) | Todo | Informe del golpe (`report --stroke backhand`) y, si hay medidas propias nuevas, medidas desde la caché | **2 min** (25 min con medidas nuevas) |
| **Saque de Rybakina** (25 golpes de remate o saque cercanos ya detectados; recall de saque en F3Set 1/15) | Pasada barata entera | Mejorar el detector del saque: `candidates` v8 y fine **solo en ventanas nuevas** | 20 s + ~20 s por ventana nueva (estimado: 30 a 60 min) |
| **La rival del mismo partido** (Sabalenka) | Pasada barata entera (≈ 74 min ahorrados) | identity y candidates (≈ 1 min) más `fine_opponent` | Hoy ≈ **3 h** (≈ 566 candidatos, ventanas propias). Con ventanas compartidas (3.3): **≈ 1 a 1,5 h** (estimación por medir) |
| **Otro partido de la misma jugadora** | Nada del vídeo | Todo | 4,5 a 5 h |
| **Jugador nuevo en partidos ya procesados** | Pasada barata | fine[jugador] | Igual que la rival |

### 3.3 Cambios de diseño para que la reutilización sea real

1. **Identidad neutra respecto al objetivo.** Hoy `identity` lleva `match_fields={"player": name}`. Si se cambia de jugadora, se rehacen identity y candidates (barato) y cambia la huella de `fine`. La identidad debe resolver **persona A y persona B** con sus nombres del marcador. La pregunta «¿quién es la jugadora objetivo?» se traslada a `fine[jugador]`.
2. **`fine` como etapa por jugadora.** Hay que generalizar `fine` y `fine_opponent` en `fine@<player_id>`, una entrada del manifiesto por jugadora, con salida `strokes_<id>.json`. `strokes.json` se mantiene como alias de la principal por compatibilidad. Así desaparece `analyze_opponent` de la configuración, que el usuario no podía cambiar sin YAML.
3. **Ventanas de punto compartidas.** Hoy cada jugadora agrupa sus candidatos en ventanas propias (`wid = w<t0>_<dur>`), así que la bola de un mismo peloteo se calcula dos veces. La propuesta tiene dos partes:
   - **Ventanas por punto**, con identificadores estables que salen de los límites del punto (marcador, audio y planos) y no de cómo se agrupen los candidatos.
   - **Caché de bola por ventana compartida** entre jugadoras: la bola es ≈ 41 min de iGPU más la CPU en paralelo por partido.
   
   La pose del lado cercano y la del lejano ya son procesos distintos (híbrido o recorte), así que no se pierde nada. Ventaja añadida: un candidato nuevo (por ejemplo, un saque) cae en una ventana que ya existe y **no invalida** las cachés de las demás.
4. **Separar `fine` en extracción y medida.** Hoy `recompute_measures.py` lo consigue con `upstream=False` y la huella de código de `fine`. Se formalizan dos etapas:
   - `fine_extract@j`: pose, bola, raqueta y 3D por ventana. Cara. Su huella depende de modelos y ajustes.
   - `fine_measure@j`: análisis del golpe, fases y medidas. 25 min. Su huella depende de `FINE_CODE` y de la ficha de la jugadora.
   
   Con esto el planificador sabe de antemano si un cambio cuesta 25 min o 3 h.

---

## 4. Relanzar los mismos partidos: idempotencia, versiones y costes

### 4.1 Lo que ya funciona (y se conserva)

- Huella por etapa: versión, ajustes de la configuración, huellas de las dependencias, ficha de la jugadora y código (en `fine`).
- `manifest.json` se guarda tras cada etapa y las escrituras son atómicas (`write_atomic`, `savez_atomic`). Una caché dañada se borra y se recalcula (`load_npz`).
- Cachés por ventana con clave de modelos (`window_cache_key`). Una interrupción a mitad de `fine` reanuda ventana a ventana.
- `MissingVideo`: si el vídeo ya no está, se conservan los resultados. `DiskFull` actúa por debajo de 3 GB libres.

### 4.2 Arreglos necesarios

| Problema | Riesgo | Propuesta |
|---|---|---|
| Huella del vídeo = `tamaño-mtime` | Copiar a otro disco, restaurar una copia o mover la carpeta relanza **todo** (4,5 h por partido; 18 h los 4) | Hash del contenido calculado una vez en la ingesta y guardado en la base de datos. Migración: los manifiestos actuales se reescriben con el hash si la huella antigua coincide, sin recalcular nada. |
| Solo `fine` tiene huella de código | Un cambio en `scenes.py` o `court.py` sin subir la versión no se rehace, y el resultado depende del historial | Opción preferida: `code=` en todas las etapas, con el módulo propio y los que importa. La huella hash de AST normalizado ignora comentarios y docstrings para no relanzar 4 h por un comentario. Alternativa: un test de CI que exija subir la versión si cambia el módulo. |
| Versión de etapa sin esquema de datos | Un informe nuevo lee un `strokes.json` antiguo y falla o muestra «—» | Campo `"schema": N` en cada JSON de salida, con lectores tolerantes y migradores (`tennisbio migrate`) para los cambios de forma que no exigen recalcular. |
| Sin registro de entorno | No se puede reproducir un resultado | El manifiesto guarda el SHA de git o la versión publicada, onnxruntime-directml, el controlador de la GPU, ffmpeg y el hash de cada modelo (`model_state` ya da parte). |

### 4.3 Qué cuesta cada cambio (un partido de 210 min; ×4 para los 4 partidos)

| Cambio | Etapas que se repiten | Tiempo por partido | Los 4 partidos |
|---|---|---|---|
| Texto o diseño del informe | informe y auditoría | 2 min (27 con capturas y `learn_check`) | 10 min a 1 h (el informe junta los 4) |
| Fórmula de una medida (`FINE_CODE`) | `fine_measure` desde las cachés | ≈ 25 min | ≈ 1 h 40 min |
| Altura o mano de la jugadora | `fine_measure` | ≈ 25 min | ≈ 1 h 40 min |
| Modelo de raqueta o 3D | raqueta, cuerdas, 3D y medidas | ≈ 40 a 60 min (estimado: raqueta 27 + 3D 12 + medidas) | 3 a 4 h |
| Modelo de pose o de bola, FP16, híbrido | `fine` completo (cambia la clave `ph`) | ≈ 193 min | ≈ 13 h (2 noches) |
| Detector de candidatos o identidad | identity y candidates (1 min); con ventanas estables, solo las ventanas nuevas | 1 min a 1 h | hasta 4 h |
| `court` (versión) | court, players, score, identity, candidates, fine | ≈ 4 h | ≈ 16 h |
| `scenes` (versión) | todo salvo probe y audio | ≈ 4,5 h | ≈ 18 h |
| Copiar o mover el vídeo (**hoy**) | todo | 4,5 a 5 h | ≈ 19 h ← arreglo 4.2 |

**Reglas para el producto**

- Antes de encolar, el panel muestra el **plan de recálculo** con su coste estimado (ritmos de 1.1 por minutos de vídeo y por candidatos). Por encima de 1 h por partido, pide una confirmación de un clic con el texto «Esta versión mejora X; recalcular 4 partidos ≈ 13 h (2 noches)». La programación es automática: de noche, dentro de la ventana horaria configurada.
- **Nunca se borra un resultado antes de tener el nuevo.** Cada etapa escribe en temporales y reemplaza al final, como ahora. Para cambios de modelo, la versión anterior del partido se guarda en `versiones/<fecha>/` (solo `strokes.json` y `series/`, ≈ 50 MB) hasta que la revisión automática diga OK. Esto cumple la regla «nunca borrar trabajo hecho».
- **Canal estable y canal de desarrollo.** El PC del usuario sigue el canal estable (etiquetas `vX.Y.Z`). El ciclo de 10 min sobre la rama de desarrollo se queda como modo «desarrollo», activable en Ajustes, para las peticiones de prueba de Claude.

---

## 5. Cómo se lanza: instalación, interfaz y cola

### 5.1 Instalación

| Pieza | Hoy | Propuesta |
|---|---|---|
| Instalador | `1_instalar.bat`, `bootstrap.ps1`, `uv sync` y `setup_models.py` | **Instalador único** `Tennisbio-Setup-x.y.z.exe` (Inno Setup, ≈ 30 MB) que trae `uv`, Python 3.11 portátil y ffmpeg. En la primera ejecución descarga dependencias y modelos (≈ 470 MB, verificados por hash). Crea un acceso directo y la tarea de inicio. |
| Rutas | `config/local.yaml` copiado a mano | El asistente de la primera ejecución detecta el disco con más espacio, propone `C:\tenis\` y lo guarda en la base de datos (exporta `local.yaml`). |
| Banco de pruebas | `benchmark.py` y `model_trials.py` por petición | Se ejecutan en la primera ejecución (≈ 5 min): eligen `device` (dml, cpu u openvino) y `hwaccel`, y guardan los ritmos de la ETA. |
| Actualización | `git pull` de la rama de desarrollo | «Hay una versión nueva (1.3.0): mejora X; recalcular cuesta Y». Se aplica con un clic, o sola de noche si está activado. Reversible: se conserva la versión anterior instalada. |

### 5.2 Interfaz (local, sin YAML)

Las pantallas son HTML servido por FastAPI con htmx, sin compilar JavaScript, dentro de una ventana pywebview.

1. **Inicio.** Lo que está pasando ahora, cuándo termina y lo último que terminó, con el enlace al informe.
2. **Partidos.** Lista con estado (cuadrícula partido × etapa), semáforo de calidad y espacio ocupado. Botón «Añadir partido».
3. **Jugadoras.** Fichas, en qué partidos aparecen y qué golpes hay analizados (con número de golpes). Botón «Analizar también a esta jugadora».
4. **Cola.** Trabajos pendientes, en curso y terminados, con prioridad, pausa y reanudación, y la franja horaria (por ejemplo, solo de 23:00 a 08:00 o cuando el PC está inactivo).
5. **Informes.** Por jugadora y golpe: abrir, exportar MP4/PDF y, en la fase 8, publicar o compartir.
6. **Almacenamiento.** Espacio por partido y categoría, y qué se puede liberar ahora sin perder nada.
7. **Ajustes.** Pocos: carpetas, franja horaria, notificaciones, copias, canal de actualización. Nada de parámetros de modelos.

### 5.3 Cola de trabajos

Tabla `jobs` en SQLite. No necesita Redis ni Celery: hay un solo usuario y una sola máquina.

- **Tipos:** `ingest`, `analyze(match, stages?)`, `analyze_player(match, player)`, `measures(match)`, `report(player, stroke)`, `audit`, `export`, `publish`, `retention`, `backup`.
- **Carriles:**
  - `gpu`: concurrencia 1. Etapas con `resource=gpu` y las mixtas `fine*`.
  - `cpu`: concurrencia 1 a 2. Informe, auditoría, exportación y publicación. Siempre que no compita con `score` en paralelo dentro de un `analyze`.
- **Planificación:** prioridad (el informe pedido por el usuario va antes que un recálculo de fondo), franja horaria, PC conectado a la corriente y no en uso intensivo (CPU por encima del 50 % durante 5 min).
- **Reintentos** (ver 7.3). Estados: `pendiente → en curso → hecho | error_transitorio(reintento n) | error | cancelado`.
- **Reanudación:** al arrancar, un trabajo `en curso` huérfano vuelve a `pendiente`. `pipeline.run` continúa donde se quedó gracias al manifiesto y las cachés de ventana.
- **Bloqueo:** un fichero `C:\tenis\datos\.lock` por proceso trabajador. Sustituye a la comprobación de «ocupado» de `ciclo_automatico.ps1`.

---

## 6. Almacenamiento

### 6.1 Estructura en disco

```
C:\tenis\datos\
  tennisbio.db                    catálogo, cola, índice, histórico de ejecuciones (≈ 10-50 MB)
  videos\<hash12>.<ext>           vídeo original (nombre estable por contenido; el nombre humano en la BD)
  partidos\<match_id>\
    manifest.json, probe/scenes/audio_onsets/court/score/identity/candidates.json   (≈ 5-30 MB)
    players.npz                                                   (decenas a cientos de MB, a medir)
    fine@<jugadora>\strokes.json, series\*.json                   (≈ 5-60 MB por jugadora)
    ventanas\<wid>.mp4            recortes CRF 16 1080p (lo más grande de las salidas)
    ventanas\<wid>_<ph>.npz/_ball.npy/raqueta   cachés por ventana
    versiones\<fecha>\            resultados anteriores mientras se valida una versión nueva
    calidad.json                  ficha de calidad (sección 7.4)
  informes\<jugadora>_<golpe>\    informe local (enlaza a partidos\…\ventanas)
  publicar\<jugadora>_<golpe>\    paquete autocontenido 720p (fase 8)
  registros\                      JSONL por trabajo (rotación 90 días)
```

### 6.2 Clases de retención

| Clase | Contenido | Tamaño por partido | Política |
|---|---|---|---|
| **P · Permanente** (copia de seguridad obligatoria) | Base de datos, fichas, JSON de etapas, `strokes*.json`, `series/`, `calidad.json`, auditoría, informe HTML | **≈ 0,05 a 0,15 GB** | Para siempre. Copia local y en la nube. |
| **E · Evidencia** (vídeo de cada golpe) | Clips de golpes **confirmados** en 720p CRF 23 (≈ 129 golpes × 4 a 5 s ≈ 10 min a ≈ 3 Mbps) | **≈ 0,2 a 0,3 GB** | Para siempre. Es lo que ve el informe si el vídeo original desaparece. |
| **C · Caché cara** | Pose, bola y raqueta por ventana (`*.npz`, `*.npy`) y `players.npz` | ≈ 0,5 a 1,5 GB (a medir) | **Se conserva mientras haya análisis activo.** Sin vídeo, es lo único que permite recalcular medidas en 25 min en lugar de rehacerlo todo. Se borra solo con confirmación cuando el partido se archiva. |
| **R · Regenerable barato** | `ventanas/*.mp4` CRF 16, miniaturas, exportaciones MP4/PDF, informe | ≈ 1 a 2 GB | Se regenera desde el vídeo en minutos. Se borra cuando falta espacio, si el vídeo existe. |
| **T · Temporal** | `source.mkv` limpio (.ts con saltos), `.part`, `.tmp`, recortes de prueba | 0 a 5 GB | Se borra al terminar el trabajo. |
| **V · Vídeo original** | Retransmisión | **≈ 5 GB** | Ver 6.3. |

> Tamaño por partido: **≈ 8 a 10 GB** mientras se trabaja con él (vídeo + R + C + P + E), **≈ 1,5 a 2 GB** archivado sin vídeo y sin ventanas CRF 16 (C + P + E), y **≈ 0,3 a 0,5 GB** «solo resultados» (P + E).

### 6.3 Presupuesto de disco (267 GB libres hoy)

| Escenario | GB por partido | Partidos en ≈ 230 GB útiles (se dejan 30 GB de margen) |
|---|---|---|
| Todo, como ahora (vídeo + salidas de producción) | ≈ 8 a 10 | ≈ 25 |
| Vídeo archivado fuera (disco USB) y cachés conservadas | ≈ 1,5 a 2 | ≈ 120 |
| Solo resultados y evidencia | ≈ 0,3 a 0,5 | > 450 |

Medidas inmediatas:

1. Borrar o archivar las carpetas `_poc*` y la copia de 600 min de `_poc9_largo`: se recuperan **≈ 20 GB**. Se conservan sus `manifest`, `strokes` y `series` como referencia de regresión, ≈ 100 MB.
2. **Guardián de espacio** en el trabajador:
   - avisar por debajo de 40 GB;
   - por debajo de 20 GB, liberar automáticamente las clases T y después R (solo si el vídeo existe);
   - no empezar un `analyze` si quedan menos de (vídeo × 1,1 + 6 GB) libres. Hoy el umbral es 3 GB.
3. Desglose de tamaño por categoría en el panel, en lugar de `tamanos.txt` por carpeta.

### 6.4 PC frente a nube para guardar

| Opción | Coste aproximado (precios públicos de oct-2026, por verificar) | Para qué |
|---|---|---|
| Disco del PC (NVMe) | 0 € | Trabajo activo: vídeos en curso y cachés |
| **Disco USB de 2 TB** | ≈ 70 a 90 € una vez | Archivo de vídeos originales (≈ 400 partidos) y copia semanal completa |
| Backblaze B2 | ≈ 6 $ por TB y mes | Copia cifrada (restic) de P + E (+ C opcional): 20 partidos ≈ 10 a 40 GB ≈ **0,06 a 0,25 $ al mes** |
| Cloudflare R2 | ≈ 0,015 $ por GB y mes, **sin coste de salida**, 10 GB gratis | Informes publicados (fase 8). La copia de seguridad también cabe aquí. |
| Vídeos originales en la nube | 100 GB ≈ 0,6 $ al mes (B2) | Solo si el usuario lo quiere, cifrados y privados (ver 6.6 y 6.7) |

### 6.5 Copias de seguridad (3-2-1 para lo permanente)

- **Diaria:** `tennisbio.db` con `sqlite3 .backup` (copia en caliente consistente) y los JSON de P. Instantánea local en `C:\tenis\copias\`, 14 días.
- **Semanal:** `restic` al disco USB cuando está conectado (P + E + C + vídeos) y a B2 o R2 (P + E). Ambas cifradas, con contraseña guardada en el Administrador de credenciales de Windows.
- **Restauración probada:** una vez al mes un trabajo `backup_verify` restaura en una carpeta temporal y comprueba hashes. Sin esto, la copia no cuenta.
- Lo que **no** necesita copia porque se regenera: clases R y T. Las cachés C son opcionales, pero ahorran 3 h de iGPU por partido.

### 6.6 Entrada de vídeos

- **Fichero local:** arrastrar a la ventana o dejar en `C:\tenis\videos\entrada\`, una carpeta vigilada que sustituye a `auto_catalog.py`. Se **mueve** (no se copia) a `videos\<hash12>.<ext>` para no ocupar dos veces 5 GB.
- **URL (yt-dlp, ya en el extra `validation`):** solo para fuentes que el usuario tenga derecho a descargar. Se descarga a 1080p, se registra la URL en la base de datos (así se sabe si el vídeo es «re-descargable», lo que decide la retención) y no se recodifica.
- **Formatos:** .ts, .m2ts y entrelazado ya están cubiertos (`st_probe` limpia el .ts y `yadif`). En la ingesta se valida que haya vídeo y audio y que la duración sea mayor de 20 min (si no, se pregunta «¿es un resumen?»).
- **Recortes:** opcionales. La previa ya se esquiva sola (búsqueda del tramo de juego, `scenes` v3 por líneas). La interfaz permite marcar inicio y fin con una miniatura cada 5 min. Se guardan como **metadatos** (`trim_start` y `trim_end` en la huella de probe), no como un vídeo nuevo, para no duplicar 5 GB.
- **Duplicados:** mismo hash, mismo partido. Mismo partido con otra retransmisión (otro idioma) se detecta por torneo, fecha y jugadoras, y se ofrece elegir una.

### 6.7 Privacidad y derechos (uso personal)

> No es asesoría legal. Las retransmisiones tienen derechos de los organizadores y las cadenas. El criterio de diseño es **uso personal y privado** y **mínima redistribución**.

- Los vídeos originales nunca salen del PC, salvo copia cifrada opcional en un almacenamiento privado del propio usuario.
- Lo publicado (fase 8) es el informe con **clips cortos** de golpes (4 a 5 s) a 720p, **detrás de autenticación** (Cloudflare Access, lista de correos), sin indexar (`noindex` y sin enlaces públicos) y con enlaces firmados que caducan para compartir golpes sueltos.
- Nada a git: sigue la regla actual de `.gitignore`. Los registros que suben a `pc-logs` ya incluyen fotogramas (`diag/`, `capturas_prueba/`). En el modo producto, la subida de imágenes de diagnóstico debe estar **apagada por defecto** y ser privada.
- Vídeos de YouTube de entrenamiento (requisito 6): la misma política. Se guardan solo los recortes analizados y la URL.
- Licencia de YOLO11 (AGPL-3.0): sin problema en uso personal. Si se distribuyera la app o se ofreciera como servicio a terceros, habría que cambiar de modelo (RTMDet/RTMPose son Apache-2.0) o aceptar las condiciones AGPL.

---

## 7. Progreso y monitorización

### 7.1 Modelo de estado

- **Por partido y etapa:** `missing | stale | queued | running | ok | error`. Sale de `pipeline.status()` más la cola.
- **Por trabajo:** porcentaje, hecho/total (ya se calculan en `Context.progress`), ETA, reintentos y último error.
- **Histórico** en `stage_runs`: cada ejecución con versión, huella, segundos, solape (`overlap_s`), resumen de la etapa (`summary`, que ya existe) y entorno.

### 7.2 ETA profesional

Hoy se extrapola linealmente dentro de cada etapa. Se propone **ETA del trabajo completo** con ritmos medidos en este PC, que se actualizan solos con una media móvil de las últimas 5 ejecuciones:

| Etapa | Unidad | Ritmo medido (vídeo entero) |
|---|---|---|
| scenes | min de vídeo | 7,9 s |
| audio | min de vídeo | 0,6 s |
| court | min de vídeo | 2,7 s |
| score | min de vídeo | 5,5 s (en paralelo con players) |
| players | min de pista (≈ 20 % del vídeo) | 48 s |
| fine | candidato de la jugadora | 20,6 s (≈ 245 ms por fotograma de ventana) |
| fine_measure | golpe confirmado | ≈ 12 s (1 538 s / 129) |

Antes de la pasada barata, los minutos de pista y los candidatos se estiman con las proporciones del vídeo entero: pista ≈ 20 % de la duración y ≈ 2,7 candidatos por minuto. Después de `candidates` ya son exactos. Error esperado: ±20 % al principio y ±5 % en `fine`.

### 7.3 Errores, reintentos y alertas

| Tipo | Ejemplos (vistos en el proyecto) | Reacción |
|---|---|---|
| Transitorio de GPU | `0xC0000005` de DirectML, sesión que se cuelga (`fine_speed` ya mata el proceso de raqueta a los 2 min) | Reintento automático ×2 con espera de 1 y 5 min. El tercero en CPU para esa etapa (más lento, mismo resultado validado). |
| Entrada | Vídeo dañado, sin audio, sin pista visible, sin nombre en el marcador | Sin reintento. El partido queda «con aviso» y el texto dice qué falta (los mensajes en español ya existen). |
| Recurso | `DiskFull`, falta de memoria (20 GB) | El guardián de espacio libera las clases T y R y reintenta una vez. Si no basta, alerta. |
| Código | Excepción de Python | Error. Se guardan la traza y un fichero de diagnóstico. Los demás partidos siguen, como ya hace `cli.py`. |
| Entorno | PC apagado o suspendido a mitad | Al volver, reanudación automática (5.3). La tarea de Windows con «reactivar para ejecutar» solo dentro de la franja. |

**Alertas:**
- toast de Windows (`winotify`) al terminar, al fallar o con poco disco;
- opcional, notificación al móvil con **ntfy.sh** (gratuito y sin cuenta, tema aleatorio) o un bot de Telegram;
- opcional, **healthchecks.io** (gratuito hasta 20 comprobaciones): el trabajador da una señal cada 15 min y, si deja de llegar con trabajos pendientes, llega un correo («el PC lleva 1 h sin procesar»). Sustituye a `ciclo_vivo.txt`.

### 7.4 Calidad por partido (la auditoría como ficha)

Cada partido genera `calidad.json` con semáforo. Los umbrales son una propuesta sobre los valores vistos:

| Indicador | Origen | `_poc9_largo` | Verde | Ámbar | Rojo |
|---|---|---|---|---|---|
| Pista encontrada / cámara principal | court.summary.court_share | 0,76 | ≥ 0,7 | 0,5 a 0,7 | < 0,5 |
| Minutos de juego con pista / duración | court_min / duration | 41,9 / 210 = 20 % | ≥ 15 % | 8 a 15 % | < 8 % (¿previa o resumen?) |
| Confianza de la identidad | identity.confidence | **0,52** | ≥ 0,7 | 0,5 a 0,7 | < 0,5 |
| Lecturas del marcador | score.readings / min de pista | 534 / 42 | ≥ 8 | 3 a 8 | < 3 |
| Golpes confirmados / candidatos | fine | 129 / 562 = 23 % | ≥ 20 % | 10 a 20 % | < 10 % |
| Golpes por hora de juego (pista) | fine | ≈ 185 | — | — | < 60 |
| Valores fuera de límites físicos | auditoría | 1 (763 km/h, ya corregido) | 0 | 1 a 2 | > 2 |
| Medidas fiables / medidas | `reliability` | — | — | — | — |
| Veredicto de la auditoría | `auto_cycle review` | REGRESIÓN / OK | OK | AVISOS | FALLOS |

- El informe muestra solo partidos verdes o ámbar en los agregados. Un partido rojo se analiza, pero queda fuera de las comparativas y el panel dice por qué.
- La identidad a 0,52 en el único partido entero procesado está justo en el borde: conviene vigilarla en los 4 partidos.
- La **revisión automática** (`auto_cycle.py review`: OK, REGRESIÓN o ERROR frente a la ejecución anterior) pasa a mostrarse en el panel con cada nueva versión.

### 7.5 Qué pasa con `pc-logs`

- Para el usuario, lo sustituyen el panel y las alertas.
- Para Claude (desarrollo remoto) se mantiene un **canal de diagnóstico** opcional y desactivable: el mismo contenido (manifiestos, auditoría, `calidad.json`, registros sin imágenes), pero exportado por el trabajador. Hay dos formas:
  - igual que hoy, a la rama `pc-logs`, en modo desarrollo;
  - mejor: un paquete JSON por ejecución en un bucket R2 privado de solo escritura desde el PC.
  
  No se piden nunca registros al usuario (requisito vigente).

---

## 8. Móvil y nube (fase 8 del plan, al final)

### 8.1 Informes estáticos (recomendado)

1. **`tennisbio publish`** empaqueta el informe **autocontenido**:
   - copia los JSON y `series/*.js`;
   - sustituye las rutas `../<partido>/windows/*.mp4` por clips de **solo los golpes confirmados**, recodificados a 720p H.264 CRF 23 con `faststart` (≈ 3 Mbps, compatibles con el móvil);
   - miniaturas WebP;
   - rutas con hash de contenido para caché inmutable.
2. Subida incremental (solo lo que cambió) a **Cloudflare R2 + Pages** con `rclone` o `wrangler`. Solo salida desde el PC.
3. **Autenticación:** Cloudflare Access (Zero Trust, gratis hasta 50 usuarios) con código por correo o Google. Sin contraseñas que gestionar.
4. **Compartir:**
   - invitar un correo (Access);
   - o un enlace firmado y caducable a un golpe o montaje (Worker de ≈ 20 líneas).
5. **Móvil:** el informe ya es HTML. Hay que adaptar el diseño a pantalla estrecha y añadir un manifiesto PWA para instalarlo como app. Sin tienda de aplicaciones.

**Volumen y coste:**

| Concepto | Tamaño | Coste |
|---|---|---|
| Por partido | ≈ 129 golpes × 4,5 s × 3 Mbps ≈ 0,2 GB, más HTML y datos (≈ 10 MB) | — |
| 4 partidos | ≈ 1 GB | R2 gratis (10 GB incluidos) |
| 40 partidos | ≈ 8 a 10 GB | ≈ 0 a 0,2 € al mes |
| Dominio propio (opcional) | — | ≈ 10 € al año |

Esfuerzo: **≈ 1 a 1,5 semanas**, de las cuales el empaquetado autocontenido y la adaptación al móvil son lo principal.

### 8.2 Procesado en la nube con GPU (opcional, por partido)

- **Requisitos técnicos:**
  - portar los `device` a CUDA (`onnxruntime-gpu`; todo el motor ya es ONNX, el punto a favor);
  - decodificación por NVDEC;
  - imagen Docker con modelos;
  - **pruebas de equivalencia** CUDA frente a DirectML en los clips de referencia (como se hizo con FP16: mismos golpes, ≤ 0,25 px).
- **Tiempo estimado por partido** en una RTX 4090 o L4: pose y bola 10 a 15 veces más rápidas que en la 780M (pasada fina ≈ 15 a 25 min en lugar de 193). La pasada barata queda limitada por la decodificación de 210 min a 1080p50 (≈ 15 a 30 min). **Total ≈ 45 a 75 min.**
- **Coste:**

| Concepto | Coste aproximado (oct-2026, por verificar) |
|---|---|
| GPU RunPod o Vast (4090) | 0,35 a 0,70 $/h |
| GPU Modal o AWS (L4) | 0,8 a 1,1 $/h |
| Arranque de la imagen y modelos | ≈ 5 min por trabajo |
| Por partido | **≈ 0,5 a 1,5 €**, más la subida de 5 GB (≈ 15 min con 50 Mbps de subida) |
| Recalcular 4 partidos por un modelo nuevo | ≈ 4 a 6 € frente a 2 noches del PC |

- **Cuándo merece la pena:** al pasar de 4 a 20 o más partidos (20 × 5 h = 100 h de PC, unas 12 noches, frente a ≈ 20 a 30 €), o cuando un cambio de modelo obligue a recalcular todo el catálogo.
- **Contras:** subir retransmisiones completas a un tercero (derechos y privacidad: el contenedor debe borrar el vídeo al terminar), 2 a 3 semanas de trabajo y mantener dos dispositivos validados.

### 8.3 Opciones comparadas

| | **A. Local + informes estáticos** (recomendada) | **B. A + GPU en la nube bajo demanda** | **C. Plataforma en la nube completa** |
|---|---|---|---|
| Qué es | App local (SQLite, cola, panel). Nube = R2/Pages + Access, solo lectura. | Como A, y un botón «procesar en la nube» para lotes. El PC sigue siendo el centro. | API web, base de datos, almacenamiento de vídeos, trabajadores con GPU, autenticación. El PC solo sube vídeos. |
| Coste fijo | 0 a 2 € al mes (+ 70 a 90 € de disco USB una vez) | Igual que A | 20 a 80 € al mes (API y base de datos siempre encendidas, almacenamiento de vídeos ≈ 100 GB a 500 GB) |
| Coste por partido | 0 € (≈ 0,3 kWh × 5 h ≈ 0,1 €) | 0,5 a 1,5 € en la nube, o 0 € en el PC | 0,5 a 1,5 € |
| Tiempo por partido | 4,5 a 5 h (de noche) | 45 a 75 min en la nube | 45 a 75 min |
| Esfuerzo | 4 a 6 semanas (fases P0 a P4) | A + 2 a 3 semanas | 2 a 3 meses |
| Privacidad y derechos | Vídeos nunca salen del PC | Vídeos salen solo en lotes, a un contenedor efímero | Vídeos guardados en la nube |
| Riesgos | Disco y un solo PC (mitigados con copias) | Diferencias CUDA/DirectML (pruebas de referencia) | Complejidad, coste fijo y seguridad para un único usuario |
| Encaje con `CLAUDE.md` | Total («el PC no puede ser servidor», «móvil/nube al final») | Bueno, como ampliación | Contradice el orden y el tamaño del proyecto |

**Recomendación:** A ahora. B solo si el catálogo pasa de unos 10 partidos o si los recálculos por modelo se vuelven frecuentes. Su base (portar a CUDA y las pruebas de referencia) se puede preparar sin compromiso dentro de P5. C no tiene sentido para un usuario.

---

## 9. Calidad de software

### 9.1 Tests y CI (GitHub Actions)

| Nivel | Qué | Dónde | Duración |
|---|---|---|---|
| Unitarios | Los ≈ 314 tests actuales (`uv run pytest`) | `ubuntu-latest` **y `windows-latest`** (rutas, `spawn`, UTF-8: los fallos de la primera instalación eran de Windows) | < 10 min |
| Lint y tipos | `ruff`; `pyright` en modo básico en `pipeline`, `catalog` y la futura app | ubuntu | 1 min |
| Huellas | Test que falla si cambia el código de una etapa sin cambiar su versión, o que verifica que `code=` cubre los módulos que importa | ubuntu | segundos |
| Contrato de datos | Esquemas JSON de `strokes`, `manifest` y `calidad`. Un fichero de cada versión anterior debe poder leerse (migradores). | ubuntu | segundos |
| Referencia (golden) | 6 a 12 clips de RacketVision y el tramo de 4 min: golpes, fases y medidas dentro de tolerancias. Hoy lo hacen `validate_rv_strokes.py` y la revisión del PC. | Nocturna en CI con modelos en caché (≈ 470 MB, `actions/cache`) en CPU, y en el PC con DirectML | 20 a 40 min |
| Interfaz | Navegador sin cabeza (playwright, ya es dependencia): añadir partido, cola, panel | ubuntu | 3 min |
| Extremo a extremo en el PC | La revisión automática actual (OK / REGRESIÓN / ERROR) sobre el tramo de 35 min antes de publicar una versión estable | PC, de noche | ≈ 1 h |

### 9.2 Versiones y publicación

- **SemVer** para la app: `MAYOR` si cambia el formato de datos sin migrador, `MENOR` para funciones o una versión de etapa que obliga a recalcular, `PARCHE` para lo demás.
- Ramas: `main` (estable, etiquetas `vX.Y.Z`) y `dev` (la rama de desarrollo actual). Las ramas `worktree-agent-*` (19 locales) se limpian tras fusionar.
- Cada versión publica las **notas de recálculo**: qué etapas suben de versión y el coste estimado por partido. Las lee el planificador (4.3).
- `CHANGELOG.md` en español, orientado al usuario.

### 9.3 Migraciones de datos

- **Base de datos:** migraciones numeradas en SQL (`migrations/0001_init.sql`…) aplicadas al arrancar, con copia previa automática.
- **Ficheros:** `"schema": N` en cada JSON. `tennisbio migrate` convierte sin recalcular cuando es posible. Si no, la etapa sube de versión y la huella hace el resto.
- **Primera migración** (adopción de la app):
  1. importar `matches.yaml` y `players/*.yaml` a la base de datos;
  2. calcular el hash de los vídeos;
  3. reescribir la huella de vídeo de los manifiestos sin recalcular nada;
  4. indexar `strokes*.json`.

### 9.4 Reproducibilidad

- `uv.lock` (ya existe), hash de cada modelo en el manifiesto (ampliar `model_state` a SHA-256), versiones de ffmpeg, onnxruntime y controlador de la GPU por ejecución.
- **Semillas** y orden determinista donde haya azar.
- Tolerancias documentadas entre dispositivos (CPU frente a DirectML: ≈ 1e-5 en el mapa de calor de la bola).
- «Reproducir este informe»: el informe lleva en su pie la versión de la app, las versiones de etapa y la fecha. Con la versión etiquetada y las cachés se regenera idéntico.

---

## 10. Modelo de datos (SQLite)

```
players(id PK, name, hand, backhand, height_m, grip_fh_deg, grip_bh_deg, created_at)
videos(hash PK, path, original_name, size, duration_s, fps, width, height, interlaced,
       audio_tracks, source_url, rights_note, added_at, archived_to, status)        -- status: activo|archivado|borrado
matches(id PK, video_hash FK, tournament, date, surface, round, trim_start_s, trim_end_s,
        name_a, name_b, created_at)                                               -- nombres leídos del marcador
match_players(match_id FK, player_id FK, role, analyze BOOL)                       -- role: A|B; analyze = fine@jugadora
analyses(id PK, player_id, stroke, scope)                                          -- informe por jugadora y golpe
stage_runs(id PK, match_id, stage, player_id NULL, version, fingerprint, status,
           started_at, finished_at, seconds, overlap_s, summary_json, env_json, error)
jobs(id PK, kind, params_json, lane, priority, status, attempts, max_attempts,
     not_before, started_at, finished_at, progress_done, progress_total, eta_s, last_error)
artifacts(id PK, match_id, path, kind, retention_class, bytes, regenerable_from, updated_at)
quality(match_id PK, json, verdict, computed_at)
strokes_index(match_id, player_id, stroke_id, stroke, side, t, confirmed, quality, situation_json)
publications(id PK, analysis_id, url, published_at, bytes, access_list)
settings(key PK, value_json)
```

Restricciones: `stage_runs` es un histórico, y lo vigente sigue en `manifest.json`. `strokes_index` y `artifacts` se reconstruyen desde el disco.

---

## 11. Hoja de ruta (alineada con el plan vigente de `CLAUDE.md`)

El plan vigente (pasos 1 a 6 en curso o casi hechos; 7 = ejecutar los 4 partidos una vez; 8 = móvil/nube) no cambia de orden. Las fases de producto se intercalan **sin bloquear** el trabajo técnico.

| Fase | Contenido | Esfuerzo | Encaje con el plan |
|---|---|---|---|
| **P0 · Higiene** (ya) | Hash de contenido del vídeo (con migración sin recálculo). Huella de código en todas las etapas o test de versión. CI (pytest en Windows y Linux, ruff). Limpiar `_poc*` (≈ 20 GB). Desglose de tamaño por categoría. Esquema en los JSON. | 3 a 5 días | Antes del paso 7. Evita relanzar 18 h por mover un vídeo. |
| **P1 · App local mínima** | SQLite e importación del YAML. Cola con dos carriles y reanudación. Panel (partido × etapa, ETA, errores). Formularios «añadir partido» y «jugadora». Toasts. El YAML pasa a ser exportación. | 2 a 3 semanas | Cumple el requisito 5 («sin editar configuración»). **El paso 7 (4 partidos) se lanza desde aquí.** |
| **P2 · Ejecución de los 4 partidos** (paso 7) | 4 × 5 h ≈ 20 h, en 2 a 3 noches. Ficha de calidad por partido. Revisión automática. | 3 noches | Paso 7 del plan |
| **P3 · Más jugadoras y golpes** | Identidad neutra (A/B). `fine@jugadora`. Ventanas de punto estables y compartidas. División `fine_extract` / `fine_measure`. Rival de los 4 partidos (≈ 4 a 12 h de PC según 3.3). Revés y saque como informes. | 2 a 3 semanas | Fase 4 de `CLAUDE.md` (orden: revés → rival → saque…) |
| **P4 · Almacenamiento y copias** | Clases de retención y guardián de espacio. Clips de evidencia en 720p. restic al disco USB y a B2/R2. Verificación mensual. Instalador único y canal estable. | 1 a 1,5 semanas | En paralelo con P3 |
| **P5 · Móvil y nube** (paso 8) | `publish` autocontenido, R2/Pages y Access, PWA, enlaces firmados, avisos ntfy y healthchecks. | 1 a 1,5 semanas | Paso 8, al final, como pide `CLAUDE.md` |
| **P6 · Opcional: GPU en la nube** | Port a CUDA, Docker, pruebas de equivalencia, botón «procesar en la nube». | 2 a 3 semanas | Solo si el catálogo crece más de ~10 partidos |

Hito de aceptación de cada fase: auditoría OK en el PC, CI en verde, y el usuario solo ha hecho clics.

---

## 12. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Recalcular sin necesidad (huella por mtime o por un comentario en el código) | Alta hoy | 4,5 a 18 h de PC | P0: hash del contenido y huella de código normalizada |
| Etapa cambiada sin subir la versión, con resultados viejos que parecen nuevos | Media | Datos incoherentes | Huella de código en todas las etapas y test de CI |
| Disco lleno a mitad de un lote | Media (≈ 25 partidos llenan el disco) | Lote parado | Guardián de espacio, retención y archivo en USB |
| Pérdida del PC o del disco | Baja | Pérdida de todo lo calculado | Copias 3-2-1 de P + E (céntimos al mes) y verificación mensual |
| Fallos del controlador DirectML (`0xC0000005`) | Media | Etapa caída | Reintentos con salto a CPU (ya parcial en la raqueta) |
| Identidad dudosa en partidos nuevos (0,52 en el único partido entero) | Media | Golpes de la rival atribuidos a la jugadora | Semáforo de calidad, partido rojo fuera de los agregados, y la identidad A/B de P3 |
| Windows suspende o actualiza a mitad | Media | Horas perdidas | Reanudación (manifiesto y cachés), franja horaria y bloqueo de suspensión mientras hay trabajo |
| Cambio de modelo que obliga a recalcular todo el catálogo | Media | n × 3 h | División extracción/medida, ventanas estables y, si crece, la opción B |
| Derechos de las retransmisiones al publicar o compartir | Baja (uso personal) | Retirada o reclamación | Solo clips cortos, autenticación, `noindex`, vídeos originales nunca publicados |
| AGPL de YOLO11 si se distribuye la app | Baja | Obligaciones de licencia | Uso personal. Si cambia, RTMDet o RTMPose (Apache-2.0). |
| Proyecto mantenido por sesiones de Claude sin CI | Alta hoy | Regresiones en el PC | CI (P0), canal estable y pruebas de referencia |
| Alcance creciente (la interfaz se come el tiempo del análisis) | Media | Retraso del paso 7 | P1 mínima (htmx, sin framework de frontend), lo demás después |

---

## 13. Lo que hay que medir para cerrar las cifras

1. Desglose real de los 7,8 GB de `_poc9_largo`: copia del tramo, `windows/*.mp4`, `*.npz`/`*.npy`, `players.npz`, `series`, informe y exportación. Basta ampliar `comun.ps1` para que lo calcule por extensión y subcarpeta.
2. Coste real de `fine_opponent` en `_poc9_largo` con las cachés actuales, y el ahorro de las ventanas compartidas.
3. Tamaño de los clips de evidencia en 720p CRF 23 de los 129 golpes.
4. Tiempo del hash SHA-256 de 5 GB en el disco del PC.
5. Ritmos de la ETA en los 4 partidos (para validar el ±20 %).

---

### Archivos clave para la implementación
- src/tennisbio/pipeline.py — huellas (`video_fingerprint`, `fingerprint`, `code_fingerprint`), `run`, `status`, `Context.progress`: base de la cola, la ETA y el hash del contenido.
- src/tennisbio/stages.py — `@stage` de cada etapa (versiones, `match_fields` de `identity`, `fine` y `fine_opponent`, `window_cache_key`, `cut_window`): generalización a `fine@jugadora`, ventanas compartidas y división extracción/medida.
- src/tennisbio/catalog.py — `load_matches`, `Player`, `Match`: punto de entrada para pasar del YAML a la base de datos sin romper el CLI.
- src/tennisbio/cli.py — comandos `run`, `status`, `report`, `audit` y `export`, que el trabajador de la cola reutilizará.
- src/tennisbio/report.py — rutas relativas a `windows/*.mp4` (líneas ≈ 503-526) que hay que hacer autocontenidas para `publish` y el móvil.
- scripts/auto_cycle.py y scripts/windows/ciclo_automatico.ps1 — ciclo y revisión automática actuales, que se convierten en el modo «desarrollo» y en la ficha de calidad.
