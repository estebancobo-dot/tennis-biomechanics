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
