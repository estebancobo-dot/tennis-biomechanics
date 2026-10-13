# Prueba de modelos en este PC (2026-10-13 22:14, dml, 48.0 min de este tramo)

| Variante | ms/fotograma | F1 golpes | Precisión | Recall | Error instante | Temblor (% altura) | Seguida | Pies | Dif. FP16 (px) |
|---|---|---|---|---|---|---|---|---|---|
| yolo11m-pose@960 | 279.8 | 0.643 | 0.6 | 0.692 | 1.0 | 0.734 | 0.996 | 0.0 | — |
| rtmpose-x | 719.5 | 0.64 | 0.667 | 0.615 | 1.0 | 0.281 | 1.0 | 0.887 | — |
| rtmpose-m | 327.1 | 0.56 | 0.583 | 0.538 | 1.0 | 0.302 | 1.0 | 0.964 | — |
| yolo11m-pose@960-fp16 | 128.2 | 0.643 | 0.6 | 0.692 | 1.0 | 0.73 | 0.996 | 0.0 | 0.25 |
| hybrid-x-fp16 | 268.4 | 0.667 | 0.643 | 0.692 | 1.0 | 0.477 | 0.996 | 0.997 | — |
| hybrid-x | 305.2 | 0.667 | 0.643 | 0.692 | 1.0 | 0.482 | 0.996 | 0.997 | — |
| rtmpose-x-fp16 | 1806.8 | 0.64 | 0.667 | 0.615 | 1.0 | 0.282 | 1.0 | 0.886 | 0.14 |
| yolo11m-pose@640 | 151.9 | 0.714 | 0.667 | 0.769 | 1.0 | 0.772 | 0.98 | 0.0 | — |

| Bola | Encontradas a ≤10 px | ms/fotograma |
|---|---|---|
| balltrack | 0.86 | 167.5 |
| balltrack-fp16 | 0.86 | 173.4 |

**Recomendadas frente a la actual (yolo11m-pose@960):** rtmpose-x: con pies (F1 0.64 frente a 0.643; 719.5 frente a 279.8 ms/fotograma); yolo11m-pose@960-fp16: más rápida (F1 0.643 frente a 0.643; 128.2 frente a 279.8 ms/fotograma); hybrid-x-fp16: con pies (F1 0.667 frente a 0.643; 268.4 frente a 279.8 ms/fotograma); hybrid-x: con pies (F1 0.667 frente a 0.643; 305.2 frente a 279.8 ms/fotograma); rtmpose-x-fp16: con pies (F1 0.64 frente a 0.643; 1806.8 frente a 279.8 ms/fotograma)
