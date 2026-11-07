# Modelos candidatos frente a los actuales (2026-11-07 14:30, dml)

Regla: se adopta si su precisión es igual o mejor **y** no es más lento en la pasada completa de un partido nuevo. Nada de esto cambia el análisis: adoptar uno es un cambio aparte.

| Candidato | Frente a | Precisión (candidato / actual) | Velocidad (candidato / actual) | ¿Se adopta? |
|---|---|---|---|---|
| wasb | ours (TrackNetV3, fp16) | F1 0.863 / 0.906 | 44.4 / 34.5 fps | no: F1 bola a 10 px 0.863 frente a 0.906 (peor); fotogramas/s 44.4 frente a 34.5 (no más lento) |
| rtmw | YOLO11m-pose + RTMPose-x (hybrid-x) | F1 0.667 / 0.667; temblor 0.356 / 0.357 %; pies 0.998 / 0.997 | 10.0 / 3.3 fps | **sí**: F1 golpes 0.667 frente a 0.667 (igual o mejor); fotogramas/s 10.0 frente a 3.3 (no más lento) |
| court14 | tennisbio.court.fit_court | puntos a ≤7 px 0.956 / 0.91; pista hallada 1.0 / 0.957 | 6.3 / 3.6 fotogramas/s | **sí**: puntos a ≤7 px 0.956 frente a 0.91 (igual o mejor); fotogramas/s 6.3 frente a 3.6 (no más lento) |
| rfdetr | YOLO11m-pose en la mitad lejana | jugadora lejana hallada 1.0 / 0.903 | 0.5 / 1.3 fotogramas/s | no: lejana hallada 1.0 frente a 0.903 (igual o mejor); fotogramas/s 0.5 frente a 1.3 (más lento) |
| f3ed | detector propio (spotting) | F1 golpes (test) 0.994 / 0.997 | 0.153 / 0.031 min por min de vídeo | no: F1 golpes 0.994 frente a 0.997 (peor); min por min de vídeo 0.153 frente a 0.031 (más lento) |
| ocr5 | rapidocr-onnxruntime 1.4 (PP-OCRv4) | lecturas coherentes por muestra 0.438 / 0.518; leídas 0.456 / 0.526 | 0.573 / 0.693 s por muestra (CPU) | no: lecturas coherentes por muestra 0.438 frente a 0.518 (peor); s por muestra 0.573 frente a 0.693 (no más lento) |
| mag3d | RTMW3D (tennisbio.pose.wholebody3d) | a ≤15° 0.58 / 0.13; mediana 12.486 / 40.399°; X-factor 10.4 / 10.188° | 196.5 / 34.1 fotogramas/s (el candidato usa la pose 2D que ya tiene la pasada fina) | **sí**: giro del tronco a ≤15° de la referencia 0.58 frente a 0.13 (igual o mejor); fotogramas/s 196.5 frente a 34.1 (no más lento) |
| bounce | regla del giro más brusco (tennisbio.ball) | F1 botes con nuestra bola 0.899 / 0.581; con la bola anotada 0.936 / 0.811 | 0.1 / 0.1 min por hora de vídeo (1.6 / 0.5 s) | **sí**: F1 botes (bola de nuestro detector) 0.899 frente a 0.581 (igual o mejor); min añadidos a la pasada por hora de vídeo 0.1 frente a 0.1 (no más lento) |
| bounce_own | | error: OSError: TrackNet: descarga sin terminar tras 8 intentos | | no |

- wasb: La bola corre sobre todo el juego de un partido nuevo (detector de golpes): su velocidad por fotograma es la de esa parte de la pasada.

- rtmw: Sin esqueletos anotados en nuestros datos: la precisión es la de la tarea (golpes encontrados frente a los giros de bola anotados de RacketVision), más el temblor de los puntos y los pies vistos.

- court14: Conjunto de validación de TennisCourtDetector (300 fotogramas 1280x720; ese modelo eligió sus pesos con él, así que su cifra es algo optimista).

- rfdetr: Referencia: la raqueta anotada del jugador lejano en los fotogramas de prueba de RacketVision (la persona hallada la contiene, con un margen de media caja).

- f3ed: F3ED se entrenó con la parte «train» de F3Set: la comparación justa es la de los puntos de «test». Velocidad: minutos de cálculo por minuto de vídeo; el propio es el tiempo de la etapa spotting (sin la pasada barata que también usan otras etapas).

- ocr5: Sin marcadores anotados: no es una precisión frente a la verdad, sino acuerdo entre motores y coherencia (una lectura cuenta si encaja con la secuencia del partido según las reglas del tenis: juegos que solo crecen, el marcador de juegos más leído para cada total, puntos que no retroceden dentro de un juego; tennisbio.point_count). Un error que dé otra puntuación posible no se detecta. Muestras: instantes en que nuestra etapa leyó el marcador (score.json) y, aproximados, instantes en que lo intentó sin leerlo; los dos motores leen exactamente los mismos fotogramas, sin reutilizar lecturas, en la CPU (donde corre la etapa).

- mag3d: 01_23_2026_17_00_court2 tramo 1: la misma persona no se encuentra en las dos vistas 01_23_2026_17_00_court2 tramo 2: la misma persona no se encuentra en las dos vistas 01_23_2026_17_00_court2 tramo 3: la misma persona no se encuentra en las dos vistas Referencia: la línea de hombros y la de caderas triangulada desde dos vistas calibradas y sincronizadas de CalTennis (nuestra pose 2D en las dos; no depende de ninguna profundidad estimada). Cada modelo 3D se lee en una sola vista; error = diferencia de su dirección alrededor de la vertical. Las cámaras de CalTennis están a ~1,7 m de altura, a un lado o detrás de la pista; la de la tele está más alta. Un modelo que falla aquí no sirve; uno que acierta aquí no queda probado para la vista de la tele (allí RTMW3D aplanaba la profundidad: tennisbio.reliability). RTMW3D se sitúa a la profundidad real de la pelvis (sacada de la referencia): es su mejor caso.

- bounce: Bote acertado si está a ≤3 fotogramas (0,1 s) de uno anotado. El modelo CatBoost se entrenó con este mismo conjunto (10 partidos, 75 % de sus fotogramas al azar): su cifra es optimista; no hay otro conjunto público con botes anotados. Con la bola de nuestro detector las entradas ya no son las de su entrenamiento. Con la bola anotada la regla recibe los golpes anotados; con la de nuestro detector, los golpes que saca tennisbio.ball.ball_hits, como en un partido. Las dos son pasos sobre la trayectoria de la bola ya calculada. Velocidad: lo que cada una añade a la pasada completa, en minutos por hora de vídeo redondeados hacia arriba a 0,1 (la pasada dura ~75 min por hora de vídeo y varía minutos entre ejecuciones; menos de 6 s por hora no la cambia); entre paréntesis, los segundos medidos.
