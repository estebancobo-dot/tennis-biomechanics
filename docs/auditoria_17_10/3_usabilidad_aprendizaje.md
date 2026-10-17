# Auditoría de usabilidad y aprendizaje de la web (17-10)

No he modificado ningún fichero del repositorio; solo he usado ficheros temporales en `/tmp/claude-0/aud3/`. He mirado las 9 capturas reales del PC, recortadas y vistas enteras. La de «Cópiala» ya incluye la lección nueva: se generó a las 13:42 UTC y la lección entró a las 13:38. También he leído `renderLesson`, `learn.LESSON` y `learn.CHECKS`, y la maqueta. Por último, he generado la web con 200 golpes sintéticos y la he medido con Playwright a 1280×900 y a 390×844 (script en `/tmp/claude-0/aud3/measure.py`).

## Lo esencial, con datos

El problema no es una pantalla concreta. Hay **demasiadas puertas y demasiado texto antes del vídeo**.

**En «Cópiala»:**
- **Arriba del todo no hay vídeo.** La primera pantalla son «Novedades», «Empieza aquí» y el selector de golpe con 14 filas y unos 50 botones de condición. El vídeo de la lección empieza en y≈1050 px en la captura del PC y en 1201 px a 1280×900. En el móvil, la primera clave está en y=3115 (3,7 pantallas).
- **Es enorme.** A la vista hay 13 secciones con título (h2), 96 desplegables, 127 botones y unas 1.960 palabras (4.000 con «Su patrón típico» abierto).
- **La numeración está rota:** 1, la lección (sin número), 2, Su firma, Su ritmo, 3, 4, 5, Si te pasa, 6. La guía de arriba manda a practicar «Tu plan (punto 5)», no la lección. Hay tres sitios que dicen «esto es lo que tienes que copiar»: la lección, Su firma y Tu plan.
- **Cada fase de la lección es más texto que vídeo.** Tiene 3 claves, pero ocupa 218-319 palabras y 660-890 px de altura a 1280. Cada clave junta 7 elementos: valor, rango, etiqueta, objetivo, cómo, ejercicio y comprobación. Son unas 21 cosas que leer por fase.
  - «Tu objetivo» casi siempre repite lo que pone «Ella:»: «Aterriza 0,08 s después… como ella».
  - En los datos reales cada clave lleva su etiqueta «provisional».

**En el resto de la web:**
- **Navegación.** El menú tiene 2 entradas principales y 8 en «Más». Dos de ellas son alias de otras pantallas: «Su patrón típico» va a «Cópiala» y «Dónde golpea» va a «Sus golpes».
- **Nombres de los golpes.** En la videoteca, en Comparar y en la tabla, cada golpe se llama por el nombre del fichero: `smoke_tennis-yusipopen-final-sobolenko-rybakin-0013323`.
- **Conclusiones se sale por la derecha.** En la captura a 1440 de ancho, la página mide 1556 px, así que hay scroll lateral y los botones «Datos» quedan cortados. De los 10 hallazgos, 9 son «No concluyente». La tabla «Lo que cambia según la situación» son 12 filas de «—» y «Pocos golpes».
- **El análisis de un golpe mide 5.789 px.**
  - Con la capa «Todo», el vídeo lleva unas 10 etiquetas encima a la vez.
  - Hay dos barras de capas que hacen lo mismo: grupos y capas sueltas.
  - Debajo vienen unos 16 fotogramas fijos, un panel con 12 barras y dos gráficas.

---

## 1. Veredicto por pantalla

