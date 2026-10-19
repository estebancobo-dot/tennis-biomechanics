# Golpes perdidos: recall frente a F3Set

613 golpes anotados de Rybakina en 349 puntos de 4 partidos (tolerancia ±0.2 s). **Encontrados 0 (0 %)**; precisión 0 % (0 de 3 golpes suyos dentro de los puntos; 0 eran golpes de la rival).

## Recall por lado y tipo

| | saque | derecha | revés | volea / remate / otro | total |
|---|---|---|---|---|---|
| cercana | 0/77 | 0/105 | 0/90 | 0/3 | **0/275** (0 %) |
| lejana | 0/91 | 0/134 | 0/109 | 0/4 | **0/338** (0 %) |

## Dónde se pierden (primera etapa que falla)

| Etapa | cercana | lejana | total |
|---|---|---|---|
| fuera de la cámara principal | 39 | 48 | **87** |
| jugadora cercana no seguida (sin tramo) | 6 | 6 | **12** |
| descartado como repetición | 26 | 31 | **57** |
| identidad sin decidir | 185 | 235 | **420** |
| identidad equivocada | 2 | 5 | **7** |
| no es candidato | 15 | 10 | **25** |
| criba «sin golpe» (sin pose) | 2 | 0 | **2** |
| no confirmado (bola vista) | 0 | 3 | **3** |

Lo que más importa arreglar: **identidad sin decidir** (420 golpes perdidos de 613).

## Por tipo de golpe

| Tipo | recall | etapa principal de pérdida |
|---|---|---|
| saque | 0/168 (0 %) | identidad sin decidir (107) |
| derecha | 0/239 (0 %) | identidad sin decidir (171) |
| revés | 0/199 (0 %) | identidad sin decidir (140) |
| volea / remate / otro | 0/7 (0 %) | no es candidato (4) |

## Identidad

Golpes suyos en un tramo con la identidad bien puesta: 33; mal puesta: 7; sin decidir: 474; sin tramo: 99. Perdidos por identidad: 427.

Tramos de la jugadora cercana dentro de puntos anotados: 314.

| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |
|---|---|---|---|---|---|---|
| cambios de lado | 32 | 23 | 9 | 0 | 2 | 0 |
| conflicto | 5 | 0 | 0 | 5 | 0 | 0 |
| ropa | 3 | 3 | 0 | 0 | 0 | 0 |
| sin decidir | 274 | 0 | 0 | 274 | 73 | 73 |

> Nota: 20200218-W-Dubai-R32-Elena_Rybakina-Sofia_Kenin: 78 de 84 puntos descargados

> Nota: 20230124-W-Australian_Open-QF-Jelena_Ostapenko-Elena_Rybakina: 81 de 85 puntos descargados

> Nota: 20230126-W-Australian_Open-SF-Elena_Rybakina-Victoria_Azarenka: 76 de 78 puntos descargados

> Nota: 20230128-W-Australian_Open-F-Aryna_Sabalenka-Elena_Rybakina: 114 de 123 puntos descargados

Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión.
