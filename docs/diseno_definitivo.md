# Diseño definitivo de la web (17-10)

Este documento fija el diseño de la web de una vez. Sale de tres auditorías completas, hechas de arriba abajo y en paralelo (en `docs/auditoria_17_10/`):

1. Peticiones y requisitos del usuario: `CLAUDE.md`, `peticiones_usuario.md` (1-130 y Mejoras 1-15), la matriz y las vistas pedidas.
2. Conocimiento técnico: entrenadores de YouTube (R1-R25), literatura, taxonomía y guía de Ivanovic.
3. Usabilidad y aprendizaje: capturas reales del PC frente a Sportsbox, Hudl, OnForm, SwingVision y TennisViz, y frente a los principios de aprendizaje motor (Wulf, Sweller, Bandura, Ericsson, Masters, Chiviacowsky).

**Regla de trabajo.** A partir de aquí no se rediseña. Se construye contra este documento y se comprueba con los criterios de la sección 5, de forma automática en el navegador, en los tests y en el PC con datos reales. Claude valida y el usuario no.

**Meta (requisito 1).** Que cualquiera, solo con retransmisiones, aprenda a pegar la derecha de la jugadora en todas sus variantes, con su vídeo real como prueba, sin nada inventado y diciendo lo que la tele no puede medir.

## 1. Estructura: 3 entradas y nada borrado

```
LECCIÓN (entrada)      SUS GOLPES (la prueba)      MÁS (extra técnico)
```

### Lección

1. **Una línea de contexto:** «Su derecha · N golpes · todas las situaciones [Cambiar ▾]».
   - [Cambiar] abre el selector completo, que incluye **ataque/neutra/defensa** y **bola centrada/abierta**.
   - Encima van 6 atajos: rápida, lenta, alta, baja, en carrera, abierta.
2. **Tira de fases 1-8 y Pies,** con la marca «empieza por aquí» en las 3 fases del plan.
3. **Vídeo de la fase en bucle,** primero y grande, con su marca dibujada encima.
   - Se puede ver a 0,25× o a velocidad real.
   - Botones: otro golpe suyo, golpe entero.
4. **Foco:** una frase de foco externo o analogía, sin cifras del cuerpo.
   - Si el foco general de los entrenadores choca con lo que hace ella, se dice: «regla general; ella arma 0,14 s después del bote».
5. **Hasta 3 claves.** Cada una muestra: nombre, su valor (en tus cm si hay altura) con el nº de golpes, una línea de «Cómo», y «Cambia con la bola» solo si supera el error.
   - «Tu objetivo» solo aparece si convierte a tus unidades; si repite el valor, no.
   - El error típico va plegado en «Más».
6. **Cuerdas en cada fase** (requisito 4): una línea fija con hacia dónde miran (valla trasera, suelo, cielo…) y en qué % de golpes. En el impacto, marcada como «estimación».
7. **Practica:** un ejercicio con criterio de éxito («8 de 10») y un botón «Conseguido» que se guarda solo en el navegador. Los demás ejercicios van plegados.
8. **‹ Fase anterior · Fase siguiente ›**
9. **Plegado (extra, se queda todo):** Su firma, Su ritmo, Qué cambia, Tu plan completo, Si te pasa…, Lo que la tele no mide (con **empuñadura**), Glosario, Todas las medidas y Su patrón típico.
   - «Novedades» pasa a Datos.
   - La guía «Empieza aquí» se reduce a una frase.

### Sus golpes

- Videoteca con títulos legibles, por ejemplo «2.º set 5-5 30-30 · rápida, corta · abierto», en lugar del nombre del fichero. La misma situación que en la Lección.
- **Análisis de un golpe:**
  - a la vista: vídeo con la capa «Cuerpo», línea de tiempo con las 8 fases y «La bola y ella»;
  - plegado: Su cuerpo, Sus pies, Métricas, Gráficas, Raqueta y Recorrido del brazo.

### Más

- **Comparar:** las frases a la vista y la tabla plegada.
- **Conclusiones:** a la vista, solo las «diferencias reales»; lo no concluyente, plegado.
- **Vista lateral, Tabla de golpes, Fiabilidad y Datos (+ Novedades):** como están.

## 2. Lo que está bien y se queda tal cual

- **Mecanismo de la lección:** vídeo en bucle con marca por fase, como mucho 3 claves fiables, `lBySpeed`, «Otro golpe suyo» y «Ver el golpe entero».
- **Fiabilidad:** filtro de ruido y sesgo en «Cópiala», «no medible desde la tele», y las pantallas de Fiabilidad y Datos.
- **Focos externos buenos y comprobaciones con criterio:** «Bote = armado», «aterriza cuando oigas el golpe», «8 de 10».
- **Videoteca:** cuadrícula de vídeo con avance al pasar el ratón.
- **Reproductor del golpe:** las 8 fases, las miniaturas, «La bola y ella», «Sus pies» con fotogramas reales, «Raqueta por fase».
- **Comparar** sincronizado en el impacto.
- **Tu altura → tus cm,** glosario y estética.
- **Vista lateral marcada aparte;** auditoría automática con capturas del PC.

## 3. Errores que se corrigen (contradicen requisitos o fuentes)

**Requisitos y funcionamiento**

1. **Requisito 3:** Métricas, Comparar, Explorador y Conclusiones no miran la fiabilidad. Deben usar `DATA.reliability`: lo que es ruido o sesgo se marca «no fiable desde la tele» y se excluye de los hallazgos.
2. **Comparar** trata un valor que falta como 0. Conclusiones cuenta golpes lejanos para el mínimo y da «diferencia real» con grupos pequeños.
3. **Informe con 0 golpes** deja de funcionar (`tab-modelo`). Conclusiones se sale de pantalla a 1440 px. Los recuentos de dudas no cuadran entre la cabecera y Datos.
4. **«Provisional = menos de 5 golpes»** en la guía y el glosario, cuando el código usa 12.

