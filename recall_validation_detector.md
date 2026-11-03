# Golpes perdidos: recall frente a F3Set

648 golpes anotados de Rybakina en 368 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 413 (64 %)** y 10 más apartados como de identidad dudosa (con ellos 65 %); precisión 88 % (414 de 471 golpes suyos dentro de los puntos; 10 eran golpes de la rival).

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 43/82 | 73/108 | 64/95 | 0/3 | **180/288** (62 %) |
| lejana | 59/96 | 98/145 | 74/115 | 2/4 | **233/360** (65 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 36 | 49 | **85** |
| jugadora cercana no seguida (sin tramo) | 6 | 10 | **16** |
| descartado como repetición: el mismo recorrido, más lento | 35 | 26 | **61** |
| identidad equivocada | 2 | 6 | **8** |
| no es candidato | 16 | 25 | **41** |
| bola no vista y no confirmado | 0 | 1 | **1** |
| no confirmado (bola vista) | 4 | 9 | **13** |

Lo que más importa arreglar: **fuera de la cámara principal** (85 golpes perdidos de 235).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 102/178 (57 %) | fuera de la cámara principal (27) |
| derecha | 171/253 (68 %) | fuera de la cámara principal (28) |
| revés | 138/210 (66 %) | fuera de la cámara principal (29) |
| volea / remate / otro | 2/7 (29 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 526; mal puesta: 9; sin decidir: 5; sin tramo: 108. Perdidos por identidad: 8.

Tramos de la jugadora cercana dentro de puntos anotados: 334.

| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |
|---|---|---|---|---|---|---|
| cambios de lado | 2 | 2 | 0 | 0 | 0 | 0 |
| ropa | 3 | 3 | 0 | 0 | 0 | 0 |
| ropa + clic | 289 | 286 | 3 | 0 | 82 | 66 |
| ropa y cambios de lado | 36 | 27 | 9 | 0 | 2 | 0 |
| sin decidir | 4 | 0 | 0 | 4 | 0 | 0 |

> Nota: 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina: 83 de 85 puntos descargados

> Nota: candidatos del detector entrenado (spotter.enabled), no de las reglas

Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión.
