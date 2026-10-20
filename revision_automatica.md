# Revisión automática: REGRESIÓN

284 cumplidos · 23 no cumplidos · 121 sin golpes suficientes · 89 avisos (antes: 283 cumplidos, 31 no cumplidos)

## Peticiones del usuario SIN TERMINAR: 114 de 219

Registro `docs/peticiones_usuario.md`: 95 hechas · 94 a medias · 20 sin hacer · 3 no medibles desde la tele · 7 no aplican. Que las comprobaciones de abajo pasen **no** significa que estas estén hechas.

- **#1 [FALTA]** Derecha de Rybakina en sus 4 partidos completos, una vez y al final (10-10 17:27; 11-10 19:37) — falta: Ningún partido completo analizado. 19-10: el análisis de los 4 partidos encuentra como mucho el 43 % de sus golpes y el 29 % de sus saques (`audit.recall_items…
- **#155 [FALTA]** es fisicamente imposible que en un partido solo de 86 o 77 golpes ... no quiero que se pierdan golpes (Chat, 19-10 06:15) — falta: Detección sin arreglar: como mucho 43 % de sus golpes y 29 % de sus saques en la final del US Open. Falta correr el banco de 650 golpes anotados y corregir la …
- **#176 [FALTA]** Nuevo split step antes del siguiente golpe de la rival (Matriz (literatura), §3) — falta: La ventana acaba 0,8 s tras el impacto: medible alargándola.
- **#189 [FALTA]** «Cómo» de la fase 1: «mirando la raqueta de la rival» (YouTube, 18-10 Olivari 4) — falta: No está en `learn.py`.
- **#193 [FALTA]** Mano libre en la aceleración y el impacto (pliegue, que no cruce) (Guía Ivanovic, hueco 10) — falta: No hay medida ni punto de control (`impact.wrist_non_lateral` no existe).
- **#196 [FALTA]** Medidas de lado: codo por delante de la cadera, inclinación del tronco en la espera (Guía Ivanovic, hueco 18) — falta: No están en `practice.SIDE_METRICS`.
- **#197 [FALTA]** Progresión por etapas sin calendario y paso a pista (Guía Ivanovic, hueco 19) — falta: Pendiente de confirmar con el usuario (descartó la hoja de sesión).
- **#198 [FALTA]** Tiempo entre puntos (rutina) bajo presión (Guía Ivanovic, hueco 20) — falta: Opcional, fuera del golpe.
- **#199 [FALTA]** Bote: GBDT/CatBoost sobre la trayectoria (Estado del arte, 13-10) — falta: Sigue la heurística.
- **#200 [FALTA]** Pista: TennisCourtDetector (14 puntos) + refinado (Estado del arte, 13-10) — falta: Sigue la detección por líneas propia.
- **#201 [FALTA]** Marcador: rapidocr 3.x con PP-OCRv5 (Estado del arte, 13-10) — falta: Hecho solo «OCR cuando cambia».
- **#202 [FALTA]** Bola: probar WASB (Estado del arte, 13-10) — falta: No probado.
- **#203 [FALTA]** 3D: prueba A/B con MotionAGFormer (Estado del arte, 13-10) — falta: No probado.
- **#204 [FALTA]** Golpe: clasificador aprendido con F3Set (E2E-Spot/F3ED) (Estado del arte, 13-10) — falta: No hecho; ayudaría a la pérdida de golpes del 19-10.
- **#205 [FALTA]** Volumen: unos 400 golpes con 4 partidos (Comparativa apps, §4.3) — falta: Los 4 partidos dieron menos de la mitad de sus golpes.
- **#209 [FALTA]** Passing y globo (Revisión completa, §3 B) — falta: Medible en parte (rival en la red + trayectoria); sin hacer.
- **#210 [FALTA]** Dejada (bote muy corto en campo rival) (Revisión completa, §3 B) — falta: Medible con el bote de su bola; sin hacer.
- **#211 [FALTA]** CHECKS de la mano en el armado da por hecho que va por debajo del hombro (Auditorías 17-10, técnica #5) — falta: Decir «a la altura que marca su valor».
- **#216 [FALTA]** Pendiente de la guía: punta arriba/codo alto, terminación hacia adelante, codo libre (Auditorías 17-10, técnica #25) — falta: Ver huecos 3 y 9 de Ivanovic.
- **#217 [FALTA]** Documentos desactualizados (aprendido_entrenadores §2 y §4) (Auditorías 17-10, técnica #26) — falta: Sin prueba de que se actualizaran.
- **#2 [PARCIAL]** Ver informe y salidas en el móvil (11-10 18:21, 18:29, 18:33) — falta: 19-10: copia hecha; el paso directo al Pixel 8 sin probar en el teléfono.
- **#4 [PARCIAL]** Responder de forma profesional a «¿qué hay que hacer para pegar como X?», con todas las posibilidades y como base para cualquiera (11-10 19… — falta: Valores de 1 a 10 golpes, todos «provisional». SuD, `copy_cue` y `COACH` no se ven (≥12).
- **#5 [PARCIAL]** Taxonomía completa con todas las variantes (bola rápida/lenta, alta/baja, corta/profunda, carrera/parada/salto, apoyo, dirección, ataque/de… — falta: 0 de 2.992 combinaciones con ≥12. Niveles vacíos: parada 0, paralela 0, rodilla 0, en el aire 0. 19-10: faltaban de su mensaje del 10-10 18:05 «ángulos» (golpe…
- **#6 [PARCIAL]** Juego de pies: split step, primer paso, ajuste, reacción, recuperación (11-10 08:22, 19:23) — falta: Pasos medidos en el 40 % de los golpes. El golpe capturado dice «no medible» en el primer paso, el ajuste y tras golpear.
- **#7 [PARCIAL]** Empuñadura en la espera y al golpear (11-10 19:23) — falta: El bisel no se mide. `ready_hands` da «mano libre separada» en el 100 % (7 golpes) y en revés a dos manos, contra R2 de los entrenadores: medida dudosa. La lis…
- **#9 [PARCIAL]** Información, no tablas; profesional, «con sentido humano», nivel de las apps punteras (10-10 18:09-18:47; 11-10 18:06-19:23; 12-10 16:22-17… — falta: SuD vacía. Comparativas: 8 «Sin datos…». Explorador: 41 «—». El 13-10 05:48 el usuario dice que «no vale para nada».
- **#10 [PARCIAL]** Ver los cambios en la prueba rápida, sin 1 h (12-10 17:32, 17:40) — falta: Una medida nueva exige volver a analizar el vídeo: la prueba media dura 5 h 02 min. La prueba rápida deja unas 5 derechas.
- **#11 [PARCIAL]** Validar solo que las salidas reales tienen todo lo pedido y todos los casos del modelo y la taxonomía (12-10 13:14, 16:36, 17:10; 13-10 05:… — falta: Comprueba que la estructura existe, no que el valor sea correcto. Las peticiones 64-113 no tienen regla.
- **#12 [PARCIAL]** Validar cada medida con clips públicos anotados; el usuario no valida a mano (11-10 09:05, 09:12) — falta: Ninguna medida corporal (codo, rodillas, pasos, apoyo, fases) está validada.
- **#13 [PARCIAL]** Casos nominales, límite, esquina y error en fuentes, algoritmos, IA, procesado, rendimiento e informe (11-10 19:23) — falta: Ningún partido completo. En la última ejecución, la etapa `fine` falló en 4 golpes.
- **#15 [PARCIAL]** Bajar y analizar vídeos de entrenadores de YouTube para aprender y encontrar huecos (12-10 16:30-17:51) — falta: 6 de las 15 mejoras siguen en NO o a medias (filas 99-113).
- **#16 [PARCIAL]** Distinguir por contexto (derecha junto a la red o volea) y cubrir las medias voleas (10-10 18:05; 11-10 09:02) — falta: Ningún caso en los datos (0 y 0). La volea no tiene técnica propia. 20-10: la regla de la media volea es una sola para la clase y la marca de revisión (`techni…
- **#17 [PARCIAL]** Una entrada que se entienda sola: «no entiendo nada ni cómo usarla» (12-10 16:22) — falta: La segunda pestaña (SuD) está vacía. Aprende y SuD se solapan. Las «Novedades» están en SuD.
- **#23 [PARCIAL]** Seguir a la jugadora en los cambios de lado (10-10 17:27) — falta: Sin validar con datos anotados. 19-10: fallos de identidad en los partidos completos; validar con `validation/recall_eval.py`.
- **#25 [PARCIAL]** Métricas por derecha: apoyo, base, rodillas, cadera, hombros, X-factor, codo, impacto, cadena, pista (10-10 17:27) — falta: X-factor 2D: mediana de 1° en Aprende, sospechoso (fila 113). 19-10: giro de hombros y X-factor 2D salen «sesgo» y no se dan; rodillas con escorzo; impacto del…
- **#36 [PARCIAL]** Mano y antebrazo, cierre de la muñeca (11-10 09:56, 10:19) — falta: El lag sale en el 40 % de los golpes y Aprende lo da con **1 golpe**.
- **#45 [PARCIAL]** Todo automático y completo: el usuario no revisa nada (11-10 09:05, 19:38; 12-10 11:41) — falta: 4 golpes fallaron (`strokes_errores.json`) y nadie los recupera.
- **#55 [PARCIAL]** Ver una bola cerca de la red y un apoyo cerrado con golpe paralelo (12-10 17:40) — falta: En sus datos hay 0 paralelas y 1 cerrado más «invertida paralela»: el ejemplo no se puede ver. 19-10: apoyo cerrado + paralela sí se combinan; «cerca de la red…
- **#64 [PARCIAL]** Todos los tipos de desplazamiento, del split step a la recuperación, con cada tipo de paso; «hay que hacer la inversa» (12-10 18:03, 18:06;… — falta: El paso cruzado no aparece en ningún golpe. El primer paso y el ajuste salen «no medible» si los tobillos se ven quietos menos del 40 % del tiempo.
- **#68 [PARCIAL]** La meta: mejorar mi derecha tomando la de X como base (12-10 22:25; 13-10 05:48 p5) — falta: Valores provisionales de 1-10 golpes. Sin progresión ni prioridad (qué copiar primero según lo que la distingue).
- **#69 [PARCIAL]** Ejemplo: «derecha paralela, apoyo cerrado, parada, bola plana, lado derecho» (cómo lo hace ella y cómo replicarlo) (13-10 05:48 p8) — falta: Con sus datos hay 0 golpes exactos: se quitan las 5 condiciones y se ven las 10 derechas. «Qué cambia» es texto general, no lo que hace ella.
- **#70 [PARCIAL]** Las 2000 y pico combinaciones, usables y validadas (13-10 05:48 p2; 06:00) — falta: Combinaciones de medida y nivel: 0 de 2.992 visibles. Solo se prueba un trío o más (el ejemplo del usuario).
- **#71 [PARCIAL]** El conocimiento de los vídeos de entrenadores en la web (12-10 21:31; 13-10 05:48 p3) — falta: La fuente es una etiqueta genérica. Falta «Lo que la distingue» (mejora 12). El examen R no sale en la web (decisión de diseño).
- **#72 [PARCIAL]** El conocimiento del chat (modelo técnico, taxonomía, matriz) implementado en la web, no solo en documentos (13-10 06:00, 06:30) — falta: Está en la web, pero con 10 golpes casi nada se puede afirmar. SuD (fases, `copy_cue`) no se ve.
- **#73 [PARCIAL]** Revisar la web de arriba abajo para que aporte valor (13-10 05:48 p6) — falta: SuD vacía, Comparativas con 8 «Sin datos», Explorador con 41 «—». Panel dice 14 derechas y Aprende 10 (cuenta las lejanas).
- **#74 [PARCIAL]** ¿El análisis de las apps de pago y libres fue profundo o superficial? (13-10 05:48 p7) — falta: Solo documental: sin contrastar pantalla a pantalla. Aprende imita las posiciones P de Sportsbox.
- **#77 [PARCIAL]** No lanzar pruebas de 6 h para validar (13-10 06:01) — falta: Validar el análisis exige la prueba media (5 h).
- **#78 [PARCIAL]** No depender de que al usuario se le ocurran funciones (13-10 06:09) — falta: Quedan sin hacer 4 mejoras propuestas por Claude (filas 102, 106, 110, 112).
- **#79 [PARCIAL]** Vídeos de entrenamiento con otras cámaras, en un apartado aparte y marcado (12-10 21:31, 21:32) — falta: Solo 3 derechas de lado medidas (de 23 laterales), así que no hay resumen. En Aprende, «— menos de 12» aunque haya 13 estimaciones 3D.
- **#84 [PARCIAL]** Matriz §1 Cadena cinética (suelo → pelvis → separación → tronco → codo → muñeca) (12-10 21:14) — falta: Fuerza contra el suelo, pronación y snap: solo «no medible». X-factor 1°. Lag con 1 golpe.
- **#85 [PARCIAL]** Matriz §2 Cuerpo (cabeza, brazos, tronco, piernas, pie de arrastre) — falta: Mirada y core: no medibles. Cabeza quieta: 2 golpes. Rodillas desde detrás: escorzo; la rodilla de lado sale «—».
- **#86 [PARCIAL]** Matriz §3 Raqueta (bucle, caída, cara, trayectoria) — falta: Caída bajo la bola solo de lado («—»). Dentro-fuera: no medible. Cara en el impacto estimada.
- **#88 [PARCIAL]** Matriz §5 Pies (split, ajuste, cruzado, paso de ataque, recuperación) — falta: El paso cruzado nunca aparece. Pasos en 4 de 10 golpes.
- **#89 [PARCIAL]** Matriz §6 Modalidades (plano, liftado, cortado, botepronto, volea, 3 terminaciones) — falta: «Plano» = trayectoria, no efecto: 0 casos. Botepronto y volea: 0. Terminaciones: sí.
- **#90 [PARCIAL]** Matriz §7 Adaptación a la bola (rápida, corta, alta, lateral) — falta: Ningún nivel llega a 12 golpes. «Qué cambia» es texto genérico, no su cambio medido.
- **#91 [PARCIAL]** Matriz §8 Dirección (cruzado, paralelo, dentro-fuera, dentro-dentro) — falta: Paralela 0, invertida cruzada 0.
- **#92 [PARCIAL]** Matriz §9 Control (zona de impacto, relajación, equilibrio) — falta: «Delante de la cadera» solo de lado o en 3D: en Aprende «—». Equilibrio: 1 golpe.
- **#95 [PARCIAL]** Matriz §12 Neuro y visión (latencia, mirada, EMG) — falta: Latencia con 4 golpes. Mirada y EMG: no medibles.
- **#97 [PARCIAL]** Matriz §14 Fugas de energía (apertura prematura, casting, vector) — falta: Casting solo de lado (3 golpes, «—»).
- **#100 [PARCIAL]** Mejora 2: raqueta al lado del cuerpo o detrás de la espalda, y adónde apunta la punta — falta: Sale «—» en sus 10 golpes. `tip_points_to` no existe.
- **#107 [PARCIAL]** Mejora 9: caída por debajo de la bola — falta: Desde la tele no existe.
- **#109 [PARCIAL]** Mejora 11: frases con datos existentes (mano libre, terminación, base al terminar, desplazarse bajo) — falta: Faltan la mano libre en el armado, `finish.elbow_non`, la base al terminar y la cadera durante el desplazamiento.
- **#113 [PARCIAL]** Mejora 15: examen interno con las afirmaciones de entrenadores (R1-R25) — falta: Nada confirmado ni refutado. R2 apunta a un fallo de `ready_hands` (100 % «mano libre separada»).
- **#124 [PARCIAL]** Hacia dónde mira el tronco y las manos en la espera, medidas fiables (13-10 13:00) — falta: Manos en la espera solo en 3 de 10 golpes (la raqueta casi no se ve en la espera).
- **#130 [PARCIAL]** Resto de derecha (devolver el saque) con todas sus variantes, en la matriz y en la aplicación (13-10 14:30) — falta: Pocos restos en la prueba corta; primer/segundo saque es probable (un corte entre saques lo confunde); el tipo de resto sale de las clases de preparación, term…
- **#135 [PARCIAL]** distancia al fondo, red (Chat, 11-10 19:23) — falta: Hay distancia al fondo, pero no a la red: «dentro de la pista» junta todo lo que está a más de 0,5 m dentro de la línea, de la zona de saque a la red. 20-10: h…
- **#140 [PARCIAL]** de la jugadora de fondo se sacan imagenes para la captura de datos en vista frontal? (Chat, 14-10 20:08) — falta: No se usa como vista frontal para medidas del cuerpo: a 60-90 px los tobillos y la raqueta salen imprecisos.
- **#142 [PARCIAL]** (punto 2) como se puede hacer una aplicacion profesional ... mas jugadores, mas golpes ... como se lanza, almacenamiento, videos, progreso … — falta: Construida y probada, pero el análisis real de los 4 partidos (18-10) se lanzó con el ciclo, no desde la aplicación; nunca usada con datos correctos.
- **#143 [PARCIAL]** (punto 3) esta es una guia para la derecha de otra jugadora ... revisar si aplica todo (Chat, 17-10 09:49) — falta: De sus 20 huecos, 7 siguen a medias o sin hacer (ver fuente «Guía Ivanovic»).
- **#147 [PARCIAL]** la guia de ivanovic esta aplicada al 100 por 100? sobre todo los puntos 1 2 3 5 6 y 10 (Chat, 17-10 10:52) — falta: 3 a medias (falta «punta arriba / codo alto»), 6 a medias (faltan 3 alarmas), 10 sin hacer (mano libre en aceleración e impacto).
- **#154 [PARCIAL]** mi movil es android google pixel 8 ... que copie directo al pixel (Chat, 18-10 12:11) — falta: Sin probar con el teléfono conectado.
- **#156 [PARCIAL]** como sabes la identidad de la jugadora y porque hay fallos? porque no buscas en la web de la wta la imagen y altura (Chat, 19-10 06:29) — falta: Fallos sin explicar ni corregir; una foto de la WTA sería una fuente externa (requisito 6) y no sirve desde detrás: la identidad debe validarse con `validation…
- **#159 [PARCIAL]** volea a media pista con el golpe de fondo derecha o reves (sin ser empuñadura de volea) (Chat, 19-10 08:11) — falta: La empuñadura no se ve en la tele: el golpe de fondo se reconoce por el swing (preparación no compacta y terminación completa). La medida «bola seguida» (`ball…
- **#160 [PARCIAL]** la app que hiciste completa como se arranca, se puede usar ahora? (Chat, 19-10 08:11) — falta: Arranca, pero los análisis de los 4 partidos no son válidos (golpes perdidos).
- **#162 [PARCIAL]** Galerías ordenadas por calidad de captura, representatividad y resultado del punto (CLAUDE.md, Informe) — falta: No hay orden por resultado del punto (solo filtro).
- **#163 [PARCIAL]** Final del armado (máximo giro, raqueta más atrás) (Matriz (literatura), §1) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#164 [PARCIAL]** Final de la extensión (Matriz (literatura), §1) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#165 [PARCIAL]** Giro de cadera y de hombros al final del armado (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#166 [PARCIAL]** Separación cadera–hombros (X-factor) (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#167 [PARCIAL]** Cabeza quieta tras el impacto (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#168 [PARCIAL]** Hombros más girados que la cadera en el impacto (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#169 [PARCIAL]** Transferencia de peso del armado al impacto (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#170 [PARCIAL]** Empuje de piernas («bajar y subir») (Matriz (literatura), §2) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#171 [PARCIAL]** Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral) (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#172 [PARCIAL]** Cada paso nombrado: lateral (sin cruzar), cruzado, de carrera, hacia delante, hacia atrás, de ajuste (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#173 [PARCIAL]** Frenado: último paso largo con caída de la velocidad (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#174 [PARCIAL]** Patada atrás (tijera) tras el impacto (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#175 [PARCIAL]** Recuperación: tipo de cada paso de vuelta, cuándo empieza (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#177 [PARCIAL]** Orientación del pie (talón → dedo gordo respecto a la línea de fondo) en el armado y el impacto (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#178 [PARCIAL]** Pivote sobre la punta del pie de atrás (talón arriba, punta apoyada) (Matriz (literatura), §3) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#179 [PARCIAL]** Raqueta al lado del cuerpo o por detrás de la espalda en el armado (debate WTA/ATP) (Matriz (literatura), §4) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#180 [PARCIAL]** Retraso de la muñeca (lag) (Matriz (literatura), §4) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#181 [PARCIAL]** Cara en el impacto (Matriz (literatura), §4) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#182 [PARCIAL]** Velocidad de la raqueta relativa entre golpes (Matriz (literatura), §4) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#183 [PARCIAL]** Posición de la mano en el mango (Matriz (literatura), §4) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#184 [PARCIAL]** Altura de la bola en su vuelo, bote, punto más alto; contacto subiendo / arriba / cayendo (Matriz (literatura), §5) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#185 [PARCIAL]** Longitud del peloteo (Matriz (literatura), §5) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#186 [PARCIAL]** Resto, globo, dejada, volea, subida a la red (Matriz (literatura), §5) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#187 [PARCIAL]** Ganador / error (forzado o no) (Matriz (literatura), §5) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#188 [PARCIAL]** Resto de primer o de segundo saque (Matriz (literatura), §5b) — falta: Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral.
- **#190 [PARCIAL]** Clase de forma del armado: bucle verdadero, loop falso, recto atrás; tendencia «punta arriba / codo alto» (Guía Ivanovic, hueco 3) — falta: Falta la tendencia «punta arriba / codo alto».
- **#191 [PARCIAL]** Alarmas por golpe: cara al cielo, punta hacia la red tras el giro, pausa arriba, caída bajo la rodilla, cabeza que sube, retrocede en el im… — falta: Faltan «punta hacia la red tras el giro», «caída bajo la rodilla» y «se mueve hacia atrás en el impacto»; la alarma de pausa usa una medida declarada no medibl…
- **#192 [PARCIAL]** Terminación «hacia adelante», «la mano libre recoge la raqueta», codo al terminar (Guía Ivanovic, hueco 9) — falta: Faltan el nivel «hacia adelante» en `technique.finish_class` y el codo libre al terminar (`finish.elbow_non`).
- **#194 [PARCIAL]** «Sus principios» (5-6 frases) y «Lo que la distingue» (Guía Ivanovic, hueco 13) — falta: No hay «Sus principios».
- **#195 [PARCIAL]** Fuentes en COACH: Iino y Kojima 2001, Bahamonde y Knudson 2003, Kawamoto 2019, LTA, Wulf, autoinstrucciones (Guía Ivanovic, hueco 17) — falta: Faltan Iino, Kojima, Bahamonde, Knudson 2003, Kawamoto, LTA y el metaanálisis.
- **#206 [PARCIAL]** Validación de cuerdas y 3D con referencia real (Comparativa apps, §4.4) — falta: Sin referencia 3D real.
- **#207 [PARCIAL]** Golpes: sin volea, remate ni cortado (Comparativa apps, §3 Peor) — falta: Sin técnica propia de volea, remate ni cortado. 20-10: la volea también a media pista y fuera de la línea de saque (`class.contact_type`).
- **#208 [PARCIAL]** Lógica duplicada JS/Python: calcular una vez en Python (Revisión completa, §2 fallo 17) — falta: La plantilla aún calcula en JavaScript partes de Comparar, la videoteca y la lección.
- **#212 [PARCIAL]** Grados de estimaciones poco fiables como objetivo (cara en el impacto) (Auditorías 17-10, técnica #15) — falta: Sigue mostrando grados en el impacto.
- **#213 [PARCIAL]** Textos COACH (el porqué con fuente) en todas las claves de la lección (Auditorías 17-10, técnica #17) — falta: Sin COACH: `footwork.recovery_start_s`, `class.recovery_first_step`, `footwork.rear_leg_step_after`, `class.approach_main`.
- **#214 [PARCIAL]** Fuentes de Ivanovic §3 #17 (Auditorías 17-10, técnica #18) — falta: Ver hueco 17 de Ivanovic.
- **#215 [PARCIAL]** Armado «antes» o «al» bote según el sitio (Auditorías 17-10, técnica #22) — falta: Unificar en «armado completo cuando bota».
- **#218 [PARCIAL]** La fuente son los partidos: que funcione la vista de fondo en los dos lados, que funcionen las repeticiones (velocidad normal o cámara lent… — falta: Falta validarlo con los partidos reales (umbrales de clasificación), medir sobre esas tomas (pasada fina en la cámara lenta: `views.fine_on_slowmo`, pendiente)…
- **#219 [PARCIAL]** Las tomas de la cámara de fondo cuentan para los dos lados: golpes del fondo contados y con lo medible a esa distancia, no descartados (19-… — falta: Se confirman ~20 % de los golpes del fondo (Zheng: 36 de ~175).


