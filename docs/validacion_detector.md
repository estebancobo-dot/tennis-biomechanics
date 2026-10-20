# Detector de golpes entrenado: medida

Validación cruzada por partido: cada uno de los 4 partidos de Rybakina se mide con un modelo entrenado **sin él** (con los otros y 0 de otras jugadoras de F3Set) (±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.

**Golpes encontrados: 618 de 1301 (48 %)**, precisión 61 %, tipo de golpe acertado en el 86 % de los encontrados.

| | saque | derecha | revés | otro | total |
|---|---|---|---|---|---|
| cercana | 88/186 | 146/243 | 108/224 | 1/6 | **343/659** (52 %) |
| lejana | 56/180 | 123/232 | 96/226 | 0/4 | **275/642** (43 %) |

| Partido | encontrados | recall | precisión | cercana | lejana |
|---|---|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 195/279 | 70 % | 71 % | 78 % | 61 % |
| 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina | 7/268 | 3 % | 7 % | 4 % | 1 % |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 159/308 | 52 % | 67 % | 54 % | 49 % |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 257/446 | 58 % | 64 % | 64 % | 51 % |

Primera medida (20-10, 04:30 UTC): solo con los 4 partidos de Rybakina (la descarga de otros partidos la bloqueó YouTube),
esqueleto a 10 fps y sin la jugadora lejana en las características (el detector barato no la ve: solo el sonido la delata).
Cuenta los golpes de **las dos** jugadoras (la identidad la pone después el clic). El partido de cuartos del Australian Open
falla antes del detector: solo el 34 % de su vídeo se reconoce como juego (cámara principal), pendiente de arreglar.
Antes, con las reglas a mano: 10 de 642 golpes suyos (2 %), `recall_validation.md` de la petición 35.
