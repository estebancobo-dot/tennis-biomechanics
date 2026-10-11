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

## Impactos — F3Set-Tennis (TV, contacto exacto por fotograma)
`uv run python scripts/validate_f3set.py --root <datasets> --player Rybakina --clips 20`
Se ejecuta en el PC del usuario (los vídeos vienen de YouTube, bloqueado desde la nube).
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