## No cumplidos

- **Golpes encontrados frente al marcador: smoke_tennis-yusipopen-final-sobolenko-rybakin**: marcador: 45-51 puntos jugados (7 juegos leídos, 0 sin leer), 17 con su saque. Esperados: 17-38 saques (1 o 2 por punto de saque) y 72-133 golpes en total (rango típico de 1.6-2.6 golpes suyos por punto, no exacto). Encontrados: 27 golpes, 1 saques/remates → como mucho 38% de sus golpes y 6% de sus 
- **Partido smoke_tennis-yusipopen-final-sobolenko-rybakin: salida de cada etapa, ventanas y series**: 15 ficheros de etapa, 27 golpes con ventana y serie; faltan o están vacíos: spotting/spotting.json
- **#1 Derecha de Rybakina en sus 4 partidos completos, una vez y al final**: SIN HACER según el registro (#1, docs/peticiones_usuario.md)
- **#83 Árbol de ficheros generados y validados**: 4 comprobaciones: 1 falta, 3 ok; la peor: «Partido smoke_tennis-yusipopen-final-sobolenko-rybakin: salida de cada etapa, ventanas y series» (15 ficheros de etapa, 27 golpes con ventana y serie; faltan o están vacíos: spotting/spotting.json)
- **#155 es fisicamente imposible que en un partido solo de 86 o 77 golpes ... no quiero que se pierdan golpes (Chat, 1**: SIN HACER según el registro (#155, docs/peticiones_usuario.md)
- **#176 Nuevo split step antes del siguiente golpe de la rival (Matriz (literatura), §3)**: SIN HACER según el registro (#176, docs/peticiones_usuario.md)
- **#189 «Cómo» de la fase 1: «mirando la raqueta de la rival» (YouTube, 18-10 Olivari 4)**: SIN HACER según el registro (#189, docs/peticiones_usuario.md)
- **#193 Mano libre en la aceleración y el impacto (pliegue, que no cruce) (Guía Ivanovic, hueco 10)**: SIN HACER según el registro (#193, docs/peticiones_usuario.md)
- **#196 Medidas de lado: codo por delante de la cadera, inclinación del tronco en la espera (Guía Ivanovic, hueco 18)**: SIN HACER según el registro (#196, docs/peticiones_usuario.md)
- **#197 Progresión por etapas sin calendario y paso a pista (Guía Ivanovic, hueco 19)**: SIN HACER según el registro (#197, docs/peticiones_usuario.md)
- **#198 Tiempo entre puntos (rutina) bajo presión (Guía Ivanovic, hueco 20)**: SIN HACER según el registro (#198, docs/peticiones_usuario.md)
- **#199 Bote: GBDT/CatBoost sobre la trayectoria (Estado del arte, 13-10)**: SIN HACER según el registro (#199, docs/peticiones_usuario.md)
- **#200 Pista: TennisCourtDetector (14 puntos) + refinado (Estado del arte, 13-10)**: SIN HACER según el registro (#200, docs/peticiones_usuario.md)
- **#201 Marcador: rapidocr 3.x con PP-OCRv5 (Estado del arte, 13-10)**: SIN HACER según el registro (#201, docs/peticiones_usuario.md)
- **#202 Bola: probar WASB (Estado del arte, 13-10)**: SIN HACER según el registro (#202, docs/peticiones_usuario.md)
- **#203 3D: prueba A/B con MotionAGFormer (Estado del arte, 13-10)**: SIN HACER según el registro (#203, docs/peticiones_usuario.md)
- **#204 Golpe: clasificador aprendido con F3Set (E2E-Spot/F3ED) (Estado del arte, 13-10)**: SIN HACER según el registro (#204, docs/peticiones_usuario.md)
- **#205 Volumen: unos 400 golpes con 4 partidos (Comparativa apps, §4.3)**: SIN HACER según el registro (#205, docs/peticiones_usuario.md)
- **#209 Passing y globo (Revisión completa, §3 B)**: SIN HACER según el registro (#209, docs/peticiones_usuario.md)
- **#210 Dejada (bote muy corto en campo rival) (Revisión completa, §3 B)**: SIN HACER según el registro (#210, docs/peticiones_usuario.md)
- **#211 CHECKS de la mano en el armado da por hecho que va por debajo del hombro (Auditorías 17-10, técnica #5)**: SIN HACER según el registro (#211, docs/peticiones_usuario.md)
- **#216 Pendiente de la guía: punta arriba/codo alto, terminación hacia adelante, codo libre (Auditorías 17-10, técnic**: SIN HACER según el registro (#216, docs/peticiones_usuario.md)
- **#217 Documentos desactualizados (aprendido_entrenadores §2 y §4) (Auditorías 17-10, técnica #26)**: SIN HACER según el registro (#217, docs/peticiones_usuario.md)

