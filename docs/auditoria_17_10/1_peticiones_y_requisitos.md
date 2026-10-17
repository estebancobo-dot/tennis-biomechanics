# Auditoría de la web frente a las peticiones y al modelo técnico

**Conclusión:** la lección («Cópiala») se ve bien en el PC y la nueva estructura merece quedarse. Pero en tres cosas contradice requisitos vinculantes:
- **Cuerdas:** no aparecen en ninguna fase de la lección (requisito 4).
- **Medidas no fiables:** las pantallas antiguas enseñan y usan como «hallazgo» medidas que la propia web declara no fiables (requisito 3).
- **Vídeo primero:** en la pantalla de entrada el vídeo queda por debajo del primer pantallazo (requisito 2).

Además hay 6 fallos de código concretos: el informe deja de funcionar si no hay ningún golpe, Comparar trata un dato que falta como si fuera 0, y hay textos y recuentos que se contradicen.

No he modificado ningún fichero. Las capturas recortadas están en `/tmp/claude-0/aud1/capturas_prueba/`.

**Sobre los datos:** las 9 capturas del 17-10 son del informe de `_smoke` (10 derechas cercanas y 4 lejanas), no del partido entero. `auditoria_poc9_largo.md` (55 derechas cercanas) es del 15-10, **antes de la lección**. La lección no se ha visto nunca con el partido entero. `revision_automatica.md` da OK: 284 cumplidos, 0 no cumplidos, 117 sin golpes suficientes y 21 avisos.

---

## 1. Tabla de peticiones y requisitos

Abreviaturas: **L** = lección de «Cópiala» · **C-plegado** = «4 · Todas las medidas» · **AG** = Sus golpes › un golpe · **SPT** = «Su patrón típico» (plegado al final de Cópiala).

### A. Requisitos vinculantes de `CLAUDE.md`

