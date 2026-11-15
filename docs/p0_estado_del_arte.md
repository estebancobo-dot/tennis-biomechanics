# P0 · Estado del arte de verdad: pantallas y flujos de las referencias (15-11, #302)

Sustituye, para el diseño, a la comparativa de fichas del 15-11 (`comparativa_completa.md`). Aquí solo entra lo leído
en la documentación oficial, manuales o páginas de producto de hoy, con su fuente. Lo que no se pudo leer se dice.

## 1. Lo confirmado, por referencia

### Hudl Sportscode (escritorio, análisis de vídeo de equipos)
Fuente: [manual de Sportscode](https://www.hudl.com/support/manuals/sportscode/review-and-analyze/code-matrix/using-the-code-matrix).
Las páginas de cuerpo son del manual de la versión 10, así que la aplicación actual puede diferir.
- **Ventanas:**
  - de código: botones por categoría que marcan instantes («instancias»);
  - línea de tiempo: el vídeo arriba y su línea de tiempo debajo;
  - matriz;
  - ordenador (*sorter*): organizador, secuenciador y estadística en una;
  - organizador de vídeos, búsqueda, notas y dibujo.
- **La matriz:** filas = categorías y columnas = etiquetas; cada celda cuenta sus instancias, con totales por fila y
  columna. **Doble clic en una celda, fila, columna o total = un vídeo con esas instancias.** Un clic las selecciona en
  la línea de tiempo.
- **El ordenador:** una fila por instancia. Se reordena, recorta y anota, se ordena por tiempo, por orden alfabético o
  por frecuencia, y se convierte en un vídeo, como una lista de reproducción.

### Kinovea (escritorio, gratuito)
Fuentes: [interfaz](https://kinovea.readthedocs.io/en/latest/userinterface/ui.html),
[funciones](https://www.kinovea.org/features), [versión 2025.1](https://www.kinovea.org/download/releases/2025.1.html).
- **Disposición:**
  - panel de navegación a la izquierda (ficheros, accesos, cámaras);
  - zona central con una o dos pantallas de reproducción;
  - barra de estado.
- **Dos pantallas:** lado a lado o superpuestas, también en vertical; sincroniza vídeos de distinta velocidad de
  imagen y exporta el vídeo compuesto.
- **Imágenes clave con comentario,** que se repasan en orden.
- **Medida sobre la imagen:** línea, ángulo, goniómetro, cronómetro, calibración del plano; trayectorias y seguimiento.
- **Cinemática:** velocidades lineales y angulares, diagramas ángulo-ángulo y exportación CSV.

### OnForm (móvil y web, para entrenadores)
Fuentes: [buscar y encontrar](https://help.onform.com/set-up/search-and-find.md),
[herramientas de análisis](https://help.onform.com/how-onform-works/analysis-tools.md), [inicio](https://onform.com/).
- **Biblioteca** por deportista, equipo o colección. Búsqueda por etiqueta, título o persona, filtros (destacados, con
  voz) y «saltar a una fecha».
- **Reproductor:**
  - cámara lenta de 2× a 1/8× y avance fotograma a fotograma;
  - dibujo: línea, flecha, círculo, ángulo, distancia con escala, cronómetro y texto;
  - esqueleto 2D con ángulos.
- **Comparar:** lado a lado o uno encima de otro, con «Enlazar» para avanzar los dos a la vez; superposición con
  deslizador de transparencia.
- **Guías de primer uso por papel:** entrenador, deportista, padre…

### SwingVision (móvil, tenis; versión 11.9.70, octubre de 2026)
Fuente: [ficha de la App Store](https://apps.apple.com/us/app/swingvision-tennis-pickleball/id989461317).
- **Pestañas:** Grabar y «Yo» (las grabaciones, con filtro por sesión y jugadores etiquetados).
- **Reproducción:**
  - golpe a golpe o punto a punto, con marcador;
  - capas de velocidad y de golpe, trazador de la bola y mapa de calor;
  - editar y corregir un punto.
- **Filtros:** momentos destacados por tipo de golpe, intercambios, efecto del saque, ganadores y errores.
- **Práctica:** entrenador con IA tras cada sesión, objetivos semanales, práctica con zonas y retos del mes.

### Sportsbox AI (golf; tenis sin confirmar)
Fuentes: [Sportsbox](https://sportsbox-ai.web.app/about), [lanzamiento de 3D Practice](https://sportsbox-ai.web.app/press-releases/3dpractice-launch)
(2022). La ficha de la App Store no se pudo leer (error 429).
- **El golpe:** en 3D desde un vídeo, visto desde 6 ángulos (de frente, en la línea, detrás, desde el objetivo, arriba
  y abajo), con más de 30 puntos.
- **Práctica:** más de 150 guías. Cada guía tiene su punto de atención («Watchlist»), ejercicios, una evaluación del
  golpe frente al objetivo y práctica con objetivo.

### TennisViz (datos del circuito ATP)
Fuente: [ATP, presentación de INSIGHTS](https://www.atptour.com/en/news/insights-introduction) (2022). El portal propio
no se pudo leer (página vacía).
- **Cinco ejes:**
  - tipo de golpe (más de 60);
  - calidad de 0 a 10;
  - situación del jugador (sacando, restando, los dos al fondo, en la red);
  - fase del juego (ataque, neutra, defensa);
  - tácticas y patrones (7 y 48).
- **Comparación:** cada dato va con la media del jugador, del circuito y del torneo.

### IBM en el US Open 2026
Fuente: [IBM](https://newsroom.ibm.com/2026-08-24-ibm-and-the-usta-introduce-new-ai-powered-fan-experiences-for-2026-us-open).
- Nota de 0 a 100 de cada saque tras el partido (21 puntos del cuerpo y la raqueta a 50 por segundo).
- Resumen del partido con un chat para preguntar.

### SportAI (tenis y pádel)
Fuentes: [plataforma](https://sportai.com/platform), [blog del 11-11-2024](https://sportai.com/blog/ai-powered-technique-analysis-for-racket-sports).
La documentación de su API da error 404.
- Vídeo 2D convertido en pose 3D, con cadena cinética, detección de mejoras y comparación de golpes.
- Mide la velocidad de la muñeca, el giro de cadera y de hombros y el punto de contacto.

### No se pudo leer
- **Dartfish:** la web devuelve una verificación anti-robots.
- **El portal de TennisViz.**
- **Las capturas de Sportsbox en la App Store.**

Lo que el diseño del 17-10 dice de ellas viene de la memoria de entonces (`auditoria_17_10/3`) y se marca así.

## 2. Patrones, y qué hace P0 con cada uno

| Patrón (fuente) | En P0 |
|---|---|
| **Cada número abre sus clips** (matriz de Sportscode) | Regla de toda la aplicación (ya era requisito). Las tablas por situación son matrices: cada celda, fila y total abre sus golpes |
| **Matriz situación × clase con recuentos** (Sportscode) | «Comparar situaciones»: filas = situaciones, columnas = clases (apoyo, terminación, resultado); cada celda con su n y sus golpes |
| **Lista de reproducción ordenable** (*sorter* de Sportscode) | «Reproducir todos» de cualquier selección, ordenado por tiempo, captura, representatividad o resultado; guardar una lista de estudio |
| **Biblioteca por persona y colección, con búsqueda y filtros** (OnForm, SwingVision) | Catálogo: jugadoras, partidos, análisis; videoteca con filtros por situación, partido, set, resultado, presión y fecha |
| **Navegación a la izquierda y zona central** (Kinovea, escritorio) | Disposición de la aplicación de escritorio |
| **Dos pantallas: lado a lado, en vertical o superpuestas, enlazadas** (Kinovea, OnForm) | Comparar dos golpes: sincronizados en el impacto, lado a lado o superpuestos con transparencia, avance enlazado |
| **Imágenes clave con comentario, en orden** (Kinovea) | Los 8 fotogramas clave del golpe, cada uno con su frase |
| **La medida dibujada sobre la imagen** (Kinovea, OnForm) | El ángulo o la distancia medidos, dibujados en su fotograma (automático, nunca a mano) |
| **Cámara lenta de 2× a 1/8× y fotograma a fotograma** (OnForm) | Reproductor: velocidad real, 1/2, 1/4, 1/8 y fotograma a fotograma |
| **Golpe a golpe o punto a punto, con marcador** (SwingVision) | En un partido: ver sus golpes de un punto seguidos, con el marcador leído |
| **Trazador de la bola y mapa de calor** (SwingVision) | Capa de la bola en el reproductor; Pista con impactos y botes |
| **Guía con un punto de atención, ejercicios, evaluación y objetivo** (Sportsbox Practice) | La fase de la lección: foco, ≤ 3 claves, un ejercicio con criterio «8 de 10» y «Conseguido» (ya en `diseno_definitivo.md`) |
| **Situación del jugador y fase del juego** (TennisViz) | Situaciones: sacando o restando, los dos al fondo, en la red; ataque, neutra y defensa (ya en la taxonomía) |
| **Cada dato con la media de referencia** (TennisViz) | Cada dato frente a lo habitual en ella (sus partidos); nunca frente a otras jugadoras sin analizarlas (requisito 6) |
| **Nota única 0-10 / 0-100** (TennisViz, IBM) | **No:** no está validada para la tele (`CLAUDE.md`) |
| **Chat sobre el análisis** (IBM) | #299, más adelante |
| **3D desde varios ángulos** (Sportsbox) | #300, más adelante y como estimación |
| **Guías de primer uso por papel** (OnForm) | «Empieza aquí» de una línea y ayuda contextual |