**Textos que contradicen las fuentes**

5. La paralela dice a la vez «adelantar» y «más tarde».
6. El codo y la empuñadura se contradicen entre COACH y `grip_compatible`.
7. La comprobación de la mano en el armado presupone el signo.
8. El codo alto y el pie de delante cruzado se presentan como errores cuando son estilos válidos.
9. El foco de la preparación dice «valla del fondo» y debe ser «valla lateral».
10. La pausa presenta como absoluto «se pierde energía».
11. El glosario describe el apoyo abierto como «pierna de atrás».
12. Hay un «lado izquierdo» escrito a fuego; debe decir «brazo libre».
13. «Hip_height» habla del peso cuando mide la altura de la cadera.

**Medidas**

14. **«Pausa arriba» y «loop falso».** El umbral es relativo al pico del swing y la ventana es muy larga. Hay que validarlo con clips antes de enseñarlo como objetivo. Mientras tanto, va al final de la lista del armado.
15. **Grados poco fiables enseñados como objetivo:** cara en el impacto y en la caída, y X-factor negativo. Deben salir sin grados o como «estimación».

## 4. Lo que falta, en orden de trabajo

**A. La lección: estructura y contenido**

1. **Estructura:** lección arriba y vídeo en la primera pantalla; contexto en una línea con [Cambiar]; Novedades a Datos; guía en una frase.
2. **Cuerdas** por fase en la lección.
3. **Orden de claves** de `learn.LESSON` según la auditoría 2, sección 2, con los puntos de control nuevos:
   - `takeback.hands_apart` (giro con la mano libre);
   - `loaded.com_over_feet` (peso atrás);
   - cadena cinética;
   - `stroke.swing_rise_after`;
   - `footwork.off_centre_at_opp_hit_m`;
   - el apoyo en los Pies;
   - `stroke.weight_shift` en el impacto.
4. **Clave compacta:** valor + Cómo; «Tu objetivo» solo si convierte; error típico y otros ejercicios, plegados.
5. **Un ejercicio con criterio «N de 10»** y el botón «Conseguido». «Cómo comprobarlo» en todas las claves de la lección.
6. **Foco frente a sus datos:** aviso cuando el foco de los entrenadores no es lo que hace ella.
7. **Condiciones** `intent` y `width`; empuñadura y altura del split en «lo que la tele no mide».
8. **Velocidad real** en el bucle, y «Siguiente fase».

**B. Correcciones**

9. Todos los errores de la sección 3.

**C. Coherencia**

10. Títulos legibles de los golpes; un solo cálculo de «rápida» y «alta» (las clases) en la videoteca y en los indicadores.
11. Su firma sin negaciones de eventos raros; COACH en las 21 claves sin texto; las fuentes Iino, Kojima, Bahamonde, Knudson, Kawamoto y Wulf visibles; ~14 términos nuevos en el glosario.
12. Análisis de golpe con la capa «Cuerpo» por defecto y los extras plegados; Comparar y Conclusiones con la tabla y lo no concluyente plegados; enlaces a la exportación (PDF y MP4).

**D. Datos reales**

13. Ver la lección con el partido entero: pedir al PC el informe de `_poc9_largo` con capturas.

**Pendiente después:** la guía de Ivanovic que queda de la sección 3 (táctica medida, pies según lo que corre, resto «bloqueo», progresión por etapas). Luego la aplicación local.

## 5. Criterios de aceptación

Son automáticos: `learn_check`, `tests/test_learn_web.py` y `screens.py` en el PC. Se miden a 1280×900, 390×844 y 1440.

**Primera pantalla**

1. El vídeo de la lección cabe entero en la primera pantalla a 1280×900. En el móvil empieza en la primera mitad.
2. El vídeo avanza solo en ≤ 2 s. A su vídeo de cualquier fase se llega con ≤ 1 clic, y el golpe entero está a 1 clic.
3. Por encima de la lección hay ≤ 120 px. En la primera pantalla hay ≤ 12 controles.

**Lección, por fase**

4. Como mucho 3 claves visibles y ≤ 120 palabras en las claves. Panel de la lección ≤ 900 px a 1280.
5. Un foco de ≤ 20 palabras, sin «%», «°» ni «cm».
6. Un ejercicio visible con criterio «N de M».
7. Cuerdas dichas en cada fase (en el impacto, «estimación»).
8. «Tu objetivo» nunca repite el número de «Ella».

**Toda la web**

9. Al abrir la Lección se ven ≤ 3 títulos de sección, ≤ 400 palabras y ≤ 25 botones.
10. Menú con ≤ 3 entradas principales. En «Más» se mantienen los accesos directos que pidió el usuario («Su patrón típico» y «Dónde golpea» llevan a su sitio).
11. Sin desplazamiento lateral en ninguna pantalla (390, 1280, 1440). Ningún nombre de fichero visible como título de un golpe.
12. Ninguna medida de ruido o sesgo se da como valor ni como hallazgo en ninguna pantalla.
13. Informe con 0 golpes sin errores. 0 errores de página.

**Lo que no se puede romper**

14. Nada borrado: una ficha por cada clave de `learn_keys()` en «Todas las medidas», y todas las pantallas y secciones de antes accesibles.
15. «Conseguido» se guarda; si el almacenamiento falla, la página carga igual.
