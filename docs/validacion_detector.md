# Detector de golpes entrenado: medida

Validación cruzada por partido: cada uno de los 4 partidos de Rybakina se mide con un modelo entrenado **sin él** (con los otros y 7 de otras jugadoras de F3Set) (±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.

**Golpes encontrados: 730 de 1301 (56 %)**, precisión 51 %, tipo de golpe acertado en el 84 % de los encontrados.

| | saque | derecha | revés | otro | total |
|---|---|---|---|---|---|
| cercana | 95/186 | 166/243 | 135/224 | 1/6 | **397/659** (60 %) |
| lejana | 74/180 | 124/232 | 135/226 | 0/4 | **333/642** (52 %) |

| Partido | encontrados | recall | precisión | cercana | lejana |
|---|---|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 196/279 | 70 % | 73 % | 82 % | 59 % |
| 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina | 39/268 | 15 % | 8 % | 16 % | 13 % |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 219/308 | 71 % | 72 % | 72 % | 70 % |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 276/446 | 62 % | 70 % | 66 % | 58 % |