| Pantalla | Veredicto | Por qué |
|---|---|---|
| **Cópiala → la lección** (fases + vídeo en bucle + ≤3 claves) | **Sirve para aprender. Es el núcleo.** | Es lo único que sigue el modelo de las apps profesionales y del aprendizaje motor: ver al experto en la fase exacta, con pocas claves. Falla en dónde está colocada (debajo del filtro) y en la cantidad de texto de cada clave. |
| Cópiala → «1 · ¿Qué golpe quieres aprender?» (14 filas) | Sirve, **pero tal como está estorba** | Dos o tres situaciones comunes resuelven casi todo: rápida/lenta, alta/baja, en carrera. Las 14 filas tienen que ir plegadas. Ahora es lo primero que se ve y empuja el vídeo hacia abajo. |
| Cópiala → «Novedades» y «Empieza aquí» | **Sobran en la pantalla de aprender** | Un registro de cambios y un manual de 5 pasos son la señal de que la pantalla no se explica sola. Las novedades, a «Datos». La guía, una línea. |
| Cópiala → Su firma | Extra | Compite con la lección y mete negaciones que no se pueden copiar, como «Paso hacia dentro: no en 6 de 6». |
| Cópiala → Su ritmo, distancia y peso | Extra (o como dato dentro de su fase) | Son 7 números con rangos, y cada uno ya tiene su fase en la lección. |
| Cópiala → 3 · Qué cambia en este golpe | Sirve, **dentro de la clave** | `lBySpeed` ya lo hace en la lección y solo lo enseña si supera el error. Como sección aparte, sobra. |
| Cópiala → 4 · Todas las medidas | Extra (ya está plegada) | Bien así. |
| Cópiala → 5 · Tu plan | Sirve **como marca, no como sección** | La idea (3 prioridades en orden) es buena. Debe convertirse en el orden y en una señal sobre la tira de fases, no en otra lista con sus propios «Ver». |
| Cópiala → Si te pasa… | Extra útil | Es un diagnóstico por síntomas. Útil al entrenar, pero no para entrar. |
| Cópiala → 6 · Lo que la tele no permite medir; Glosario; Su patrón típico | Extra | Son honestos y deben quedarse, pero plegados. «Su patrón típico» duplica la lección. |
| **Sus golpes (videoteca)** | **Sirve.** Es la prueba de cada dato | La cuadrícula de vídeo con avance al pasar el ratón está al nivel de SwingVision. Sobran: los nombres de fichero, los filtros duplicados (8 desplegables y 6 filas de botones) y «Reproducir todos» escondido entre ellos. |
| **Análisis de golpe** | Sirve **como evidencia**, no como lección | Reproductor, línea de tiempo con las 8 fases, miniaturas y «La bola y ella» son únicos. La serie de unos 16 fotogramas fijos, las dos gráficas y la tabla de raqueta son extra. Por defecto debería abrir con la capa «Cuerpo», no con «Todo». |
| Dónde golpea (mapa de pista) | Extra | |
| **Comparar dos golpes** | Extra útil (práctica) | Sincronizado en el impacto, con frases arriba: bien. Le sobran los selectores con nombres de fichero y la tabla de 30 filas abierta por defecto. |
| Conclusiones | Extra técnico | Sirve para estudiarla, no para aprender a pegar. Tiene scroll lateral, 9 «No concluyente» con la gráfica completa y una tabla de guiones. |
| Tabla de golpes | Extra técnico | Es la videoteca en forma de tabla. |
| Vista lateral (entreno) | Extra, **con un dato que debería subir a la lección** | 9 de 14 medidas dicen «pocos golpes… sin resumen» y la mayoría de los 24 vídeos «impacto sin confirmar, no se mide». Lo que sí tiene (impacto por delante de la cadera, ángulo del swing, en 3D) debería aparecer en la fase 5 de la lección, marcado «Vista lateral (entreno)». |
| Fiabilidad de las medidas | Extra técnico | Honesta y clara. Se queda tal cual. |
| Datos del análisis | Extra técnico | Bien. Es el sitio natural para «Novedades». |

---

## 2. Arquitectura de información recomendada (definitiva)

**Regla:** 3 entradas en el menú, el vídeo arriba en la primera pantalla y todo lo demás plegado o en «Más». No se borra nada.

```
LECCIÓN (entrada, por defecto)   SUS GOLPES        MÁS
```
- **Más** contiene, en este orden: Comparar dos golpes, Vista lateral (entreno), Conclusiones, Tabla de golpes, Fiabilidad y Datos + Novedades.

### A. Lección (pantalla de entrada), en este orden

1. **Una línea de contexto:** «Su derecha · 55 golpes · todas las situaciones [Cambiar ▾]».
   - [Cambiar] abre las 14 filas, con 6 atajos encima: rápida, lenta, alta, baja, en carrera, abierta.
   - La guía «Empieza aquí» se reduce a una frase bajo el título: «Elige una fase, mírala en su vídeo y practica un ejercicio».
2. **Tira de fases P1-P8 + Pies, con miniatura real de cada fase.** Las 3 fases del «plan» llevan la marca «empieza por aquí».
3. **El vídeo en bucle de la fase.**
   - Ocupa la mitad o más del ancho en escritorio y todo el ancho en el móvil, siempre antes de las claves.
   - Añadir un botón «a velocidad real» (ver la nota sobre aprendizaje implícito).
4. **Foco:** una frase grande, con atención en algo exterior al cuerpo o con una analogía. Ya existe: «Bote = armado».
5. **Hasta 3 claves.** Cada una enseña a la vista solo: nombre, su valor en tus unidades (con nº de golpes) y una línea de «Cómo».
   - «Tu objetivo» desaparece cuando repite el valor. Solo se enseña si convierte a tus centímetros.
   - Rango y etiqueta, en texto pequeño.
   - «Cambia con la bola», solo si supera el error (ya es así).
6. **Un solo bloque «Practica» por fase:** un ejercicio con criterio de éxito («8 de 10 = conseguido») y un botón «Conseguido».
   - El botón se guarda solo en el navegador y la página tiene que funcionar igual si ese almacenamiento falla.
   - Los otros dos ejercicios y sus comprobaciones, en «Más ejercicios».
