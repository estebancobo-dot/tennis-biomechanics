# Almacenamiento definitivo (especificación, 19-10)

Aprobada por el usuario («con que cubra los requisitos y escenarios vale»). Se implementa en el bloque 4 de
`docs/plan_maestro.md`, antes de la pasada definitiva de los 4 partidos. Hoy la aplicación usa todavía las carpetas
del proceso (`output\<id-del-fichero>\`, pruebas mezcladas con lo real, informes sueltos).

## Árbol
```
C:\tenis\
  videos\                         del usuario; la aplicación nunca los mueve ni borra
  biblioteca\
    datos\tennisbio.db            índice; se reconstruye desde las carpetas
    jugadoras\<jugadora>\ficha.yaml   mano, revés, altura, alias (marcador, otros alfabetos)
    partidos\<año>\<partido>\
      partido.json                torneo, fecha, ronda, superficie, jugadoras, cadena, emisiones (huella + ruta)
      etapas\                     pasada barata: planos, sonido, pista, marcador, jugadoras, identidad
      golpes\<jugadora>\          pasada fina por jugadora: golpes, series, ventanas de vídeo
      repeticiones\  tomas\       repeticiones y otras cámaras, enlazadas a su golpe en directo
    analisis\<jugadora>\<golpe>\  actual\, v1..vN\, pendiente\
    exportar\<jugadora>\<golpe>\  movil\  copias\  diagnostico\
    pruebas\                      ejecuciones del ciclo y validaciones (nunca junto a lo real)
```

## Nombres
- Jugadora: `apellido-nombre`, minúsculas ASCII, transliterado (`rybakina-elena`).
- Partido: `AAAA-MM-DD_torneo_ronda_jugadoraA-jugadoraB` (jugadoras en orden alfabético por apellido, ≤ 80 caracteres).
- Golpe (tipo): `forehand`, `backhand`, `serve`, `volley`, `overhead`. Golpe concreto: partido + tiempo de impacto en ms.
- Vídeo: su huella de contenido (no el nombre ni la ruta).
- Solo `[a-z0-9_-]`; nunca dos nombres que difieran solo en mayúsculas.

## Reglas
- Entradas inmutables; cada fichero de salida guarda la huella de sus entradas, ajustes y código.
- Escritura atómica (temporal + renombrado); todo idempotente; nada se borra (versiones).
- Rutas relativas dentro de `biblioteca\` (se puede copiar a otro disco); ruta total < 240 caracteres.
- El índice es derivado: si se pierde o se daña, se reconstruye.

## Casos
| Tipo | Caso | Respuesta |
|---|---|---|
| Nominal | Partido nuevo | Carpeta por año y nombre; análisis de cada jugadora |
| Nominal | Analizar a la rival | `golpes\<rival>\` del mismo partido, sin repetir la pasada barata |
| Límite | Vídeo renombrado o movido | Misma huella → mismo partido; se actualiza la ruta, no se recalcula |
| Límite | Vídeo borrado / USB desconectado | Resultados conservados, «vídeo no disponible» |
| Límite | Partido en varios ficheros | Un partido, varios segmentos |
| Límite | Resumen o partido incompleto | Se acepta y se marca |
| Esquina | Misma final de otra cadena | Mismo partido, dos emisiones; repeticiones de ambas |
| Esquina | Dos partidos iguales en fecha/torneo/ronda/jugadoras | Sufijo `-2` |
| Esquina | Fecha desconocida | `sin-fecha_<6 de la huella>` |
| Esquina | Mismo apellido | Se añade el nombre |
| Esquina | Nombres no latinos o largos | Transliteración; recorte + huella |
| Esquina | Ruta larga en Windows | Nombres acotados; aviso si la raíz es demasiado profunda |
| Error | Disco lleno a mitad | Nada a medias (atómico); se reanuda |
| Error | Fichero dañado | Se recalcula esa etapa |
| Error | Índice dañado | Se reconstruye |
| Error | Migración cortada | Diario de migración; se reanuda sin duplicar |
| Error | Sin permisos | Aviso claro; nada a medias |

## Migración
Lo actual (`output\<id>\`, `output\analisis\`, `informe_*`, `exportar_*`, `_poc*`/`_smoke`) se traslada sin
recalcular: partidos a `partidos\`, pruebas a `pruebas\`; las carpetas viejas se dejan hasta comprobar la copia.

## Implementado (20-10, bloque 4, sin conectar todavía)
Módulo propio `src/tennisbio/library.py`, con pruebas de cada fila de la tabla en `tests/test_library.py`.
La aplicación y el proceso siguen escribiendo en `output\<id>\` hasta el paso de conexión.

**Hecho:**
- Nombres: `player_slug` (`rybakina-elena`, también desde «Елена Рыбакина», «Iga Świątek», cirílico serbio;
  «Apellido, Nombre» si hay coma; ≤ 40 con recorte + huella), `match_slug` (fecha, torneo, ronda, apellidos por
  orden alfabético; nombre completo si comparten apellido; ≤ 80 con recorte + 6 de la huella;
  `sin-fecha_<huella>` sin fecha o con fecha no válida), solo `[a-z0-9_-]`.
- Rutas: `library_root(cfg)` (`paths.library` o `biblioteca\` junto a `output\`), `match_dir`, `analysis_dir`,
  `export_dir`, `player_dir`, `tests_dir` (`pruebas\`); `etapas\` y `etapas\emision-2\`, `golpes\<jugadora>\`.
  Aviso si la raíz es demasiado profunda; error claro si una ruta llegara a 240 caracteres.
- Índice `datos\tennisbio.db` (tablas `lib_*`): huella de contenido del vídeo (`pipeline.video_sample`) → partido.
  Vídeo movido/renombrado → misma huella, se actualiza la ruta sin recalcular; `relocate` lo busca en carpetas
  (otra letra de USB); «vídeo no disponible» si falta; segmentos (`segment=`), segunda emisión (`channel=`),
  resumen o incompleto (`incomplete=`), `-2`/`-3` en colisiones, unión explícita con `match=`.
  Dos vídeos sin fecha nunca se unen por suposición.
- `partido.json` manda: el índice se reconstruye desde las carpetas si se pierde o se daña (el dañado se guarda
  aparte, no se borra). `repair` rehace un `partido.json` dañado desde el índice y lista los ficheros de etapa
  dañados (los recalculará el proceso).
- Escritura atómica (temporal + `os.replace`); disco lleno o sin permisos → mensaje en español, nada a medias.
  Ficha de jugadora en `jugadoras\<jugadora>\ficha.yaml` con alias (marcador, otros alfabetos).
- Migración: `plan_migration(output, biblioteca)` → lista de operaciones; `apply(ops, diario)` copia (nunca
  borra) con diario `datos\migracion.jsonl`: al relanzar salta lo hecho, reconoce copias ya hechas aunque falte
  su línea, rehace las copias a medias (`.partial`) y no duplica; comprueba el espacio antes de empezar;
  `verify` dice qué falta; `migrate` hace todo y reconstruye el índice. Reparto: etapas de la pasada barata
  (`probe`, `scenes`, `audio_*`, `players`, `court`, `score`, `identity`, `candidates`, `manifest`, `video.json`,
  `source.*`) → `etapas\`; el resto (pasada fina, `series\`, `windows\`, cachés) → `golpes\<jugadora>\`; el
  `partido.json` antiguo → `etapas\partido_origen.json`. `analisis\<id>_<golpe>\` → `analisis\<jugadora>\<golpe>\`;
  `informe_*` → `…\informe-antiguo\`; `exportar_*` → `exportar\<jugadora>\<golpe>\antiguo\`; `_smoke`, `_poc*` y
  toda carpeta que empiece por `_` → `pruebas\`; el mismo vídeo analizado dos veces → `pruebas\duplicados\`.
  Lo que no es nuestro se deja donde está.

**Lo que hará el paso de conexión (pendiente):**
- Que el proceso (`pipeline.Context`, etapas) lea y escriba en `etapas\` y `golpes\<jugadora>\` en vez de la carpeta
  plana; partir el `manifest.json` entre la pasada barata y la fina de cada jugadora, y separar lo de la rival
  (`strokes_opponent.json` y sus series, hoy en la carpeta de la jugadora) a `golpes\<rival>\`.
- Que la aplicación (`app/db.py`, `app/index.py`) use la biblioteca: añadir vídeos con `Library.add_video`,
  rutas de análisis/exportación/móvil con `analysis_dir`/`export_dir`, `pruebas\` para el ciclo automático,
  y fundir sus tablas con las `lib_*` en un solo `tennisbio.db`.
- La pasada barata por emisión (`etapas\emision-2\`) y las repeticiones de la segunda emisión enlazadas a su golpe.
- Ejecutar `migrate` en el PC (una vez, con el ciclo automático), comprobar y solo entonces ofrecer borrar
  las carpetas viejas.
