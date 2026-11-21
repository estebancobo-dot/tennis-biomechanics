# Cola de la nube

Última vuelta: 2026-11-21 18:49 UTC · Modal: quedan 0.44 $ de 30 $ este mes (tope de la cola 29.5 $) · Kaggle: quedan 18.6 h de GPU esta semana (tope 28 h; Kaggle dice 6.84 h usadas de 30.0, se renueva 2026-11-28 00:00)

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
| prueba_gauff_v22 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v23_calidad | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v22_v23 | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.acceleration, technique.pose.finish, racket_track, technique.pose.ready; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.ready.racket_angle, face.acceleration.tilt_deg, technique.pose.acceleration, phases.takeback.frame |
| prueba_gauff_rtmw | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v22_rtmw | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 2 distintos, medidas fuera de tolerancia: technique.phases.loaded.head_vs_hips, technique.phases.acceleration.x_factor, technique.phases.extension.hip_turn, phases.extension.confidence; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.loaded.head_vs_hips, technique.jitter.footwork.back_heel_lift, face.finish.observed, technique.jitter.takeback.knee_non |
| comparar_gauff_v22_rtmw_b | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 2 distintos, medidas fuera de tolerancia: metrics.non_elbow_impact_deg, technique.pose.ready, technique.phases.acceleration.wrist_dom_height, technique.phases.acceleration.x_factor; strokes.json: temblor de b frente a a ×0.99 (mediana de 4944 medidas; b tiembla menos en el 50 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: face.extension.yaw_deg, technique.phases.acceleration. |
| comparar_gauff_v22_v23_b | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.ready, technique.pose.extension, technique.pose.finish, racket_track; strokes.json: temblor de b frente a a ×1.00 (mediana de 5308 medidas; b tiembla menos en el 36 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.takeback.hip_turn, technique.curves.hand, technique. |
| prueba_gauff_v24 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v25_calidad | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v24_v25 | comparar |  | revisar | github | distinta; 7 etapas iguales; distintas: candidates, fine, fine_doubtful, identity, players, slowmo_fine, spotting, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 3 distintos, medidas fuera de tolerancia: technique.pose.extension, technique.pose.loaded, technique.pose.finish, technique.pose.ready; strokes.json: temblor de b frente a a ×1.00 (mediana de 5308 medidas; b tiembla menos en el 36 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: face.acceleration.tilt_deg, technique.pose.extension, techni |
| medir_youtube | medir |  | hecho | kaggle |  |
| prueba_gauff_v26 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v27_pose16 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v28_ocrgpu | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v26_v27 | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 28 de 28/28 golpes emparejados, 1 distintos, medidas fuera de tolerancia: technique.pose.loaded, technique.pose.ready, technique.pose.extension, technique.pose.finish; strokes.json: temblor de b frente a a ×1.00 (mediana de 5310 medidas; b tiembla menos en el 32 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.jitter.loaded.racket_tip_height, technique.phases.loaded.x_factor, technique.phases.loaded |
| comparar_gauff_v26_v28 | comparar |  | hecho | github | idéntica; 16 etapas iguales; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| investigar_tennis_mentor | investigar |  | hecho | kaggle |  |
| investigar_tennis_mentor_voz | investigar |  | hecho | kaggle |  |
| investigar_short_usuario_306 | investigar |  | hecho | kaggle |  |
| prueba_gauff_v29_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v29_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v29_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: T24 (15-11 20:00): las partes no reutilizan lo de la anterior: la huella de un modelo lleva la fecha de su fichero y cada sesión lo baja de Modal con fecha nueva (v29_b repitió los cortes; v29_c los repetía otra vez y seguiría con lo de GPU en la CPU). Se arregla la huella (por contenido) y la prueba se repite como v30 |
| comparar_gauff_v26_v29 | comparar |  | error |  | cancelado: sin la v29_c (ver arriba) |
| medir_bola_totnet | medir |  | error | kaggle | cancelado: T15 (15-11 23:20): en CPU no cabe en las 12 h de una sesión de Kaggle: cada clip de RacketVision tiene 600 fotogramas a 60 fps (300 ventanas de TOTNet) y cada ventana tarda unos 6 s en la CPU, unas 20 h para los 40 clips (calculé mal 3-5 h); se cortaría sin resultado. Se repite en GPU (medir_bola_totnet_gpu), con la misma regla |
| medir_sapiens2 | medir | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle |  |
| medir_sapiens2_b | medir | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| medir_sapiens2_rapido | medir | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v33_sapiens2 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v26_v33 | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 26 de 28/28 golpes emparejados, 4 distintos, medidas fuera de tolerancia: technique.phases.finish.hands_apart, technique.phases.recovery.base_width, technique.phases.extension.elbow_dom_lateral, technique.phases.loaded.elbow_dom_vs_shoulder; strokes.json: temblor de b frente a a ×2.09 (mediana de 3861 medidas; b tiembla menos en el 29 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 0 de 1/1 golpes emparejados, 2 distintos |
| prueba_gauff_v34_sapiens2 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle |  |
| comparar_gauff_v26_v34 | comparar |  | error |  | cancelado: sin la v34: se paró a los 5 min sin modelos (el ONNX de Sapiens2 se subió junto a /models/models/ y tapó los demás; arreglado); se compara con la v35 |
| leer_v34 | leer |  | hecho | github | leídos: runs__kaggle_prueba_gauff_v34_sapiens2__log.txt |
| prueba_gauff_v35_sapiens2 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v26_v35 | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 2 distintos, medidas fuera de tolerancia: technique.pose.acceleration, technique.phases.acceleration.wrist_non_height, technique.pose.ready, racket_track; strokes.json: temblor de b frente a a ×1.00 (mediana de 4930 medidas; b tiembla menos en el 50 %); strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados, medidas fuera de tolerancia: technique.phases.acceleration.shoulder_abd_non, technique.footwork.steps, techniq |
| comparar_gauff_v26_v35b | comparar |  | revisar | github | distinta; 12 etapas iguales; distintas: fine, fine_doubtful, slowmo_fine, view_clips; strokes.json: 27 de 28/28 golpes emparejados, 2 distintos, medidas fuera de tolerancia: technique.pose.impact, technique.pose.extension, technique.pose.loaded, technique.pose.finish; strokes.json: temblor de b frente a a ×1.00 (mediana de 4930 medidas; b tiembla menos en el 50 %); strokes.json: temblor por familias: brazos ×0.95, muñecas ×0.98, otras ×1.00, piernas ×0.93, pies ×1.00, raqueta ×0.98, tronco ×0.98; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparej |
| leer_v26_v35 | leer |  | hecho | github | leídos: kaggle_pruebas__prueba_gauff_v26__output___prueba_tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5__strokes.json (cortado a 512 KB), kaggle_pruebas__prueba_gauff_v35_sapiens2__output___prueba_tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5__strokes.json (cortado a 512 KB) |
| medir_lejana_rfdetr | medir |  | hecho | kaggle |  |
| prueba_gauff_v36_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v36_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v36_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v32_v36 | comparar |  | hecho | github | equivalente; 15 etapas iguales; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| prueba_gauff_v37_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v37_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v37_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v36_v37 | comparar |  | revisar | github | distinta; 14 etapas iguales; distintas: fine; strokes.json: 28 de 28/28 golpes emparejados, medidas fuera de tolerancia: height_scale.px; strokes.json: temblor de b frente a a ×1.00 (mediana de 5337 medidas; b tiembla menos en el 0 %); strokes.json: temblor por familias: brazos ×1.00, muñecas ×1.00, otras ×1.00, piernas ×1.00, pies ×1.00, raqueta ×1.00, tronco ×1.00; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| medir_bola_totnet_gpu | medir |  | hecho | kaggle |  |
| prueba_gauff_v30_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v30_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v30_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: T24 (15-11 21:00): la v30_b también repitió los cortes (122 s, velocidad de GPU, frente a los 516 s de la v30_a en CPU): queda otra causa además de R55; la v30_c en la CPU repetiría lo de GPU. Se diagnostica con leer_v30 |
| comparar_gauff_v26_v30 | comparar |  | error |  | cancelado: sin la v30_c (ver arriba) |
| leer_v30 | leer |  | hecho | github | leídos: runs__kaggle_prueba_gauff_v30_a__log.txt, runs__kaggle_prueba_gauff_v30_b__log.txt, kaggle_pruebas__prueba_gauff_v30_a__output___prueba_tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5__video.json, kaggle_pruebas__prueba_gauff_v30_a__output___prueba_tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5__manifest.json, kaggle_pruebas__prueba_gauff_v30_a__output___prueba_tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5__probe.json |
| prueba_gauff_v31_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v31_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v31_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: T24 (15-11 22:35): la parte c (CPU) repetía players en la CPU: la huella de players y de la pasada fina lleva fp16 solo en GPU (uses_fp16), así que en CPU no coincidía con lo de la parte b. Se cancela antes de que suba un players de CPU; se arregla (una parte usa lo que hizo la anterior) y se repite solo la parte c |
| comparar_gauff_v26_v31 | comparar |  | error |  | cancelado: sin la v31_c (ver arriba); se compara con la parte c repetida |
| prueba_gauff_v31_c2 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v26_v31c2 | comparar |  | hecho | github | equivalente; 13 etapas iguales; distintas: audio, slowmo_fine, views; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| prueba_gauff_v32_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v32_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v32_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| comparar_gauff_v26_v32 | comparar |  | hecho | github | equivalente; 13 etapas iguales; distintas: audio, slowmo_fine, views; strokes.json: 28 de 28/28 golpes emparejados; strokes_opponent.json: 0 de 0/0 golpes emparejados; strokes_doubtful.json: 1 de 1/1 golpes emparejados |
| leer_v31 | leer |  | hecho | github | leídos: runs__kaggle_prueba_gauff_v31_a__log.txt, runs__kaggle_prueba_gauff_v31_b__log.txt |
| leer_zheng_errores | leer |  | hecho | github | leídos: output__zheng-qinwen-elena-rybakina__strokes_errores.json |
| prueba_gauff | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | modal |  |
| prueba_gauff_v16 | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | en cola de Kaggle más de 10 min sin arrancar (4 intentos) |
| prueba_gauff_v16b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| gauff | partido | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | error | kaggle | cancelado: R48: con la raqueta en la CPU su pasada fina gastaría ~6 h de más; se relanza como gauff_b con el arreglo cuando la v20 lo compruebe (su pasada barata, ya en Modal, se reutiliza) |
| gauff_b | partido | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_final | prueba | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | hecho | modal |  |
| final | partido | tennis-yusipopen-final-sobolenko-rybakina-12-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_sinner | prueba | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | error | kaggle | cancelado: #295: la prueba corta de un partido espera con su partido a la nube nativa (comprueba el código con el que se analizará); se repite entonces como prueba_sinner_b |
| prueba_sinner_b | prueba | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | hasta acabar la nube nativa (modelos medidos en la nube; #295) |
| sinner_a | partido | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a prueba_sinner_b (pendiente) |
| sinner_b | partido | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a sinner_a (pendiente) |
| sinner | partido | zverev-alexander-sinner-jannik-indian-wells-2026-semi-final | pendiente |  | espera a sinner_b (pendiente) |
| actualizar_osaka_a | partido | us-open-2026-r4-naomi-osaka-elena-rybakina | pendiente |  | espera a sinner (pendiente) |
| actualizar_osaka_b | partido | us-open-2026-r4-naomi-osaka-elena-rybakina | pendiente |  | espera a actualizar_osaka_a (pendiente) |
| actualizar_osaka | partido | us-open-2026-r4-naomi-osaka-elena-rybakina | pendiente |  | espera a actualizar_osaka_b (pendiente) |
| actualizar_pegula_a | partido | elena-rybakina-jessica-pegula-miami-2026-quarter-final | pendiente |  | espera a actualizar_osaka (pendiente) |
| actualizar_pegula_b | partido | elena-rybakina-jessica-pegula-miami-2026-quarter-final | pendiente |  | espera a actualizar_pegula_a (pendiente) |
| actualizar_pegula | partido | elena-rybakina-jessica-pegula-miami-2026-quarter-final | pendiente |  | espera a actualizar_pegula_b (pendiente) |
| actualizar_zheng_a | partido | zheng-qinwen-elena-rybakina | pendiente |  | espera a actualizar_pegula (pendiente) |
| actualizar_zheng_b | partido | zheng-qinwen-elena-rybakina | pendiente |  | espera a actualizar_zheng_a (pendiente) |
| actualizar_zheng | partido | zheng-qinwen-elena-rybakina | pendiente |  | espera a actualizar_zheng_b (pendiente) |
| informe_beta | informe |  | hecho | modal |  |
| informe_beta2 | informe |  | hecho | kaggle |  |
| informe_beta3 | informe |  | hecho | kaggle |  |
| medir_app | medir |  | hecho | kaggle |  |
| medir_f3set_hoy | medir |  | error | kaggle | cancelado: 21-11 14:25: sus 3 cuadernos se quedaron «en cola» en Kaggle (desde las 10:16) mientras trabajos lanzados después arrancaban al momento; el mismo trabajo con otro nombre (medir_f3set_hoy_b) dice si es el cuaderno o el trabajo |
| medir_3d_metrabs | medir |  | error | kaggle |  |
| medir_3d_metrabs_b | medir |  | error | kaggle | cancelado: 21-11 13:10: 2 h en cola de Kaggle sin GPU libre (no empezó): su plaza, para comprobar la P100 (medir_raqueta_p100); se lanza otra vez en la GPU que sirva |
| medir_raqueta_p100 | medir |  | hecho | kaggle |  |
| medir_3d_metrabs_c | medir |  | hecho | kaggle |  |
| medir_f3set_hoy_b | medir |  | en_marcha | kaggle | Kaggle: running (18:49), intento 2; en cola de Kaggle más de 45 min mientras otro trabajo lanzado después ya arrancó (cuaderno atascado) |
| prueba_gauff_v38_a | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | hecho | kaggle |  |
| prueba_gauff_v38_b | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | en_marcha | kaggle | Kaggle: queued (18:49), intento 2; en cola de Kaggle más de 180 min sin arrancar |
| prueba_gauff_v38_c | prueba | tennis-yusipopen-polufinal-gauff-rybakina-10-09-2026-1080r-5 | pendiente |  | espera a prueba_gauff_v38_b (en_marcha) |
| comparar_gauff_v36_v38 | comparar |  | pendiente |  | espera a prueba_gauff_v38_c |
| informe_6 | informe |  | pendiente |  | espera a actualizar_zheng (pendiente) |
