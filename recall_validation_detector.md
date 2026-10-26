# Golpes perdidos: recall frente a F3Set

648 golpes anotados de Rybakina en 368 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 412 (64 %)** y 10 más apartados como de identidad dudosa (con ellos 65 %); precisión 88 % (413 de 471 golpes suyos dentro de los puntos; 10 eran golpes de la rival).

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 45/82 | 74/108 | 64/95 | 0/3 | **183/288** (64 %) |
| lejana | 58/96 | 95/145 | 74/115 | 2/4 | **229/360** (64 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 35 | 49 | **84** |
| jugadora cercana no seguida (sin tramo) | 6 | 9 | **15** |
| descartado como repetición | 34 | 28 | **62** |
| identidad equivocada | 2 | 7 | **9** |
| no es candidato | 16 | 26 | **42** |
| bola no vista y no confirmado | 0 | 1 | **1** |
| no confirmado (bola vista) | 3 | 10 | **13** |

Lo que más importa arreglar: **fuera de la cámara principal** (84 golpes perdidos de 236).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 103/178 (58 %) | fuera de la cámara principal (26) |
| derecha | 169/253 (67 %) | fuera de la cámara principal (28) |
| revés | 138/210 (66 %) | fuera de la cámara principal (29) |
| volea / remate / otro | 2/7 (29 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 528; mal puesta: 9; sin decidir: 5; sin tramo: 106. Perdidos por identidad: 9.

Tramos de la jugadora cercana dentro de puntos anotados: 330.

| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |
|---|---|---|---|---|---|---|
| cambios de lado | 2 | 2 | 0 | 0 | 0 | 0 |
| ropa | 3 | 3 | 0 | 0 | 0 | 0 |
| ropa + clic | 286 | 283 | 3 | 0 | 81 | 67 |
| ropa y cambios de lado | 35 | 26 | 9 | 0 | 2 | 0 |
| sin decidir | 4 | 0 | 0 | 4 | 0 | 0 |

> Nota: 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina: 83 de 85 puntos descargados

> Nota: candidatos del detector entrenado (spotter.enabled), no de las reglas

Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión.
