# Estado del proyecto y contexto para continuar

Este fichero lo mantiene Claude: resume lo hecho, lo decidido con el usuario y lo pendiente, para que
cualquier sesión (en la nube o en el PC) continúe sin perder nada. Los requisitos del usuario y el
plan están en `CLAUDE.md`; la taxonomía en `docs/matriz_cobertura.md`; las validaciones en
`docs/validacion.md`; la revisión de errores en `docs/revision_completa.md`.

## Cómo se trabaja (acordado con el usuario)
- El usuario **no revisa datos, no lee documentos, no copia registros**: todo automático.
- En el PC solo hace doble clic en `1_instalar.bat`, `2_prueba_rapida.bat`, `3_analisis_completo.bat`.
- **Registros del PC → Claude, automáticos:** cada script sube al terminar (o al fallar) sus
  registros a la rama **`pc-logs`** del repositorio (carpeta local `C:\tenis\registros`):
  `instalacion.log`, `prueba_rapida.log`, `analisis_completo.log`, `equipo.txt` (CPU, gráfica,
  RAM, disco) y `partidos/<id>.log` + manifiestos y errores de cada partido.
  Para leerlos desde cualquier sesión: `git fetch origin pc-logs && git show origin/pc-logs:instalacion.log`
  (o `git log origin/pc-logs` para ver cuándo se subieron).
- Código y documentación se desarrollan en la rama `claude/tennis-biomech-setup-jggqb0`. En el PC el
  proyecto está clonado con Git en `C:\tenis\tennis-biomech` y `1_instalar.bat` hace `git pull`.
- El partido completo (los 4 partidos) se ejecuta **una sola vez, al final**, cuando todo funcione.
- Móvil y nube: al final, después de que el PC funcione.

## Estado (LEER PRIMERO; Claude lo actualiza en cada cambio) — 11-11
Conceptos (glosario en `CLAUDE.md`): **Plan** (corto / medio / largo) → **Paquete** → **Tarea**; cada **Petición** del
usuario pertenece a un paquete; un paquete está **aceptado** cuando su prueba principal pasa en las salidas reales
(tabla «¿Cerrado?» de `estado_real_partidos.md`, calculada, no a mano).

**PLAN ÚNICO A SEGUIR (14-11 16:30; sustituye al orden de la tabla «DÓNDE ESTAMOS» de abajo, que queda como historia)**

