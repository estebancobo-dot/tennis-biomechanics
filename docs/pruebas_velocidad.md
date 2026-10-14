# Escenarios de los cambios de velocidad y modelos (13-10, noche)

Para que la prueba de velocidad en el PC (petición 1) se haga una sola vez: cada escenario, qué pasa y
cómo está cubierto. ✔ = cubierto por prueba automática o por diseño; ◐ = se ve en la prueba del PC.

| Área | Escenario | Tipo | Qué pasa | Cobertura |
|---|---|---|---|---|
| FP16 | Conversión del modelo a media precisión en el PC | nominal | copia `_fp16.onnx` junto al modelo, una vez | ✔ hecha ya por la prueba de modelos en el PC |
| FP16 | La conversión o la carga fallan | error | aviso y modelo normal (FP32) | ✔ `test_pose_model_fp16_uses_half_copy_on_dml` |
| FP16 | Dispositivo CPU (sin iGPU) | límite | FP16 no se usa (en CPU es más lento) | ✔ `test_fp16_only_when_asked_and_on_dml` |
| FP16 | Puntos distintos a FP32 | calidad | 0,25 px de mediana; mismos golpes (F1 igual) | ✔ medido en el PC (`model_trials.md`) |
| FP16 | Cachés de pose antiguas (FP32) en `_smoke` | esquina | se reutilizan: el recálculo no cambia las medidas | ✔ huella de la etapa; revisión automática OK/REGRESIÓN |
| Pista | Plano con una cámara ya vista | nominal | reutiliza la homografía (umbral igual que una búsqueda) | ✔ `tests/test_court.py` (mismo resultado que el código antiguo) |
| Pista | Plano sin pista (primer plano, público) | límite | búsqueda completa y sin homografía, como antes | ✔ idem |
| Escenas (v3) | Cámara principal con líneas visibles | nominal | dos laterales que convergen + una línea que las cruza → plano principal | ✔ `test_scenes_main_camera.py`; 41 retransmisiones de RacketVision, ninguna perdida |
| Escenas (v3) | Primer plano / vista lateral ante una pared del color de la pista, público | error en fuentes | sin líneas de pista → no es plano principal | ✔ idem (sintéticos) y 26 imágenes de `pc-logs:diag/` |
| Escenas (v3) | Misma vista sin líneas (sombra, líneas tenues) | esquina | se parece (miniatura 16×9) a una vista confirmada → se queda | ✔ `test_shots_main_camera_by_lines_and_by_the_same_view` |
| Escenas (v3) | Corte no detectado (punto + primer plano en un plano) | límite | el plano entero se queda; la pista decide por bisección | ✔ idem |
| Escenas (v3) | Retransmisión cuyas líneas no se ven nunca (cámara baja) | límite | si las líneas dan < 10 % de lo que da el color, decide el color (como v2) y avisa | ✔ `test_without_visible_lines_the_colour_rule_stays` |
| Escenas (v3) | Coste | rendimiento | ~1 ms por fotograma a 160 px (≈ 20 s en 35 min a 10 fps) | ◐ `seconds` de la etapa en el PC |
| Pista | Zoom lento de la cámara | esquina | revisión cada 2 s (búsqueda completa como mucho cada 8 s); si la conocida baja de 0,5 se busca de nuevo | ✔ por diseño; ◐ «court_presets» en el PC |
| Pista | Corte no detectado (punto + primer plano en un mismo «plano») | error en fuentes | fotograma cada 2 s y bisección a 0,5 s del cambio | ✔ `test_court_stage_finds_a_rally_inside_a_missed_cut` |
| Pista | Líneas tapadas o borrosas con la cámara quieta | límite | se conserva la pista del vecino de la misma vista si puntúa ≥ 0,3; nunca tras un corte | ✔ idem y `test_court_stage_does_not_carry_the_court_over_a_cut` |
| Pista | Sombra sobre parte o toda la pista | límite | máscara de líneas en sombra (contraste local, sin brillo mínimo alto) | ✔ `test_fit_in_the_shade` |
| Pista | 4 ffmpeg a la vez | rendimiento | lectura adelantada en hilos | ◐ no probado en el PC |
| Marcador | Marcador igual entre muestras | nominal | se reutiliza la lectura (OCR al cambiar o cada 30 s) | ✔ `tests/test_scoreboard.py` |
| Marcador | Cambia un dígito, el saque o un rótulo | límite | cuenta como cambio → OCR | ✔ idem |
| Marcador | Marcador semitransparente o con reloj | esquina | siempre «cambia»: correcto, sin ganancia | ✔ por diseño |
| Marcador | Se pierde la zona del marcador | error | búsqueda en el fotograma entero, como antes | ✔ idem |
| Marcador | ffmpeg cambia el formato de `showinfo` | error | cada muestra por búsqueda (más lento, correcto) | ✔ `tests/test_video.py` |
| Pasada fina | Proceso de la raqueta persistente | nominal | un proceso para todas las ventanas | ✔ `tests/test_fine_speed.py` |
| Pasada fina | Ese proceso muere (driver) | error | CPU + fichero de aviso, como antes | ✔ idem |
| Pasada fina | Ese proceso se cuelga sin morir | error | se corta a 2 min + 2 s/fotograma y sigue en CPU | ✔ `test_worker_that_hangs_is_killed_not_waited_forever` |
| Pasada fina | Ventanas que se solapan (hasta ~14 s) | escalabilidad | fotogramas en flujo, no en memoria | ✔ por diseño (≈4 GB evitados) |
| Pasada fina | RacketPose por lotes en la iGPU | calidad | idéntico en CPU; en iGPU, diferencias solo en empates raros | ◐ revisión automática |
| Ciclo | Petición con código recién llegado | nominal | se hace en el ciclo siguiente (sin código nuevo) | ✔ corregido (antes solo con código nuevo) |
| Ciclo | Tarea de Windows con límite de 3 h | error | se registra de nuevo con 12 h en cada ciclo | ✔ corregido |
| Ciclo | Otra ejecución a la vez | concurrencia | la nueva ve «ocupado» y sale sin error | ✔ instancias en paralelo + comprobación |
| Ciclo | Prueba de 4 min falla | error | no se lanza la de 35 min; registro en `prueba_poc4.log` | ✔ por diseño |
| Ciclo | Reinicio del PC a mitad | error | la petición no se repite sola (se pide con otro id) | ✔ por diseño |
| Datos | La prueba toca `_smoke` | error | nunca: carpetas `_poc4` y `_poc`; registros `poc_*` | ✔ `--out-name` |
| Cascada | Ventana sin golpe de bola en su lado y bola bien vista junto a los candidatos | nominal | solo bola (que ya hacía falta); sin pose, raqueta ni 3D | ✔ `tests/test_fine_gate.py` |
| Cascada | Ventana con golpe | nominal | pasa; la pose completa y todo lo demás como antes (mismos resultados: la bola se lee de la caché) | ✔ idem |
| Cascada | Bola no vista junto a un candidato (cercano) | límite | pasa: un golpe sin bola visible se confirma solo con el brazo | ✔ idem |
| Cascada | Lado lejano sin golpe de bola lejano | límite | descartada: allí solo cuentan los golpes que confirma la bola | ✔ idem |
| Cascada | Sin modelo de bola o `fine_pass.gate: false` | error | pasan todas, como antes | ✔ idem |
| Cascada | ¿Descarta algo que la pasada completa confirmaría? | calidad | no por construcción (condición necesaria de `fuse_with_ball` + tolerancia de 0,4 s); 400 ventanas al azar con la lógica real, sin margen | ✔ `test_gate_never_drops_what_the_full_pass_confirms`; ◐ `gate_misses` en `validate_rv_strokes.py --ball` |
| Cascada | Cuánto ahorra | rendimiento | registro por ventana («descartada sin pose» / «pasa») y en el resumen de `fine`: `gate` (descartadas, pasan, motivos, segundos) | ◐ prueba del PC |
| Modelos | Híbrido YOLO + RTMPose-x | nominal | RTMPose-x solo en las personas grandes | ✔ `tests/test_hybrid_pose.py`; medido en el PC: mismos golpes, −35 % de temblor, pies en el 99,7 % |
| Modelos | Híbrido activado en la pasada fina (14-10, `fine_pass.pose_model: hybrid`, etapa `fine` v11) | nominal | lado cercano con el híbrido (mismo bucle que YOLO: tramos `keep`, lectura adelantada, tiempos) y los pies de la jugadora seguida en `run.feet` / `run.feet_conf`; lado lejano con YOLO (pies vacíos); registro por ventana «pose hybrid … modelo N s; pies en M» | ✔ `test_hybrid_extract_honours_keep_prefetch_and_frames`, `test_run_clip_feet_contract`, `test_window_cache_key_changes_only_with_hybrid` |
| Modelos | Coste del híbrido | rendimiento | ≈ 2× el tiempo de pose de YOLO FP16 en las ventanas cercanas (≈ 10 de 52 ventanas en la prueba 3: unos minutos más por partido); la caché de cada ventana cambia de clave, así que la pasada fina (pose y bola de las ventanas) se repite una vez | ◐ prueba del PC |
| Escala | Partido de 3,5 h | escalabilidad | tiempo lineal estimado desde 35 min | ◐ la prueba de 35 min lo da |
| Etapas a la vez | Jugadoras (iGPU) y marcador (OCR en la CPU) tras la pista | nominal | se ejecutan juntas (las dos solo necesitan planos y pista); el resto, una tras otra como antes | ✔ `tests/test_parallel.py` |
| Etapas a la vez | Sin iGPU (`device: cpu`/`openvino`) | límite | la pose también es CPU: una tras otra (no compiten por los mismos núcleos) | ✔ `test_real_stages_players_and_score_are_paired_only_on_the_igpu` |
| Etapas a la vez | `pipeline.parallel: false` | límite | todo una tras otra, en el orden de siempre | ✔ `test_disabled_runs_one_after_the_other_in_the_old_order` |
| Etapas a la vez | Falla una de las dos | error | no empieza ninguna etapa más; la otra termina y queda guardada; el error sale como antes | ✔ `test_an_error_stops_new_stages_but_the_running_one_finishes` |
| Etapas a la vez | Registro y `progreso.json` | concurrencia | cada línea de la etapa en paralelo lleva `[players]`/`[score]`; el progreso se escribe con cerrojo; el tiempo total del informe y de la auditoría cuenta una vez lo simultáneo (`overlap_s`) | ✔ idem |
| Etapas a la vez | El OCR quita CPU a la lectura de vídeo de jugadoras | rendimiento | se ve en el resumen de `players` («espera real») | ◐ prueba del PC |
| Jugadoras | Lectura de vídeo y preparación de la entrada en otro hilo | nominal | mismo resultado fotograma a fotograma; la apariencia (ropa) en un segundo hilo | ✔ `test_players_stage_output_is_the_same_as_one_frame_at_a_time` |
| Jugadoras | Se corta a mitad (error del modelo) | error | el hilo lector para y cierra ffmpeg | ✔ `test_read_ahead_stops_when_the_caller_fails` |
| Jugadoras | Lotes de 4 en la iGPU | rendimiento | no se hace: el modelo exportado es de lote 1 fijo y la pasada fina y la búsqueda lejana usan el mismo fichero | — |

