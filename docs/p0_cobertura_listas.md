# Tus listas frente a la aplicación (15-11, #303)

Comprobado en el código (`learn.py`, `technique.py`, `report_template.html`) y en el informe beta real. No sale de los
documentos.
- ✔ está y se ve;
- ◐ está a medias;
- ✘ falta;
- **NM** no medible desde la tele (la aplicación lo dice).

## 1. Tu matriz de 15 puntos (12-10; peticiones #84-#98; detalle en `matriz_cobertura.md` §6)

| # | Punto | Estado |
|---|---|---|
| 1 | Cadena cinética (suelo → pelvis → separación → tronco → codo → muñeca) | ◐ el orden de los picos (68 % en orden); los valores en °/s, NM |
| 2 | Cuerpo (cabeza, brazos, tronco, piernas, pie de arrastre) | ◐ cabeza, brazo libre, tronco, codo y pie de arrastre ✔; rodillas con escorzo |
| 3 | Raqueta (bucle, caída, cara, trayectoria) | ◐ bucle, caída y cara por fase ✔; cara en el impacto, estimada; trayectoria de dentro a fuera, NM |
| 4 | Apoyos (abierto, semiabierto, neutro, cerrado, salto, abierto extremo) | ✔ |
| 5 | Pies (split, ajuste, cruzado, paso de ataque, recuperación) | ◐ todos medidos (sección 4); falta el nuevo split step antes del siguiente golpe |
| 6 | Modalidades (plano, liftado, cortado, media volea, volea, 3 terminaciones) | ◐ las 3 terminaciones ✔; plano, liftado o cortado por la trayectoria de la mano; la volea y la media volea, con muy pocos casos |
| 7 | Adaptación a la bola (rápida, corta, alta, lateral) | ◐ son las situaciones; faltan las diferencias ajustadas con suficientes golpes |
| 8 | Dirección (cruzado, paralelo, dentro-fuera, dentro-dentro) | ◐ clase medida; el 27 % cruzada en la beta |
| 9 | Control (zona de impacto, relajación, equilibrio) | ◐ zona de impacto y equilibrio ✔; relajación, NM |
| 10 | Propiedades de la raqueta | NM (dicho) |
| 11 | Cinemática cuantitativa (velocidad de raqueta, °/s, fuerza, rpm) | NM; solo comparación relativa |
| 12 | Neuro y visión (latencia, mirada, EMG) | ◐ latencia (split, primer paso) ✔; mirada y EMG, NM |
| 13 | Microbiomecánica (muñeca, codo, hombro) | NM (rotaciones sobre el eje del brazo) |
| 14 | Fugas de energía (apertura prematura, casting, vector) | ◐ apertura prematura (2D) ✔; el casting, solo en la vista lateral de entreno |
| 15 | Contexto y ambiente (superficie, aerodinámica) | ◐ superficie ✔; el ambiente, NM |

**Detalle de los 59 elementos de la matriz:** 25 ✔, 20 ◐ y 14 ✘. Los 14 ✘ son todos no medibles desde la tele, y la
aplicación lo dice en «Lo que la tele no mide».

## 2. La guía «Derecha estilo Ivanovic» (sus 20 huecos, `comparacion_guia_ivanovic.md` §3)

| Estado | Huecos |
|---|---|
| ✔ (7) | 1: «sin pausa arriba», que se dice como no medible; 2: sus claves en la lección; 4: «Su ritmo, distancia y peso»; 5: «Si te pasa…», con 7 síntomas; 7: «Cómo comprobarlo» en cada clave; 8: el glosario, con los 14 términos que faltaban (56 en total); 16: el resto «bloqueado» |
| ◐ (8) | 3: la forma del armado (bucle, loop falso, recto atrás; falta «punta arriba / codo alto»); 6: avisos de técnica por golpe; 9: terminación «hacia adelante» y mano libre; 11: pies según la distancia que corre; 12: último apoyo frente al bote (medido; falta la frase); 13: «Sus principios» (hay «Su firma»); 14: táctica (hay «Cómo usa su derecha»); 17: fuentes |
| ✘ (5) | 10: mano libre en la aceleración y el impacto; 15: bajo presión, también la dirección y la profundidad; 18: codo por delante de la cadera e inclinación en la espera (vista lateral); 19: progresión por etapas; 20: rutina entre puntos |

