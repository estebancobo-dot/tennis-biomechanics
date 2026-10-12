# Validación automática

Cada número sale de un script reproducible contra datos anotados por humanos; nada se valida a ojo.

## Raqueta — RacketVision (tenis, retransmisión TV, split `test`)
`uv run python scripts/validate_racket.py --root <datasets> --images 250`
(YOLO11m-seg + YOLO11m-pose a 1280; silueta → eje y cabeza de la raqueta)

| Conjunto | Raquetas | Detectadas | Error de eje (mediana) | Eje ≤15° | Extremo de la cabeza correcto | Error de elevación (mediana) | Error del centro de la cabeza |
|---|---|---|---|---|---|---|---|
| Todas | 283 | 95,8 % | 4,0° | 85 % | 98 % | 4,0° | 7 % de la longitud |
| Jugador cercano (≥80 px) | 66 | 97,0 % | 3,2° | 89 % | 98 % | 3,4° | 7 % |
| Grandes (≥120 px) | 12 | 91,7 % | 3,1° | 100 % | 100 % | 3,2° | 6 % |

Notas: en ~57 % de las anotaciones la empuñadura está oculta en la mano; el eje se toma de
garganta→punta. La cara abierta/cerrada no se mide con la silueta (requiere el modelo de 5 puntos).

### Modelo de 5 puntos (RacketVision RTMPose-m, exportado a ONNX)
`uv run python scripts/export_racketpose.py` (pesos oficiales, licencia MIT). Con la caja de la
raqueta, 292 raquetas del split `test` (L = longitud punta→garganta):

| Punto | Error mediano | PCK@0,2·L |
|---|---|---|
| Punta | 0,054·L | 93 % |
| Garganta | 0,057·L | 93 % |
| Empuñadura (visible en 130) | 0,066·L | 88 % |
| Borde izquierdo | 0,093·L | 74 % |
| Borde derecho | 0,089·L | 76 % |

Eje punta–garganta: error mediano 2,9°, p90 9,2°. Las puntuaciones del modelo no separan
aciertos de fallos (no se filtra por ellas; la continuidad temporal decide). Los bordes dan la
anchura aparente del cabezal → apertura de la cara, sin depender de la silueta.

## Golpes del jugador cercano — RacketVision sin audio (pose + bola)
`uv run python scripts/validate_rv_strokes.py --root <datasets> --clips 12 --ball models/balltrack.onnx`
Referencia: giros de la bola anotada (cada 5-11 fotogramas), tolerancia ±6. Clips de dobles
(dos personas dentro de la mitad cercana, por homografía) excluidos: 3 de 12.

| Método | Precisión | Recall | F1 | Error del instante (mediana) |
|---|---|---|---|---|
| Solo pose (pico de muñeca) | 0,22 | 0,43 | 0,30 | 2 fot. |
| Solo bola | 0,74 | 0,89 | 0,81 | — |
| **Pose + bola (pipeline)** | **0,73** | **0,84** | **0,78** | **1 fot.** |

Revisados a ojo 2 de los 6 "falsos positivos": ambos son golpes reales que la referencia no
recoge (la bola no estaba anotada en ese tramo), así que la precisión real es mayor. Bola: vista en
el 73-100 % de los fotogramas, 96-100 % a ≤15 px de la anotación (mediana 2 px).

## Golpes del jugador lejano — RacketVision sin audio (pose en recorte que la sigue + bola)
`uv run python scripts/validate_rv_strokes.py --root <datasets> --clips 12 --ball models/balltrack.onnx --side far`

| Clips | Golpes de referencia | Precisión | Recall | F1 | Error del instante |
|---|---|---|---|---|---|
| 12 (2 de dobles excluidos) | 11 | 0,67 | 0,73 | 0,70 | 2 fot. |

Cuando el recorte la sigue (94-100 % de los fotogramas) encuentra casi todos sus golpes; los
fallos vienen de clips donde se pierde (3 %) o de giros de la bola sin golpe. Del lado lejano
solo se publican posición, desplazamiento, altura del impacto y destino.

## Destino del golpe (bote en el campo rival) — final del US Open, revisado a ojo
| Golpe | Desde | Resultado | A ojo |
|---|---|---|---|
| 5,28 s | x = +3,6 m (derecha) | cruzada, dentro, 5,5 m del fondo rival, 0,73 s tras el impacto | correcto (bota a 6,02 s) |
| 7,66 s | x = +2,3 m | paralela, dentro, 5,5 m del fondo rival, 0,83 s | correcto (bota a 8,49 s) |
| 1,97 s | x = −2,6 m | sin valor | bola muy profunda: tras botar sigue subiendo en la imagen, sin quiebro visible |

