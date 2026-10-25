# Golpes perdidos: recall frente a F3Set

648 golpes anotados de Rybakina en 368 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 133 (20 %)** y 3 más apartados como de identidad dudosa (con ellos 21 %); precisión 93 % (133 de 143 golpes suyos dentro de los puntos; 3 eran golpes de la rival).

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 17/82 | 45/108 | 38/95 | 0/3 | **100/288** (35 %) |
| lejana | 0/96 | 22/145 | 11/115 | 0/4 | **33/360** (9 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 39 | 50 | **89** |
| jugadora cercana no seguida (sin tramo) | 8 | 9 | **17** |
| descartado como repetición | 34 | 28 | **62** |
| identidad sin decidir | 1 | 1 | **2** |
| identidad equivocada | 2 | 7 | **9** |
| no es candidato | 16 | 26 | **42** |
| criba «sin golpe» (sin pose) | 4 | 35 | **39** |
| bola no vista y no confirmado | 0 | 4 | **4** |
| no confirmado (bola vista) | 81 | 167 | **248** |

Lo que más importa arreglar: **no confirmado (bola vista)** (248 golpes perdidos de 515).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 17/178 (10 %) | no confirmado (bola vista) (56) |
| derecha | 67/253 (26 %) | no confirmado (bola vista) (102) |
| revés | 49/210 (23 %) | no confirmado (bola vista) (88) |
| volea / remate / otro | 0/7 (0 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 528; mal puesta: 9; sin decidir: 5; sin tramo: 106. Perdidos por identidad: 11.

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