## 3. Los demás golpes

| Golpe | Hoy |
|---|---|
| Derecha | ✔ análisis completo: lección, golpes, comparar… |
| Revés | ◐ cada golpe se clasifica y el informe se genera con la misma plantilla (`config/strokes/backhand.yaml`); en la nube todavía no se ha generado el «Revés de Rybakina»; la exportación del revés se colgaba en el PC (arreglado, #232) |
| Saque y remate | ◐ se clasifican (`overhead.yaml`); faltan sus medidas propias (trofeo, lanzamiento, aterrizaje) y sus tipos: plano, cortado, kick, primero o segundo (#224) |
| Resto | ◐ como situación («tipo de resto», «bloqueado», primer o segundo saque) |
| Volea, media volea | ◐ clase de contacto; 0-6 casos reales, demasiado pocos para enseñarlos |
| Cortado, passing, globo, dejada | ✘ (#223, #209, #210) |

## 4. Juego de pies y patrones de movimiento

| Medida | Estado |
|---|---|
| Split step: aterrizaje frente al golpe de la rival | ✔ |
| Primer paso tras el split: tiempo | ✔ (el tipo, gravity, jab o pivot, ◐, #171) |
| Tipo de pasos hacia la bola, pasos cruzados, pasos de ajuste | ✔ |
| Último apoyo frente al bote; armado frente al último apoyo | ✔ |
| Paso de ataque hacia dentro, paso de frenado, pie que se arrastra | ✔ |
| Pivote sobre la punta del pie de atrás (talón arriba y cuándo) | ✔ |
| Recorrido hasta la bola (m) y desplazamiento según la bola | ✔ |
| Recuperación: cuándo empieza, primer paso, cuánto vuelve al centro, la pierna de atrás pasa adelante | ✔ |
| Orientación del pie en el armado y el impacto | ◐ (#177) |
| Nuevo split step antes del siguiente golpe de la rival | ✘ (#176) |
| Huellas numeradas sobre la pista y patrones de pasos por situación | ◐ (#236, Ivanovic 11) |

## 5. Alturas, y ella frente a la bola

| Medida | Estado |
|---|---|
| Bajar y subir: espera → punto más bajo → más alto, en cm (#115) | ✔ |
| Altura del impacto, de la cabeza y de la terminación | ✔ |
| Altura de la bola: vuelo, bote, punto más alto; contacto subiendo, arriba o cayendo (#184) | ◐ (`ball3d`, estimación; acotada desde el 14-11) |
| **La bola y ella:** su cuerpo cuando golpea la rival, la bola cruza la red, bota, sube y ella golpea (#54, #114) | ✔ fotogramas reales con medidas |
| Ritmo con la bola: gira al cruzar la red, arma con el bote, golpea en el pico | ✔ |

## 6. En la aplicación nueva (P0)

Todo lo ✔ y ◐ tiene su sitio en el diseño (`p0_diseno.md`):
- **las medidas:** en la fase de la lección, en «Todas las medidas» y en el análisis de cada golpe;
- **los pies:** en su propia fase de la lección;
- **la bola y ella, y las alturas:** en el análisis de cada golpe;
- **los otros golpes:** cada uno con su análisis cuando tenga casos;
- **lo no medible:** en «Lo que la tele no mide».

La maqueta completa tiene que enseñar todo esto; la retirada del 15-11 no lo hacía. Lo ◐ y ✘ medible es trabajo de los
paquetes de medidas M1-M7, por este orden (`config/plan_peticiones.yaml`).
