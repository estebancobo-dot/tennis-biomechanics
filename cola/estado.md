# Cola de la nube

Última vuelta: 2026-11-14 23:54 UTC · Modal: quedan 0.53 $ de 30 $ este mes (tope de la cola 29.5 $) · Kaggle: quedan 9.8 h de GPU esta semana (tope 28 h)

| Trabajo | Acción | Partido | Estado | Dónde | Nota |
|---|---|---|---|---|---|
| medir_raqueta_trt | medir |  | hecho | kaggle |  |
| medir_raqueta_trt_b | medir |  | hecho | kaggle |  |
| medir_video_nvdec | medir | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v17 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v18 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: la v19 comprueba lo mismo (el dispositivo y la subida) y además las 2 T4: 0,9 h de cuota ahorradas y una plaza libre; si la v19 sale distinta, se repite para aislar la causa |
| comparar_gauff_v16b_v18 | comparar |  | error |  | cancelado: sin la v18 (ver arriba) |
| prueba_gauff_v19 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v16b_v19 | comparar |  | hecho | github | idéntica; 16 etapas iguales; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| perfil_gauff_fina | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v20 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | en_marcha | kaggle | Kaggle: running (23:54), intento 1 · fine:  25 % (7/28 golpes candidatos · 7 confirmados · 0 ventanas descartadas sin pose) · 2 min · quedan ≈ 5 min (23:54:08; GPU 14 %·8 %, CPU 85 %, 10.6 GB) |
| comparar_gauff_v19_v20 | comparar |  | pendiente |  | espera a prueba_gauff_v20 |
| prueba_gauff | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | modal |  |
| prueba_gauff_v16 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | en cola de Kaggle más de 10 min sin arrancar (4 intentos) |
| prueba_gauff_v16b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| gauff | partido | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | en_marcha | kaggle | Kaggle: running (23:54), intento 1 · identity terminada a las 23:43:37 en 8.0 min (23:52:33; GPU 54 %·0 %, CPU 39 %, 4.8 GB) |
| prueba_final | prueba | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | hecho | modal |  |
| final | partido | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | pendiente |  | sin capacidad: kaggle: ocupado con gauff, prueba_gauff_v20; Modal: quedan 0.53 $ este mes y necesita 13.65 $; pc: no se usa (decisión del usuario, 14-11, #284) |
| prueba_sinner | prueba | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a final (pendiente) |
| sinner | partido | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a prueba_sinner (pendiente) |
| actualizar_osaka | partido | us-open-2026-r4-naomi-osaka-elena-rybakina | pendiente |  | espera a sinner (pendiente) |
| actualizar_pegula | partido | elena-rybakina-jessica-pegula-miami-2026-quarter-final | pendiente |  | espera a actualizar_osaka (pendiente) |
| actualizar_zheng | partido | zheng-qinwen-elena-rybakina | pendiente |  | espera a actualizar_pegula (pendiente) |
| informe_6 | informe |  | pendiente |  | espera a actualizar_zheng (pendiente) |
