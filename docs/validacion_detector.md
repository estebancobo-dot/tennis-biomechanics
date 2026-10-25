# Detector de golpes entrenado: medida

Validación cruzada por partido: cada uno de los 3 partidos de Rybakina se mide con un modelo entrenado **sin él** (con los otros y 16 de otras jugadoras de F3Set) (±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.

Con la bola (8 números por fotograma: `tennisbio.ball_features`). Se excluye el cuarto de final del Australian Open 2023 (Ostapenko – Rybakina): el 70 % de sus golpes anotados en F3Set caen fuera de la cámara principal del vídeo de YouTube (anotaciones desfasadas con ese vídeo), así que no sirve ni para entrenar ni para medir.

**Golpes encontrados: 928 de 1046 (89 %)**, precisión 86 %, tipo de golpe acertado en el 92 % de los encontrados.

| | saque | derecha | revés | otro | total |
|---|---|---|---|---|---|
| cercana | 128/143 | 189/207 | 160/176 | 0/2 | **477/528** (90 %) |
| lejana | 133/142 | 164/197 | 154/177 | 0/2 | **451/518** (87 %) |

| Partido | encontrados | recall | precisión | cercana | lejana |
|---|---|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 258/287 | 90 % | 83 % | 91 % | 89 % |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 276/308 | 90 % | 90 % | 94 % | 85 % |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 394/451 | 87 % | 86 % | 88 % | 87 % |