## Empeora respecto a la ejecución anterior

- **Partido smoke_tennis-yusipopen-final-sobolenko-rybakin: salida de cada etapa, ventanas y series**: ok → falta: 15 ficheros de etapa, 27 golpes con ventana y serie; faltan o están vacíos: spotting/spotting.json
- **#83 Árbol de ficheros generados y validados**: ok → falta: 4 comprobaciones: 1 falta, 3 ok; la peor: «Partido smoke_tennis-yusipopen-final-sobolenko-rybakin: salida de cada etapa, ventanas y series» (15 ficheros de etapa, 27 golpes con ventana y serie; faltan

## Mejora

- #4 Responder de forma profesional a «¿qué hay que hacer para pegar como X?», con todas las posibilidades y como b: falta → pocos datos
- #5 Taxonomía completa con todas las variantes (bola rápida/lenta, alta/baja, corta/profunda, carrera/parada/salto: falta → pocos datos
- #16 Distinguir por contexto (derecha junto a la red o volea) y cubrir las medias voleas: falta → pocos datos
- #89 Matriz §6 Modalidades (plano, liftado, cortado, botepronto, volea, 3 terminaciones): aviso → pocos datos
- #90 Matriz §7 Adaptación a la bola (rápida, corta, alta, lateral): falta → pocos datos
- #132 ángulos (golpe angulado) — repetido el 19-10 08:11: «golpe angulado ... te lo he dicho muchas veces» (Chat, 10: falta → pocos datos
- #157 bola corta baja cerca de la red (Chat, 19-10 08:11): aviso → pocos datos
- #158 bola corta alta cerca de la red (Chat, 19-10 08:11): aviso → pocos datos
- #159 volea a media pista con el golpe de fondo derecha o reves (sin ser empuñadura de volea) (Chat, 19-10 08:11): falta → pocos datos
- #218 La fuente son los partidos: que funcione la vista de fondo en los dos lados, que funcionen las repeticiones (v: falta → aviso

