# Modelo de calidad: puntuación (petición #256; generado por `tennisbio calidad`, no editar)

**Total:** 94 % de 410 comprobaciones cumplidas · casillas aceptadas 10 de 25 (umbral 95 %) · **sin medir: 7**

## Por dominio

| Dominio | Puntuación | Comprobaciones | Casillas aceptadas | Sin medir |
|---|---|---|---|---|
| Catalogo, registro y datos | 79 % | 15/19 | 0/3 | 1 |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | 83 % | 30/36 | 1/3 | 0 |
| Deteccion de golpes e identidad | 90 % | 26/29 | 1/2 | 0 |
| Orquestacion, PC y resiliencia | 93 % | 57/61 | 2/4 | 1 |
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | 96 % | 172/179 | 1/3 | 1 |
| Pantallas, video y UX | 96 % | 53/55 | 2/5 | 2 |
| Situaciones del golpe | 100 % | 9/9 | 1/2 | 1 |
| Exportacion | 100 % | 1/1 | 1/1 | 0 |
| Modelos de IA | 100 % | 21/21 | 1/2 | 1 |

## Por característica (ISO/IEC 25010)

| Característica | Puntuación | Comprobaciones | Sin medir |
|---|---|---|---|
| Fiabilidad y resiliencia (fallos, pausa, reanudacion) | 79 % | 22/28 | 0 |
| Usabilidad y aprendizaje del usuario | 84 % | 16/19 | 0 |
| Exactitud (frente a datos anotados o limites fisicos) | 85 % | 40/47 | 2 |
| Adecuacion funcional (hace lo pedido) | 96 % | 259/269 | 0 |
| Eficiencia y rendimiento | 100 % | 17/17 | 2 |
| Mantenibilidad (pruebas, nada fijo en el codigo) | 100 % | 30/30 | 1 |
| Portabilidad (Windows, sin CUDA, movil) | — | 0/0 | 2 |

## Casillas (dominio × característica × capa)

| Dominio | Característica | Capa | Puntuación | ok / decididas | pocos datos | Estado | Lo que falla |
|---|---|---|---|---|---|---|---|
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | — | 0/0 | 0 | SIN MEDIR |  |
| Situaciones del golpe | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | — | 0/0 | 0 | SIN MEDIR |  |
| Pantallas, video y UX | Eficiencia y rendimiento | Pantallas (capturas del navegador) | — | 0/0 | 0 | SIN MEDIR |  |
| Pantallas, video y UX | Portabilidad (Windows, sin CUDA, movil) | Pantallas (capturas del navegador) | — | 0/0 | 0 | SIN MEDIR |  |
| Catalogo, registro y datos | Mantenibilidad (pruebas, nada fijo en el codigo) | Codigo y pruebas automaticas | — | 0/0 | 0 | SIN MEDIR |  |
| Orquestacion, PC y resiliencia | Portabilidad (Windows, sin CUDA, movil) | PC con datos reales | — | 0/0 | 0 | SIN MEDIR |  |
| Modelos de IA | Eficiencia y rendimiento | PC con datos reales | — | 0/0 | 0 | SIN MEDIR |  |
| Catalogo, registro y datos | Adecuacion funcional (hace lo pedido) | PC con datos reales | 60 % | 3/5 | 0 | no aceptada | Lista de partidos: rival, torneo, ronda y fecha; Aplicación: lo que consume abierta |
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | Exactitud (frente a datos anotados o limites fisicos) | PC con datos reales | 67 % | 4/6 | 1 | no aceptada | forehand: medidas que dependen de la cámara (la cámara explica ≥ 10% de su variación); Valores dentro de límites físicos |
| Orquestacion, PC y resiliencia | Fiabilidad y resiliencia (fallos, pausa, reanudacion) | PC con datos reales | 71 % | 10/14 | 0 | no aceptada | Golpes dudosos (duda sobre el golpe, no sobre una medida); Pruebas del código en este PC; Orquestador: espera hasta empezar cada trabajo (+1) |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 74 % | 14/19 | 0 | no aceptada | R10 Armado completo cuando bota la bola (±0,1 s); R17 La terminación más frecuente es sobre el hombro; R18 Preparación compacta (+2) |
| Pantallas, video y UX | Usabilidad y aprendizaje del usuario | Pantallas (capturas del navegador) | 82 % | 9/11 | 0 | no aceptada | Tablas a la vista en «Conclusiones (Panel y Comparativas)»; Primera pantalla, anchura y nombres (diseño definitivo) |
| Catalogo, registro y datos | Fiabilidad y resiliencia (fallos, pausa, reanudacion) | PC con datos reales | 86 % | 12/14 | 0 | no aceptada | Vídeos exportados: exportar_reves; Vídeos exportados: exportar_saque |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Usabilidad y aprendizaje del usuario | Pantallas (capturas del navegador) | 88 % | 7/8 | 1 | no aceptada | La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cómo comprobarlo |
| Deteccion de golpes e identidad | Adecuacion funcional (hace lo pedido) | PC con datos reales | 89 % | 25/28 | 0 | no aceptada | Golpes encontrados frente al marcador: sin-fecha_f43dd2_rybakina; Saques por punto de su saque: sin-fecha_f43dd2_rybakina; Saques por punto de su saque: sin-fecha_584c5b_rybakina |
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | Adecuacion funcional (hace lo pedido) | PC con datos reales | 97 % | 168/173 | 27 | aceptada | Fotograma clave: inicio de preparación; Fotograma clave: armado; Fotograma clave: inicio de aceleración (+2) |
| Pantallas, video y UX | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 15/15 | 0 | aceptada |  |
| Situaciones del golpe | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 9/9 | 6 | aceptada |  |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Adecuacion funcional (hace lo pedido) | Pantallas (capturas del navegador) | 100 % | 9/9 | 0 | aceptada |  |
| Pantallas, video y UX | Adecuacion funcional (hace lo pedido) | Pantallas (capturas del navegador) | 100 % | 29/29 | 0 | aceptada |  |
| Orquestacion, PC y resiliencia | Eficiencia y rendimiento | PC con datos reales | 100 % | 17/17 | 5 | aceptada |  |
| Exportacion | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 1/1 | 0 | aceptada |  |
| Deteccion de golpes e identidad | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 100 % | 1/1 | 0 | aceptada |  |
| Orquestacion, PC y resiliencia | Mantenibilidad (pruebas, nada fijo en el codigo) | Codigo y pruebas automaticas | 100 % | 30/30 | 0 | aceptada |  |
| Modelos de IA | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 100 % | 21/21 | 0 | aceptada |  |