| # | Requisito | Dónde está en la web | Estado | Qué falta exactamente |
|---|---|---|---|---|
| R1 | «¿Qué hay que hacer para pegar como X?», con todas las variantes y toda la taxonomía | Cópiala: condiciones (13 grupos), L con 8 fases y pies, C-plegado, SPT | **A medias** | **Ataque/defensa y bola centrada/abierta no se pueden elegir:** `learn.CONDITIONS` no tiene `intent` ni `width`, aunque los datos existen (`model.FACTORS`, `technique.py:493`). **La lección solo dice qué cambia según la velocidad de la bola** (`lBySpeed`), no según altura, profundidad, carrera o apoyo. **Empuñadura:** ausente de la lección y de «6 · Lo que la tele no permite medir»; solo aparece en SPT (`explain.grip_compatible`). |
| R2 | Información y no tablas; vídeo primero; pocos números | L (vídeo en bucle y como mucho 3 claves); AG | **A medias / se contradice** | **Pantalla de entrada:** a 1440 px, la guía y el selector de condiciones (unos 1000 px) empujan el vídeo a y≈1120 (captura 1). **Tablas sin frase:** Explorador y Comparar abren la «Tabla completa» desplegada. **Fichas sin nombre:** la videoteca titula cada golpe con el id crudo (`smoke_tennis-yusipopen-…-0013323`). |
| R3 | Nada inventado; no mostrar lo no fiable; diferencias solo sobre el error | Cópiala (`aStat` usa `DATA.reliability`); Fiabilidad | **Se contradice fuera de Cópiala** | **Métricas, Comparar, Explorador, Conclusiones y Hallazgos no consultan `DATA.reliability`.** Usan `report.METRICS` (claves `xf`, `sh`, `rFaceImp`…) con el ruido provisional fijo (`report.py:31-61`). Ejemplos en la captura 5: «X-factor con bola rápida −8°»; «Cara en el impacto» (que Fiabilidad marca como «ruido») sale con su valor en Comparar. **Bug** `report_template.html:2013`: un valor que falta se toma como 0 → «altura de la cabeza en el armado 26 cm frente a — (supera el error)» (captura 4). **Conclusiones:** `findings.conclusions` cuenta también los golpes lejanos (n=14 ≥ 12) y da «Diferencia real» con n=6/8. |
| R4 | Cuerdas y cara obligatorias, honesto en el impacto | AG (rótulo «CUERDAS → …», «Raqueta por fase» con las 8 fases); Conclusiones; C-plegado (`loaded/acceleration/impact/finish.face_tilt`) | **Se contradice en L** | `learn.LESSON` no lleva **ninguna** clave de cara en ninguna fase. La vista principal nunca dice adónde miran las cuerdas. |
| R5 | 100 % automático | Sin revisión manual; dudas como etiquetas | **Cumple** | Los recuentos de dudas no cuadran: la cabecera dice «2 con dudas» y Datos «1 de 10» (`report_template.html:767` frente a `renderData`). |
| R6 | Sin fuentes externas; la vista lateral aparte y marcada | Vista lateral con aviso «Fuente aparte»; 0 enlaces externos | **Cumple** | La lección no usa la vista lateral, ni marcada como extra (por ejemplo, «impacto delante de la cadera», 3D: 27 %, 12 golpes). |
| R7 | Partido completo solo al final | — | Pendiente por diseño | Antes de eso falta ver la lección con `_poc9_largo` (petición `accion: informe`). |
| R8 | Cobertura de casos (también el informe) | Tests y `learn_check` | **A medias** | **Con 0 golpes el informe deja de funcionar:** `report_template.html:779` llama a `getElementById("tab-modelo")`, que ya no existe → TypeError y se para el script. No hay test que lo cubra. |
| R9 | Rendimiento | Datos: «180 min para 35 min de vídeo» | Cerrado por el usuario | — |
| R10 | Orden; exportación hecha; móvil al final | `export.py` (PDF y MP4) | **A medias** | **La exportación no se alcanza desde la web:** no hay enlace a `resumen.pdf` ni a los MP4. **Desbordamiento horizontal a escritorio:** Conclusiones mide 1556 px de ancho con la ventana a 1440 (las filas de Hallazgos se salen). |

### B. «Vistas por golpe pedidas por el usuario»

| Vista | Dónde está | Estado | Qué falta |
|---|---|---|---|
| La bola y ella | AG «La bola y ella», con medidas reales | **A medias** | **Golpe de la captura:** solo 3 de los 6 momentos (rival, bota, impacto); faltan «cruza la red», «cae» y «sube». **En Aprende:** solo como ritmo (`takeback_vs_net`, `loaded_vs_bounce`, `contact_vs_top`). |
| Bajar y subir | AG (3 fotogramas, barras y cm); L marca «heights»; `hip_drop_cm` es la 3.ª clave de la aceleración | **Cumple en AG; a medias en L** | `stroke.hip_rise_after_cm` no está en la lección. **Valor sospechoso:** «punto más alto tras golpear: +0,00 s, impacto» (captura 3). |
| Base | AG en armado, impacto y terminación (m) | **Cumple en AG; a medias en L** | En la lección solo `impact.base_court_m`, y como 4.ª clave (casi nunca se ve). `loaded.base_court_m`, `finish.base_court_m` y `feet_move_m` solo en C-plegado. |
| Tronco al terminar | AG | **Cumple en AG; a medias en L** | `class.finish_trunk` es la 5.ª clave de la terminación, así que no sale. |

### C. «Informe y salida visual»

