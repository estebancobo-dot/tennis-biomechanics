# Validación de golpes con RacketVision

**Camino medido:** producción: las etapas del análisis (detector entrenado (spotter.enabled: true) → candidates → pasada fina).

Clips: 8 usados de 12 elegidos del conjunto de prueba (4 de dobles y 0 con error, fuera). Tolerancia ±6 fotogramas del vídeo (≈ 0.24 s). Detector: detector entrenado (spotter.enabled: true) → candidates → pasada fina.

| Lado | Anotados | Detectados | Aciertos | Precisión | Recall | F1 | Error de instante (mediana, fotogramas) | Sesgo |
|---|---|---|---|---|---|---|---|---|
| cercano | 16 | 25 | 12 | 0.48 | 0.75 | 0.58 | 2.0 | 1.5 |
| lejano | 13 | 14 | 9 | 0.64 | 0.69 | 0.67 | 2.0 | -0.56 |

## Diferencias con un partido completo

- Los clips de RacketVision no tienen sonido: los rasgos de sonido del detector entrenado van vacíos (se entrenó con ellos).
- Cada clip dura 10 s (100 fotogramas a los 10 fps del detector): poco contexto, ninguno antes del primer segundo ni después del último.
- La identidad no se puede decidir en 10 s de jugadores desconocidos: sus golpes van a strokes_doubtful.json (la aplicación también los cuenta como encontrados); aquí se leen strokes.json y strokes_doubtful.json por lado.
- Referencia: contactos deducidos de la bola anotada (validation.ball_hits, la misma que el camino antiguo); la bola está anotada cada ~12 fotogramas a 60 fps.

Referencia anterior (camino antiguo, petición 154 del PC): petición 154: precisión 0,64, recall 0,74, 19 golpes (lado cercano, run_clip).

## Clips

| Clip | Anotados cerca / lejos | Detectados cerca / lejos | Golpes del detector | Candidatos | Nota |
|---|---|---|---|---|---|
| match1_000 | [] / [459] | [161, 479] / [531] | 3 | 3 |  |
| match104_000 | [31, 179, 315] / [] | [20, 182, 318] / [90] | 4 | 4 |  |
| match112_000 | [51, 112, 192] / [23, 84, 155, 225] | [0, 51, 119, 196] / [21, 86, 151, 225] | 8 | 8 |  |
| match115_000 | [22, 80, 152] / [53, 116, 184] | [21, 83, 151] / [53, 120, 182] | 6 | 6 |  |
| match118_000 | [554] / [] | [214, 553] / [74] | 3 | 3 |  |
| match120_000 | [139, 341] / [] | [168, 371, 447, 582] / [300] | 5 | 5 |  |
| match123_000 | [46, 112] / [23, 79, 159] | [0, 45, 112] / [21] | 4 | 4 |  |
| match126_000 | [63, 202] / [103, 175] | [4, 68, 135, 206] / [174, 235] | 6 | 6 |  |
