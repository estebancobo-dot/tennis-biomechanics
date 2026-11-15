# P0 · Mapa de pantallas, recorridos y sistema de diseño (P0.4, 15-11)

La aplicación nueva junta la aplicación de hoy (10 pantallas) y el informe (11 pantallas) en **5 secciones**. Cada
una responde a una pregunta. **15-11 (#301): aplicación de escritorio en el PC**, a 1280-1920 px de ancho y con un
mínimo de 1024. Nada de móvil. La navegación va en una columna a la izquierda. Patrones de la comparativa: `docs/comparativa_completa.md`.

**Maqueta para revisar:** página privada <https://claude.ai/artifact/Vi3ags11xK2ap6gSAJvt6N> (versión 2, 15-11: de escritorio, #301; la 1 era para el móvil). Lleva
los números reales del informe beta. Se rehace con `python design/p0/build_maqueta.py <informe> <salida>`; la
plantilla, sin datos, está en `design/p0/maqueta.html`. El repositorio es público y no guarda la página con datos.

## 1. Las 5 secciones (columna de navegación a la izquierda)

| Sección | Pregunta | Qué junta de hoy | Contenido |
|---|---|---|---|
| **Su derecha** | ¿Cómo pega la derecha en esta situación? | Aprende, Conclusiones, Modelo (derecha típica), Ritmo | Aviso beta; «Lo esencial» (conclusiones con su confianza y sus golpes); «Cómo la pega» (8 fases + pies, una tarjeta por fase con su fotograma real, 1-5 medidas, consigna, error típico y ejercicio); ritmo y cadena cinética; «Lo que puedes copiar» |
| **Golpes** | ¿Dónde lo veo en vídeo? | Videoteca, Explorador, Análisis de golpe | Lista ordenada por captura, tiempo o partido; cada golpe abre su vídeo con capas, sus fases y sus medidas frente a lo habitual |
| **Comparar** | ¿Qué cambia entre dos situaciones? | Comparar, comparativas por situación, fatiga, presión | Dos situaciones lado a lado (medidas y vídeos con el impacto alineado); las diferencias ajustadas, con su veredicto |
| **Pista** | ¿Dónde golpea y adónde va la bola? | Pista | Impactos y botes en la pista a escala; porcentajes |
| **Partidos** | ¿Qué hay analizado y cómo añado uno? | Inicio, Análisis, Partidos, Partido, Cola, Almacenamiento | Partidos con su estado; añadir uno en 3 pasos (subir, el clic de identidad, aprobar); estado de la cola |

Fuera de la barra (menú de la cabecera): Jugadoras, Fiabilidad y calidad (juntas), Vista lateral (entreno, apartado
marcado, requisito 6), Exportar. **Desaparece:** Ajustes (100 % automático; lo poco que queda va a Partidos) y las
tablas sueltas de «Datos» (van a Exportar).

**La situación** (Todas, bola rápida o lenta, abierta, corta, baja, alta, en carrera, parada) está arriba y vale para
todas las secciones. Cada botón lleva su número de golpes.

## 2. Recorridos (aceptación: toques como máximo)

| Tarea | Toques | Camino |
|---|---|---|
| Ver cómo pega en una situación | 1 | Su derecha → la situación |
| Ver un golpe en vídeo con sus medidas | 1-2 | Un dato o una conclusión → sus golpes → el golpe |
| Comparar dos situaciones | 3 | Comparar → A → B |
| Añadir un partido | 3 + la subida | Partidos → elegir el vídeo en el PC → el clic de identidad → aprobar |
| Pausar la cola | 2 | Partidos → pausar |

## 3. Sistema de diseño (lo que fija la maqueta)

- **Colores** (claro y oscuro, en variables):
  - azul de pista dura como acento;
  - verde de la zona exterior;
  - amarillo de bola solo para el impacto;
  - tres colores de estado (bien, aviso, mal) aparte del acento.
- **Letra:**
  - Barlow Condensed para títulos y cifras, como los rótulos de la tele;
  - Inter para el texto;
  - cifras tabulares.
- **Componentes:**
  - botón de situación con su número;
  - tarjeta de conclusión: frase, confianza y «ver sus N golpes»;
  - tarjeta de fase: fotograma, momento respecto al impacto, medidas, consigna, error y ejercicio;
  - medida: valor, la mitad central de sus golpes, fiabilidad y diferencia solo si supera el error;
  - marca de fiabilidad: fiable, media, baja o estimada;
  - gráfico de ritmo: mediana y mitad central por momento;
  - hoja del golpe: vídeo, controles, fases y medidas;
  - pista a escala.
- **Reglas:**
  - una diferencia solo se marca si supera el error de la medida (requisito 3);
  - menos de 10 golpes, sin mediana;
  - la fiabilidad siempre a la vista;
  - nada de tablas en la primera pantalla.

## 4. Lo que la maqueta no tiene todavía (se construye en P0.5)

- **Fotogramas y vídeos reales:** los recuadros los marcan; los recortes están en el almacenamiento privado.
- **Ajuste por la bola y el partido en las medianas por situación:** la maqueta usa medianas simples; las conclusiones y
  «Lo que cambia, con ajuste» ya lo llevan.
- **La medida dibujada sobre el fotograma** (arco del ángulo, regla de la base).
- **Subida, descarga de resultados y cola reales:** llegan con N (`docs/n_web.md`: escritorio, sin web).

## 5. Revisión del usuario (P0.4 se cierra con ella)

Se pide **una** revisión de la maqueta: si las 5 secciones, el orden de «Su derecha» y las tarjetas de fase son como
las quiere. No se revisan datos. Lo que diga va a `docs/peticiones_usuario.md` y a la siguiente versión de la maqueta.