| Elemento | Dónde | Estado |
|---|---|---|
| Resumen con conclusiones en frases | Más › Conclusiones | Cumple; mínimo de golpes mal aplicado (ver R3) |
| Derecha típica | SPT (plegado) | Cumple (con 12 o más derechas cercanas) |
| Explorador con filtros y comparar lado a lado | Tabla de golpes; Comparar | Cumple; bug de Comparar (R3) |
| Comparativas por situación | Conclusiones › «Lo que cambia» | Cumple; usa el ruido provisional, no el medido |
| Mapa de pista | Sus golpes › En la pista | Cumple |
| Cada número enlaza a sus clips | Conclusiones (▶ N vídeos), Explorador | **A medias.** Las claves de la lección y las líneas de «Su ritmo» llevan a la ficha, no al vídeo; Fiabilidad y Datos no enlazan nada. |
| 8 fotogramas clave, estroboscópica, tira | AG (tira de 8 y «recorrido del brazo» plegado) | Cumple |
| Galerías ordenadas por calidad, representatividad y resultado | Videoteca | **A medias:** hay orden por representatividad, calidad, tiempo y atípicos, pero no por resultado (solo filtro) |
| Sin «mejor técnica» | — | Cumple |

### D. Mejoras 1-15 (la lista de 15 puntos)

| Mejora | Estado hoy | Dónde y qué falta |
|---|---|---|
| 1 Líneas dibujadas | **Cumple** | AG capa «Líneas»; L marca «lines» en la preparación |
| 2 Raqueta al lado o a la espalda; adónde apunta la punta | **A medias** | `loaded.racket_head_lateral` en C-plegado («dudosa»); no está en L; no hay «adónde apunta» |
| 3 Codo: altura y separación | Cumple (plegado) | `loaded.elbow_dom_vs_shoulder` y `_lateral` solo en C-plegado |
| 4 Punta frente a la cabeza | Cumple (plegado) | `loaded.racket_tip_vs_head` solo en C-plegado |
| 5 Transferencia de peso | Cumple | «Su ritmo» y C-plegado; no en L |
| 6 Empuje de piernas | Cumple | L (aceleración, 3.ª clave; extensión, `hip_rise`) |
| 7 Ritmo con la bola (aceleración y bote) | **A medias** | `acceleration_vs_bounce` está en «Su ritmo», pero **no en las claves de la aceleración en L** |
| 8 Frenado de hombros | Cumple (plegado) | «No comprobable» en Fiabilidad |
| 9 Caída bajo la bola | **A medias** | Solo vista lateral (6 de 12 derechas de lado) |
| 10 Gira mientras corre | Cumple (plegado) | 5.ª clave de la preparación en L: no sale |
| 11 Frases con datos existentes | **A medias** | Falta `finish.elbow_non` y la cadera durante el desplazamiento |
| 12 Lo que la distingue | **A medias** | «Su firma» incluye rasgos negativos como firma («Paso hacia dentro: no en 6 de 6», «Paso de frenado: no en 5 de 5», captura 1) |
| 13 Consigna y error que evita, por fase | **Se pierde en L** | L enseña Cómo, Ejercicio y Cómo comprobarlo, pero no `c.mistake`; la intro (línea 431) promete «el error típico» |
| 14 Estilo en una frase | Cumple | «Estilo de su derecha» |
| 15 Examen R1-R25 | Cumple (fuera de la web) | Ver la sección 2: el foco de la lección contradice R10 |

### E. Peticiones 1-130 de `docs/peticiones_usuario.md`