El bote está en el suelo, así que la homografía da su posición exacta. Las bolas muy profundas
pueden quedar sin dato (no se inventan). El golpe de la rival en el aire se descarta porque su
proyección cae detrás del fondo.

## Derecha/revés y apoyo — 21 golpes de RacketVision, revisados a ojo (sin ver la predicción)
Hoja de contactos por golpe (fotograma de armado + fotograma de impacto); primero se etiqueta a ojo
y después se compara con el programa.

| Medida | Golpes con etiqueta clara | Coinciden | Nota |
|---|---|---|---|
| Derecha / revés | 9 de 21 | **9/9** | En los otros 12 la miniatura no permite decidirlo con seguridad (raqueta borrosa, jugador de frente o tapado) |
| Apoyo en el impacto | 3 de 21 | 2/3 (el tercero: "neutro" frente a "semiabierto", clases vecinas) | Desde detrás y arriba el ángulo de los pies es difícil incluso a ojo |

Conclusión: la clasificación derecha/revés es fiable; el **apoyo no queda validado** con esta prueba
(muy pocas etiquetas seguras). Por eso el informe lo presenta como clase con su reparto (no como un
ángulo exacto). Ningún conjunto público anota el apoyo (F3Set anota golpe, dirección, subida a la
red y resultado, no los pies); la derecha/revés sí se vuelve a medir con F3Set en la prueba rápida del PC.

## Juego de pies en un vídeo real (final del US Open, 3 derechas) — comprobación de coherencia
Fallos encontrados y corregidos:
- Pasos de 2,6-3,7 m (imposibles): eran carreras en las que no se vieron los apoyos. Ahora un
  desplazamiento de más de 2,2 m o de más de 0,7 s en el aire no cuenta como paso.
- "Pausa en el armado" de 0,67 s cuando no se detectó el inicio de la preparación: medía la quietud
  de la posición de espera. Ahora, sin inicio de preparación, solo se mide si la pausa queda acotada.
- "Resto" en el primer golpe de un plano que empieza a mitad de punto: si el plano empieza menos de
  1,5 s antes del golpe del rival, no se sabe si es resto y no se dice.

## Final del armado frente al máximo giro de hombros — 24 golpes de RacketVision
Dos definiciones del final del armado: la pausa de la muñeca (la que usa el programa) y el máximo
giro de hombros (la de la literatura). En 2D desde detrás las dos son ruidosas.

| | Diferencia mediana | A menos de 100 ms |
|---|---|---|
| Antes (pausa buscada hasta el impacto) | 0,12 s | 48 % |
| Ahora (la pausa no puede estar en los últimos 0,1 s: ningún swing dura menos) | **0,08 s** | **54 %** |

La detección de golpes no cambia (P 0,73 · R 0,84). La cadera llega a su giro máximo 25 ms antes que
los hombros (mediana), como describe la literatura (separación cadera–hombros al empezar el swing).

## Escala de 4 partidos (datos sintéticos, 2.400 derechas)
Generados a partir de los golpes reales del US Open con variaciones, para medir el informe y la
estadística con el tamaño real de los 4 partidos.

| Paso | Antes | Ahora |
|---|---|---|
| Modelo técnico ("Su derecha", efectos ajustados) | 101 s con 600 golpes | 2,6 s con 600; informe completo de 2.400 en 47 s |
| Ruido por pares | matriz n×n (≈1 GB con 6.000 golpes) | árbol de vecinos (0,6 s con 8.000) |
| Memoria del informe | — | 363 MB |
| Página | — | 6 MB; carga en 2,7 s; cada pestaña < 0,4 s; 24 MB de memoria en el navegador |
| Exportación de 24 golpes + montajes + resumen | 203 s (CPU compartida) | 124 s (CPU libre; busca el golpe en la ventana en lugar de decodificarla entera y recorta sin transformación afín): ~4 s por golpe en este servidor de 4 núcleos |

Con datos al azar (sin efectos reales) el modelo no encuentra ninguna diferencia "real" entre
situaciones: 0 falsos positivos.

## Casos límite de los vídeos de entrada (12 variantes del clip del US Open)
Cada variante pasa por las etapas baratas (sonido, planos, jugadores, pista, identidad, candidatos)
y se corta la ventana que usaría la pasada fina; la ventana se compara fotograma a fotograma con la
del vídeo original (desfase y diferencia media de píxel, 0-255).