Pendiente de medir (no de diseñar): tiempos reales por etapa en el PC, la bola (26 % de la pasada fina) y
el híbrido. Lo que no está aquí no cambia con esta versión.

# Pasada fina: pose, bola y raqueta (14-10, tras la prueba 3)

**De dónde sale el tiempo (prueba 3, 35 min, `pc-logs`):** pasada fina 60 min = pose 25,3 + bola 23,7 +
raqueta 4,8 + cuerdas/3D 2,4. 52 ventanas (345 s de vídeo); 15 descartadas por la bola (87 s, solo bola).
- **Lado lejano**: 27 ventanas con pose, 202 s (≈ 10 100 fotogramas, ≈ 17-19 min de pose) para 12 golpes;
  17 de esas 27 no dan ningún golpe. Los 12 golpes leen ≈ 37 s. Al menos 32 s (16 %) quedan antes del
  primer golpe de bola posible de su ventana (ventanas de peloteo de 6-11 s con un candidato cada ≈ 1,2 s).
- **Lado cercano**: 10 ventanas, 56 s (2 800 fotogramas), 16 golpes que leen 45 s. Pose a 135 ms/fotograma
  (prueba 4: 144 s para 1 066) frente a 67 ms del mismo modelo en la etapa de jugadoras, que prepara la
  entrada en otro hilo: la diferencia es trabajo en serie (letterbox, apariencia), no el modelo.
