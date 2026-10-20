# Golpes perdidos: recall frente a F3Set

642 golpes anotados de Rybakina en 366 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 10 (2 %)** y 74 más apartados como de identidad dudosa (con ellos 13 %); precisión 36 % (10 de 28 golpes suyos dentro de los puntos; 14 eran golpes de la rival).

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 3/82 | 5/108 | 2/95 | 0/3 | **10/288** (4 %) |
| lejana | 0/95 | 0/141 | 0/114 | 0/4 | **0/354** (0 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 39 | 50 | **89** |
| jugadora cercana no seguida (sin tramo) | 8 | 9 | **17** |
| descartado como repetición | 30 | 26 | **56** |
| identidad sin decidir | 91 | 150 | **241** |
| identidad equivocada | 26 | 32 | **58** |
| no es candidato | 22 | 33 | **55** |
| jugadora lejana no encontrada en la ventana | 0 | 1 | **1** |
| criba «sin golpe» (sin pose) | 0 | 7 | **7** |
| no confirmado (bola vista) | 8 | 26 | **34** |

Lo que más importa arreglar: **identidad sin decidir** (241 golpes perdidos de 632).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 3/177 (2 %) | identidad sin decidir (65) |
| derecha | 5/249 (2 %) | identidad sin decidir (96) |
| revés | 2/209 (1 %) | identidad sin decidir (78) |
| volea / remate / otro | 0/7 (0 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 114; mal puesta: 60; sin decidir: 362; sin tramo: 106. Perdidos por identidad: 299.

Tramos de la jugadora cercana dentro de puntos anotados: 328.

| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |
|---|---|---|---|---|---|---|
| cambios de lado | 88 | 61 | 27 | 0 | 21 | 18 |
| ropa | 3 | 3 | 0 | 0 | 0 | 0 |
| ropa y cambios de lado | 35 | 26 | 9 | 0 | 2 | 0 |
| sin decidir | 202 | 0 | 0 | 202 | 57 | 48 |

> Nota: 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin: 83 de 84 puntos descargados

> Nota: 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina: 83 de 85 puntos descargados

> Nota: 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina: 122 de 123 puntos descargados

Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión.
