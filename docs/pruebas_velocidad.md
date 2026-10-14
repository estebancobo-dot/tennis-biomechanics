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
| Modelos | Híbrido YOLO + RTMPose-x | nominal | RTMPose-x solo en las personas grandes | ◐ prueba de modelos (en curso) |
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