- **Raqueta**: 17-18 s por golpe confirmado: se segmentaba alrededor de **todos** los impactos de la ventana.
  En 12 clips de RacketVision solo 21 de 54 impactos del brazo están junto a un golpe real.
- **Bola**: ≈ 8 600 pasadas del modelo (134-168 ms en la iGPU; FP16 no gana). Se usa en toda la ventana
  (golpe de la rival, botes, destino, red): no se puede recortar sin cambiar medidas.

**Probado y descartado:** usar los 4 mapas de calor que TrackNetV3 predice por pasada (4× menos pasadas):
la red de RacketVision solo entrenó el último; los otros tres ponen la bola a ≈ 300 px (encontrada a ≤ 10 px
en el 20 % de los fotogramas anotados frente al 88 %; clip match101_000).

**Cambios** (cada uno con su interruptor en `config/default.yaml`; etapa `fine` v10):

| Cambio | Qué hace | Medidas de los golpes confirmados | Prueba |
|---|---|---|---|
| `fine_pass.pose_prefetch` | letterbox del fotograma siguiente en un hilo lector y apariencia en otro mientras el modelo trabaja (como la etapa de jugadoras) | idénticas | 90 fotogramas reales (YOLO 960, CPU): bit a bit iguales; tests con modelo falso (con y sin ROI, `every`) |
| `fine_pass.racket_near_candidates` | la raqueta solo en los fotogramas que puede leer un impacto a ≤ 0,4 s de un candidato (de 2,2 s + espera antes a 0,8 s después) | idénticas (mismas siluetas en todo lo que leen) | clip match115_000: 90 → 41 fotogramas segmentados, golpe conservado igual (20 medidas, fases, raqueta); test sintético |
| `fine_pass.pose_ranges: far` | lado lejano: la pose solo de 2,8 s antes a 2,0 s después de cada impacto que la bola aún permite (`fine_gate.possible_impacts`) y, fuera, 1 de cada 5 fotogramas (`pose_fill_every`): se la sigue por toda la ventana como antes; si cubre ≥ 85 %, ventana entera; si la pose de la ventana entera ya está en caché, se reutiliza; si en lo posado no se mide su altura, ventana entera | puntos idénticos en todo lo que lee el golpe; medidas en % de altura a ≤ 0,6 puntos (escala de la ventana) | RacketVision (abajo); 400 ventanas al azar: todo impacto que confirma un candidato cae dentro; tests sintéticos |
| `ball.static_batch` | en la iGPU, la bola con lote fijo de 8 (el último se rellena): DirectML compila la red para una forma | mismo mapa de calor (CPU: ≤ 1e-3 px) | test con el modelo real en CPU; la velocidad solo se ve en el PC |

