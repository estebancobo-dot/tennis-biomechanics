# Modelo de calidad: puntuación (petición #256; generado por `tennisbio calidad`, no editar)

**Total:** 95 % de 402 comprobaciones cumplidas · casillas aceptadas 12 de 25 (umbral 95 %) · **sin medir: 7**

## Por dominio

| Dominio | Puntuación | Comprobaciones | Casillas aceptadas | Sin medir |
|---|---|---|---|---|
| Deteccion de golpes e identidad | 81 % | 22/27 | 1/2 | 0 |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | 83 % | 30/36 | 1/3 | 0 |
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | 96 % | 172/179 | 1/3 | 1 |
| Pantallas, video y UX | 96 % | 53/55 | 2/5 | 2 |
| Orquestacion, PC y resiliencia | 97 % | 58/60 | 2/4 | 1 |
| Situaciones del golpe | 100 % | 9/9 | 1/2 | 1 |
| Exportacion | 100 % | 1/1 | 1/1 | 0 |
| Catalogo, registro y datos | 100 % | 14/14 | 2/3 | 1 |
| Modelos de IA | 100 % | 21/21 | 1/2 | 1 |

## Por característica (ISO/IEC 25010)

| Característica | Puntuación | Comprobaciones | Sin medir |
|---|---|---|---|
| Usabilidad y aprendizaje del usuario | 84 % | 16/19 | 0 |
| Exactitud (frente a datos anotados o limites fisicos) | 85 % | 40/47 | 2 |
| Fiabilidad y resiliencia (fallos, pausa, reanudacion) | 90 % | 18/20 | 0 |
| Adecuacion funcional (hace lo pedido) | 96 % | 255/265 | 0 |
| Eficiencia y rendimiento | 100 % | 21/21 | 2 |
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
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | Exactitud (frente a datos anotados o limites fisicos) | PC con datos reales | 67 % | 4/6 | 1 | no aceptada | forehand: medidas que dependen de la cámara (la cámara explica ≥ 10% de su variación); Valores dentro de límites físicos |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 74 % | 14/19 | 0 | no aceptada | R10 Armado completo cuando bota la bola (±0,1 s); R17 La terminación más frecuente es sobre el hombro; R18 Preparación compacta (+2) |
| Orquestacion, PC y resiliencia | Fiabilidad y resiliencia (fallos, pausa, reanudacion) | PC con datos reales | 78 % | 7/9 | 0 | no aceptada | Golpes dudosos (duda sobre el golpe, no sobre una medida); Pruebas del código en este PC |
| Deteccion de golpes e identidad | Adecuacion funcional (hace lo pedido) | PC con datos reales | 81 % | 21/26 | 0 | no aceptada | Golpes encontrados frente al marcador: sin-fecha_f43dd2_rybakina; Saques por punto de su saque: sin-fecha_f43dd2_rybakina; Saques por punto de su saque: sin-fecha_584c5b_rybakina (+2) |
| Pantallas, video y UX | Usabilidad y aprendizaje del usuario | Pantallas (capturas del navegador) | 82 % | 9/11 | 0 | no aceptada | Tablas a la vista en «Conclusiones (Panel y Comparativas)»; Primera pantalla, anchura y nombres (diseño definitivo) |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Usabilidad y aprendizaje del usuario | Pantallas (capturas del navegador) | 88 % | 7/8 | 1 | no aceptada | La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cómo comprobarlo |
| Taxonomia del golpe (fases, cuerpo, pies, raqueta) | Adecuacion funcional (hace lo pedido) | PC con datos reales | 97 % | 168/173 | 27 | aceptada | Fotograma clave: inicio de preparación; Fotograma clave: armado; Fotograma clave: inicio de aceleración (+2) |
| Pantallas, video y UX | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 15/15 | 0 | aceptada |  |
| Situaciones del golpe | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 9/9 | 6 | aceptada |  |
| Aprendizaje (Copiala / Aprende, examen de entrenadores) | Adecuacion funcional (hace lo pedido) | Pantallas (capturas del navegador) | 100 % | 9/9 | 0 | aceptada |  |
| Pantallas, video y UX | Adecuacion funcional (hace lo pedido) | Pantallas (capturas del navegador) | 100 % | 29/29 | 0 | aceptada |  |
| Orquestacion, PC y resiliencia | Eficiencia y rendimiento | PC con datos reales | 100 % | 21/21 | 0 | aceptada |  |
| Exportacion | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 1/1 | 0 | aceptada |  |
| Deteccion de golpes e identidad | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 100 % | 1/1 | 0 | aceptada |  |
| Orquestacion, PC y resiliencia | Mantenibilidad (pruebas, nada fijo en el codigo) | Codigo y pruebas automaticas | 100 % | 30/30 | 0 | aceptada |  |
| Catalogo, registro y datos | Adecuacion funcional (hace lo pedido) | PC con datos reales | 100 % | 3/3 | 0 | aceptada |  |
| Catalogo, registro y datos | Fiabilidad y resiliencia (fallos, pausa, reanudacion) | PC con datos reales | 100 % | 11/11 | 0 | aceptada |  |
| Modelos de IA | Exactitud (frente a datos anotados o limites fisicos) | Validacion con verdad anotada | 100 % | 21/21 | 0 | aceptada |  |
