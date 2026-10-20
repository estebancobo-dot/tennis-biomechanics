# Detector de golpes entrenado: medida

Validación cruzada por partido: cada uno de los 4 partidos de Rybakina se mide con un modelo entrenado **sin él** (con los otros y 14 de otras jugadoras de F3Set) (±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.

**Golpes encontrados: 798 de 1301 (61 %)**, precisión 53 %, tipo de golpe acertado en el 86 % de los encontrados.

| | saque | derecha | revés | otro | total |
|---|---|---|---|---|---|
| cercana | 99/186 | 173/243 | 135/224 | 1/6 | **408/659** (62 %) |
| lejana | 111/180 | 141/232 | 138/226 | 0/4 | **390/642** (61 %) |

| Partido | encontrados | recall | precisión | cercana | lejana |
|---|---|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 213/279 | 76 % | 76 % | 76 % | 76 % |
| 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina | 33/268 | 12 % | 7 % | 14 % | 11 % |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 239/308 | 78 % | 80 % | 80 % | 75 % |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 313/446 | 70 % | 71 % | 70 % | 70 % |