**Rangos de pose en RacketVision** (CPU; el golpe del candidato, ventana entera frente a rangos con relleno 1/5):

| Clip | Lado | Fotogramas posados | Pose (s) | Puntos en el golpe | Fases | Mayor diferencia |
|---|---|---|---|---|---|---|
| match115_000 | lejano | 145 de 239 | 77 → 38 | idénticos | iguales | altura del contacto 45,6 → 45,1 % |
| match123_000 | lejano | 147 de 249 | 64 → 39 | idénticos | iguales | 0,1 puntos |
| match104_000 (179) | cercano | 347 de 576 | — | idénticos | iguales | 0,16 puntos |
| match107_000 (471) | cercano | 351 de 600 | — | idénticos | iguales | altura del contacto 53,0 → 51,6 % |
| match120_000 (341) | cercano | 363 de 600 | — | — | — | su altura sale de 5 fotogramas (cara de espaldas): sin ellos no se mide → ahora ventana entera |

Sin relleno (cada tramo por separado) el cercano cambiaba hasta 3 puntos (match104) y un tramo empezó
siguiendo a un recogepelotas (ahora se arranca desde quien golpea la bola). Por eso en el cercano no se
activa: allí la altura depende de qué fotogramas se posan (también hoy, según cómo se agrupan las
ventanas: tarea aparte) y el ahorro es casi nulo (ventanas de un candidato).