7. **‹ Fase anterior · Fase siguiente ›**
8. **Plegado («extra»):** Su firma, Ritmo, Todas las medidas, Plan completo, Si te pasa, Lo que la tele no mide, Glosario y Su patrón típico.

### B. Sus golpes

- Una sola fila de situación, la misma que la de la Lección y compartida con ella.
- Cuadrícula con títulos legibles, por ejemplo «2.º set 5-5 30-30 · rápida, corta · abierto», y «Reproducir todos» bien visible.
- Pulsar un golpe abre el **análisis del golpe**, en este orden:
  1. Vídeo con la capa «Cuerpo».
  2. Línea de tiempo y miniaturas de las fases.
  3. «La bola y ella».
  4. Plegados: «Su cuerpo en este golpe» (bajar/subir, base, tronco, pies), métricas, gráficas y raqueta.

### C. Más

- **Comparar:** las frases a la vista y la tabla plegada.
- **Conclusiones:** a la vista solo las «diferencias reales»; las no concluyentes y la tabla, plegadas.
- **Vista lateral, Tabla, Fiabilidad, Datos:** como están.

### Por qué esta forma

**En las apps.** Lo marcado como (memoria) es conocimiento mío, no comprobado hoy en la web.
- **Sportsbox:** una posición clave del golpe cada vez (P1-P10, memoria), el vídeo con el avatar primero, el rango por medida y rangos objetivo que fija el entrenador. Es exactamente la tira de fases con vídeo y ≤3 claves.
- **Hudl Technique y OnForm** (memoria): cámara lenta, lado a lado y dibujar encima; el vídeo es la interfaz y los números son secundarios.
- **SwingVision:** resúmenes por golpe y filtros. Es la videoteca, no la pantalla de aprender.
- **TennisViz y Hawk-Eye** (memoria): un dato por tarjeta con su imagen, nunca una tabla de 30 filas a la vista.

**En el aprendizaje motor:**
- **Modelado (Bandura, McCullagh):** se aprende viendo al experto. Por eso el vídeo va primero y en la fase exacta.
- **Carga cognitiva (Sweller):** hoy son unas 21 cosas por fase y deberían ser como mucho 5: foco, 3 claves de una línea y un ejercicio.
- **Foco externo (Wulf):** «Aterriza cuando oigas el golpe de la rival» o «Bote = armado» son buenos. «Espera con la cadera al 43 % de tu altura», «el codo como el suyo» o «brazo no dominante 123°» desvían la atención al cuerpo. Su sitio es el dato, no la instrucción.
- **Práctica deliberada (Ericsson):** un ejercicio con criterio claro («8 de 10») y una prioridad cada vez.
- **Retroalimentación elegida por el que aprende (Chiviacowsky y Wulf):** el botón «Conseguido» y «Cómo comprobarlo» a demanda.
- **Aprendizaje implícito y analogías (Masters, Liao y Masters):** una analogía por fase como foco y el bucle también a velocidad real para captar el ritmo, sin leer.
- **Autoeficacia (Bandura):** fases marcadas como conseguidas y un orden de lo fácil a lo difícil (el plan). Menos etiquetas «provisional» repetidas: un único aviso global cuando todas lo son.

---

## 3. Criterios de aceptación medibles en el navegador

Para Playwright, igual que `test_lesson_meets_the_requirements`. Se miden sin datos guardados en el navegador, a 1280×900 y a 390×844, con los datos reales del PC y los sintéticos.

**Entrada y primera pantalla**
1. A 1280×900, el vídeo de la lección (`#a-l-cv`) entra entero en la primera pantalla: arriba ≥ 0 y abajo ≤ 900. A 390×844, su borde superior queda a ≤ 0,5 × la altura de la ventana. *Hoy: 1201 px y 2,5-3,7 pantallas.*
2. El vídeo avanza solo en ≤ 2 s sin hacer clic (`currentTime` sube).
3. Por encima de la lección hay ≤ 120 px de contenido visible, y en «Lección» no se ve ni «Novedades» ni la guía de 5 pasos.
4. En la primera pantalla hay ≤ 12 controles visibles. *Hoy: unos 60 botones de condición.*

**La lección**