| Nº | Estado en la web hoy | Qué falta |
|---|---|---|
| 1, 2, 3 | Pendientes por diseño o aplazadas | — |
| 4, 5, 68, 69, 70, 72 | A medias | Las de R1. Además: 0 golpes exactos del ejemplo del usuario; con el partido entero, 1 parecido (auditoría poc9) |
| 6, 64, 88, 95 | A medias | Pasos medidos en el 33 % de los golpes (poc9); paso cruzado solo en C-plegado y en la 5.ª clave de Pies |
| 7 | A medias | Empuñadura (R1) |
| 8 | **Se contradice en L** | R4 |
| 9, 17, 73 | A medias | R2; la guía «Empieza aquí» y las Novedades no mencionan la lección (`report_template.html:410-429`) |
| 10, 11, 12, 13, 14, 15, 75, 77, 78, 125 | Proceso, fuera de la web | Sin cambios |
| 16, 89 | A medias | 0 casos de media volea y volea |
| 18-24, 26-35, 37-44, 46, 47, 49-54, 56-58, 65-67, 76, 80-83, 99, 104, 108, 110-112, 114-123, 126-128 | Cumplen | Matices de 114-117 en la tabla B |
| 25 | Cumple, con reserva | Rotación 2D y X-factor se muestran sin juicio de fiabilidad (R3) |
| 36, 84, 97 | A medias | Lag en L como 5.ª clave; casting solo de lado |
| 45 | Cumple | Recuentos de dudas incoherentes (R5) |
| 48 | Cumple | — |
| 55 | A medias | Sin golpes de ese tipo |
| 59 | **Se contradice fuera de Cópiala** | R3 |
| 60-63, 129 | No aplican | — |
| 71, 113 | A medias | Un foco de entrenador contradice sus datos (sección 2) |
| 74 | Documental | — |
| 79 | A medias, mejor que el 13-10 | Cópiala ya usa la estimación 3D cuando hay pocas derechas de lado (`aStat`); L no la usa |
| 85, 86, 92 | A medias | Rodillas y caída bajo la bola solo de lado |
| 87, 90, 91 | A medias | Faltan las condiciones de ataque/defensa y anchura (R1) |
| 93, 94, 96 | Cumplen como «no medible» | `learn.NOT_FROM_TV` no incluye empuñadura (bisel), altura del split, el nuevo split step ni el momento de los picos en ms (sí están en `explain.py:647`, solo en SPT) |
| 98 | Cumple | Superficie con «por qué importa» (`report_template.html:2423`) |
| 100, 101, 102, 103, 105, 106, 107, 109 | Ver tabla D | — |
| 124 | A medias | `ready_hands` refutada por R2 (73 % de dos manos, poc9) y es la 2.ª clave de la espera en L |
| 130 | A medias | Restos: 35 % de los golpes con datos (poc9); sin medida propia de bloqueo |

**Documentación desfasada:**
- `docs/matriz_en_la_web.md` es de 10 derechas y anterior a Cópiala. Dice «Pasos cruzados / Superficie / Adaptación a la bola: no hay sitio en la web» y «cómo hacerlo: no» en todo, cuando ya están en Cópiala.
- `docs/peticiones_usuario.md` no tiene fila para la lección del 17-10.

---

## 2. Lo que el diseño actual de la lección contradice o pierde

1. **Cuerdas (requisito 4, obligatorio):** `learn.LESSON` (`learn.py:639-649`) no tiene ninguna clave `face_tilt`. Como solo se ven 3 claves por fase, las cuerdas no salen nunca en la vista principal.
2. **Error típico (Mejora 13):** `renderLesson` (`report_template.html:2539`) no pinta `c.mistake`, aunque la intro (línea 431) lo promete.
3. **Variantes (requisito 1):** la lección solo enseña qué cambia según la velocidad de la bola (`lBySpeed`). Altura, profundidad, carrera, apoyo, ataque/defensa y anchura no aparecen.
4. **Vistas pedidas, que quedan como 4.ª-5.ª clave y casi nunca salen:**
   - la base en el armado, el impacto y la terminación;
   - el tronco al terminar;
   - lo que sube tras golpear;
   - el apoyo (`class.stance_impact` es la 6.ª clave de Pies);
   - el ritmo de la aceleración con el bote (Mejora 7).