**Ahorro esperado en la prueba de 35 min** (pasada fina 60 min): prefetch ≈ 2-3 min (cercano: 135 → ~80-90
ms/fotograma), raqueta ≈ 2-2,5 min (la mitad de fotogramas segmentados), rangos lejanos ≥ 2,5 min (cota: solo
lo anterior al primer golpe de bola posible de cada ventana; probablemente 4-6), bola con lote fijo: se sabrá
en el PC (de 0 a la mitad de 23,7 min si DirectML compila la red). Total seguro ≈ 7-11 min; la bola es lo
que queda: su coste es el modelo (134-168 ms por pasada), no la lectura (≈ 5 ms/fotograma).

Registro nuevo por ventana: «pose en N de M fotogramas (s; modelo s; fotogramas a 960 px por perderla) · bola s ·
raqueta s (impactos que pueden quedarse de los encontrados)», y en el resumen de `fine` el bloque `counts`.

| Área | Escenario | Tipo | Qué pasa | Cobertura |
|---|---|---|---|---|
| Rangos de pose | Lado cercano | nominal | sin rangos (`pose_ranges: far`), como antes | ✔ `test_fine_one_passes_ranges_targets_and_far_starts` |
| Rangos de pose | Ventana de un solo candidato | nominal | el rango cubre ≥ 85 % → ventana entera, como antes | ✔ `test_pose_keep_ranges_join_and_whole_window` |
| Rangos de pose | Su altura no se ve en lo posado | error en fuentes | ventana entera | ✔ `test_pose_ranges_fall_back_to_the_whole_window_when_her_height_is_not_seen` |
| Rangos de pose | Peloteo lejano con candidatos de las dos jugadoras | nominal | solo alrededor de sus golpes de bola | ✔ idem; ◐ registro por ventana |
| Rangos de pose | Bola no vista junto a un candidato cercano | límite | todo el tramo donde podría haber un golpe sin bola, más los márgenes | ✔ idem |
| Rangos de pose | Entre tramos (relleno 1/5) | nominal | se la sigue como en la ventana entera; huecos de 4 fotogramas rellenados como siempre | ✔ `test_pose_ranges_with_fill_follow_her_through_the_window` |
| Rangos de pose | Sin relleno (`pose_fill_every: 0`, no por defecto) | esquina | cada tramo desde su inicio (lejana: se la busca; cercana: desde quien golpea la bola) | ✔ `test_pose_ranges_track_each_stretch_on_its_own`, `..._start_from_the_person_the_ball_leaves` |
| Rangos de pose | Caché de pose de la ventana entera (`_smoke`) | esquina | se reutiliza, sin recalcular | ✔ `test_pose_ranges_measure_the_stroke_inside_as_the_whole_window` |
| Rangos de pose | ¿Pierde un golpe que la pasada completa confirmaría? | calidad | no: el impacto está siempre dentro (condición necesaria de `fuse_with_ball`) | ✔ `test_every_impact_the_full_pass_confirms_is_inside_a_possible_range` |
| Raqueta | Impactos del brazo lejos de todo candidato | nominal | sin segmentar salvo lo que lee un golpe conservable | ✔ `test_racket_only_near_candidates_keeps_the_kept_stroke_identical` |
| Prefetch | Fallo del modelo a mitad | error | el hilo lector se para y cierra la lectura (`read_ahead`) | ✔ por diseño (`test_read_ahead_stops_when_the_caller_fails`) |
| Lote fijo | DirectML no acepta la forma fija | error | la sesión cae a la CPU con la misma forma (más lento, correcto); `ball.static_batch: false` lo quita | ◐ prueba del PC |