## Comprobaciones nuevas

- Repeticiones y otras cámaras enlazadas: smoke_tennis-yusipopen-final-sobolenko-rybakin: ok (48% de sus golpes con repetición enlazada (13 de 27, 0 a cámara lenta) · 82% con otra cámara (22) · tomas: 22 repeticiones, 2 laterales, 1 frontales, 96 primero)
- 5. Bola, resultado y contexto · Golpe angulado (cruzado, corto y junto al lateral): ok (medido en el 60% de los golpes y en el informe)
- 5. Bola, resultado y contexto · Bola corta cerca de la red: baja, media, alta: ok (medido en el 100% de los golpes y en el informe (parcial: ver la matriz))
- Golpe angulado (#132): pocos datos (0 golpes de 10 (la clase «Golpe angulado» se pudo decidir en 6; sin señal, ninguna clase: nunca se inventa); sin golpes suficientes (se enseña con ≥ 12))
- Bola corta baja cerca de la red (#157): pocos datos (0 golpes de 10 (la clase «Bola corta cerca de la red» se pudo decidir en 0; sin señal, ninguna clase: nunca se inventa); sin golpes suficientes (se enseña con ≥)
- Bola corta alta cerca de la red (#158): pocos datos (0 golpes de 10 (la clase «Bola corta cerca de la red» se pudo decidir en 0; sin señal, ninguna clase: nunca se inventa); sin golpes suficientes (se enseña con ≥)
- Volea a media pista con golpe de fondo (#159): pocos datos (0 golpes de 10 (la clase «Contacto» se pudo decidir en 8; sin señal, ninguna clase: nunca se inventa); sin golpes suficientes (se enseña con ≥ 12))
- Volea fuera de la línea de saque: pocos datos (0 golpes de 10 (la clase «Contacto» se pudo decidir en 8; sin señal, ninguna clase: nunca se inventa); sin golpes suficientes (se enseña con ≥ 12))
- Botepronto / media volea: casos (#16): pocos datos (0 golpes de 10 (la clase «Contacto» se pudo decidir en 8; sin señal, ninguna clase: nunca se inventa); candidatos marcados por la misma regla: 0; golpes sin bot)

## Comprobaciones que ya no aparecen

- Golpe angulado (10-10 18:05, 19-10 08:11)
- Bola corta baja / alta cerca de la red (19-10 08:11)
- Volea a media pista con golpe de fondo (19-10 08:11)