5. **El foco del entrenador contradice sus datos:** la fase 3 y el plan dicen «Bote = armado», pero su valor es +0,12 s (`_smoke`) y +0,14 s (poc9, R10 refutada). En la captura 1, el plan dice «Foco: Bote = armado» y justo debajo «Tu objetivo: armado completo como mucho 0,12 s después del bote». Pasa lo mismo con «Abre primero la cadera» frente a R23 refutada.
6. **Vídeo primero:** la guía y el selector van antes que la lección; a 1280×900 no se ve ningún vídeo al abrir.
7. **Guía y glosario desfasados:** la guía no menciona la lección. La guía y el glosario dicen «provisional = menos de 5 golpes» (línea 429 y `learn.GLOSSARY`), pero la etiqueta se pone por debajo de 12 (`A_MIN`). Con 10 golpes todo sale «provisional», en contra de lo que explica la propia leyenda.

---

## 3. Lo que está bien y debe quedarse tal cual

- **Cópiala › La lección:** pasos 1-8 más Pies; vídeo en bucle a 0,25× con la marca de la fase («Otro golpe suyo» y «Ver el golpe entero»); como mucho 3 claves con valor suyo, número de golpes, «Tu objetivo», Cómo, Ejercicio y Cómo comprobarlo. Mide unos 950 px a 1440. `aStat` nunca da como suyo un valor de ruido o sesgo.
- **Cópiala:** selector de condiciones con recuento por nivel y niveles vacíos atenuados; «2 · Sus golpes de ese tipo» con los más parecidos cuando no hay exactos; «Su ritmo, distancia y peso»; «Tu plan» con 3 prioridades; «Si te pasa…» con sus valores al lado; «6 · Lo que la tele no permite medir»; glosario; «4 · Todas las medidas» plegada; SPT plegado.
- **AG:** vídeo con capas por grupos y pantalla completa; tira de 8 fases; «La bola y ella» con cm y m en cada fotograma; «Su cuerpo en este golpe» (bajar y subir, base, tronco al terminar); «Sus pies en este golpe» con fotogramas reales; «Raqueta por fase» con las cuerdas de las 8 fases y la estimación del impacto marcada; ficha con «Medidas que faltan» y «Avisos de técnica» (que sí filtran ruido y sesgo).
- **Vista lateral:** aviso «Fuente aparte», resumen solo con 12 o más golpes y estimación 3D marcada.
- **Fiabilidad** (salvo el bug de texto de la sección 4) y **Datos del análisis**.
- **Conclusiones:** «▶ N vídeos» y «Típicos» en cada conclusión; cara en el impacto marcada «estimada (desenfoque)».

---

## 4. Lo que falta, por prioridad

**P1. Contradicen requisitos vinculantes o rompen la web**

1. **Cuerdas en la lección.**
   - `learn.py` `LESSON`: poner `loaded.face_tilt` entre las 3 primeras del armado, `acceleration.face_tilt` en la aceleración y `finish.face_tilt` en la terminación.
   - O bien, en `renderLesson`, una línea fija «Cuerdas: hacia X en N % (n golpes)» por fase, a partir de `s.face[ph]` (como `findings.conclusions:285-295`), con el impacto marcado «estimación».
   - `learn_check.check_lesson`: exigir esa línea en las fases 3, 4, 5 y 7.
2. **Fiabilidad en todas las pantallas.**
   - `report.py`: añadir a `METRICS` la clave de fiabilidad de cada métrica (`xf`→`loaded.x_factor`, `sh`→`loaded.shoulder_turn`, `elbow`→`impact.elbow_dom`, `head`→`stroke.head_motion_cm`, `rFaceArm/Imp/Fin`→`*.face_tilt`…).
   - `findings.discover:214`: saltar las de ruido o sesgo.
   - Plantilla: marcar «no fiable desde la tele» en `renderMetricsPanel` (1528), `renderKTable` (2011), `renderTable` y en la evolución.
   - Usar el ruido medido (`rel.noise`) en lugar de `m.noise`.
