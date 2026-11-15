# Cola de la nube

Última vuelta: 2026-11-15 04:48 UTC · Modal: quedan 0.53 $ de 30 $ este mes (tope de la cola 29.5 $) · Kaggle: quedan 4.1 h de GPU esta semana (tope 28 h; Kaggle dice 17.26 h usadas de 30.0, se renueva 2026-11-21 00:00)

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
| prueba_gauff_v20 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v19_v20 | comparar |  | hecho | github | idéntica; 16 etapas iguales; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| prueba_gauff_v21_calidad | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v20_v21 | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.finish, racket_track, technique.pose.impact, technique.pose.acceleration; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.ready.hands_apart, technique.jitter.loaded.front_foot_angle_deg, technique.phases.ready.base_width, technique.phases.impact.hip_tilt |
| comparar_gauff_v20_v21b | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.ready, technique.pose.impact, technique.pose.acceleration, technique.pose.loaded; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.ready.racket_head_vs_wrist, technique.jitter.ready.hip_turn, technique.jitter.ready.face_tilt, technique.jitter.impact.face_tilt |
| comparar_gauff_v20_v21c | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.loaded, technique.pose.acceleration, technique.pose.impact, racket_track; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.pose.loaded, technique.phases.loaded.x_factor, technique.jitter.ready.arm_extension, technique.phases.ready.base_width |
| comparar_gauff_v20_v21d | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.loaded, technique.pose.finish, technique.pose.extension, technique.pose.ready; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.pose.takeback, technique.jitter.ready.shoulder_turn, technique.phases.ready.shoulder_turn, face.takeback.tilt_deg |
| prueba_gauff_v22 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | pendiente |  | sin capacidad: kaggle: ocupado con final, gauff_b |
| prueba_gauff_v23_calidad | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | pendiente |  | sin capacidad: kaggle: ocupado con final, gauff_b |
| comparar_gauff_v22_v23 | comparar |  | pendiente |  | espera a prueba_gauff_v22, prueba_gauff_v23_calidad |
| prueba_gauff | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | modal |  |
| prueba_gauff_v16 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | en cola de Kaggle más de 10 min sin arrancar (4 intentos) |
| prueba_gauff_v16b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| gauff | partido | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: R48: con la raqueta en la CPU su pasada fina gastaría ~6 h de más; se relanza como gauff_b con el arreglo cuando la v20 lo compruebe (su pasada barata, ya en Modal, se reutiliza) |
| gauff_b | partido | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | en_marcha | kaggle | Kaggle: running (04:48), intento 1 · fine:  91 % (334/368 golpes candidatos · 325 confirmados · 0 ventanas descartadas sin pose) · 88 min · quedan ≈ 9 min (04:48:29; GPU 79 %·43 %, CPU 83 %, 12.3 GB) |
| prueba_final | prueba | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | hecho | modal |  |
| final | partido | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | en_marcha | kaggle | Kaggle: running (04:48), intento 1 · fine:  82 % (310/377 golpes candidatos · 294 confirmados · 0 ventanas descartadas sin pose) · 80 min · quedan ≈ 17 min (04:47:59; GPU 0 %·3 %, CPU 85 %, 12.3 GB) |
| prueba_sinner | prueba | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a final (en_marcha) |
| sinner | partido | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a prueba_sinner (pendiente) |
| actualizar_osaka | partido | us-open-2026-r4-naomi-osaka-elena-rybakina | pendiente |  | espera a sinner (pendiente) |
| actualizar_pegula | partido | elena-rybakina-jessica-pegula-miami-2026-quarter-final | pendiente |  | espera a actualizar_osaka (pendiente) |
| actualizar_zheng | partido | zheng-qinwen-elena-rybakina | pendiente |  | espera a actualizar_pegula (pendiente) |
| informe_6 | informe |  | pendiente |  | espera a actualizar_zheng (pendiente) |