5. Clics desde que se abre la página hasta su vídeo de la fase k: **≤ 1**. Tras pulsar la fase k, `currentTime − impacto` cae dentro de t_k ± 0,3 s. Desde una clave hasta el golpe entero: **1 clic**.
6. Por fase: ≤ 3 claves visibles; ≤ **120 palabras** visibles en el bloque de claves (hoy 218-319); bloque de claves de ≤ 1,3 veces la altura del vídeo; panel de la lección de ≤ **900 px** a 1280. El límite actual de 1400 px es demasiado holgado.
7. Exactamente 1 «Foco» por fase, de ≤ 20 palabras y sin cifras con «%», «°» ni «cm» (regex). Así se comprueba que el foco no es una medida del cuerpo.
8. Exactamente 1 ejercicio visible por fase, con un criterio que cumpla `/\d+ de \d+/`.
9. «Tu objetivo» no aparece si su número es igual al de «Ella:».
10. No hay rangos con guion entre negativos (`/-\d+,\d+–\d/`). Se escriben «entre −0,06 y 0,10 s».

**Tamaño y navegación**

11. «Lección», al abrirse: ≤ 3 secciones con título (h2) visibles, ≤ 400 palabras y ≤ 25 botones. *Hoy: 13, 1.961 y 127.*
12. Menú: ≤ 3 entradas principales y ≤ 6 en «Más», sin alias (cada botón va a una pantalla distinta).
13. Sin scroll lateral en ninguna pantalla a 390, 1280 y 1440 (`scrollWidth ≤ innerWidth`). *Hoy falla Conclusiones a 1440.*
14. Ningún texto visible cumple el patrón del nombre de fichero del golpe (`/[a-z]+_[\w-]+-\d{7}/`).
15. Análisis de golpe: a la vista ≤ 4 rótulos sobre el vídeo por defecto; el vídeo es lo primero del contenido; con los extras plegados la página mide ≤ 3 × 900 px. *Hoy: 5.789.*
16. Conclusiones: los hallazgos visibles son todos «diferencia real»; ninguna fila visible tiene solo «—».
17. Botones de fase y de vídeo de ≥ 44 px de alto en el móvil.

**Lo que no se puede romper**

18. Nada borrado: «Todas las medidas» sigue teniendo una ficha por cada clave de `learn_keys()` (el test actual). Siguen existiendo todas las pantallas y secciones actuales, plegadas o en «Más».
19. «Conseguido» en la fase k sigue marcado al recargar. Si el almacenamiento del navegador lanza un error, la página carga sin errores.
20. 0 errores de página.

---

## 4. Lo que está bien y no hay que tocar

- **El mecanismo de la lección:** su vídeo en bucle alrededor de la fase a 0,25×, con la marca de cada fase (`learn.LESSON`: hand / lines / heights / base), «Otro golpe suyo» y «Ver el golpe entero». Es lo mejor de la web y lo que hacen Sportsbox y Hudl.
- **Como mucho 3 claves fiables por fase, con valor suyo y nº de golpes.** Lo que es ruido o sesgo nunca se da como suyo, y el cambio por bola solo sale si supera el error (`lBySpeed`).
- **Los focos externos buenos y las comprobaciones con criterio:** «Bote = armado», «aterriza cuando oigas el golpe», «8 de 10 = conseguido».
- **La honestidad:** fiable, ruido o sesgo; «no medible desde la tele»; la pantalla de Fiabilidad y la de Datos.
- **La videoteca:** cuadrícula de vídeo con avance al pasar el ratón y conteos por situación.
- **El reproductor del golpe:** línea de tiempo con las 8 fases, miniaturas, pantalla completa, grupos de capas y «La bola y ella», que no tiene equivalente.
- **Comparar:** sincronizado en el impacto, con frases de diferencias que superan el error encima de la tabla.
- **Tu altura → tus centímetros,** y el glosario con palabras subrayadas.
- **El diseño visual y la estética oscura,** coherentes con la maqueta.
- **La auditoría automática con capturas desde el PC.** Basta con cambiar los umbrales, por ejemplo de 1400 a 900 px, y añadir los criterios 1-17.

Una aclaración sobre las capturas: son de `_smoke` (10 derechas cercanas). Que todo salga «provisional» o «no concluyente» es falta de golpes, no del diseño. Aun así, el diseño debería decirlo una vez, no en cada clave.

Fuentes: [Sportsbox 3D Golf (App Store)](https://apps.apple.com/us/app/-/id1578921026) · [Golf.com sobre Sportsbox](https://golf.com/instruction/sportsbox-ai-exposed-flaws-golf-swing-play-smart/?amp=1) · [Barla Golf Academy, Sportsbox](https://www.barlagolfacademy.com/did-you-know-coach-barla-now-uses-sportsbox-studio-ai-for-3d-swing-analysis/) · [Tennis.com sobre SwingVision](https://prod.tennis.com/news/articles/swingvision-delivers-pro-level-insights-for-recreational-players) · [SwingVision en LTA ClubSpark](https://clubspark.lta.org.uk/Aspire2Achieve/Slinger/SwingVision) · el resto (Hudl Technique, OnForm, TennisViz y las referencias de Wulf, Sweller, Bandura, Ericsson, Masters y Chiviacowsky) es de memoria.