3. **Bug de Comparar** (`report_template.html:2013`): filtrar con `isN(a.m[m.k]) && isN(b.m[m.k])` antes de restar.
4. **Informe vacío** (`report_template.html:779`): `"tab-modelo"` → `"tab-aprende"`; añadir un test del informe con 0 golpes en `tests/test_learn_web.py`.
5. **Mínimos de Conclusiones** (`findings.conclusions:269`): contar solo los golpes cercanos. En `discover`, no dar «Diferencia real» con grupos de menos de 12, o marcarlo como provisional.

**P2. La lección frente a lo pedido**

6. **Foco frente a sus datos:** en `learn.py`, un mapa foco→(clave, rango). En `renderLesson` y en el plan (2481), cuando su mediana está fuera del rango, decir «regla general; ella arma +0,12 s tras el bote» en lugar de presentar el foco como suyo.
7. **Error típico:** añadir `c.mistake` («Error que evita») en `.lhow` (línea 2539).
8. **Variantes:**
   - `learn.CONDITIONS` y `RELAX_ORDER`: añadir `intent` (ataque / neutra / defensa) y `width` (centrada / abierta / muy abierta).
   - `lBySpeed`: generalizarlo a las condiciones elegidas o a velocidad, altura, anchura e intención, siempre por encima de la dispersión y del error.
9. **Vídeo primero** (`report_template.html:421-439`): la lección arriba; el selector reducido a una línea («Todas sus derechas · cambiar») y la guía plegada por defecto tras la primera visita.
10. **Textos:** corregir «provisional = menos de 5» → 12 (línea 429 y `learn.GLOSSARY`); añadir la lección a la guía y a «Novedades» (410-429).
11. **Empuñadura:** una línea en la fase 1 o la 5 de la lección con `grip_compatible` (o «no concluyente»); añadir «Empuñadura exacta (bisel) y cambio de empuñadura», «altura del split» y «momento de los picos en ms» a `learn.NOT_FROM_TV`.
12. **Vistas pedidas en la lección:** subir `class.finish_trunk` y `stroke.hip_rise_after_cm` en la terminación, y `stroke.acceleration_vs_bounce` en la aceleración; o un bloque fijo «base y altura» por fase con la marca de vídeo que ya existe (base / heights).

**P3. Coherencia y calidad**

13. **Un solo cálculo por concepto:** `report.py:96-103` usa sus propios umbrales de «rápida» (< 1,15 s) y de «alta/baja» (40/75 %), distintos de `class.ball_speed` y `class.ball_height`. Por eso la videoteca dice «rápida 8», Cópiala «rápida 3 + muy rápida 2» y el KPI «57 %». Usar las clases en las etiquetas de la videoteca (línea 1881) y en los KPI.
14. **Texto de sesgo:** `renderReliability` (790-793) y `aStat` (2259-2263) no contemplan el sesgo por lecturas rechazadas (`refused`) y muestran «2D —° · 3D —°». Hay que decir «punta del pie tapada en N lecturas».
15. **Recuentos:** una sola cuenta de dudosos y de golpes cercanos para la cabecera (767), Datos y Conclusiones.
16. **Desbordamiento:** que `.frow` de Hallazgos no se salga a 1440 px; extender la comprobación de «sin scroll lateral» de la lección a todas las pantallas en `screens.py`.
17. **Su firma** (`aSignature`, 2345): no tomar como firma los «no» de eventos raros (paso hacia dentro, frenado).
18. **Exportación:** enlaces a `resumen.pdf` y al MP4 de cada golpe en Datos y en AG.
19. **Ver la lección con el partido entero:** pedir al PC un informe de `_poc9_largo` (`accion: informe`, `carpeta: _poc9_largo`) con capturas, y regenerar `docs/matriz_en_la_web.md` (`scripts/matrix_in_web.py`, que debe leer `learn.matrix_places`).
20. **Documentación:** añadir a `docs/peticiones_usuario.md` la fila de la lección con su regla en `audit.PETITIONS`.