# Escala de su altura en píxeles (14-10, `fine_pass.height_scale`, etapa `fine` v12)

**Antes:** toda medida en % de altura o en cm se dividía por su altura en píxeles = mediana de nariz → tobillo
× 1,08 en los fotogramas con cara y pies a la vez. De espaldas casi nunca se le ve la cara (RacketVision:
4-163 de 250-600 fotogramas) y en juego está agachada: leía el **61-92 %** de su altura real según el clip, y
cambiaba hasta un 3-42 % según qué fotogramas se posaban (rangos de pose, agrupación de ventanas).

**Ahora (`court`, por defecto):** su altura real (`config/players`, 1,84 m) proyectada con la cámara que da
la homografía de la pista (focal, inclinación, posición; `ball3d.camera`) en el sitio donde pisa (tobillos en
el plano a la altura del tobillo, mediana de 1 s), fotograma a fotograma (`src/tennisbio/body_scale.py`). Se
comprueba con su tronco y sus piernas (proporciones antropométricas): si dicen otra altura (factor fuera de
0,8-1,25: pista mal ajustada o zoom) se usan ellos (`segments`); sin pista, también. `pose` = como antes.
Los golpes se siguen encontrando con la escala de antes (umbrales validados): los mismos impactos.

| Comprobación (12 clips RacketVision, lado cercano) | Resultado |
|---|---|
| Tronco y piernas medidos con la escala de la pista | 0,955-1,034 de lo esperado en los 12 |
| Escala de antes / nueva | 0,61-0,92 (mediana 0,81; un clip raro 1,16) |
| Cambio de la escala junto al golpe al posar solo rangos (relleno 1/5) | 0,00 % (antes 0,1-42 %) |
| Medidas en % de altura (54 golpes) | ×0,78 de mediana: altura del contacto 69 → 53 %, base 24 → 21 %, separación lateral 15 → 11 % |
| Fases | algunas «espera»/«recuperación» se mueven (umbrales en alturas/s y % de altura, ahora en su altura real) |

| Área | Escenario | Tipo | Qué pasa | Cobertura |
|---|---|---|---|---|
| Escala | Cámara de TV (14-22°) y jugadora en cualquier punto de su mitad o al fondo | nominal | su altura en la imagen a ≤ 2 % | ✔ `test_court_scale_is_her_height_at_every_court_position` |
| Escala | Agachada / inclinada | límite | igual (≤ 1 %); la de antes la acortaba ~10 % | ✔ `test_court_scale_does_not_change_when_she_crouches_and_the_former_one_does` |
| Escala | Sin ninguna cara | límite | igual | ✔ `test_court_scale_without_any_face_seen` |
| Escala | Corre hacia la red / salta en el split step | nominal | sigue el tamaño (≤ 3 %); el salto no cuenta (≤ 1 %) | ✔ `test_court_scale_follows_her_as_she_moves_and_ignores_a_hop` |
| Escala | Otros fotogramas posados | esquina | idéntica junto al golpe | ✔ `test_court_scale_does_not_depend_on_which_frames_were_posed`, `test_run_clip_measures_with_the_court_scale_and_the_same_with_pose_ranges` |
| Escala | Pista de antes de un zoom o mal ajustada | error en fuentes | la contradicen tronco y piernas → `segments` (≤ 6 %) | ✔ `test_a_court_the_body_contradicts_is_not_used` |
| Escala | Sin pista | límite | `segments`; sin tronco ni piernas, la de antes | ✔ `test_without_court_segments_then_pose` |
| Escala | Rival sin ficha en `config/players` | límite | 1,80 m por defecto: error ±5 % en sus medidas | ◐ añadir su altura |
