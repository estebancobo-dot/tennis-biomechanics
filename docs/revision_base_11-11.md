# Revisión de toda la Base, 11-11 (#260, tarea 10d de B8)

La anterior, del 27-10 (`revision_base.md`), revisó componentes y velocidad; esta revisa cada petición y su prueba.

**Por qué:** el 11-11 aparecieron dos comprobaciones que daban por bueno algo que no lo era:
- la del tiempo de análisis, que sumaba etapas que solo releían datos guardados;
- la de «un partido nuevo de principio a fin», que pasó con el partido de otro jugador.

El usuario no se fía de que el resto de la Base esté mejor validado (con razón). Esta revisión mira **cada petición** de
B1-B8 (77) con las mismas cinco preguntas. Lo que no pase vuelve a FALTA o PARCIAL en `peticiones_usuario.md`, con su
tarea en la tabla de `estado_proyecto.md`. El análisis completo (tarea 11) espera a esta revisión.

## Método (las cinco preguntas, por petición)
1. **¿La prueba mide lo pedido?** Se ponen lado a lado las palabras del usuario y lo que comprueba la prueba principal.
   - Veredicto: mide lo pedido / mide otra cosa / solo una parte.
2. **¿Falla cuando debe?** Se pasa la comprobación por un caso real malo (un registro o una salida que debería
   suspender), no solo por datos inventados de una prueba unitaria.
3. **¿Sus números son de hoy y desde cero?** Cada cifra se rastrea hasta una ejecución con el código actual (huellas)
   que calculó de verdad. No cuentan las que solo releyeron datos guardados.
4. **¿Se analizaron las alternativas?** Por cada pieza (modelo, algoritmo, forma de hacerlo) se anota:
   - qué opciones existían y cuáles se midieron (con su fichero de prueba);
   - con qué resultado;
   - qué falta por medir. Lo que pueda cambiar el resultado se mide; si no, se descarta con su motivo.
5. **Veredicto por petición:** válida / se rehace (con la tarea concreta).

## Hallazgos (en orden de aparición)

| # | Paquete | Qué pasó | Pregunta | Estado |
|---|---|---|---|---|
| 1 | B1 velocidad | La prueba principal («Tiempo: …») sumaba el último tiempo de cada etapa, incluidas las que solo releían datos guardados. Decía 1,2-2,1 h por partido; desde cero, 35 min de vídeo tardaron 116 min (petición 206: ≈ 3,3 veces el vídeo, ≈ 11,5 h por partido de 3,5 h). Las últimas medidas desde cero por etapa son del 18-10 (prueba de 35 min: 67 min) y del 26-27-10 (los 4 partidos: `revision_base.md`, §1); después se cambiaron y añadieron etapas sin volver a medir desde cero. | 1, 3 | B1 **no válido**; tarea 10c (tiempos desde cero, alternativas medidas) |
| 2 | B7 aplicación | «Un partido nuevo de principio a fin» pasaba con que el trabajo terminara, sin mirar el resultado: la 206 analizó Zverev-Sinner como Rybakina (identidad 0 %, informe con fallos). | 1, 2 | corregido el 11-11 (vídeo de la jugadora; suspende con el registro real de la 206); repetido en la petición 207 |
| 3 | Forma de trabajar | Un cambio se subió con 2 pruebas fallando: la orden encadenaba la subida al final de la salida de las pruebas, no a su resultado. | — | corregido (la subida depende del resultado de las pruebas) y vuelto a subir con todas bien |

## Paquetes (se rellena paquete a paquete)
B1 velocidad (10 peticiones) · B2 robustez (3) · B3 mejores modelos (10) · B4 no perder golpes (6) · B5 exportación (1) ·
B6 referencia de los 4 partidos (4) · B7 aplicación e infraestructura (36) · B8 orquestador (7 + #259, #260).