| Vídeo | Qué hace el programa | Golpes candidatos | Ventana |
|---|---|---|---|
| Original 1080p 60 fps | — | 3 (2,11 · 5,38 · 7,83 s) | 1920×1080, 60 fps |
| Sin sonido | aviso; golpes solo con la imagen | 3 (instantes del pico de muñeca) | idéntica |
| Sonido más corto que el vídeo | usa lo que hay | 3 | idéntica |
| Dos pistas (comentario + ambiente) | analiza las dos; elige por coincidencia con los golpes (con pocos golpes, la principal) | 4 | desfase 1 fotograma, dif. 0,3 |
| .ts con un salto de reloj de 1000 s | copia limpia sin recodificar (duración 12,4 s, no 1006 s) | 3 | idéntica |
| 4K | ventanas a 1920 px; pista escalada | 3 | dif. 0,9 |
| Entrelazado (1080i 25) | un fotograma por campo | 3 | 50 fps, dif. 1,0 |
| fps variables | ventanas a fps constante | 3 | 43,6 fps, desfase 0 |
| 720p 25 fps | — | 3 | dif. 2,3 (menos resolución) |
| Fichero cortado (MP4 con índice delante) | analiza la parte que hay | 2 | idéntica |
| Fichero cortado (.ts) | copia limpia de la parte que hay | 3 | idéntica |
| Ruta con acentos, espacios y apóstrofo | — | 3 | idéntica |
| MP4 cortado sin índice, vacío, texto, solo audio | mensaje claro ("dañado o incompleto", "no tiene pista de vídeo") | — | — |

Con dos pistas de sonido y solo 12 s no hay golpes suficientes para decidir con seguridad (un pico de
muñeca falso coincide por azar con el comentario); con menos de 20 golpes se usa la pista principal,
que también lleva los impactos. En un partido, con cientos de golpes, la elección es clara (prueba
automática con 80 golpes).

## Impactos — F3Set-Tennis (TV, contacto exacto por fotograma)
`uv run python scripts/validate_f3set.py --root <datasets> --player Rybakina --clips 30`
Se ejecuta solo en el PC del usuario (paso 4 de `2_prueba_rapida.bat`): YouTube bloquea las
descargas desde servidores. Descarga solo los segundos de cada punto anotado (4 partidos de
Rybakina en F3Set) y mide, golpe a golpe: detección, derecha/revés, dirección de su golpe
(cruzada, paralela, al centro, invertida cruzada, invertida paralela), subida a la red y errores.
Pendiente del primer resultado.

## Orientación de las cuerdas (3D) — validación sintética
`tennisbio.validation.racket3d_synth.run()` · golpes sintéticos con orientación conocida, cámara
con inclinación 15-25° (el solver asume 20°), ±2 fotogramas de desenfoque en el impacto.
Método actual: silueta (acortamiento del eje y del cabezal) + ancla del impacto + continuidad de
giro (Viterbi de 2.º orden) + ajuste continuo.

Ruido real de la proporción anchura/longitud del cabezal medido en RacketVision:
sd 0,083 con cabezas de 25-50 px y 0,045 con 50-100 px (sesgo +0,05 / +0,01).

| Ruido de la proporción | Error mediano de la normal | ≤15° | ≤30° | "Apunta a…" correcto |
|---|---|---|---|---|
| 0 (ideal) | 0° | 76 % | 81 % | 89 % |
| 0,02 | 14° | 51 % | 65 % | 77 % |
| 0,045 (cabeza 50-100 px) | 21° | 42 % | 58 % | 71 % |
| 0,08 (cabeza 25-50 px) | 26° | 34 % | 54 % | 68 % |

Conclusión: con la silueta sola **no es suficiente**. Incluso sin ruido, ~11 % de fotogramas
caen en la rama espejo. Falta la restricción de la mano/antebrazo en 3D y una medida más
precisa del cabezal (modelo de 5 puntos, más resolución).

### Con la mano y el antebrazo en 3D (RTMW3D)
La normal de la palma (más el desfase de la empuñadura) y la dirección del antebrazo entran como
evidencia ponderada en la búsqueda. Validación sintética con ruido de silueta 0,06:

| Error de la evidencia de la mano | Error mediano | ≤15° | ≤30° | "Apunta a…" correcto |
|---|---|---|---|---|
| Sin mano | 20° | 42 % | 60 % | 72 % |
| 60° | 8,6° | 75 % | 90 % | 87 % |
| 40° | 7,6° | 83 % | 96 % | 91 % |
| 25° | 6,6° | 90 % | 99 % | 92 % |

Pendiente: medir el error real de la palma de RTMW3D en TV (no hay datos públicos con la
orientación 3D de la mano en tenis; primera comprobación por coherencia en clips reales).
