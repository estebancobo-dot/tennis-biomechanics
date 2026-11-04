# Golpes perdidos: recall frente a F3Set

648 golpes anotados de Rybakina en 368 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 462 (71 %)** y 11 más apartados como de identidad dudosa (con ellos 73 %); precisión 88 % (463 de 528 golpes suyos dentro de los puntos; 13 eran golpes de la rival).

**Sin 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina** (anotaciones desfasadas con el vídeo: la mitad o más de sus golpes anotados caen fuera de la cámara principal, que sí se reconoce): **encontrados 461 de 517 (89 %)**; precisión 94 %. Cercana 92 %, lejana 87 %.

| Partido | recall | precisión | principal pérdida |
|---|---|---|---|
| 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin | 133/141 (94 %) | 98 % | jugadora cercana no seguida (sin tramo) (5) |
| 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina (desfasado) | 1/131 (1 %) | 3 % | fuera de la cámara principal (82) |
| 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka | 135/154 (88 %) | 92 % | no confirmado (bola vista) (6) |
| 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina | 193/222 (87 %) | 94 % | no es candidato (15) |

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 59/82 | 82/108 | 70/95 | 0/3 | **211/288** (73 %) |
| lejana | 65/96 | 106/145 | 79/115 | 1/4 | **251/360** (70 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 35 | 49 | **84** |
| jugadora cercana no seguida (sin tramo) | 6 | 10 | **16** |
| descartado como repetición: el mismo recorrido, más lento | 2 | 0 | **2** |
| identidad equivocada | 2 | 10 | **12** |
| no es candidato | 17 | 28 | **45** |
| jugadora lejana no encontrada en la ventana | 0 | 1 | **1** |
| bola no vista y no confirmado | 0 | 1 | **1** |
| no confirmado (bola vista) | 5 | 9 | **14** |

Lo que más importa arreglar: **fuera de la cámara principal** (84 golpes perdidos de 186).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 124/178 (70 %) | fuera de la cámara principal (26) |
| derecha | 188/253 (74 %) | fuera de la cámara principal (28) |
| revés | 149/210 (71 %) | fuera de la cámara principal (29) |
| volea / remate / otro | 1/7 (14 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 523; mal puesta: 12; sin decidir: 5; sin tramo: 108. Perdidos por identidad: 12.

Tramos de la jugadora cercana dentro de puntos anotados: 334.

| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |
|---|---|---|---|---|---|---|
| cambios de lado | 2 | 2 | 0 | 0 | 0 | 0 |
| ropa | 3 | 3 | 0 | 0 | 0 | 0 |
| ropa + clic | 289 | 285 | 4 | 0 | 82 | 66 |
| ropa y cambios de lado | 36 | 27 | 9 | 0 | 2 | 0 |
| sin decidir | 4 | 0 | 0 | 4 | 0 | 0 |

> Nota: 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina: 83 de 85 puntos descargados

> Nota: candidatos del detector entrenado (spotter.enabled), no de las reglas

Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión.
