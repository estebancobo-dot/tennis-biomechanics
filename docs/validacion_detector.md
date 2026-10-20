# Detector de golpes entrenado: medida

Validación cruzada por partido: cada uno de los 4 partidos de Rybakina se mide con un modelo entrenado **sin él** (con los otros y 3 de otras jugadoras de F3Set) (±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.

**Golpes encontrados: 631 de 1301 (48 %)**, precisión 47 %, tipo de golpe acertado en el 86 % de los encontrados.

| | saque | derecha | revés | otro | total |
|---|---|---|---|---|---|
| cercana | 92/186 | 157/243 | 125/224 | 1/6 | **375/659** (57 %) |
| lejana | 54/180 | 96/232 | 106/226 | 0/4 | **256/642** (40 %) |

| Partido | encontrados | recall | precisión | cercana | lejana |
|---|---|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 198/279 | 71 % | 71 % | 81 % | 61 % |
| 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina | 26/268 | 10 % | 6 % | 12 % | 8 % |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 189/308 | 61 % | 70 % | 68 % | 54 % |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 218/446 | 49 % | 63 % | 62 % | 36 % |