**Dos bloques:**
- **Base (B1-B8):** cerrarla.
- **Nube nativa e híbrida (NN, #287-#289):** va dentro del cierre de la Base.
  - **Fase B (infraestructura):** antes de los partidos que faltan. Da los mismos resultados con menos cuota.
  - **Fase C (modelos):** en paralelo. Es la que cierra B3.

**Reparto:** Claude escribe el código y las pruebas (nube de Claude, sin GPU); Kaggle y Modal ejecutan por la cola.

| # | Tarea | Bloque | Dónde | Depende de | Estado |
|---|---|---|---|---|---|
| T1 | Prueba de 10 min de Gauff (marcador v16, sin la bola en la CPU): marcador leído y tiempo | Base B6 | Kaggle (cola) | — | **hecho (17:06)**: sin fallos C0 ni C1 (el marcador ya se lee: sin él habría quedado «revisar»); 52 min de análisis y 0,9 h de Kaggle (antes 1,64 h, con la bola en la CPU; Modal 26 min) |
| T2 | Recursos minuto a minuto en Kaggle (CPU, cada GPU, memoria), como en Modal | NN-A | Claude | — | **hecho en el código (14-11 18:15)**: `recursos.jsonl` y su resumen en `estado.json` (cada GPU por separado: `gpu_pct`, `gpu1_pct`), y lo de ahora en la cola en vivo («GPU 85 %·0 %, CPU 60 %, 9,1 GB»); se acepta con el primer análisis en Kaggle |
| T3 | Comprobaciones de auditoría nuevas: «Uso de la nube por etapa», «Cola de la nube», «Equivalencia entre infraestructuras», «Prueba de concepto medida» | Base B1, B7, B8; NN | Claude | — | **hecho en el código (14-11 19:20)**: «Uso de la nube por etapa» (CPU, cada GPU y memoria de cada etapa: `nube.per_stage`), «Cola de la nube» (la cola deja su estado también en el volumen, `/cola/`: vuelta reciente, cada partido del informe hecho por la cola, cada error con su motivo), «Progreso visible» en la nube, «Equivalencia entre infraestructuras» (las comparaciones de la cola, `/cola/comparaciones/`) y «Prueba de concepto medida» (`runs/kaggle_medir_*`). Se aceptan con la auditoría de la nube (T11) |
| T4 | Esqueleto híbrido: puertos (cálculo, almacenamiento, vídeo, inferencia, modelos) y descubrimiento de capacidades; el dispositivo por descubrimiento (fuera el parche `dml`→CUDA), con los mismos resultados | NN-B | Claude | — | **en curso**: hecho el descubrimiento (`tennisbio.infra.discovery`) y el **puerto de inferencia** (14-11 19:00, `tennisbio.infra.devices`): `device: auto` elige CUDA en Kaggle y Modal, DirectML en el PC, la CPU en el resto; todo lo que preguntaba «¿es la iGPU?» pregunta «¿es una GPU?», con las mismas opciones de CUDA y la misma memoria devuelta que el parche, que ya no se activa. Se comprueba con `prueba_gauff_v17` + `comparar_gauff_v16b_v17` (T9). Faltan los puertos de vídeo, almacenamiento y modelos |
| T5 | Banco de pruebas de concepto: acción «medir» en la cola (variante × clip de referencia × infraestructura → calidad, tiempo, coste) | NN-B | Claude | T4 | pendiente |
| T6 | Prueba de inferencia: raqueta con ONNX CUDA frente a TensorRT FP32 y FP16, en lotes de 1 a 64 (velocidad e igualdad de salidas) | NN-B | Kaggle | — (adelantada: no espera a T5) | **en la cola (17:50)**: trabajo `medir_raqueta_trt` (acción nueva «medir»; `tennisbio.infra.poc_raqueta`) |
| T7 | Prueba de vídeo: ffmpeg en la CPU frente a NVDEC (TorchCodec, PyNvVideoCodec) al recortar las ventanas | NN-B | Kaggle | T5 | **en la cola (14-11 19:30)**: `medir_video_nvdec` (`tennisbio.infra.poc_video`: el lector del análisis con y sin «-hwaccel cuda» sobre 8 ventanas de la retransmisión de Gauff; tiempo, segundos de CPU y diferencia de cada fotograma). TorchCodec y PyNvVideoCodec, después si NVDEC gana (necesitan otra forma de entregar los fotogramas) |
| T8 | Prueba de las 2 T4: pose en una, raqueta y bola en la otra | NN-B | Kaggle | T6 | pendiente |
| T9 | Adoptar lo que gane y comprobar la equivalencia en Kaggle y Modal | NN-B | Claude + Kaggle | T6-T8 | **herramienta hecha (14-11 19:00)**: `tennisbio.infra.equivalence` (dos ejecuciones del mismo clip: «idéntica» si cada etapa da el mismo contenido, «equivalente» si los mismos golpes y medidas dentro de su tolerancia, «distinta» con lo que cambia) y la acción «comparar» de la cola, que la ejecuta en GitHub sin GPU; un cambio de código de la pasada fina declarado equivalente por ella conserva su huella (`config/codigo_equivalente.json`), así nada ya analizado se repite. Primera: `comparar_gauff_v16b_v17` (T4) |
| T10 | Partidos: Gauff, la final, Sinner; poner al día Osaka, Pegula y Zheng | Base B6 | Kaggle (cola) | T1, T9 | en la cola (esperan a T9) |
| T11 | Informe y auditoría de los 6 → cierre de la Base | Base | Modal (CPU) o Kaggle | T10, T3 | pendiente |
| T12 | Niveles de error C0-C4 (R23-R26, #265) | Base B2 | Claude | — | en curso |
| T13 | Exportación de vídeos por golpe en la nube | Base B5 | Claude + Kaggle | T10 | pendiente |
| T14 | Estado del arte, segunda vuelta (lo que falta en `docs/estado_del_arte_nube.md`) | NN-C | Claude | — | pendiente |
| T15 | Datos anotados en Modal (RacketVision) y pruebas de modelos, por orden de tiempo: raqueta, pose, bola, detector de golpes, 3D, cortes, marcador | NN-C, Base B3 | Kaggle | T5, T14 | pendiente |
| T16 | Si un modelo gana: rehacer los 6 partidos con él (referencia nueva) | NN-C | Kaggle | T15 | si procede |
| T17 | **Trazabilidad**: cada requisito de `CLAUDE.md`, cada petición de nube (#268-#290) y cada documento interno (`analisis_nube.md` §2, §6-§9, `arquitectura_producto.md` §9.1, `orquestador.md`, `plan_maestro.md`, `matriz_cobertura.md`, `validacion.md`) frente a este plan. Lo que falte se convierte en tarea. Incluye los riesgos abiertos: derechos, privacidad y licencias | NN, Base | Claude | — | **en curso** (14-11: `analisis_nube.md` ya traía análisis que no se reutilizó; integrado en `nube_nativa.md`) |
| T18 | **Prueba de referencia con GPU** antes de cada versión (`analisis_nube.md` §7; `docs/operacion_nube.md` §3) como trabajo de la cola | NN | Claude + Kaggle | T5 | pendiente |
| T19 | **Repartir** la pasada fina por ventanas entre las 2 sesiones de Kaggle (y sus 2 T4) y el detector por planos, con prueba de determinismo (fase N2 de `analisis_nube.md` §8) | NN-B | Claude + Kaggle | T9 | pendiente |
| T20 | **Usar los recursos en paralelo** (detalle en `docs/operacion_nube.md`): las 2 sesiones de Kaggle a la vez (un partido o prueba y una prueba de concepto), Modal desde el 1-12, y en la nube de Claude pruebas en paralelo y sesiones hermanas para tareas independientes (si el usuario lo quiere: gastan su plan) | NN | Claude | T5 | **las 2 sesiones de Kaggle, hecho (14-11 19:00)**: la cola lanza hasta 2 trabajos de Kaggle a la vez (`KAGGLE_SESSIONS`), cada uno en su cuaderno |
| T21 | **Progreso en vivo y Claude sin parar (#291):** cada trabajo escribe su etapa y su % cada 2 min (Kaggle y Modal) y la cola lo muestra en `nube-logs/cola/estado.md` y en la página de cada vuelta; la vuelta y el latido de la cola separados (un cambio se atiende al momento); Claude retoma solo cada hora (tarea programada, minuto 48) | N | Claude | — | **hecho en el código (14-11 18:10)**; se acepta cuando el primer análisis en marcha salga con su % en `cola/estado.md` |

**Después:** P0 (rediseño de la aplicación), N (la aplicación en la web, el usuario solo sube), M1-M7, P1-P6.

**Para continuar en cualquier caso** (fallos, Kaggle, Modal, pruebas en «revisar») y el **modelo de validación y aceptación**: `docs/operacion_nube.md`.

**Capacidad a 0 €:**
- **Kaggle:** 30 h de GPU por semana, 2 sesiones a la vez, 12 h cada una; se renueva el sábado 00:00 UTC.
- **Modal:** 30 $ al mes, desde el 1-12.
- **Otra nube gratuita** (Lightning AI, ~22 h de T4 al mes; necesita cuenta del usuario): solo si las medidas de la
  fase B muestran que no basta.

**DÓNDE ESTAMOS Y CÓMO SEGUIR: todo en Modal (13-11 tarde, #275-#277; sustituye a lo de abajo sobre el PC)**
El PC está en pausa total (`config/pausa_pc.txt`: «pausa: si»); ya subió a Modal lo que solo él tenía. Claude lanza y lee
todo por el flujo «Nube» de GitHub Actions (`.github/workflows/nube.yml`); el tope de la cuenta de Modal en su crédito
mensual (30 $) deja el gasto en 0 €. R22 va como diferencia conocida y escrita (#276).

| Paso | Qué | Estado |
|---|---|---|
| 1 | Subir a Modal: modelos y compilaciones de F3Set (291), los 6 vídeos (293, 23 GB), clics de identidad (294) | hecho (13-11 20:23) |
| 2 | F3Set en la nube frente a la v18 del PC | **HECHO (14-11 04:05)**, tag nube2: en los 517 golpes válidos la nube encuentra **469 (91 %)**, precisión **94 %** (PC v18: 465, 93,6 %; v15: 467, 94,5 %); identidad equivocada 8 = 8; mismo paso en el 98,5 % de los 648 golpes. El veredicto automático dice «distinto» por el criterio estricto (±2 golpes, ±0,005): la nube da 4 golpes más y 0,6 puntos más de precisión, con el código de hoy (marcador v15 incluido). 4 h 29 min en T4, 5,5 $ estimados (con los núcleos reservados). 1.ª vuelta (13-11 20:02) sin medir nada: compilación no reconocida, arreglado |
| 3 | Prueba corta: 10 min de Osaka en la nube (`accion: prueba`) | **5.ª (23:03-23:28): BIEN** — estado «hecho», las 16 etapas, 0 ventanas fallidas, 0 modelos en la CPU, memoria de la T4 como mucho 2,7 GB, 24 min. Usa unos 18 de los 24 núcleos que ve (Modal cobra lo usado si pasa de lo reservado): el coste ya se calcula con lo medido (`nube.used`). 3.ª (21:58): GPU bien (0 modelos en la CPU), pero la etapa identity se rompió (`clothes.groups_check`: pocos cambios de lado y ningún saque visto → `vote_agree` None; fallo también del PC, que con el partido entero no se daba). Arreglado con su prueba (`tests/test_identity_photos_check.py`). 4.ª (22:36, 19 min, 0,40 $): todas las etapas hasta `fine_doubtful` bien y 0 modelos en la CPU, pero la T4 se llenó (14,6 de 15 GB) y fallaron 14 de 58 ventanas: el modelo de errores lo paró (C0, 24 % frente al 2 % permitido). Arreglo: cada sesión CUDA devuelve tras cada inferencia la memoria que no usa (`nube_gpu.CudaSession.run`). 5.ª prueba. Acción «parar» (cancela un trabajo por su fc-...): Pegula viejo parado. 1.ª (20:50, 109 s, 0,04 $): falló en jugadoras: los modelos del PC quedaron anidados en el disco de Modal (`/models/models/`) y no se vio ninguno (TransNet, pista, YOLO); el clip cortado del `.ts` no se pudo limpiar. Arreglado: `nube.unnested`, subida sin «/» final, la prueba limpia el `.ts` entero con la orden de la etapa probe y corta de ahí (`tests/test_nube.py`). 2.ª (21:14): los modelos ya bien, pero el ffmpeg de la nube (Debian 7.1.5) **no limpia el `.ts` entero de Osaka** con ninguno de los dos intentos de la etapa probe (el del PC sí, desde el 18-10). Osaka no se lanza así. Diagnóstico solo con CPU (`diag_ts`): **ningún ffmpeg lo limpia** (7.1 y 9.0, 4 variantes, fallan en el primer segundo) **y el PC tampoco pudo** (probe de f43dd2 «cleaned: false» desde el 18-10): Osaka se analiza del `.ts` tal cual, igual que en el PC; la prueba ya no se para por eso. Prueba de Pegula (21:28, `.mkv`): la cadena entera funciona en la nube (cortes 1,2 min, jugadoras 1 min, marcador, identidad 26/28 planos, detector 91 golpes, pasada fina en marcha), pero la T4 se llenó (`CUBLAS_STATUS_ALLOC_FAILED`) y modelos de la pasada fina pasaron a la CPU (mismo resultado, mucho más lento). Arreglado en `cloud/arranque/nube_gpu.py` (cada sesión CUDA reserva solo lo que pide; cuDNN con poco espacio de trabajo) y cada análisis cuenta `modelos_en_cpu`. 3.ª prueba de Osaka con el arreglo |
| 4 | Lote 1: Osaka entero (`accion: partidos`); resultados, tiempo y coste al usuario | **HECHO (14-11 02:28)** en la nube, estado «hecho», 0 modelos en la CPU. Frente al PC (13-11): golpes detectados 455 = 455; identidad 139 planos, confianza 0,94 = 0,94; golpes suyos 224+9 = 233 (PC 226+7 = 233); derechas 117+2 = 119 (PC 120); 0 ventanas con error. Aviso C2: 7 de 307 tomas de otras cámaras sin recortar (el `.ts` dañado). Tiempo: pasada barata 28 min + resto 1 h 53 min (1.ª vuelta caída al empezar la pasada fina, no repetida). Coste ≈ 3,8 $ (16 núcleos usados de media). |
| 5 | Lote 2: Pegula y Zheng · Lote 3: Gauff y la final · Lote 4: Zverev-Sinner, uno tras otro, con su informe | lote 2 lanzado el 14-11 02:37 (Pegula `fc-01M7BV8C8T79QQQJM44KJHS1XX`, Zheng `fc-01M7BV8CC69JQT9KQD2EHA51CZ`; 112 y 117 min de vídeo, cada uno en su contenedor; ≈ 12 $ estimados con lo medido en Osaka, 0,054 $ por minuto de vídeo). Presupuesto de noviembre: ≈ 16 $ gastados al acabar F3Set; lo que no quepa sigue con el crédito de diciembre (el tope para en 30 $ y las etapas hechas se guardan) |
| 5b | Zheng (lote 2): **0 lecturas del marcador** en la nube (el PC leyó 454 el 09-11): el catálogo dice «Zheng Qinwen» y se buscaba la última palabra, «Qinwen», pero la tele escribe ZHENG (en chino el apellido va primero); igual pasaría con «Zverev Alexander» y «Sobolenko» (SABALENKA). El PC lo leía porque entonces su catálogo no tenía rival y lo leía del marcador. Parado (`fc-01M7BV8CC69JQT9KQD2EHA51CZ`) y arreglado: el rival se lee siempre del marcador primero y, si no, vale cualquier palabra de su nombre (`stages._opponent_on_scoreboard`, `scoreboard._is_name`; marcador v15; `tests/test_scoreboard.py`). Zheng relanzado (03:52): marcador **462 lecturas** (PC 454), identidad 263/264 planos, confianza 0,97 (PC 0,96); el nombre leído fue «Chn» (el país, en la misma fila: vale para encontrar su fila). Pegula sigue (su nombre sí coincide: 516 lecturas = PC); su contenedor se perdió a las 03:19Z y Modal lo reintentó solo con el código nuevo: rehízo el marcador (516 de nuevo), saltó lo que no cambió y siguió en la pasada fina |
| 5c | **Capacidad a 0 € (#278-#280, 14-11):** la aplicación no se para (lo que no es GPU sigue ya con Osaka, Pegula y Zheng); más partidos al mes: (a) abaratar cada partido en Modal sin perder calidad — la CPU es casi la mitad del coste (16 núcleos de media: 0,75 $ por hora frente a 0,59 $ de la T4): decodificar el vídeo en la GPU (el PC lo hacía con su decodificador; en la nube se quitó), la bola de la pasada fina (929 s frente a 159 s en el PC); medido con una prueba corta y comparado con Osaka; (b) Kaggle como segunda nube gratuita (~30 h de GPU por semana) lanzada desde GitHub igual que Modal, si el usuario crea la cuenta | propuesto, espera su visto bueno |
| 6 | Terminar el lote 2 (Pegula, Zheng): resultados frente al PC, tiempo y coste al usuario | **HECHO (14-11 07:26)**. **Pegula** frente al PC (13-11, casi el mismo código): golpes detectados 912/900, marcador 516 = 516, identidad 289/296 = 289/296 (confianza 0,53 / 0,54; las dos de blanco), golpes suyos 424+23 = **447** (PC 446), derechas 138+7 = **145** (PC 143), 0 errores; ≈ 7,3 $ (un contenedor perdido y reintentado). **Zheng** frente al PC (09-11, sin la bola en el detector, R17): golpes suyos 330+14 = **344** (PC 302), derechas 128+5 = **133** (PC 135), marcador 462 (PC 454), identidad 263/264 (0,97); 1 ventana con error de 345 (C2, R36); ≈ 6,9 $ (una vuelta parada por el marcador, un contenedor perdido). |
| 7 | **Análisis de capacidad a bajo nivel** (`docs/capacidad_nube.md`, R35, #279): perfil función a función de una prueba corta (dónde va cada segundo de CPU y GPU), límites actuales comprobados de Kaggle y otras opciones gratuitas, partidos al mes con cada una; propuesta al usuario antes de cambiar nada | tras el paso 6 (aprobado por el usuario el 14-11) |
| 8 | **Encadenar sin depender de una sesión** (#278, #281-#283): una sola cola de trabajos (`config/cola_nube.yaml`) que el flujo «Cola» de GitHub (cada 30 min, gratis: repositorio público) lee sin ningún chat: mira lo que está en marcha, recoge lo terminado y lanza lo pendiente en la primera fuente gratuita con sitio — Kaggle (horas de la semana) → Modal (crédito del mes, con su cuenta del gasto y un tope de 29,5 $, sin quedarse nunca a medias) — (el PC no se usa: #284) —; si ninguna tiene sitio, el trabajo espera con su motivo y la cola sigue. Estado, gasto y lista de partidos en la rama `nube-logs` (`cola/estado.md`) | **aprobado por el usuario (14-11, «haz el 1») y en curso**: 8a cola + Modal + cuenta del gasto + `nube-logs` (`cloud/cola.py`, `.github/workflows/cola.yml`, `tests/test_cola.py`) **hecho y comprobado** (1.ª vuelta 14-11 08:53: leyó los 6 partidos de la nube, `nube-logs:cola/partidos.json`); **corrección 10:45**: GitHub no ejecutó ni una vez la programación cada 30 min en sus 2 primeras horas (las vueltas de las 08:53, 09:02 y 10:04 las lanzó Claude a mano; a las 10:20 Claude dijo por error al usuario que la de las 10:04 había sido sola): ahora, mientras quede un trabajo sin terminar, cada vuelta lanza la siguiente 25 min después, y también la lanzan un cambio de la cola y el final de un «Nube»: **comprobado, vueltas solas a las 10:50, 11:16 y 11:41**; pruebas de 10 min hechas por la cola en Modal: Gauff (26 min, 0,62 $) y la final (11 min, 0,27 $); quedan 0,53 $ hasta el 1-12; en la cola, los lotes 3 y 4 (aprobados) con su prueba de 10 min antes de cada partido y el informe al final: la prueba de Gauff cabe en lo que queda de Modal (0,8 $ previstos); los partidos esperan sitio (escrito en `cola/estado.md`); 8b Kaggle: **cuenta creada por el usuario (14-11)**; código hecho (`cloud/kaggle/`); `kaggle_comprobar` **bien a las 11:34** (2 × T4, 4 núcleos, 31 GB, 966 GB de disco; la clave de Modal por el conjunto de datos privado, porque los secretos del cuaderno no llegan por la API; datos de Modal en 23 s; el mismo entorno en 45 s; CUDA); `kaggle_prueba` de Gauff (11:42-13:20) **da lo mismo que Modal**: tomas, pista, 55 golpes (34 cerca, 21 lejos), enlaces y fallos iguales; 18 derechas frente a 19; 0 modelos en la CPU; 1,64 h frente a 26 min, por «la bola en paralelo en la CPU» del PC, que ahogaba sus 4 núcleos (ya no se usa con menos de 8). **Kaggle activado en la cola (13:40)**; la prueba de la final en Modal leyó bien el marcador («Sabalenka», 7 lecturas; su C1 es que esos 10 min son la previa: 0,8 min de cámara principal); solo si da lo mismo pasa a la cola (guía en `docs/kaggle.md`); el PC no se usa (#284) |
| 9 | Seguir la aplicación con los partidos ya analizados (no espera a la GPU): auditoría de la Base en la nube (solo CPU), criterios B1/B7/B8 reescritos para la nube, informe con los 3 partidos; después P0 | **en curso.** 1.ª vuelta (`informe1`, 14-11 06:40-06:56, 0,08 $): informe y auditoría con código 0 sobre Osaka, Pegula y Zheng: 346 comprobaciones cumplidas, **4 no cumplidas** (el resto de ✘ son peticiones que heredan alguna de estas 4): R36 (Zheng, arreglado), R37 (una altura de bote fuera de límites, arreglado), R38 (el vídeo de la lección bajo la primera pantalla, arreglado) y R39 (124 palabras en las claves del armado; pendiente de ver el texto real). R38 y R39 también salían en el PC (13-11, auditoría de sus 3 partidos): son del informe, no de la nube. 2.ª vuelta (`informe2`, 07:31-07:37, 0,03 $, código de R36-R38): **R38 comprobado** (ya no sale) y la comprobación dice qué claves del armado pasan (53 + 42 + 29 palabras). R39 comprobado en los datos reales sin gastar: `scripts/informe_real.py` rehace la página de la nube con el código del repositorio y pasa las comprobaciones del navegador: las 9 fases sin fallos (como mucho 105 palabras; el armado 105), el vídeo en y=333-636 de 900, 0 errores. Quedan 2 ✘, los dos se van al rehacer la pasada fina (paso 10): R36 (Zheng) y R37 (la altura del bote). **Propuesta de criterios para la nube (espera visto bueno, van con el paso 8):** B1 = un partido de 3,5 h desde cero en ≤ 8 h en la nube, a 0 € (dentro del crédito del mes) y sin perder calidad (mismos golpes que el PC); CPU, GPU y memoria por etapa medidas en cada ejecución (`recursos.jsonl`). B7 = un partido nuevo de principio a fin sin el chat (subir el vídeo, el clic y aprobar; la cola de la nube hace el resto) y capturas de cada pantalla sin fallos (auditoría en la nube). B8 = la cola de trabajos de la nube como única entrada: el chat y la web envían, paran y reanudan con el mismo código. Después: P0 |
| 10 | Poner los 3 partidos al día con el código final: marcador v15 (Osaka, Pegula) y la pasada fina desde sus cachés de ventana (R36, R37 cambian su código; las ventanas no se repiten: pose, bola y raqueta no cambian). Solo CPU, ~20-30 min por partido | **en la cola (14-11)**: `actualizar_osaka`, `actualizar_pegula`, `actualizar_zheng` (Kaggle; cada uno baja de Modal lo ya hecho y rehace solo lo que cambió: marcador v16, R36, R37), detrás de los partidos nuevos; después el informe y la auditoría de los 6 |
| 11 | Lotes 3 (Gauff y la final) y 4 (Zverev-Sinner), aprobados | en la cola (paso 8) en cuanto haya fuente gratuita con sitio: Kaggle (espera la cuenta del usuario) o el crédito de Modal del 1-12 |
| 12 | Cierre de la Base: los 6 partidos con el mismo código y la auditoría en ✔ | al final; criterios B1, B7 y B8 reescritos para la nube (#286, 14-11) |
| 13 | **Nube nativa (#287, fallo crítico, 14-11):** el código de la nube sigue decidido para el PC; plan en `docs/nube_nativa.md`: A medir, B infraestructura nativa de GPU (los mismos resultados), C cada modelo frente al estado del arte con datos anotados | **plan escrito** (14-11 15:00). Los partidos enteros esperan a la fase B (`partidos_en_espera` en la cola): con el código de hoy cada partido gasta 3-4 × más cuota de Kaggle; la fase B no cambia los resultados, así que lo ya hecho sigue valiendo. La final, lanzada por la cola en Kaggle a las 14:32 y nunca arrancada por Kaggle (en cola desde las 13:48 con la prueba de Gauff), vuelve a esperar (`reiniciar`). Kaggle queda para la prueba de Gauff v16 y las medidas de la fase B. El usuario puede pedir lo contrario (partidos ya con el código de hoy). 15:50 (#288, #289): decisiones por pruebas de concepto medidas; arquitectura híbrida (puertos y adaptadores, descubrimiento); primera vuelta del estado del arte por capas en `docs/estado_del_arte_nube.md` (11 búsquedas, con lo que falta); un cuaderno de Kaggle por trabajo (R42) |

**Por qué se llegó aquí (13-11, #267; respuesta al usuario, sin excusas: es trabajo de Claude).**
1. *Funciones antes que base*: 267 peticiones, muchas medidas y pantallas encima de una base sin cerrar (B1-B8 abiertos;
   la revisión automática del 13-11: 137 de 263 peticiones sin terminar, 28 comprobaciones no cumplidas).
2. *Ninguna política de errores*: la regla implícita «el análisis nunca se para» convirtió fallos en vacíos silenciosos
   (323 `except`, ~268 sin decir nada). R17 (el detector sin la bola) estuvo tres semanas a la vista («bola 0 s» en cada
   registro) sin que nada lo parara.
3. *Lo validado no era lo que corría*: F3Set en carpetas planas, los partidos en la biblioteca; ninguna prueba exigía
   que dieran lo mismo (R20 ahora sí).
4. *Comprobar que algo existe, no lo que contiene*: la auditoría llega después y solo ve lo que alguien pensó en mirar;
   no había contratos de datos al terminar cada etapa (#265).
5. *«Hecho» sin verlo en las salidas reales* (09-11) y *varios cambios a la vez antes de cada validación* (v16 midió
   R14 + R16 juntos: no se sabe cuál pierde precisión, R22).
6. *Sesiones que empiezan sin memoria*: cada una arreglaba lo último que fallaba en vez de seguir el plan (de ahí la
   tabla única de tareas, 11-11).
Remedios: #264 (R17-R20) y #265 (niveles C0-C4, contratos por etapa, ningún `except` sin clasificar, inyección de fallos,
puerta de aceptación); una validación por cambio en el PC cuando el cambio puede mover resultados.

**Qué va en paralelo (13-11, #266):** la nube escribe el código (#265) mientras el PC valida por la cola lo ya subido
(R17 en Osaka y Pegula, diagnósticos R22). Es secuencial lo que necesita el resultado de otra cosa: la validación final en
el PC (Osaka, Pegula, F3Set) necesita #265 terminado; la previsión y el plan de los 6 partidos necesitan esa validación;
los 6 partidos, la aprobación del usuario (#262).

**Resumen de la noche (12-11 22:30 → 13-11 07:30, #269), con lo comprobado en el PC**
- **Útil:** Osaka con la bola del partido (265, 00:40-04:03): detector 28 min, pasada fina 2 h 39 min (40 s por golpe nuevo).
  Diagnósticos 268-273 y 272 (entradas): dieron las causas de R22 y R27.
- **Fallos y su arreglo:**
  - R22 (mío, de R16): el relleno de huecos de pista también rellenaba el principio de un plano y un punto de Azarenka
    pasó a la otra jugadora. Arreglado.
  - R27 (mío): el mínimo del 25 % para la jugadora lejana, y su C0, habrían parado todos los partidos (la pasada barata
    nunca la ve, tampoco en F3Set). Quitado antes de que corriera.
  - 270 vacío (mío): el nombre de la carpeta está cortado («azaren»). Repetido como 273 (unos 15 min).
  - R28 (proceso): el ciclo del PC recalculaba la prueba fuera de la cola y no atendió la cancelación 279 durante
    unos 50 min. Parada 16, arreglo (ahora encola) y reanudación 285 a las 06:19. Se perdió en total ~1 h de PC
    (Osaka 274, cortado).
  - Pruebas del PC: 1 fallo con el código 1258cc2 (05:20) que no se reproduce con ese código en la nube. La siguiente
    pasada del PC (446465f, 06:10-06:22) da 1178 bien y 0 fallos: cerrado; la auditoría 120 ya leerá esa pasada.
- **En marcha (07:30):** R26 por la cola del PC, de uno en uno: 119 Osaka (pasada fina 75 %; bola del partido seguida en
  17 de 17 min de juego, sin fallos C0/C1 en el registro) → 120 auditoría → 121 F3Set v17 (~5 h: el cambio de
  `io/video.py` invalida las ventanas) → 122 Pegula (~3,5-4 h) → 123 auditoría final. Cuando la cola quede libre, el PC trae
  el código nuevo y hace 286 (R29, minutos) y 124 (informe de la prueba). Fin previsto hacia las 18:00-18:30.
- **En la nube, en paralelo:** el análisis de la aplicación en la nube (#268, `docs/analisis_nube.md`, hecho), sin implementar
  nada; espera la decisión del usuario (reabre #145).
- **Cuánto falta para proponer los 6 partidos:** si R26 cumple todo, R29 (arreglo y prueba, ~1-2 h tras 286) y la previsión
  (R21) → el plan con su tiempo, hacia las 21:00 del 13-11. Los 6 partidos desde cero: 714 min de vídeo (Osaka 71, Sinner 71,
  Pegula 112 a 60 fps, Zheng 117, Gauff 133, la final 210), entre 2,2 y 3,3 veces el vídeo según lo medido (Osaka
  entrelazado, el más lento) → **~26-39 h, provisional** hasta la previsión. Si algo de R26 no cumple, otra vuelta de
  validación de 5-12 h antes.

**Qué queda de la Base, por tipo (13-11 09:15, #270)**
- **Grave (datos equivocados), en diagnóstico:**
  - R29: en Osaka, 8 de 140 tramos donde la ropa y los cambios de lado no coinciden. Si el marcador acierta, sus golpes están asignados a la otra jugadora.
  - «Misma ropa dentro de un juego» al 93 % apunta a que es la ropa la que se equivoca. 286 lo dirá.
- **Validación pendiente (no son fallos conocidos):** R26 con F3Set v17 (121, en curso), Pegula (122) y la auditoría final (123).
- **Lo arregla el propio análisis desde cero** (son resultados calculados con código viejo):
  - la pose en el contacto en 4 partidos (58-79 %);
  - los saques de 3 partidos en aviso;
  - los vídeos de revés y saque;
  - el «Tiempo desde cero».
- **Leve:**
  - 7 tomas de otra cámara sin recorte en Osaka (C2, `toma.sin_recorte`);
  - la memoria de la aplicación abierta (1,45 GB; P0);
  - Zheng sin torneo ni fecha (#258, P0);
  - la espera hasta empezar de algún trabajo (aviso de B8).
- **Medidas incorrectas:** ninguna conocida en la Base. Las medidas son M1-M7 (después); ninguna medida del cuerpo está validada con datos anotados (#12, nivel 4 = 0). Lo dice el informe.
- **Consumo medido del PC (`recursos/`, 13-11):**
  - en la pasada fina de Osaka, procesador al 76-82 % y memoria a 17,6-18,1 de 19,8 GB durante más de una hora; iGPU al 22-36 %;
  - en F3Set (09:10), procesador al 90-95 % y memoria a 18 GB.
  - El PC queda inutilizable durante los análisis; la memoria está al 91 %.

**Índice de documentos:** `docs/README.md` (cuál manda para cada cosa). **Guía de Ivanovic** (#143, #189-#198) y **matriz del
usuario de 15 puntos** (#84-#98): sus puntos son peticiones de los paquetes M1-M7 y P1, que van después de la Base.

**Plan a corto plazo: cerrar la Base.** Paquetes B1-B7 (ver la tabla automática) y **B8, orquestador único** (el actual).
Después (decisión del usuario, 11-11): **P0, rehacer la aplicación por completo**: primero el modelo de calidad (#256, el «cubo»:
dominio × calidad ISO 25010 × capa, con puntuación por casilla), después el análisis a fondo de lo actual y del estado del
arte, huecos y lo que sobra; diseño, prototipo, aplicación nueva (#252). Medio plazo = M1-M7 (medidas); largo = P1-P6 (el móvil, el último).
#253 hecha (11-11): la tabla «Notas históricas: dónde está cada pendiente», abajo; dos pendientes nuevos: #254 y #255.

**Resumen de la noche (11-11 22:30 → 12-11 06:45), con lo comprobado en el PC**
- **Revisión de la Base** (#260, `docs/revision_base_11-11.md`): 15 peticiones vuelven a PARCIAL; salen las tareas R1-R8.
- **R1 cerrada:** de las 550 comprobaciones de la auditoría real, ninguna de las pruebas principales de B1-B8 queda sin un caso que la haga fallar. Antes había 6, una de ellas siempre «ok».
- **R2:**
  - Prueba principal nueva, «Tiempo desde cero».
  - Mismo tramo que el 03-11: 49,4 min frente a 44-47,5 (≈ 4,9 h por partido). El vídeo de 60 fps de Pegula: 2,17 veces (≈ 7,6 h, bajo el límite de 8 h).
  - La bola del detector reutilizada: pasada fina −14 %, 42 de 43 golpes iguales; **pendiente de la verdad de F3Set** (peticiones 223 y 224).
- **R3 cerrada:** RTMW-x va un 3 % más lento en la pasada real, con los mismos golpes: se queda RTMPose-x. El primer A/B no lo probaba (fallo corregido). RF-DETR, no (2 golpes de 517). Candidatos de 2025-2026, apuntados.
- **R4 hecha:** detector frente a F3Set, 90 %; tipo de golpe, 97,3 % (derecha/revés) y 100 % (saques).
- **R5:** los vídeos exportados se reproducen (24 de 24). El esqueleto se buscaba en un momento sin pose; ahora mira 3 momentos. Se confirma en la próxima auditoría.
- **R6 hecha:**
  - Partido nuevo con la aplicación: **10b aceptada** (215: 78,7 min, identidad bien).
  - Rival, torneo, ronda y fecha salen del nombre del vídeo, también en ruso. A Zheng su nombre no le da torneo, ronda ni fecha (#258).
- **R7 hecha y vista en el PC:** el ejecutor arranca solo al siguiente con el código nuevo (1 s); las órdenes de la cola se atienden con código en espera.
- **R8 medida:** la aplicación abierta usa 1,45 GB en 8 procesos (límite 800 MB): falla; la aplicación de P0 debe cumplirlo.
- **Fallos encontrados y arreglados esta noche:**
  - el A/B de la pose ignoraba su configuración;
  - el registro no recibía los datos del catálogo;
  - el partido nuevo se juzgaba con peticiones ajenas;
  - «Tiempo desde cero» tomaba una ejecución vieja;
  - con la cola ocupada el PC no veía las peticiones;
  - una función nueva iba a cambiar la huella del detector (5-6 h de recálculo): evitado.
- **En marcha en el PC:**
  - 223, recuento de F3Set con el código de hoy, desde las 04:07; rehace la pose de los tramos, por eso tarda.
  - Detrás, 224: el mismo con la bola reutilizada.
- **Qué falta para la tarea 11 (análisis completo):**
  - decidir la bola reutilizada con 223/224;
  - una auditoría con R5 confirmado.
  - Previsión: 1,1-20,8 h. Lo que queda abierto de B4 (saques de Osaka, 76 %) y de B6 (datos del 09-11) se recalcula en ella.

**Paquete actual: B8 — tareas en orden**
| # | Tarea | Dónde se ejecuta | Validación | Estado |
|---|---|---|---|---|
| 1 | A: registro único de partidos | nube (código) | pruebas + `registro_partidos.json` en pc-logs | hecho |
| 2 | B: ejecutor único (`tennisbio worker`, `tennisbio jobs`) | nube | pruebas | hecho |
| 3 | D: el ciclo del PC y el chat por la cola única | nube + PC | petición 184 hecha por la cola en el PC | **aceptada** (11-11 12:35) |
| 4 | C: flujos (`config/flujos.yaml`) | nube + PC | petición 187: flujo «prueba» hecho en el PC | **aceptada** (11-11 13:01, 2/2 pasos) |
| 5 | E: la aplicación por la misma cola (detalle abajo) | nube | pruebas + capturas de su «Cola» en el PC | código hecho (11-11); captura en el PC con la petición 188 |
| 6 | Pegula sola por la cola (identidad v10 y saques con datos reales; no es el análisis completo) | PC, **en paralelo** con 5 y 7 | su auditoría (identidad ≥ 95 %, saques ≥ 85 %) | **aceptada** (11-11 17:09): identidad 98 % (marcador v9: juegos apilados en una caja), saques 88 %, 316 golpes |
| 7 | F: extremo a extremo automático (enviar como el chat, pausar con el código de la app, reanudar como el chat) | PC | `scripts/e2e_orquestador.py` (flujo «prueba_pausa»): acaba hecho, sigue en el paso cortado, no repite el primero | **aceptada** (11-11 17:19, petición 205: las 5 comprobaciones bien) |
| 8 | Todo el trabajo del PC por la cola única: completo, prevision, medir, rehacer y repetir encolan; las peticiones de cola se atienden aunque el ejecutor esté ocupado | nube + PC | una petición `control` atendida mientras Pegula se analiza | código hecho (11-11) |
| 9 | Documentos normalizados: índice `docs/README.md`, históricos marcados, `aplicacion_local.md` y la cabecera de la cola del PC al día | nube | — | hecho (11-11) |
| 10 | Continuidad sin el chat: avisos programados a esta sesión que retoman la cadena si una vigilancia muere | nube | un aviso que llega y sigue la tabla | **aceptada** (11-11: avisos de 60 min que retoman la cadena) |
| 10b | B7 (#242): un partido nuevo de principio a fin desde la aplicación, por el ejecutor único, sin el ciclo ni el chat | PC | auditoría «Aplicación: un partido nuevo de principio a fin», juzgado con las comprobaciones del propio partido (R6) | **215 (12-11 01:13)**: 78,7 min para 35 min, identidad bien, 40 derechas; ya no falla la etapa del rival. Lo que no pasa no es del partido: inicio de preparación en el 40 % de los golpes (medida, M1), dos registros antiguos sin final (app_cola.log, prueba_completo.log de la 181) y la comprobación que se mira a sí misma. **Auditoría real 217 (12-11 01:30): «Aplicación: un partido nuevo de principio a fin» ok** → **aceptada** |
| 10c | Velocidad (#259): tiempo de cada etapa desde cero y dónde se va | nube + PC | tabla de tiempos | **hecha (11-11)**: `capturas_diag/tiempos_etapas.md` (peticiones 208 y 210): 76 min para 35 min (2,2 veces el vídeo); pasada fina 43 % (pose 19 + 15 min, bola 11,5, pose de medida del fondo 10 min para 14 golpes, raqueta 8,7), detector 17 %, golpes dudosos 12 %; iGPU 99 %, procesador 30 %. Mismo tramo que el 03-11 (44-47 min) con el código de hoy: petición 211. Las alternativas se miden en R2 |
| 10d | Revisión de toda la Base (#260) | nube | veredicto por petición en `docs/revision_base_11-11.md` | **hecha (11-11)**: 78 peticiones: 43 válidas, 8 válidas con su prueba a cambiar, 15 vuelven a PARCIAL, 12 siguen abiertas; 83 de 544 comprobaciones sin un caso que las haga fallar. Salen las tareas R1-R8 |
| R1 | Toda comprobación con un caso que la haga fallar | nube + PC | 0 de las pruebas principales sin caso que falle; el total en la auditoría | **aceptada en la nube (12-11 01:45)** con la auditoría real del PC: 550 tipos de comprobación, **0 de las pruebas principales de B1-B8 sin caso que falle** (antes 6: «Tiempo», «Tomas de cámara», «Golpes que fallaron», «Nada pide revisión manual», que era siempre ok, «Exportación» y F3Set); fuera de ellas, 62 sin prueba y 18 que nunca fallan, que se irán cerrando con sus paquetes. En el PC lo dirá «Comprobaciones que saben fallar» tras sus pruebas de fondo |
| R2 | B1: «Tiempo» solo con ejecuciones desde cero; alternativas medidas | nube + PC | desde cero ≤ 8 h por partido de 3,5 h; cada alternativa adoptada o descartada con su medida de calidad | **cerrada (12-11 09:28)**: «Tiempo desde cero» en el PC: 7,6 h en el peor vídeo (Pegula 60 fps, 2,16 veces; la final 1,41). Alternativas: (1) bola del detector reutilizada: −14 % de pasada fina, pero en F3Set 460 de 517 frente a 465 (5 saques menos), precisión 0,943 frente a 0,945 e instante 0,03 frente a 0,02 s → **no** (pierde calidad); (2) RTMW-x: 3 % más lento → no; (3) pose de medida del fondo limitada al impacto: ≤ 5 % con riesgo para sus medidas → no; (4) mitad de fotogramas (10-11) → no. Queda la mejor sin pérdida de calidad medida |
| R3 | B3: RF-DETR medido en la pasada real; RTMW resuelto; candidatos de 2025-2026 | nube + PC | decisión por «calidad antes que velocidad» con su medida | **RF-DETR resuelto con datos (11-11)**: en F3Set no encontrar a la jugadora del fondo pierde 2 de 517 golpes (pasos «lejana_no_encontrada»): sus +10 puntos de detección cambian como mucho esos 2, a 2,6 veces su coste: se queda YOLO. **RTMW**: A/B desde cero en el PC con `bench_fine_fps.py --tag rtmw --set fine_pass.refine=rtmw-x` (tras la petición 215). **Candidatos 2025-2026** (`docs/revision_base_11-11.md`, §R3): TrackNetV4 y TOTNet para la bola, a medir cuando haya pesos de tenis (si no, entrenarlos con los datos del PC); T-DEED y UMEG-Net para los golpes, más adelante (la pérdida que queda es sobre todo «fuera de cámara»). **A/B de RTMW (219) no válido**: B igual a A hasta el último decimal porque la pasada fina construía el modelo de pose con la configuración del fichero y no con la de la prueba (`clip_pipeline.run_clip`, corregido con `pose_cfg` y su prueba que falla sin el arreglo); repetido como petición 222: **A/B válido (12-11 04:06, 15 min de Pegula desde cero): RTMW-x un 3 % más lento en la pasada fina (1257 → 1298 s), los mismos 43 golpes, medidas a ≤ 0,14 de su dispersión → se queda RTMPose-x** (confirma la pasada real del 03-11; el banco aislado del 07-11 solo medía el modelo). R3 **cerrada** |
| R4 | B4: prueba principal con el detector actual frente a F3Set; «Tipo de golpe frente a F3Set» (≥ 95 %) | nube | en la auditoría con su caso que falla | **código hecho (11-11)**: «Golpes encontrados frente a F3Set (detector del análisis)» (≥ 85 %; hoy 466 de 517, 90 %) y «Tipo de golpe frente a F3Set» (derecha/revés 327 de 336, 97,3 %; saques 129 de 129) en la prueba principal de B4 en lugar del camino antiguo; #151 la usa. Falta verlo en la auditoría del PC |
| R5 | B5: cada vídeo exportado se reproduce, dura lo de su ventana y lleva el esqueleto | nube + PC | comprobación con su caso que falla | **código hecho (11-11)**: «Vídeos exportados: <carpeta>»: 8 vídeos repartidos de cada exportación, formato del navegador, 2-60 s y los colores del esqueleto en un fotograma (≥ 75 % de la muestra); en la prueba principal de B5 y en #41. Auditoría 217: los vídeos se reproducen con su duración (24 de 24), pero el esqueleto salía en 6, 3 y 4 de 8: se miraba a los 0,5 s y la pose solo se calcula cerca del impacto; ahora mira 3 momentos del vídeo. Se confirma en la próxima auditoría **12-11**: no era la comprobación: esos vídeos no tienen esqueleto porque su golpe no tiene pose en el contacto → R10 |
| R6 | B7: mismas etapas en la aplicación que en el ciclo; registro real con rival, torneo, ronda y fecha (con #258); registros en escritura no suspenden; el partido nuevo se juzga con sus comprobaciones | nube + PC | app_nuevo sin fallos propios; registro real con los campos llenos | **código hecho (11-11)**: la etapa del rival solo se exige cuando corrió (en la aplicación es un trabajo aparte); un registro de PowerShell aún en escritura no suspende; el partido nuevo se juzga con sus propias comprobaciones (ficheros, errores, identidad y golpes del partido), no con las 20 peticiones fuera de la Base; comprobación nueva «Lista de partidos: rival, torneo, ronda y fecha» sobre el registro real; `tennisbio.match_name` lee esos datos del nombre del vídeo (los 6 del PC, también los rusos) y el catálogo rellena solo lo vacío (peticiones 213 y 214). Zheng no dice torneo, ronda ni fecha en su nombre: queda para #258. Falta: app_nuevo otra vez y verlo en el PC |
| R7 | B8: el ejecutor se reinicia solo con el código nuevo; comprobaciones «Orquestador: …» | nube + PC | 0 min sin ejecutor tras un reinicio; prueba principal de B8 medida | **código hecho (11-11)**: el ejecutor que se cierra por código nuevo suelta el bloqueo y arranca él mismo el siguiente (antes esperaba al ciclo: 18 min parado); comprobaciones «Orquestador: prueba de extremo a extremo», «… ejecutor vivo cuando hay trabajo» y «… espera hasta empezar cada trabajo» (≤ 5 min; con los datos del 11-11 sale el trabajo 54, 10,5 min); #246, #249, #237 y #119 las usan. Falta verlo en el PC tras el próximo reinicio. **12-11**: con la cola ocupada y código nuevo en espera, el ciclo no veía ninguna petición (no actualiza el repositorio con un trabajo en marcha): las peticiones esperan, como deben, para correr con ese código, pero las órdenes de la cola (pausar, reanudar, cancelar) ahora se leen de lo descargado y se atienden al momento **12-11 11:00**: el ejecutor murió sin rastro mientras corría Osaka (lo había arrancado su predecesor con la salida tirada) y el ciclo de Windows, esperando código nuevo hasta 45 min, no lo volvió a arrancar: 4 trabajos esperando. Arreglo: su salida y los errores de su bucle a `datos/trabajos/ejecutor.log`; un error del bucle (base de datos ocupada...) se apunta y se reintenta en vez de matarlo; el ciclo que espera comprueba el ejecutor cada 5 min. La comprobación «Orquestador: ejecutor vivo cuando hay trabajo» lo habría marcado |
| R8 | B2: lo que consume la aplicación en el PC | PC | medida y comprobación en la auditoría | **código hecho (11-11)**: `scripts/app_recursos.py` abre la ventana sin cola, mide 1 min CPU y memoria de su proceso y sus hijos (WebView2) y la cierra; comprobación «Aplicación: lo que consume abierta» (CPU media ≤ 5 %, memoria ≤ 800 MB), en #225. **Medido (petición 218, 12-11 01:26)**: CPU media 0,03 % (máx 0,06 %), **memoria 1,45 GB en 8 procesos** (objetivo ≤ 800 MB): la comprobación falla. Con el PC a 18 de 20 GB durante un análisis, importa. #225 sigue PARCIAL; la aplicación nueva de P0 debe cumplir el límite (se mide igual) |
| R9 | **Regresión de identidad** (12-11): el recuento de F3Set con el código de hoy (223) da 353 de 517 golpes (68 %, el 08-11 90 %) con 124 dudosos, 122 de la compilación de Azarenka: el control de la ropa (v9, hecho para Pegula) la descarta cuando no sigue los cambios de lado del marcador (54 %), y en una compilación el marcador es lo que falla. Identidad v13: los saques vistos deciden (si la ropa explica ≥ 85 % de ≥ 8 votos, son dos personas). Regla nueva: ningún cambio de identidad se da por bueno sin F3Set y los partidos | nube + PC | recuento 228 (≥ 85 % y la identidad bien frente a F3Set) y Pegula sigue ≥ 95 % (229-230) | **F3Set con v13 (228, 12-11 08:46): 465 de 517 (89,9 %; el 08-11 466), dudosos 6, precisión 0,945, identidad 489 bien y 5 mal de 494, Azarenka 138 de 154 (antes 26)**; **Pegula con v13 (229-230): identidad 98 % (313 de 320), saques 88 %** → **aceptada** |
| R10 | **Golpes sin su pose en el contacto** (12-11, hallado por R5): en los análisis de la biblioteca (09-11) el 15 % de sus derechas cercanas, el 21 % de los reveses y el **41 % de los saques** se guardan sin ningún punto de su pose a ±0,3 s del impacto (sin medidas del cuerpo; el vídeo exportado sin esqueleto). En los análisis anteriores (carpetas planas) ninguno: son sobre todo los golpes que añadió B4 desde el detector y el marcador (la final: 25 saques cercanos con pose → 50, 28 sin pose). La auditoría los daba por válidos. Comprobación nueva «Golpes con su pose en el contacto» (≥ 95 % de los cercanos; en la prueba principal de B6). **Causa (237)**: la ventana empieza en otra toma (un primer plano de 950 px), el seguimiento arranca en esa persona y no vuelve a ella cuando vuelve la cámara principal, aunque la pose la ve (1 persona de 210 px en el contacto). **Arreglo**: si su seguimiento está vacío a ±0,3 s de un golpe y la pose ve a la jugadora cercana (sin primeros planos), se la sigue desde ahí hacia los dos lados, solo en el hueco (`clip_pipeline.refind_at_targets`). En el PC: Osaka (238), recuento (239), F3Set (240), auditoría (241) | nube + PC | ≥ 95 % de sus golpes cercanos con pose en el contacto en los 6 partidos, sin perder los golpes de B4 | **validado en Osaka (241, 12-11 11:32): cerca 90 de 90 (antes 54 de 93)**; F3Set igual (240: 465 de 517, precisión 0,945, error de instante 0,02 s). Los otros 4 partidos (58-79 %) se rehacen en la tarea 11 |
| R11 | **Saques de Osaka** (12-11, la auditoría de 241): 27 de 36 puntos de su saque con su saque (75 %; objetivo ≥ 85 %, fallo conocido de B4 desde el 08-11). **Causa (243, `scripts/diag_saques.py`, hojas de fotogramas)**: 8 de los 9 puntos no eran de su saque: en los juegos 2, 6, 10 y 12 saca Osaka (icono de saque en su fila, saca ella en la imagen) y el marcador se leyó como saque de Rybakina. La marca de color se leyó en 57 lecturas (100 % bien); el resto lo puso el marcador aprendido, que acierta el 87 %: juegos enteros al revés. **Arreglo**: marcador v10, quién saca en cada juego por la regla del tenis (el saque alterna cada juego): un primer saque por set votado por todas sus lecturas (`scoreboard.by_alternation`; sin cambio si no es claro, ≥ 60 %; el tie-break conserva la marca). Residuo real: 1 punto (64,2 min): su primer saque justo después de un fundido no lo ve el detector y el segundo queda dudoso (identidad del tramo sin decidir) | nube + PC | Osaka ≥ 85 %, Pegula con identidad ≥ 95 % y F3Set sin perder golpes ni identidad, con la versión final | v10 en Osaka (245): 43 lecturas corregidas y 49 completadas, pero el primer saque se votó por lecturas y ganó con solo el 61 %; **v11**: un voto por juego y, dentro de cada juego, manda la marca de color si se ve (en Osaka acierta el 100 %). **Osaka con v10 (248): 24 de 25 puntos de su saque con su saque (96 %, antes 75 %)**; 4 «saques» falsos menos (restos suyos que la regla del saque convertía en saques en los juegos de Osaka leídos al revés); pose en el contacto 88 de 88. 246-247 cancelados (249-250). Validación de v11 en cola: Osaka (251), Pegula (252), F3Set (253), auditoría (254). **v11 validado**: Osaka primer saque claro en 15 de 15 juegos; Pegula identidad 313 de 320 (igual); **F3Set 467 de 517 (antes 465), precisión 0,945, identidad 489 bien y 5 mal (igual)**. **Pero** la auditoría 254, con la comprobación ampliada (R11b: también el final de cada juego y el principio del siguiente), da 80-83 % en los 5 partidos de Rybakina (Osaka 29 de 36: dentro de cada juego 24 de 25, en los cambios de juego 5 de 11): las reglas que recuperan saques no miran los cambios de juego. Fallo conocido de B4, bloquea la tarea 11. Diagnóstico 257-258. A mirar también: «misma ropa dentro de un juego» de Osaka 94 % (objetivo 95 %) |
| R12 | **Ventana vacía de PowerShell en el PC** (12-11, petición del usuario): 242 la identifica: Windows Terminal titulado «.venv\Scripts\python.exe», abierto a las 11:08:21, el segundo en que el ejecutor arrancó a su sucesor. Causa: el sucesor (R7) y la aplicación lo arrancaban con DETACHED_PROCESS, con el que Windows ignora CREATE_NO_WINDOW; el lanzador del venv no tenía consola y el intérprete real recibía una nueva, visible. Arreglo: `orchestrator.background_kwargs` (consola sin ventana, nunca DETACHED) y un ejecutor que se encuentra solo en una consola propia se reabre oculto y termina (`leave_visible_console`, una sola vez) | nube + PC | 244 (`ventanas_visibles`) sin la ventana | **comprobado en el PC (12-11 12:00)**: ninguna consola en la pantalla tras el reinicio del ejecutor (a las 11:40 seguía Windows Terminal «python.exe» desde las 11:08); el ciclo repite la lista en cada pasada y la auditoría la comprueba (#261) |
| R13 | **Registro de versiones de las etapas** (12-11, visto al revisar R11): el registro que obliga a subir la versión de una etapa cuando cambia su código (`config/stage_code.json`) solo miraba su función y lo que importa ella misma, no las auxiliares que llama: `candidatos → add_serve_candidates → point_count.her_serve_points` podía cambiar sin aviso y dejar candidatos viejos por buenos. Ahora cuenta todo lo que la etapa alcanza en `stages.py` y los módulos que eso importa (`stage_code.reachable`); el registro se rehízo con las mismas versiones (no recalcula nada) | nube | prueba con una auxiliar editada | **hecho** |
| R11b | **La comprobación de saques miraba solo parte de sus puntos** (12-11): en Osaka 36 de los 62 puntos de su saque; no contaba el último punto de cada juego ni el primero cuando el 0-0 no se lee (y en los juegos 9 y 13 no se leyó quién sacaba: v10 los completa). `serve_gaps` cuenta ahora esos tramos (`game_change_servers`); las reglas que convierten su primer golpe en saque siguen dentro de cada juego (cruzando juegos podría entrar el primer punto de la rival si su 0-0 se lee tarde) | nube + PC | auditoría tras 248 con el código nuevo | hecho en la nube; se ve en el PC tras 248 |
| R14 | **Nada reutilizado de otro código** (12-11, #263, pregunta del usuario «¿está todo versionado?»): quedaban tres cachés guardadas sin la huella del código que las hizo: la pose, la bola y la raqueta de cada ventana (solo modelos y ajustes), la bola del partido (`ball_track.npz`, sin ninguna huella: se reutilizaba siempre) y los vídeos exportados (no miraban el código que dibuja). Ahora llevan la huella de su código (`stages.WINDOW_CODE`, `stages.ball_track_key`, `pipeline.function_fingerprint`, firma de `export.encode_stroke`) | nube | pruebas: cada caché hecha con otro código se calcula de nuevo | **hecho** |
| R15 | **Ejecución desde cero** (12-11, #263): `tennisbio desde-cero` mueve lo calculado de cada partido a `<biblioteca>/archivo/desde_cero_<fecha>/` (no se borra nada) y deja solo la ficha (partido.json), su clic de identidad y el vídeo si vive en la carpeta; flujo `desde_cero` = eso + el flujo completo. Sin `--ejecutar` solo dice qué movería | nube + PC | simulación en el PC (255) | hecho; **la ejecución real solo con la aprobación del usuario (#262)** |
| R16 | **Saques en los cambios de juego** (12-11, B4, tras la comprobación ampliada: 80-83 % en los 5 partidos). Diagnósticos 257-260: (a) la pista no se encuentra unos segundos bajo un rótulo o al final de un plano corto y esos segundos quedaban «sin juego»: el detector no veía nada (64:17 y 33:04 de Osaka) → `play_mask` rellena huecos ≤ 6 s dentro de un plano de la cámara principal con pista (jugadores v5, marcador v12, bola con la huella de `play_mask`); (b) el detector no da su saque cercano en algunos puntos aunque la ve bien colocada (34:56 y 35:24: es ella, en la marca de saque); dentro de cada juego las reglas lo rescatan, en los cambios de juego no miraban → `her_serve_points` también al final de su juego, como mucho 45 s desde su último marcador (candidatos v16); (c) Pegula: saques del fondo que el detector ve y la pasada fina descarta (no encuentra a la jugadora lejana): limitación conocida del lado lejano (08-11), dicha en el informe | nube + PC | F3Set sin perder golpes ni precisión, Osaka y Pegula ≥ 85 % con la comprobación ampliada | código hecho; Osaka (261) y Pegula (262) rehechos, pero con el detector sin la bola (R17): se repiten con R17 · **264 (13-11 00:39)**: saques por punto de su saque Osaka 89 % (33 de 37) y Pegula 85 % (53 de 62), pose en el contacto 100 % en los dos (sin la bola todavía) · **F3Set v16 (263, 13-11 00:33, 5 h: jugadores v5, bola y ventanas con la huella de su código)**: 465 de 517 (v15 467), precisión 0,936 (v15 0,945; 24 falsos frente a 20), dudosos 4 (6) → **no cumple «sin perder precisión»**: R22 |
| R17 | **El detector de golpes iba sin la bola en todos los partidos de la biblioteca** (12-11, visto en el registro de Pegula: «la bola del partido se calcula de nuevo» y «bola 0 s»). `ball_features.cached_track` leía `scenes.json` y `court.json` en la raíz de la carpeta del partido; en la biblioteca viven en `etapas/`, así que la bola del partido salía vacía y sus 8 columnas del detector iban a cero. El detector se entrenó y se valida en F3Set (carpetas planas) con la bola: precisión 0,945 y 467 de 517 golpes; en los 6 partidos reales trabajaba sin ella desde que existe la biblioteca (ningún registro de un partido tiene la línea «bola: … min de juego» y todas las detecciones dicen «bola 0 s»). Posible causa también de R16(b) (saques cercanos con probabilidad 0 aunque se la ve en la marca de saque). **Arreglo**: se lee donde el partido los guarda (`match_files.at`); sin `scenes.json` es un error; una bola vacía nunca se reutiliza; la huella de la bola del partido sigue a `cached_track` y lo que alcanza; el detector (v2) dice cuánta bola tuvo y se para si cubre menos del 25 % del juego; comprobación nueva «La bola del partido para el detector» (≥ 90 % del juego) | nube + PC | Osaka y Pegula con la bola (≥ 90 % del juego) y sin perder golpes, saques ≥ 85 %; F3Set igual (no le afecta: carpetas planas) | código hecho · **Osaka con la bola (265, 13-11 00:40-04:03, 3 h 23 min)**: detector 28 min (antes 1,6, sin la bola), pasada fina 2 h 39 min (232 ventanas nuevas, 40 s por golpe: el detector con la bola propone otras ventanas y Osaka es entrelazado, 50 campos/s); resultados en la auditoría 108. Pegula (266) cancelada (271): se valida en R26 con el código final |
| R18 | **Ningún dato que falta se vuelve «vacío» en silencio** (#264, 12-11): revisar cada etapa y cada lectura de un fichero del partido; donde la falta de una entrada se convierte en una lista vacía, ceros o «sin dato» y el análisis sigue, pasa a ser un error o una comprobación de la auditoría | nube | lista de sitios revisados con su decisión; una prueba por cada cambio | **hecha (12-11)**: (1) lecturas que se saltan la carpeta del partido: solo la de R17 (las demás uniones directas son de carpetas planas antiguas o de pruebas); (2) las 21 lecturas «si existe, si no vacío» de `stages.py` son salidas de etapas declaradas como dependencia (la ejecución las hace antes y comprueba que existen): se quedan; (3) modelos que, si fallan, ceden a otro método: TransNetV2 → histogramas (ya en el resumen), pista de 14 puntos → búsqueda de líneas (solo se imprimía: ahora la pista v6 lo guarda en su resumen), MotionAGFormer y tamaño de personas (en el registro por ventana): los dos primeros entran en «Entradas de los modelos»; (4) lecturas de fotogramas clave que fallan → fotogramas exactos (mismos fotogramas, más lento): se quedan |
| R19 | **Cobertura de cada entrada de los modelos en los partidos reales** (#264): pose, pista, audio, marcador y bola (R17) con su cobertura en la auditoría por partido | nube + PC | comprobaciones con su caso que falla; ok en Osaka y Pegula | **código hecho (12-11)**: «Entradas de los modelos: <partido>» (cortes con TransNetV2, cámara principal ≥ 10 % del vídeo, pista ≥ 50 % y con el detector de 14 puntos, sonido ≥ 5 golpes/min, marcador con quién saca ≥ 50 %, cada jugadora vista ≥ 25 % del juego por el detector v2) y «La bola del partido para el detector» (R17). Con los manifiestos actuales: todas las entradas presentes en los 6 partidos; falta lo que vio el detector de cada jugadora (análisis anteriores). Umbrales de entrada rota, no de calidad. En el PC: 267 |
| R20 | **La misma etapa da lo mismo en la biblioteca que en una carpeta plana** (#264): prueba que pasa la pasada barata, el detector y los candidatos por las dos estructuras y exige el mismo resultado (F3Set valida carpetas planas; los partidos corren en la biblioteca) | nube | la prueba falla con el fallo de R17 y pasa con su arreglo | **hecha (12-11)**: `tests/test_library_same_as_flat.py` (detector con la bola y candidatos en las dos estructuras: mismos golpes, misma bola, mismos resúmenes); con el fallo de R17 puesto a propósito la prueba falla (bola de 250 muestras frente a ninguna) |
| R21 | **La previsión de tiempo no distinguía la versión de cada etapa** (12-11, visto con la bola de R17): los ritmos guardados (`ritmos.json`) no decían con qué versión de la etapa se midieron y la previsión tomaba el más rápido; el detector medido sin la bola del partido (1,4 s por minuto de vídeo) habría pasado por el detector con ella (el modelo de la bola sobre todo el juego: en F3Set, 4 compilaciones, ~4 h frente a 25 min de la v15). Ahora cada ritmo lleva la versión de su etapa; solo cuentan los de la versión de ahora y una etapa medida solo con otra lo dice («medido con otra versión») y se mide antes, sola | nube | pruebas de `tests/test_budget.py`; la previsión del análisis desde cero con el detector medido con la bola en Osaka y Pegula (265-266) | código hecho (12-11); la previsión, tras 265-266 |
| R22 | **F3Set v16 pierde 0,9 puntos de precisión y 2 golpes** (13-11; código de R14 + R16, sin R17). Golpe a golpe (497 anotados de las 3 compilaciones válidas): gana 4 que v15 perdía (sin seguimiento 10 → 3, el relleno de huecos de pista de R16) y pierde 8: 3 de un mismo punto de Azarenka que pasa a la otra jugadora (identidad) y 5 de la jugadora del fondo (3 no propuestos por el detector, 2 no confirmados); 4 golpes falsos más (Azarenka +1, Sabalenka +3). La evaluación no decía cuáles eran los falsos: ahora los lista y marca si caen en un hueco de pista rellenado (`recall_eval.filled_court_gaps`) | nube + PC | 268-269 (v15 y v16 evaluados otra vez, sin ejecutar nada) y 270 (los tramos de identidad decididos al revés): causa de cada pérdida → arreglo o motivo medido | **causa encontrada y arreglada (13-11)**: 268-269 (evaluación de nuevo): de los 8 falsos nuevos solo 1 cae en un hueco de pista rellenado y los perdidos caen en ellos como antes (7 de 48 frente a 8 de 44): el resto es dispersión del detector con entradas nuevas (bola recalculada, jugadores v5). 273 (identidad): el punto de Azarenka pasa a la otra jugadora porque su tramo empieza 6,6 s antes (fotograma 10959 en vez de 11025) y su ropa mezcla a dos personas (margen 0,28 frente a 0,55): `play_mask` también rellenaba el principio de un plano antes de que aparezca la pista (el fundido del plano anterior), algo que R16 ni diagnosticó ni probó (sus casos de Osaka tenían la pista desde el primer fotograma del plano). Arreglo: solo huecos después de encontrar la pista (dentro del plano o a su final); jugadores v6, marcador v13; prueba nueva. Se valida en R26 (280-284) · **13-11 13:23, F3Set v17 (121): NO arreglado.** v17 sale igual que v16 golpe a golpe (0 cambios en los 648 anotados): 465 de 517, precisión 0,936; v15 dio 467 y 0,945. El punto de Azarenka sigue en la otra jugadora. Causa probable, no comprobada: en ese plano la pista se encuentra en sus primeros fotogramas, durante el fundido que aún enseña la pista del plano anterior; después se pierde unos segundos y vuelve. El hueco queda «después de encontrar la pista» y se sigue rellenando. El arreglo solo miraba un plano sin pista al principio, y su prueba usaba ese caso, no el real. Diagnóstico 287 (`scripts/diag_play_mask.py`): cada hueco rellenado con la pista que lo rodea, la tira fotograma a fotograma del punto de Azarenka y los huecos de Osaka y Pegula que R16 debe conservar. Se ejecuta cuando la cola quede libre (~18:00). Después: el arreglo con el caso real y F3Set v18 · **Arreglo (13-11 tarde, aprobado por el usuario, #274):** un hueco se rellena solo si la pista se ha visto 0,5 s seguidos justo antes (`COURT_STEADY_S`). TransNetV2 corta un fundido cerca de su mitad, así que el plano nuevo empieza con la segunda mitad del fundido (unos fotogramas con la pista de la imagen anterior). Los huecos de R16 tenían más (Osaka 64:14, 1,1 s). Jugadores v7 y marcador v14; prueba con el caso del fundido. El diagnóstico 287 compara la regla de antes y la de ahora en F3Set, Osaka y Pegula. F3Set v18 en la cola (288), justo detrás de 286 y 287; si 287 enseña que el fundido de Azarenka tenía más de 0,5 s de pista, o que se pierde un hueco de R16, se cancela y se ajusta |
| R23 | **#265 (1/4) Mecanismo de fallos por niveles** (aprobado el 13-11): catálogo `config/fallos.yaml` (cada modo de fallo con su nivel, efecto, cómo se detecta, reacción, presupuesto y prueba), `tennisbio/faults.py` (`fault(código, detalle)`: C0 para el partido y no se publica; C1 se marca y el análisis completo no se acepta; C2 se aísla con presupuesto y sube a C0; C3 reintento limitado; C4 solo registro), registro por etapa en el manifiesto y en `fallos.json`, contratos de datos al terminar cada etapa, comprobación «Fallos por niveles» (puerta) | nube | pruebas de inyección: cada nivel reacciona como dice el catálogo | **hecha (13-11)**: `config/fallos.yaml` (66 modos de fallo con nivel, efecto, detección, reacción y prueba), `tennisbio/faults.py`, colector por etapa (`manifest[etapa]["faults"]`) y por orden (`<salida>/fallos/<orden>.json`), los C0 en `fallos.json`, presupuestos (ventanas 2 %, medidas por golpe 10 %, vídeos exportados 5 %), puerta «Fallos por niveles» por partido, por orden y de la propia auditoría (✘ con un C0 sin resolver o un C1); 79 pruebas en `tests/test_faults.py` |
| R24 | **#265 (2/4) Ningún `except` sin clasificar**: los 323 sitios, módulo a módulo (primero el análisis: etapas, pasada fina, vídeo, modelos; después orquestador, biblioteca, auditoría, aplicación); cada uno relanza, llama a `fault()` o es un resultado esperado con su motivo escrito (`# esperado: …`) | nube | prueba que recorre el código: 0 sin clasificar; cada código usado está en el catálogo y cada entrada del catálogo se usa y tiene su prueba | **hecha (13-11)**: los 323 clasificados (0 sin clasificar). Cambios de comportamiento: falta el modelo de la bola → C0 (antes un aviso); detector sin la bola → C0; salida de una etapa de la que se depende ausente o dañada → C0 (antes lista vacía); modelos alternativos (TransNetV2, pista de 14 puntos, MotionAGFormer, raqueta, 3D, OCR) → C1; un partido del registro omitido o sin vídeo → C1; una comprobación de la auditoría que no puede calcularse → «falta» (antes «aviso») |
| R25 | **#265 (3/4) Contratos por etapa con sus umbrales** (lo que hoy mira la auditoría después: cámara principal, pista, sonido, marcador, jugadoras vistas, bola, pose en el contacto) comprobados al terminar cada etapa: vacío = C0, por debajo del mínimo = C1 | nube | una prueba por contrato que lo incumple | **hecha (13-11)**: `tennisbio/contracts.py` (probe, escenas, pista, sonido, marcador, detector, pasada fina; los mínimos de `audit.INPUT_FLOORS`), aplicados por `pipeline.run_stage` al terminar cada etapa; 13 casos que los incumplen y uno que los cumple en `tests/test_faults.py`. En los partidos reales no cambian nada (la última auditoría: todas sus entradas por encima de los mínimos) |
| R26 | **#265 (4/4) Validación en el PC de todo junto** (R17 + R22 + #265): Osaka, Pegula y F3Set con el código final; previsión de los 6 partidos (R21) | PC (~9-10 h: el cambio de `io/video.py` invalida las cachés de las ventanas, como cualquier código nuevo; 274-278 cancelada (279) por el arreglo de R22; **encolada de nuevo con él el 13-11 como 280-284**: Osaka, auditoría, F3Set v17, Pegula, auditoría final) | F3Set sin perder golpes ni precisión frente a v15, Osaka y Pegula ≥ 85 % de saques y la bola ≥ 90 % del juego, 0 C0 y 0 C1 en «Fallos por niveles» | **en marcha** (13-11 06:19) · **Osaka cumple (119-120, 08:21)**: 0 C0 y 0 C1 (C2: 7 tomas de otra cámara sin recorte, `toma.sin_recorte`; audio, pista, probe y escenas reutilizadas de antes del 13-11, sin registro de fallos), saques por punto de su saque 90 % (35 de 39), pose en el contacto 123 de 123, bola seguida en 17 de 17 min de juego, entradas de los modelos bien, 226 golpes (dentro de lo esperado por el marcador), pruebas del PC 1178 bien y 0 fallos (446465f). Queda la identidad en aviso («misma ropa dentro de un juego» 93 %): R29 · **F3Set v17 (121, 13:23): no cumple** (465 de 517 y 0,936 frente a 467 y 0,945 de v15; igual que v16 golpe a golpe): R22 sigue abierto · **Pegula cumple (122-123, 18:32)**: saques por punto de su saque 94 % (59 de 63), identidad 98 % y «misma ropa dentro de un juego» 95 %, pose en el contacto 206 de 207, bola 36 de 36 min, entradas bien, ningún C0 ni C1 · Queda R22 (F3Set v18, 288, en curso desde ~18:45) y R30 |
| R27 | **La jugadora lejana en los rasgos del detector** (13-11, auditoría 108 de Osaka: «jugadora lejana vista solo en el 0 % del juego»; con el contrato de R25 habría parado el partido). Diagnóstico 272 (`scripts/diag_entradas.py`): ~0,1 % en los 6 partidos **y también en las 4 compilaciones de F3Set** donde se entrenó y se valida el detector; la pasada barata ve una persona por fotograma (1,0-1,5 cajas: la cercana). **No es un desajuste como R17**: el detector nunca la tuvo y encuentra sus golpes por la bola y el sonido. El mínimo del 25 % que le puse en R19 y el C0 de R25 estaban mal: quitados (se informa, no se exige); la cercana sigue exigida (≥ 25 %). Ampliación posible (no ahora): verla en la pasada barata daría al detector más del lado lejano | nube + PC | pruebas de la auditoría y del contrato con la lejana al 0,1 % | **hecha (13-11)** |
| R28 | **El ciclo del PC trabajaba fuera de la cola única** (13-11, visto al cancelar con 279): al traer código nuevo, el propio ciclo recalculaba las medidas de la prueba `_smoke` (con el código de #265 sus cachés de ventanas eran nuevas: más de una hora), compartiendo la iGPU con el trabajo de la cola y, mientras tanto, sin leer las órdenes de la cola (la cancelación esperaba) ni las peticiones (se ponen en la cola después del recálculo). Va contra el orquestador único (CLAUDE.md). **Arreglo**: `auto_cycle.py decide` pone en la cola el flujo `medidas_prueba` o `informe_prueba` (config/flujos.yaml) con prioridad 9, detrás de lo pedido, y el ciclo no ejecuta nada él mismo; `jobs submit --prioridad`. Parada 16 para cortar el recálculo en marcha y Osaka con el código anterior; 285 reanuda la cola | nube + PC | pruebas de `tests/test_auto_cycle.py`; en el PC: tras traer este código, 280-284 en la cola sin esperar a ningún recálculo | código hecho (13-11) |
| R29 | **Identidad con el clic cuando la ropa y los cambios de lado no coinciden** (13-11, auditoría 108 de Osaka: «misma ropa dentro de un juego» 93 %, objetivo 95 %; ropa y cambios de lado de acuerdo en 125 de 133 planos). Con el clic, `identity.apply_pick` decide por el grupo de ropa cada plano con ropa clara (margen ≥ 0,08) sin mirar los cambios de lado: en esos 8 planos, si el marcador acierta, sus golpes serían de la otra jugadora. F3Set no lo puede decir (sus compilaciones no tienen cambios de lado; allí «ropa + clic» acierta 274 de 279). Diagnóstico 286 (`diag_identity.py --conflictos`): los fotogramas enteros de esos planos con lo que dice cada señal, para decidir con la verdad a la vista qué señal manda cuando discrepan (o marcarlos como dudosos) | nube + PC | quién acierta en los planos en desacuerdo; después el arreglo y su prueba | **resuelto sin cambio de regla (13-11 18:42, diagnóstico 286)**: los planos en desacuerdo son Osaka 8, Zheng 10, Gauff 7, la final 12 y Pegula 0. En las hojas de fotogramas **la ropa acierta casi siempre**: en Osaka amarillo frente a blanco, y en la final naranja (Sabalenka) frente a amarillo y negro (Rybakina). Lo que falla es el recuento de cambios de lado del marcador, que lee mal los juegos; dar prioridad al marcador empeoraría. Solo un caso dudoso con margen medio (Osaka 714 s, 0,36). Los errores que sí hay son otros partidos y un estudio de televisión dentro de la retransmisión: R30 |
| R30 | **Otros partidos dentro de la retransmisión** (13-11, hallado con 286). En Zheng, a los 77 min (4628 s), Shelton – Alcaraz; al final de la final (12203-12217 s), un dobles (las Williams contra Chan y Joint); en la final, a los 11586 s, un estudio con el partido en una ventana. La identidad los decidió como partido de Rybakina (márgenes de ropa 0,08-0,13): golpes de otras personas que se le atribuirían. Puede que la regla de las repeticiones ya los quite (un plano en que el marcador nunca se lee con sus nombres cuenta como repetición «sin marcador»); hay que verlo con datos | nube + PC | diagnóstico 290 (`scripts/diag_otros_partidos.py`): minutos de planos sin su marcador, golpes suyos y planos de identidad en ellos, y lo que quedó en esos segundos → arreglo (excluir los planos sin su marcador y las personas que no se parecen a ninguna de las dos) con su prueba y su F3Set | diagnóstico en la cola, detrás de la v18 (~23:30) |
| R31 | **Identidad: caída con pocos cambios de lado y ningún saque visto** (14-11, prueba corta de Osaka en la nube; fallo del código, también en el PC: con el partido entero no se daba). `clothes.groups_check` | hecho (`tests/test_identity_photos_check.py`); validado en Osaka, Pegula y Zheng en la nube |
| R32 | **Marcador: el nombre de la rival como lo escribe la tele** (14-11, Zheng en la nube: 0 lecturas). Se buscaba la última palabra del catálogo («Qinwen») y la tele pone ZHENG; igual con «Zverev Alexander» y «Sobolenko». También fallaría hoy en el PC (su catálogo ya tiene el rival). Marcador v15 | hecho (`tests/test_scoreboard.py`); Zheng 462 lecturas (PC 454) |
| R33 | **Compilación de F3Set nunca reconocida** (13-11): la clave guardada en JSON (listas) frente a tuplas: el PC la volvía a juntar en cada vuelta y la nube pedía cada tramo a YouTube | hecho (`tests/test_compilation_key.py`); F3Set en la nube 469/517 |
| R34 | **El `.ts` de Osaka no se puede limpiar con ningún ffmpeg** (7.1 y 9.0; el PC tampoco desde el 18-10): se analiza tal cual, como en el PC; 7 de 307 tomas de otras cámaras sin recortar (C2) | aceptado y escrito (no hay arreglo sin recodificar el vídeo) |
| R35 | **Velocidad y coste del análisis en la nube** (14-11, #279): la CPU es casi la mitad del coste (16 núcleos de media); la bola de la pasada fina 929 s frente a 159 s en el PC; decodificar en la GPU | pendiente: perfil a bajo nivel antes de cambiar nada (`docs/capacidad_nube.md`) |
| R36 | **Matriz de rotación degenerada en una ventana** (14-11, Zheng en la nube: «Non-positive determinant … rotation matrix», 1 ventana de 345, C2 dentro del presupuesto): un vector nulo llega a una rotación 3D | **arreglado** (14-11): la raqueta en los fotogramas sin observación se interpolaba eje a eje y normal a normal; con dos normales opuestas, a mitad salía el vector nulo. Ahora, en ese caso (y solo en ese), se interpola la orientación entera (slerp); el resto, igual que antes (`racket3d._between`, `tests/test_racket3d.py`). Se comprueba al rehacer la pasada fina de Zheng (paso 10) |
| R37 | **Altura del bote fuera de límites** (14-11, auditoría en la nube: 1 de 63 fuera de 0,2-4,0 m): el ajuste aceptaba velocidades de subida de 0,5-12 m/s (botes de 0,01 a 7,3 m) y la auditoría pide 0,2-4,0 | **arreglado**: un solo límite para los dos (`limits.BALL_APEX_M`); fuera de él no se mide (nada inventado) (`tests/test_ball3d.py`). Se ve al rehacer la pasada fina (paso 10) |
| R38 | **El vídeo de la lección por debajo de la primera pantalla** (auditoría, PC 13-11 y nube 14-11: vídeo en y=805-1159 de 900): con datos reales aparece «Su ritmo y su cadena cinética» encima de la lección (428 px); las pruebas no lo veían porque sus golpes inventados no traían tiempos de fases | **arreglado**: el panel va a «Más sobre su derecha», plegado, como dice el diseño (§1.9); las pruebas ya llevan tiempos reales (`synthetic(timing=True)`, `tests/test_learn_web.py`, que fallaba en el móvil antes del arreglo). **comprobado en `informe2`** (la auditoría de la nube ya no lo da) |
| R39 | **124 palabras en las claves del armado** (máximo 120; auditoría, PC y nube) | **arreglado y comprobado en los datos reales** (14-11, `scripts/informe_real.py` sobre la página de `informe2`: armado 105 palabras, las 9 fases sin fallos): el «Cómo» de la lección era la primera frase de la indicación entera (hasta 25 palabras; «Gira antes de que la bola cruce la red» llevaba 48 palabras de texto fijo). Ahora cada clave tiene su «Cómo» de una línea, de 12 palabras como mucho (`learn.LESSON_CUE`; el diseño, §1.5, dice «una línea de Cómo»); la indicación entera sigue en «Más» y en las demás pantallas. Las claves de clase («Forma de la preparación»…) no repiten el texto de sus clases junto a su valor (sigue en el título). La primera frase ya no se corta dentro de un paréntesis («…que usa ella (arriba.»). Prueba: `test_every_lesson_key_has_a_one_line_cue` (texto fijo de 3 claves ≤ 90 palabras en cada fase; antes, hasta 139). La comprobación del navegador dice ahora las palabras de cada clave |
| R40 | **Marcador de Gauff: 0 lecturas en la prueba de 10 min de la nube** (14-11, cola). El arreglo R32 de esta mañana lee el rival en el marcador: la caja decía «C. GAUFF USA» y se tomó la última palabra, «Usa» (el país; en Zheng, «Chn», que por suerte sí valió); buscando «Usa» no se encontró ninguna fila. El PC sí leía este partido (su catálogo no tenía rival) | **arreglado** (marcador v16): el apellido es la última palabra de 4 letras o más, nunca el país; y los nombres del catálogo cuentan siempre junto al leído, así una lectura equivocada no deja el marcador vacío (`tests/test_scoreboard.py`). Antes de lanzar Gauff entero; Osaka, Pegula y Zheng rehacen solo el marcador (y lo que dependa de él si cambia) al ponerse al día (paso 10) |
| R41 | **Kaggle no arranca la sesión («en cola») y la cola la relanzaba cada 10 min** (14-11 13:48-14:32: 4 intentos y error; ya pasó a las 10:18 durante 1 h). Lo más probable: sus GPU gratis ocupadas; cada relanzamiento la mandaba al final de su cola | **arreglado**: en cola de Kaggle se espera (relanzar solo tras 45 min), cada vuelta apunta lo que dice Kaggle y el resumen lo muestra; la clave ya no se sube como versión nueva en cada lanzamiento; la prueba vuelve a la cola (`prueba_gauff_v16b`). Pendiente: si Kaggle sigue sin GPU muchas horas, que la cola lo diga y use Modal en cuanto tenga crédito (1-12) |
| R42 | **Kaggle: «Maximum batch GPU session count of 2 reached»** (14-11, sonda de las 15:36). Las versiones 7 y 8 del cuaderno se quedaron en «Starting…» (captura del usuario, 15:34) y ocupan las 2 sesiones de GPU que permite la cuenta; desde entonces Kaggle rechaza todo lanzamiento, y su herramienta lo hace con código 0, así que la cola lo apuntaba como lanzado. La cuota está bien (1,74 h de 30 h; se renueva el 21-11) | **arreglado en el código**: un rechazo de Kaggle no cuenta como lanzamiento y sale en el resumen de la cola. **Para desatascar hoy, el usuario para las versiones 7 y 8** («…» → parar la sesión): la API de Kaggle no da el identificador de sesión para cancelarlas. Siguiente: un cuaderno por trabajo (uno atascado no bloquea a los demás) |
| 11 | Análisis completo de los 6 partidos **desde cero** (carpetas nuevas; las anteriores al archivo, solo se copia su clic) y flujo «completo» | PC (~21 h), **después de R1-R13 y solo con la aprobación del usuario (#262, 12-11)** | su auditoría y la tabla de cierre recalculada (`estado_real_partidos.md`) cierran B1-B7 y #242 | al final, sin fallos conocidos (#247) · **Previsión 221 (12-11 03:10)**: 1,1-20,8 h (desde las cachés - calculando todo); se rehacen marcador, identidad, pasada fina, golpes dudosos y recortes en los 6 partidos. Las decisiones de R2/R3 (bola reutilizada, RTMW) van antes: cambian la pasada fina entera · **12-11 23:30: esa previsión y el «~21 h» se quedan cortos**: ninguna medida de un partido real incluía la bola del partido para el detector (R17: salía vacía en la biblioteca); se suma el modelo de la bola sobre el juego de cada partido (por medir en Osaka y Pegula, 265-266; R21). La previsión nueva sale después |

**P0 (después de la Base; su análisis y diseño se adelantan en paralelo en la nube):** P0.1 plan de bajo nivel (`docs/p0_plan.md`:
tareas, arquitectura de la interfaz, sistema de diseño y gráficos, modelo de datos, pantallas, métricas de aceptación por casilla) ·
P0.2 modelo de calidad completo (#256: métricas de las casillas sin medir) · P0.3 comparativa catalogada (#257) · P0.4 diseño y
prototipo (una revisión del usuario) · P0.5 construcción (tras cerrar la Base) · P0.6 aceptación por el modelo de calidad.

Detalle de la tarea 5 (E): (1) `window.worker` deja de lanzar procesos propios (desactivado por configuración): al
abrirse comprueba que el ejecutor único vive y si no lo arranca; (2) pausar/reanudar/cancelar/reanalizar llaman a
`orchestrator.pause/resume/cancel/submit`; (3) partido/rival/informe los hace el mismo ejecutor; (4) la «Cola» lee
`orchestrator.status` (en curso, paso N de M, eventos, pausa); (5) el icono junto al reloj, del mismo estado;
(6) «Añadir partido» → registro único + trabajo en la cola; (7) pruebas y capturas en el PC.

**Paquete N, prueba N0 en paralelo (13-11, #273, aprobada por el usuario «sí, empieza con el código»)** — guía y
pasos del usuario en `docs/nube_n0.md`; no toca nada de lo que corre en el PC
| # | Tarea | Dónde | Validación | Estado |
|---|---|---|---|---|
| N0.1 | Código: `cloud/` (Modal: imagen con las dependencias bloqueadas y onnxruntime-gpu 1.24.4; «dml» con sesiones en CUDA), flujo «Nube» de GitHub Actions, `scripts/subir_nube.py`, `5_conectar_nube.bat`, comparación PC/nube | nube (código) | `tests/test_nube.py` (14 pruebas); ningún módulo del paquete cambia | hecho (13-11) |
| N0.2 | Cuenta de Modal con tope 0 € (límite de uso 30 $), token, secretos `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` en GitHub | usuario (una vez) | el flujo «Nube» → comprobar despliega y ve la GPU | **hecho (13-11 19:02)**: tras cuatro arreglos míos de la imagen (secretos con espacios, salida de Modal, HOME en el volumen, PYTHONPATH, sitecustomize), comprobar va bien en una Tesla T4 (no había L4): ONNX Runtime 1.24.4 con CUDA y TensorRT, y las sesiones «dml» en CUDA en un proceso nuevo |
| N0.3 | Clave en el PC (`5_conectar_nube.bat`) y subida de modelos y compilaciones de F3Set por la cola (`script subir_nube`) | usuario (1 min) + PC | `capturas_diag/nube_clave.json` y `subir_nube.json` en pc-logs | **clave guardada (13-11 ~19:30, «Clave correcta»)**: el primer intento falló porque el secreto se pegó sin su «as-» y el script no decía por qué; ya acepta el comando entero de Modal. Subida pedida (291, `--pc-tag v18`), detrás de la v18 |
| N0.4 | F3Set en la L4 desde cero y comparación golpe a golpe con el PC (v17) | Modal | `runs/nube/comparacion.md`: veredicto, k por etapa, coste | pendiente |

**Decisión del usuario (13-11, #271/#272):** después de los 6 partidos (cierre de la Base) y antes de P0, toda la
aplicación pasa a la nube: paquete **N** en `config/plan_peticiones.yaml` (`docs/analisis_nube.md` §8, §13), con un
**tope de 0 € al mes** (crédito mensual de Modal con el tope de la cuenta; si se agota, se espera al mes siguiente). Hasta
entonces, todo sigue en el PC.

**Ahora mismo (13-11 12:40):** PC = F3Set v17 (121) en curso desde las 08:21 (iGPU al 50-67 %, sin errores ni alarmas
nuevas; 135 GB libres); detrás, Pegula (122), la auditoría final (123) y, con la cola libre, 286 (R29) y 124.

**Antes (13-11 07:30):** PC = R26 por la cola (119 Osaka en curso; 120-123 detrás; 286 y 124 cuando la cola quede
libre). Nube = Claude: el análisis de la nube (#268) en paralelo; R29 cuando llegue 286; después la previsión (R21) y el
plan de los 6 partidos, que espera la aprobación del usuario (#262).
**Si se acaban los tokens:** todo está en la rama y en el PC (cachés, cola en `datos/tennisbio.db`); la sesión siguiente
sigue por la primera tarea no hecha de esta tabla.

---

## Notas históricas: dónde está cada pendiente (petición #253, 11-11)
Cada cosa pendiente que dicen las notas de abajo está hecha, es una petición de un paquete (se implementa allí) o está
descartada con su motivo. Nada queda solo aquí.
| Nota (fecha) | Pendiente que dice | Dónde está |
|---|---|---|
| 17-10 orden 2 | Huecos 1-6 de la guía de Ivanovic | Peticiones #189-#198 (M2, M3, M4, M7, P1) |
| 17-10 orden 3 | Huella del vídeo por contenido | Hecho: #229 |
| 17-10 orden 3 | Huella de código en todas las etapas | Hecho (10-11): huellas por etapa (`pipeline.code_fingerprint`) |
| 17-10 orden 3 | Integración continua | Hecho: las pruebas corren en el PC con cada código nuevo (`pruebas_fondo.ps1`, auditoría «Pruebas del código en este PC») y en la nube antes de cada subida |
| 17-10 orden 3 | Liberar las carpetas `_poc*` | Hecho: #146 (petición `borrar`); `_poc9_largo` se conserva hasta la limpieza final con el usuario |
| 17-10 | «Cópiala» como lección | P1 (#4, #46, #47…) |
| 13-10 Pendiente | Más golpes por situación | Hecho: los 4 partidos (#205, 445 derechas) |
| 13-10 Pendiente | Velocidad | B1 (#14, #248) |
| 13-10 Pendiente | Validar los giros del tronco con una referencia | **Nueva: #254** (M3) |
| 13-10 Pendiente | Los 4 partidos y móvil/nube al final | B6 (#1) y P6 (#2, #154) |
| 12-10 entrenadores | Raqueta al lado/detrás del cuerpo (plano del swing) | **Nueva: #255** (M4) |
| 12-10 entrenadores | Punta frente a cabeza; freno de hombros | Hechos: #102, #106 |
| 12-10 entrenadores | «Lo que la distingue»; clase de estilo | #194 (P1); #112 hecho |
| 12-10 entrenadores | Examen de 25 afirmaciones | #113 (P1) |
| 12-10 vista lateral | Verla en el PC | #79 (P1) |
| 12-10 repeticiones | Otras cámaras de la retransmisión como vista lateral enlazada | #218 (B4; enlazadas 95 % en Pegula; medir en ellas: #218) |
| 12-10 auditoría | Combinaciones medida × situación; peticiones y afirmaciones como comprobaciones; más medidas con clips anotados | #11, #12, #113, #238 (P3) |
| 12-10 informe | Entrada que se entienda sola | #17 (P2) y el rediseño P0 (#252) |
| 12-10 PC | Instalación, prueba rápida, F3Set, los 4 partidos | Hecho (instalación, pruebas en el PC, F3Set 466/517); el análisis final es la tarea 11 de B8 |
| Limitaciones asumidas | Empuñadura exacta, ruido de medida, apoyo sin datos anotados, velocidad absoluta de raqueta, efecto | Descartadas con motivo: no se pueden medir desde la tele sin falsa precisión (CLAUDE.md, «Limitaciones asumidas»); se dicen «no medible desde la tele» |

# HISTÓRICO (no se sigue; notas fechadas que se conservan). Lo vigente es la sección «Estado» de arriba, `CLAUDE.md` y `docs/README.md`.

## 19-10: el plan vigente está en `docs/plan_maestro.md` (leer primero)
Todo lo pendiente, en orden, con su criterio de cierre medido en el PC. Almacenamiento definitivo: `docs/almacenamiento.md`.

## 09-11: el saque en el marcador de otras retransmisiones (etapa `score` v7)
- Problema: en Indian Wells 2026 (Zverev–Sinner) y Miami 2026 (Rybakina–Pegula) el marcador se leía (92 y 407
  lecturas, con juegos y puntos) pero la identidad tuvo 0 votos de saque y decidió 0 de 167 y 0 de 320 planos. El
  único lector del saque era una mancha de color saturado no tapada por texto en la fila del nombre (`serve_marker`),
  pensado para la pelota amarilla del US Open. En marcadores de retransmisión mundial (banderas de país junto a los
  nombres, celda de puntos de color en las dos filas, marca de saque blanca o dentro de la caja de texto del nombre)
  ese criterio da «ninguno» (dos filas iguales) o siempre la misma fila (la bandera más saturada).
- Ahora, sin nada por torneo: (1) los elementos de color que aparecen en las dos filas a la misma altura y tamaño
  (celdas, banderas iguales) no cuentan como marca; (2) cada lectura guarda la diferencia fila 0 − fila 1 de lo que
  destaca del fondo del marcador por columnas (en «alturas de fila» desde el nombre, `row_profile`), y al final del
  partido `learn_server` busca las columnas que cambian de signo cuando cambia el saque (cada juego: juegos jugados
  impares/pares, regla del tenis; los tie-breaks no cuentan): ahí está la marca, sea cual sea su forma o color. La
  regla solo dice **cuándo** cambia el saque; **quién** saca lo dice la marca leída en cada lectura. La marca
  aprendida se acepta si sigue la alternancia en ≥ 80 % de ≥ 20 lecturas. La de color se mantiene si sigue la
  alternancia (≥ 70 %; el US Open queda igual); si no la sigue (una bandera), se sustituye por la aprendida o se
  quita (nunca votos falsos). `score.json`: `server` (el que se usa), `server_marker` (el de color, como antes),
  `server_check` (cuántas, de dónde, acuerdo con la alternancia, columnas) y `roi`. Registro: «saque en el marcador».
- Diagnóstico en el PC si no bastara: `scripts/diag_scoreboard.py` (petición `medir`, `script: diag_scoreboard`)
  guarda recortes ampliados del marcador con lo que leyó el OCR, la máscara de color y el saque, en
  `pc-logs/capturas_diag/marcador_<partido>_<k>.jpg` y `diag_marcador.json`.

## 09-11: fotos del clic de la misma persona (petición 167, etapa `identity` v9)
- Problema: en Rybakina–Pegula (Miami 2026) las dos fotos del clic eran la misma mujer (vestido blanco, visera
  naranja). Las dos visten de blanco: los dos grupos de ropa no eran las dos personas (separación 1,78, igual de
  "buena" que Zverev–Sinner con 1,65; un mismo vestido blanco con luz distinta se separa con 2,5 en datos sintéticos).
  Nada lo comprobaba: sin votos de saque (0 en los dos partidos) no había cambios de lado decididos que lo desmintieran.
- Ahora la etapa comprueba sus grupos (`clothes.groups_check`): deben seguir la paridad de los cambios de lado
  leída en el marcador (≥ 70 % de los planos, no hace falta ver un saque), la jugadora del fondo debe caer en el
  otro grupo y la ropa típica de los dos grupos debe diferir (≥ 0,10). Si no, la ropa no decide nada y el clic va
  por los **cambios de lado** (`click_by: ends`: una foto de cada lado de la pista; el clic dice en qué paridad está
  ella cerca, `identity.apply_pick`); sin marcador, no se pide clic y la aplicación lo dice.
- Fotos (`app/identity_click.photo_set`): de cada grupo, el plano más típico de su ropa; la ropa se mide en la foto
  misma y debe parecerse más a su grupo que al otro; las dos fotos deben diferir (≥ 0,10). La caché de fotos sigue a
  `identity.json` (antes una foto vieja no se rehacía nunca). `estado.json` marca «fotos no distinguibles» con el
  motivo, y se sube `<partido>_identidad.json` (resumen sin códigos) para diagnosticarlo sin pedir nada.

## 19-10: la ropa vuelve a contar en la identidad (etapa `identity` v5)
- Problema (partidos completos): la ropa no decidía nunca (`by_clothes` = 0 en los 4; confianzas 0,50-0,64).
  La apariencia era el histograma de la caja entera (casi todo pista) y el k-means se sembraba con los dos
  planos más raros.
- Ahora (`tennisbio.clothes`): la etapa vuelve a leer del vídeo hasta 6 fotogramas por plano (los más quietos,
  con el torso visto) y mide solo la **camiseta** (hombros-caderas) y el **pantalón/falda** (caderas-muslos),
  quitando los colores de la pista que la rodea; tono para lo que tiene color y claridad relativa a la pista
  para blanco/gris/negro (robusto a sol/sombra). Por plano, mediana de los fotogramas. Reparto en dos personas
  con 2-medoides exhaustivo (sin semillas atípicas) y margen por plano; la jugadora lejana, cuando el detector
  la ve en los mismos fotogramas, entra como pareja «no puede ser la misma».
- Fusión con los cambios de lado: de acuerdo → «ropa y cambios de lado»; en desacuerdo gana el saque visto en
  ese plano, si no la ropa con margen claro («ropa (corrige el marcador)»: un juego mal leído), si no «dudoso»
  (fuera de comparativas, no se borra). Resumen: `agree`, `ends_only`, `clothes_only`, `ends_won`,
  `clothes_won`, `doubtful`, comprobaciones (`clothes.same_game_same`, `clothes.far_opposite`, `separation`).
  Sin vídeo, vuelve a la apariencia antigua de la caja entera.
- Comprobado en 20 clips reales de RacketVision: misma persona (dos mitades del clip) mediana 0,11 frente a
  0,53 con la jugadora del otro lado. Pendiente: ver los números en los 4 partidos (`identity` se recalcula sola).

## 17-10: decisiones y orden de trabajo (leer primero)

- **Nada en la nube y nada de pago** (decisión del usuario). La aplicación profesional es local: `docs/arquitectura_producto.md`, sección «Decisión del usuario». El móvil recibe una copia del informe autocontenido, sin servidor.
- **No lanzar los 4 partidos** hasta que el usuario lo pida.
- **Orden pedido:**
  1. Rehacer «Sus pies en este golpe» (fotogramas reales) y la estroboscópica («El recorrido del brazo», plegada como extra). Hecho el 17-10.
  2. Huecos 1-6 de la guía de Ivanovic que aplican: `docs/comparacion_guia_ivanovic.md`, sección 3.
  3. Higiene de la aplicación: huella del vídeo por contenido, huella de código en todas las etapas, CI, liberar `_poc*`.
- **«Cópiala» como lección** (17-10, aprobado por el usuario sobre `docs/maqueta_leccion_armado.html`): pasos de 8 fases + pies; su vídeo en bucle de la fase con las marcas (`learn.LESSON`: hand / lines / heights / base); como mucho 3 claves fiables por fase con su valor, «Tu objetivo», cambio por velocidad de bola (solo si supera dispersión y error), cómo, ejercicio y «Cómo comprobarlo» (`learn.CHECKS`). La lista completa de medidas sigue, plegada («4 · Todas las medidas»).
  **Lista de comprobación (la valida Claude, no el usuario):** vídeo primero; ≤ 3 claves por fase, cada una con valor suyo y nº de golpes (nunca ruido/sesgo); cómo + ejercicio + comprobación; diferencias solo sobre el error; la lección ≤ 1400 px a 1280×900 y sin scroll lateral a 390 px; nada borrado; sin errores de página. Automático en `tests/test_learn_web.py::test_lesson_meets_the_requirements` y en el PC (`learn_check.check_lesson` → auditoría: «La lección…» y «La lección enseña su vídeo de cada fase»). Después, revisar la captura real `capturas_prueba/pantalla_1_aprende.jpg`.
- **El ciclo del PC se lanza sin ventanas** (`oculto.vbs`, ciclo v4): antes aparecía un terminal cada 10 min.

## Lo último (13-10, tarde): leer primero
- **Vídeo entero (`_poc9_largo`, 15-10; pasada fina v16):** 210 min, 129 golpes confirmados, 69 derechas (55 cercanas).
  La auditoría daba 18 «no cumplidos» por 4 causas, corregidas en origen:
  1. *Superficie*: el partido la sabía («dura» por el nombre del vídeo) pero no se guardaba en los golpes. Ahora cada
     golpe lleva `surface` (pantalla del golpe: «Pista»); las pruebas toman rival/torneo/superficie de la entrada de
     `config/matches.yaml` de su vídeo (`catalog.trial_match`; se recuerda en `<partido>/partido.json`) o de
     `--surface` (`prueba_rapida.ps1 -Superficie`).
  2. *Dirección del golpe / bola subiendo*: «Su derecha» solo enseñaba un factor con **dos** niveles de ≥ 12 golpes
     (hacía falta algo con qué comparar). «al centro» (15) y «bola subiendo» (27) eran los únicos: ahora un nivel con
     ≥ 12 golpes se describe siempre; si es el único, se marca «no comparado» (`compared: false`) y no se buscan efectos.
  3. *763 km/h*: el bote de una derecha estaba 8,7 m delante de ella 3 fotogramas antes del impacto (no era el bote de
     la bola que recibe) y el golpe de la rival, cortado a 1 m, caía muy detrás de la pista. `ball3d.flights` ya no mide
     nada de un bote imposible de alcanzar a tiempo, exige el golpe rival dentro de su zona y deja sin medir la velocidad
     fuera de 15–240 km/h (`limits.BALL_INCOMING_KMH`, el mismo límite que la auditoría).
  4. Petición nueva `accion: informe` + `carpeta: _poc9_largo` (`ciclo_automatico.ps1`): medidas desde las cachés,
     informe y auditoría de esa carpeta (`recompute_measures.py --out-name`), registro en
     `output\prueba_poc9_largo_informe.log`.
- **Velocidad cerrada (decisión del usuario, 14-10 noche):** prueba 7 (`_poc7_35`): pasada fina 46,3 min (antes
  62,5) con la bola en la CPU en paralelo; 61 min de etapas para 35 min de vídeo ≈ **6 h por partido** (13-10: ~25 h).
  Lo que queda (pose más ligera, raqueta FP16, menos resolución o sin golpes del lado lejano) pierde calidad:
  **no se toca**. Modelos de partida: TransNetV2 + cámara por líneas, YOLO11m-pose FP16, híbrido con RTMPose-x,
  TrackNetV3 (iGPU + CPU), raqueta de RacketVision FP32. Petición 9 (`accion: largo`; la 8 la ignoró el ciclo, que aún corría con su script anterior): el vídeo entero en
  `_poc9_largo` (una noche) para tener golpes suficientes por situación y el tiempo real de un partido.
- **Orientación del pie: causa y método nuevo (14-10, noche; pasada fina v15):** las lecturas imposibles (20-44 %) se agrupan en −90° (8 de 13 pies de delante en el armado): la punta, tapada por el talón y la pierna al verla por detrás, la dibuja el modelo del lado de la cámara. La homografía con el talón unos cm sobre la pista solo resta 8-25° (haría falta un talón 11-17 cm más alto que la punta). Ahora (`footpoints.foot_reading`): talón bajado a la pista antes de la homografía, longitud del pie según su altura, mediana de ±0,04 s y rechazo de la punta detrás del talón («punta_oculta»; `technique.feet_check` dice por qué falta cada una). La fiabilidad cuenta los rechazos como lecturas imposibles (si pasan del 15 % sigue «sesgo», es decir, «no fiable desde la tele»). Las series guardan los puntos de los pies (`feet`, `feet_conf`): con la próxima ejecución se ve cuántos golpes quedan medidos.
- **Umbrales nuevos con golpes reales (14-10, prueba 6: `_poc6_35` frente a `_poc5_35`/`_poc4`, y `_smoke` recalculado):**
  - *Giro de hombros al empezar la preparación* («ruido» ±3,4° en la revisión): no es un fallo. Cambia por la escala
    de altura por la pista: la anterior seguía el largo del tronco en la imagen (variaba ±9 % dentro de una ventana
    con la postura) y repartía los golpes (26-67°, ±10,5° entre golpes); con la pista (±2 %) 7 de 10 derechas leen
    19-23° (±1,8°) y mover el instante 1-2 fotogramas lo cambia ±3,4° (en ese instante el giro empieza). Sus golpes
    no difieren más que el instante: «ruido» es honesto (con los 13 golpes de la prueba 6 sale «fiable»; lo
    decidirán más golpes). El giro en el armado sigue fiable (prueba 6: ±2,4° entre fotogramas frente a ±7° entre golpes). Umbral sin cambios.
  - *Pies:* el pivote (talón de atrás) tomaba la referencia en el armado; las 6 derechas con armado 0,36-0,6 s antes
    del impacto (en carrera, pasos de ajuste después) daban «no» y 5 de las 6 con armado a 0,14 s daban «sí».
    Ahora la referencia es como mucho 0,2 s antes del impacto (`footpoints.PIVOT_REF_S`; los pivotes medidos van de
    −0,06 a +0,02 s). La orientación del pie apunta hacia su propia valla (< −45°, imposible con el pie apoyado) en
    el 20-44 % de las lecturas (armado y impacto) y en 7 de 8 pies de delante del revés: la fiabilidad la daba
    «fiable» porque la dispersión es enorme (±41-52°). Ahora una medida con más del 15 % de lecturas imposibles es
    «sesgo» (`reliability.PLAUSIBLE`) y no se da ni en «Aprende» ni en «Su derecha» (que tampoco daba como suyas
    las medidas de ruido o sesgo: ahora dice «no fiable desde la tele»). Pasada fina v14.
  - *Cámara principal por líneas:* 11,4 min (antes 30,3) pero la pista pasa de 9,5 a 9,2 min: lo perdido son 14 s
    en 8 planos cortos con un ajuste de pista flojo (0,47-0,59; el juego da ~0,8); los 29 golpes de antes siguen
    (31 ahora), mismos candidatos cercanos (73). Sin cambios.
  - *Escala de altura:* las medidas en % bajan un 10-15 % (la anterior daba su altura en el 80-87 %); el tronco y
    las piernas confirman la de la pista (0,94-1,08). Impacto al 53 % de su altura (≈ 0,97 m, cintura; IQR
    49-64 %), cadera en la espera 44 % y en el armado 42 %. Las clases de altura de bola (rodilla < 35 %, cadera
    < 50 %…) se pensaron para la altura real: ahora encajan. Los objetivos de «Cópiala» siguen teniendo sentido.
- **Bola en paralelo (14-10, tras la prueba 5):** la bola de las ventanas se calcula en la CPU en un hilo aparte
  (desde la última ventana hacia atrás) mientras la pose usa la iGPU (`fine_speed.ball_ahead`, `fine_ahead.py`);
  esperado 10-20 min menos en la prueba de 35 min. Solapes de ventanas: 0 s en la prueba 5 (no se implementa).
  La raqueta «el doble» en la prueba 5 no es del código: la 4 reutilizó cachés de `_poc4`. Detalle en
  `docs/pruebas_velocidad.md`.
- **Pasada fina en cascada (14-10):** antes de la pose, la bola de la ventana (que ya hacía falta y queda en
  caché) decide si puede haber un golpe confirmado de la jugadora (`tennisbio.fine_gate`): sin golpe de bola en
  su lado a ±0,4 s de algún candidato y, en el lado cercano, con la bola bien vista ahí, la ventana se descarta
  sin pose, raqueta ni 3D. Es condición necesaria de la confirmación actual (`fuse_with_ball`): los golpes
  confirmados son los mismos. Registro por ventana y `gate` en el resumen de `fine` (etapa versión 9).
- **Velocidad (13-10, noche):** pista (homografías reutilizadas, búsqueda vectorizada; ×3,7 en la búsqueda),
  marcador (OCR solo cuando cambia; ×3), pasada fina (proceso de raqueta persistente, lotes, una decodificación)
  y pose YOLO en FP16 (validada en el PC con `scripts/model_trials.py`: ×2,2, mismos golpes, 0,25 px). Prueba de
  velocidad pedida al PC con `config/peticion_pc.txt` (id 1, «poc»: 4 min en `_poc4` y 35 min en `_poc`, sin
  tocar `_smoke`). Prueba de modelos: RTMPose-x tiembla 2,6× menos y ve los pies. **Híbrido YOLO+RTMPose-x activado en la pasada fina (14-10)**, lado cercano
  (`fine_pass.pose_model: hybrid`, etapa `fine` v11): mismos golpes, −35 % de temblor, pies en el 99,7 %, ≈ 2× el
  tiempo de pose en esas ventanas. Los pies de la jugadora seguida llegan al análisis como `run.feet` /
  `run.feet_conf` (aún sin medidas que los usen); el lado lejano sigue con YOLO.
  tocar `_smoke`). Prueba de modelos: RTMPose-x tiembla 2,6× menos y ve los pies (híbrido YOLO+RTMPose-x en curso).
- **Pies con talones y puntas (14-10):** cuando el golpe trae `run.feet` / `run.feet_conf` (pose híbrida), el apoyo
  (abierto…cerrado), la base en la pista, los pasos y la posición salen del apoyo talón–punta (`footpoints.ground_track`;
  en fotogramas sin pies, el tobillo corregido por su desfase); nuevas medidas: orientación de cada pie en armado e
  impacto (`front_foot_angle_deg`, `back_foot_angle_deg`) y pivote sobre la punta del pie de atrás
  (`footwork.back_heel_lift`, `back_heel_lift_s`), en Cópiala (fases 3 y 5), «Su derecha» y el panel de pies. Sin
  pies todo sale igual que antes (test `tests/test_foot_metrics.py`) y Cópiala dice «sin talones ni puntas».
- **Cópiala para alguien que empieza** (13-10, 14 h): guía «Empieza aquí» (se oculta y vuelve), «Tu objetivo»
  con su número en cada medida fiable (`learn.TARGETS`; nunca de ruido o sesgo; en cm del usuario si pone su
  altura, guardada solo en su navegador), glosario (`learn.GLOSSARY`, palabras subrayadas y lista al final).
  La hoja de sesión la descartó el usuario. Siguiente: velocidad, rendimiento y algoritmia (antes del tramo largo).
- **Ciclo automático en el PC** (`scripts/windows/ciclo_automatico.ps1`, bucle `ciclo_bucle.ps1` al iniciar
  sesión + tarea de Windows de respaldo, cada 10 min): trae el código nuevo de la rama, decide qué recalcular
  (`scripts/auto_cycle.py decide`: medidas desde la caché ~20 min, informe ~2 min, o nada), revisa contra la
  ejecución anterior y sube `revision_automatica.md` (OK / REGRESIÓN / ERROR), `ciclo_arranque.txt`
  (cada arranque y por qué no hizo nada), `ciclo_vivo.txt` (señal horaria) y `ciclo_tarea.txt` a `pc-logs`.
  **No pedir al usuario que lance 2c/2d.** Tras subir código, programar un aviso (send_later ~30 min) y leer la revisión.
- **Cola de peticiones al PC (20-10)** (`config/peticion_pc.txt`): varios bloques separados por una línea `---`,
  cada uno con su `id:`, `accion:` y parámetros; un solo bloque sin `---` sigue valiendo. El ciclo hace en orden
  todos los pendientes seguidos (sin esperar 10 min entre ellos) y para si llega código nuevo (el ciclo siguiente
  sigue con el script nuevo) o si una acción aún no la conoce (no se da por hecha y la cola espera). Ids hechos en
  `output\peticiones_hechas.txt` (más el antiguo `peticion_hecha.txt`). Lectura igual en Python:
  `scripts/pc_requests.py` (`python scripts/pc_requests.py` dice cuál es la siguiente). Una acción nueva conviene
  subirla en un push anterior al de su petición. No mezclar el primer fichero con varios bloques en el mismo push
  que este cambio del script (el ciclo viejo juntaría los bloques en uno: haría solo el último).
- **Fiabilidad de cada medida, automática** (`tennisbio.reliability`): repetibilidad con las fases movidas
  1-2 fotogramas (por fase y del golpe entero), segundo método independiente (2D frente a 3D del tronco:
  `sesgo`), medidas derivadas heredan el veredicto. Ruido o sesgo → no se da como valor suyo y la web dice por qué.
  Hoy: giro de hombros 2D (57°) frente a 3D (12°) = sesgo; cuerdas en el impacto = ruido.
- **Golpes dudosos** solo por dudas del golpe (raqueta no vista, valor descartado, espera/recuperación no
  encontradas = medidas que faltan): 1 de 10.
- **Aprende**: firma (lo que repite ≥ 75 %, solo medidas fiables), estilo en una frase (solo ≥ 50 %),
  ~65 puntos; validado en el navegador en 677 combinaciones (`learn_check`).
- **Vistas por golpe pedidas** (peticiones 114-117): la bola y ella con «cae» y medidas reales; bajar y subir
  (barras + cm, una sola curva corregida de perspectiva, cadera 38-58 %); base en la pista (m); tronco al
  terminar (en su fotograma más girado tras la terminación).
- Medidas nuevas: punta de la raqueta respecto a la cabeza, frenado de hombros (hereda el sesgo del giro),
  transferencia de peso, ritmo con la bola, codo en el armado, base al terminar, pasos cruzados
  (`footwork.crossover_steps`), máximo lag (`stroke.racket_lag_deg`), manos en la espera en toda la espera,
  raqueta a ±2 fotogramas, superficie del torneo o del nombre del vídeo.
- **Pendiente:** más golpes (un tramo largo; el usuario decide si el ciclo lo lanza de noche), velocidad
  (~15 h por partido), validar los giros del tronco con una referencia (vista lateral de entreno o clips
  anotados), los 4 partidos y móvil/nube al final.

## Estado (octubre de 2026)
Hecho y validado en la nube (ver `docs/validacion.md`):
- Pipeline completo por etapas con caché e idempotente; identidad automática (cambios de lado +
  ropa + saque); marcador por OCR; pista por homografía (comprobada cada ~8 s y en cada impacto).
- Detección de golpes con pose + bola: lado cercano P 0,73 / R 0,84; lado lejano P 0,67 / R 0,73.
- Modelo técnico completo (8 fases, ~200 descriptores, pies, ritmo, raqueta, clases y situaciones)
  con fuentes (`docs/matriz_cobertura.md`); estadística ajustada por situación y partido (OLS
  robusto + Benjamini-Hochberg); pantalla "Su derecha"; videoteca, comparar, exportación MP4/PDF.
- Casos límite de vídeo: sin audio, varias pistas, .ts con saltos, fps variables, 1080i, 4K,
  cortados, rutas con acentos, vacíos (todos probados).
- Escala: 2.400 derechas → informe en 47 s, 6 MB, carga en 2,7 s.

### Primera prueba rápida en el PC (12-10-2026)
- Equipo real: Ryzen 7 8745HS, Radeon 780M (DirectML disponible), 20 GB RAM, Windows 11, ffmpeg 9.0.2.
- Instalación: 88/88 pruebas pasan en Windows (tras arreglar ffmpeg 9, nombres en cirílico y UTF-8).
- **F3Set (Rybakina, Open de Australia 2023, 21 clips; 9 no se descargaron):** precisión 0,92,
  recall 0,65 (golpes de fondo 29/33 = 0,88; saques 1/15, no son el objetivo), derecha/revés 0,97,
  dirección 0,89, subida a la red 0,97, instante ±1 fotograma.
- **Su vídeo (final US Open 2026, retransmisión rusa, 1080p50, 210 min): 0 golpes analizados.**
  Marcador 0 lecturas (sin nombre del rival en el catálogo y el OCR no lo encontró), pista en 3 de
  11 tramos, identidad sin decidir → todo descartado; solo 2 candidatos en 4 min. **Bloqueante.**
  **Causa (imágenes de diagnóstico):** los 4 min elegidos (minuto 30) eran la previa: himno,
  bandera, entrenamientos y un resumen del partido anterior de Sabalenka contra Noskova; no había
  juego. El clasificador de planos tomaba esos planos por "cámara principal". Retransmisión de
  Eurosport con el marcador internacional (latino, legible). Arreglado: la prueba rápida busca
  sola un tramo con juego; jugadores y lectura del rival solo donde se ve la pista.
- Segunda prueba (minuto 121, un juego al saque de Sabalenka desde el fondo): marcador 48 lecturas,
  13 candidatos, pero identidad sin decidir → 0 golpes. Causa: solo se votaba cuando la cercana
  sacaba. Arreglado: si saca la del fondo, la cercana es la que resta (voto de resto).
- Velocidad: YOLO 960 en la iGPU 112 ms/fotograma (CPU 479); decodificación 1080p50 27 fps (CPU),
  40 fps (d3d11va). Estimación lineal 5,6 h por partido sin la pasada fina → ~1 día los 4. La etapa
  de jugadores domina (277 s por 4 min).

- Tercera/cuarta prueba: 10 golpes confirmados (6 derechas), identidad decidida (voto de resto).
  Pasada fina 93 → 26 s por golpe (raqueta en la iGPU en proceso aparte: el controlador DirectML
  dio un 0xC0000005 en el proceso principal). Estimación ~5 h por partido (~2 h jugadores, ~2 h
  pasada fina). Progreso por etapa con % y tiempo restante; hojas de imágenes de cada golpe.
- Revisión a ojo de los 10 golpes: derecha/revés 10/10; apoyo razonable. Corregido: "en el aire"
  (10/10 por la perspectiva al avanzar), terminación de revés, "cómo llega" = velocidad antes del
  swing (en el contacto el cuerpo se mueve 2-3 m/s por el traslado de peso). Pasos uno a uno, apoyos
  y split step NO medibles en esta retransmisión (tobillos de ~190 px a 50 fps tiemblan 0,2-1 m/s):
  se ocultan por golpe cuando un pie no se ve quieto en ≥ 40 % de los fotogramas.

### Pedido por el usuario y pendiente (después de arreglar su retransmisión)
- ✔ Lo que hace respecto a la bola en cada momento (cruza la red, bota, punto más alto; golpea
  subiendo / arriba / cayendo; `ball3d.py`) y curvas de altura sincronizadas con el vídeo (cabeza,
  cadera, mano, raqueta) con su curva típica y su franja por situación (informe: «Análisis de golpe»
  y «Su derecha»). Falta verlo con golpes reales del PC (prueba rápida).
- ✔ Auditoría automática de requisitos (`tennisbio audit`, `docs` → `pc-logs:auditoria_prueba.md` y
  `capturas_prueba/`): corre al final de la prueba rápida y del análisis completo; capturas con Brave
  (el usuario no quiere Edge ni descargas). Primera auditoría en el PC (12-10): medido y no mostrado
  (3×90°, dirección del primer paso, velocidad relativa de la raqueta, mano en el mango), dirección
  del golpe no es situación, porcentajes de < 5 golpes, lista de "no medible" incompleta (13), 2
  valores fuera de rango (codo, base); imágenes de las 8 fases en negro con pocos golpes (arreglado:
  golpes mejor captados cuando no hay típico).
- ✔ Capa de interpretación (12-10): cada frase de «Su derecha» lleva qué significa y su fuente
  (`explain.COACH`), cada fase sus claves a la vista (`PRIMARY`) y el resto plegado, «Qué mirar»
  (`PHASE_FOCUS`), cuerdas por fase, cadena cinética, primer paso y pierna trasera; resumen sacado de
  las mismas frases; frase de entrada en cada pantalla; gráficas técnicas plegadas; sin YouTube
  (requisito 6); conclusiones del Panel con el mínimo de 12 golpes. La auditoría comprueba además
  frase de entrada, enlaces externos, gráficas de más de 4 líneas y que cada medida tenga su
  explicación. `2b_prueba_media.bat`: 35 min de partido para verlo con golpes suficientes.
- ✔ Vídeos de entrenadores (12-10): 16 transcripciones analizadas (`docs/aprendido_entrenadores.md`);
  hecho: capa «Líneas», «Para copiarla», codo, transferencia de peso, empuje de piernas, aceleración
  respecto al bote, girar mientras se mueve. Pendiente de esa lista: raqueta al lado/detrás del cuerpo
  (plano), punta vs cabeza, freno de hombros, «lo que la distingue», clase de estilo, y el examen de 25
  afirmaciones sobre su derecha como validación interna (nunca en el informe), con golpes suficientes.
- ✔ Prueba rápida del 12-10 23:34 en el PC: el play funciona en Brave (también con las animaciones de
  Windows desactivadas). Auditoría: 109 cumplidos, 5 huecos sin implementar y 91 «sin golpes
  suficientes» (solo 6 derechas en 4 min): hace falta la prueba media para confirmarlos.
- ◐ Vista lateral de entrenamiento (12-10, decisión del usuario): `scripts/practice_videos.py` baja en el
  PC vídeos de entrenamiento de la jugadora (YouTube), los corta en planos, la sigue (persona más grande),
  detecta sus golpes, decide la cámara de cada uno (`practice.camera_view`) y mide en las derechas de lado
  lo que la tele no ve (`practice.side_metrics`): impacto delante de la cadera, ángulo real del swing,
  rodillas, tronco, caída de la raqueta bajo el impacto y ángulo antebrazo–raqueta (lag / casting).
  Pantalla propia y marcada en el informe («Vista lateral (entreno)»); resumen solo con ≥ 12 derechas de
  lado. Prueba rápida: 2 vídeos × 90 s; prueba media: 8 × 300 s (incremental). Falta verlo en el PC.
- ✔ Repeticiones de la cámara de fondo con el marcador visible (normales o a cámara lenta): se detectan
  porque sus pies repiten un recorrido reciente más despacio o sin sonido de impactos (`replays.py`,
  etapa candidates v7). Pendiente: usar las repeticiones de otras cámaras (laterales, frontales) de la
  propia retransmisión como vista lateral, enlazadas a su golpe en directo (así la identidad y el
  instante salen del directo y solo se miden ángulos, que no dependen de la cámara lenta).
- ✔ Vista lateral: lista elegida a mano (`config/practice_videos.yaml`) tras mirar tres fotogramas de cada
  vídeo; fuera los grabados por detrás y los de cámara lenta sin factor conocido. Clasificador de cámara
  por el cambio de anchura de hombros entre espera y armado; golpes con valores imposibles descartados.
- ✔ Auditoría (12-10): combinaciones medida × situación, cada petición del chat (sección 11), validación
  F3Set, tablas a la vista y examen interno con las afirmaciones de entrenadores.
- ✔ Prueba rápida del 13-10 00:21: vista lateral bajada y analizada sola (2 vídeos, 31 golpes), pero solo 1
  derecha medible de lado (los vídeos están más en diagonal) y las derechas de frente salían como revés.
  Arreglado: análisis reflejado cuando se le ve la cara (`practice.faces_camera`) y estimación 3D en su propio
  marco del cuerpo (RTMW3D, `practice.metrics_3d`) para lado, diagonal y frente, marcada como estimación.
  Auditoría: además, el árbol de ficheros de cada ejecución (`audit.file_tree_items`).
- ✔ Profundidad de RTMW3D (14-10): rtmlib la decodificaba con los 384 px de alto en vez de los 288 del eje de
  profundidad (salida de 576 = 2 × 288), así que las diferencias de profundidad salían × 0,75. Ahora se
  decodifica en un solo sitio (`pose.wholebody3d.decode_simcc3d`) para todo: giro 3D del tronco, mano/antebrazo
  de las cuerdas y medidas 3D de la vista lateral. Se vuelven a calcular la pasada fina (versión 12) y los
  vídeos de entreno (versión 5).
- ✔ Regla del usuario (13-10): **nunca borrar trabajo hecho**; las vistas complejas se quedan como extra y
  lo nuevo se añade. Las 4 tablas (raqueta por fase, Comparar, Explorador, Comparativas) siguen igual,
  ahora con frases encima que dicen lo importante («Tabla completa» debajo, abierta). La auditoría
  comprueba que haya frases en esas pantallas y solo avisa de tablas sin frases.
- Prueba media del 13-10 (00:49-05:52, 5 h): 35 min de partido en 251 min (≈ 25 h por partido de 3,5 h:
  players 48 min, identity 30, candidates 31, court 17, score 19, fine 103 = pose 64 + bola 27). Solo 10,6 min
  de juego en el tramo (minuto 121) → 27 golpes, 14 derechas (10 cercanas). 4 ventanas sin nadie hacían
  fallar la pasada fina (arreglado). Vista lateral: 15 derechas de lado y 33 en 3D, pero las detectadas solo
  por la muñeca caen en el armado (impacto mal situado): ahora solo se miden las confirmadas por el sonido.
  Siguiente: velocidad (prioridad) y elegir un tramo con más juego.
- ✔ Cámara principal por las líneas (14-10, etapa `scenes` v3): con TransNetV2 salían 303 planos pero 248
  «principales» (30,3 min de 35; pista solo en 9,5). El color no basta: la pared azul de fondo tiene el color de
  la pista. Ahora un plano es principal si en suficientes fotogramas (1/10 del plano, como mucho 1 s) se ven dos
  laterales que convergen hacia arriba y una línea que las cruza, sobre una superficie limpia (no público), o si
  se parece a una vista ya confirmada así. Si una retransmisión no deja ver las líneas, decide el color como
  antes. Calibrado: las 26 imágenes de `pc-logs:diag/` separadas sin error; 41 retransmisiones de
  RacketVision y el resumen de la final, todo conservado. Esperado en el tramo de 35 min: ~10-14 min de cámara
  principal (pista en 9,5). En el PC: `main_camera_min` frente a `main_camera_min_colour` y `main_rule`.
- ✔ Pista (14-10, etapa `court` v4): de los 32,7 min de «cámara principal» solo 10,6 tenían pista. Causa
  (imágenes de `pc-logs:diag/`): la pista se ajustaba bien en todos los planos de juego; los planos sin pista
  eran primeros planos (jugadora sobre el fondo azul, público) que `scenes` da por cámara principal porque no
  ve el corte (mismos colores azul/verde): 159 planos en 35 min, 127 «principales». Con un solo fotograma cada
  ~8 s, un plano que mezcla punto y primer plano perdía el punto si el fotograma caía en el primer plano (y los
  límites iban ±4 s). Ahora: un fotograma cada 2 s, el cambio pista/sin pista se sitúa por bisección a 0,5 s, un
  fotograma sin pista pero con la misma vista que su vecino (línea tapada, desenfoque) conserva la pista si aún
  puntúa ≥ 0,3, y una máscara de líneas en sombra (antes: sombra parcial → homografía 17 px desviada; sombra
  total → sin pista). Búsqueda completa como mucho cada 8 s de plano (coste parecido). El resumen de la etapa da
  `court_min` / `court_share` para comprobarlo en el PC.
- ✔ «Aprende su derecha» (13-10), pantalla principal nueva (nada borrado): eliges el golpe combinando
  condiciones (dirección, apoyo, cómo llega, efecto, lado, altura, velocidad, profundidad, contacto) → sus
  golpes exactos (o, si son pocos, los más parecidos diciendo qué condición se quita) → 8 fases + pies con
  47 puntos de control: su valor (con cuántos golpes lo respaldan) y su patrón, cómo hacerlo tú, error típico,
  ejercicio, «Ver en vídeo» en el instante de la fase; qué cambia en cada condición; plan; lo no medible.
  Contenido en `learn.py` (conocimiento de entrenadores, marcado). Los 59 puntos de la matriz del usuario
  tienen sitio (`learn.matrix_places`, auditado). Validación automática en navegador (`learn_check.py`):
  677 combinaciones (cada condición, cada pareja, el ejemplo del usuario) × 9 fichas; detecta cada rotura
  probada; en los tests (400 golpes sintéticos) y en la auditoría del PC. `2c_solo_informe.bat` (1-2 min)
  rehace web + auditoría sin analizar vídeo.
- Pendiente de la auditoría (pedido el 12-10): comprobar cada combinación medida × situación, convertir
  las 63 peticiones del chat (`docs/peticiones_usuario.md`) y las 25 afirmaciones de entrenadores en
  comprobaciones automáticas, y validar la exactitud de más medidas con clips anotados.
- El usuario no entiende el informe (12-10): rehacer la entrada con una sola pantalla que se explique
  sola, con vídeo y frases; después, aprender de vídeos de análisis de entrenadores (subtítulos e
  imágenes bajados en el PC) cómo explicarlo.

Pendiente que **solo puede hacerse en el PC**:
1. Instalación (falló la primera vez; ver `pc-logs:instalacion.log`).
2. `2_prueba_rapida.bat`: velocidad real en la iGPU (DirectML) y validación F3Set (30 puntos de
   Rybakina; YouTube bloquea la descarga desde la nube).
3. Ajustes según esos resultados; después los 4 partidos (una vez).

Limitaciones asumidas (no se "arreglan" con falsa precisión): empuñadura exacta, ruido de medida
real (sale de sus golpes en los partidos), apoyo sin validación con datos anotados (ningún conjunto
público lo anota), velocidad absoluta de la raqueta, efecto de la bola.
