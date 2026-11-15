# P0 · Inventario completo antes de diseñar (P0.1 rehecho, 15-11)

**Por qué existe este documento.** La maqueta publicada el 15-11 no valía, y el usuario lo dijo así: «0 profesional, 0
funciones válidas, fija a un golpe y a una jugadora, sin gestión de catálogos, jugadores, partidos, golpes, aprendizaje
ni usabilidad». Tenía razón. Se hizo sin repasar las peticiones ni los documentos de diseño que ya existían.

Por eso, antes de dibujar nada, este inventario recoge todo lo pedido y todo lo que existe. El diseño de P0
(`docs/p0_pantallas.md`, que se rehará) tiene que cubrir cada fila de aquí o descartarla con su motivo.

## 1. Fuentes revisadas

| Fuente | Qué decide para la aplicación |
|---|---|
| `CLAUDE.md` | Requisitos 1-10. «Informe y salida visual»: 5 pantallas, 8 fotogramas clave por golpe, galerías por golpe y situación ordenadas por captura, representatividad y resultado, sin nota de «mejor técnica». «Vistas por golpe pedidas»: la bola y ella, bajar y subir, base, tronco al terminar. Situaciones del golpe, fiabilidad por medida, ampliación a otros golpes y jugadores |
| `docs/peticiones_usuario.md` | Las 301 peticiones, una a una (sección 2 de este documento) |
| `docs/aplicacion_local.md` (17-10) | **La aplicación como producto:** 5 objetos (vídeo, partido, jugadora, golpe, análisis = jugadora × golpe); 8 pantallas (Inicio, Análisis, Partidos, Jugadoras, Cola, Calidad, Almacenamiento, Ajustes); el flujo completo (añadir N partidos, elegir persona con su foto, ficha, golpe, ver); casos nominales, límite, esquina y error; lo que no hace |
| `docs/diseno_definitivo.md` (17-10) | **El visor de un análisis:** 3 entradas (Lección, Sus golpes, Más). La lección: contexto en una línea, tira de fases con miniatura, vídeo en bucle de la fase, foco, ≤ 3 claves, cuerdas por fase, un ejercicio «N de 10». 15 criterios de aceptación medibles en el navegador |
| `docs/auditoria_17_10/3_usabilidad_aprendizaje.md` | Veredicto pantalla a pantalla con capturas reales. Principios de aprendizaje motor: modelado, carga cognitiva, foco externo, práctica deliberada, autoeficacia. Por qué 3 entradas |
| `docs/auditoria_17_10/1_peticiones_y_requisitos.md`, `2_conocimiento_tecnico.md` | Peticiones 1-130 frente a la web; correcciones técnicas de textos y medidas |
| `docs/arquitectura_producto.md` | Modelo de datos (SQLite), almacenamiento por clases de retención, hora estimada de fin, versiones y migraciones, calidad por partido |
| `docs/escenarios_producto.md` | Escenarios del producto genérico: jugadores (hombre, zurdo, revés a una mano, sin altura, jugador nuevo), partidos (torneos, calidades, dobles, dañados), identidad (deshacer el clic, la otra persona), golpes (revés, saque, volea…), análisis (comparar jugadores, superficies, temporadas) |
| `docs/matriz_cobertura.md` | La taxonomía completa del golpe (fases, cuerpo, pies, raqueta, bola, resto, matriz del usuario): lo que cada fase de la lección y cada golpe deben enseñar |
| `docs/aprendido_entrenadores.md`, `docs/investigacion_youtube_usuario.md` | Cómo explican los entrenadores: orden, secuencias de 3-4 fotos, lado a lado, círculo y frase, «lo que puedes copiar», vocabulario y analogías |
| `src/tennisbio/app/ui.html` | La aplicación de hoy: las 8 pantallas de `aplicacion_local.md`, más «Añadir partido» y «Analizar también…» |
| `src/tennisbio/report_template.html` | El visor de hoy: Aprende, Videoteca, Análisis de golpe, Comparar, Conclusiones, Datos, Explorador, Vista lateral, Fiabilidad |
| `docs/maqueta_aplicacion.html`, `docs/maqueta-informe.html`, `docs/maqueta_leccion_armado.html` | Las maquetas anteriores: la aplicación (8 pantallas con 2 jugadoras y 3 golpes), el informe (5 pantallas, datos inventados) y una fase de la lección |
| `docs/comparativa_apps.md`, `docs/comparativa_completa.md`, `config/referencias.yaml` | Comparativas con otras aplicaciones. Ojo: la del 15-11 es de fichas públicas, no de sus pantallas. El estado del arte de verdad está en la sección 5 |

## 2. Lo pedido, agrupado por función de la aplicación

Cada número es una petición de `docs/peticiones_usuario.md`. «Hoy» dice dónde está en el código actual; «En P0», lo que
el diseño nuevo tiene que hacer con ella.

### 2.1 Catálogo y gestión: partidos, jugadoras, golpes y análisis
| Peticiones | Qué piden | Hoy | En P0 |
|---|---|---|---|
| 241, 32, 18 | Aplicación genérica: jugadores, golpes y partidos por configuración, nada fijo | Fichas en `config/players`, `config/strokes`; comprobación «Nada fijo en el código» | Todo se elige del catálogo; ninguna pantalla nombra a nadie por código |
| 242, 151, 161 | Flujo: añadir N partidos, elegir la persona, hombres y mujeres, un análisis por persona; separar golpes, jugadores y partidos; los partidos de una jugadora juntos | `aplicacion_local.md` §5.1b; pantalla Análisis | Análisis = persona × golpe, con todos sus partidos; «Analizar también a…» la otra persona u otro golpe |
| 226, 245 | Lista de partidos profesional: nombres normalizados, torneo, ronda, fecha, fotos; rivales, fechas y rondas bien escritos | Pantalla Partidos (`cards.py`) | Lista y ficha del partido con torneo, ronda, fecha, superficie, fotos de las dos personas y estado |
| 258 | Partidos y jugadores automáticos desde un nombre de fichero mínimo; ficha pública de las dos jugadoras y del torneo | Propuesta por nombre (`videos.py`, `cards.py`) | Al añadir un vídeo: propuesta completa (ficha pública con caché) y un solo clic de confirmación |
| 156, 222, 60 | Identidad: un clic por partido sobre su foto | `identity_click.py` | El clic dentro de «Añadir partido»; deshacer y cambiar el clic (escenario ✘) |
| 152, 220, 229 | Estructura por jugador, partido y golpe; renombrar no rompe | Huella de contenido, `storage.py` | Igual; la aplicación nunca enseña nombres de fichero |
| 130, 223, 224, 207, 209, 210, 186 | Más golpes: resto, cortados, saque (tipos), volea, remate, passing, globo, dejada | Clasificación derecha / revés / saque | Selector de golpe del análisis con los que existan; los que no tengan casos suficientes se dicen, no se esconden |
| 301 | Vídeos desde el PC; aplicación de escritorio, nada de móvil | — | Subida desde el disco; ventana del PC |
| Escenarios | Jugador nuevo creado desde el partido, deshacer el clic, analizar a la otra persona, comparar dos jugadores, misma final de dos cadenas, dobles | `escenarios_producto.md` (✘ y ◐) | Cada uno con su sitio en la gestión |

### 2.2 Trabajo en la nube, estado y avisos
| Peticiones | Qué piden | Hoy | En P0 |
|---|---|---|---|
| 50, 10 | Progreso y monitorización visibles; ver los cambios sin esperar | Cola, Inicio | Inicio: qué se hace ahora, en qué etapa va, cuánto falta y la hora de fin |
| 246, 249 | Un único orquestador para la aplicación y el chat: monitorizar, pausar, parar y arrancar | Cola (PC) → cola de la nube | Cola de la nube vista desde la aplicación, con pausar, parar y relanzar |
| 262, 263 | El análisis completo, solo con aprobación, diciendo qué hará y cuánto tardará | Chat | Botón «Aprobar» con tiempo y cuota previstos |
| 45, 119 | Todo automático; el usuario no revisa | — | Ninguna pantalla pide revisar golpes |
| 225, 261, 230 | No se cuelga, sin ventanas vacías, uso de recursos por etapa | Auditoría | Estado de cada trabajo con sus recursos, en Calidad |
| 291 | Avisos al momento, sin esperar | Buzón del PR | Aviso de Windows al terminar o fallar |

### 2.3 Aprender su golpe (la lección)
| Peticiones | Qué piden | Hoy | En P0 |
|---|---|---|---|
| 4, 68, 69, 70 | «¿Qué hay que hacer para pegar como X?», tomar su golpe como base; un ejemplo de combinación; las 2000 y pico combinaciones usables | Aprende, `learn.py` | La lección por situación es la pantalla de entrada del análisis |
| 17, 127, 9, 57 | Una entrada que se entienda sola; guía de primer uso; información, no tablas; nada de gráficas de muchas líneas | Aprende | Criterios de `diseno_definitivo.md` §5 (≤ 3 claves, ≤ 400 palabras, vídeo en la primera pantalla) |
| 123, 126, 111, 189 | Plan de 3 prioridades, foco externo por fase, consignas con su número, la fase 1 «mirando la raqueta de la rival» | Aprende | Igual, con la marca «empieza por aquí» |
| 71, 72, 113, 147, 143, 194, 195, 213, 214, 215 | El conocimiento de entrenadores y del chat en la aplicación; examen interno; guía de Ivanovic; sus principios; fuentes | `learn.py`, COACH | Cada clave con su porqué y su fuente, plegado |
| 110, 112 | Lo que la distingue; su estilo | Su firma | Plegado en la lección |
| 197, 129 | Progresión por etapas (FALTA); hoja de sesión (NO) | — | Progresión: hueco del diseño |
| 128 | Glosario | Aprende | Glosario accesible desde cualquier término |

### 2.4 Lo medido de su golpe (la taxonomía que enseña cada fase)
Peticiones 5, 6, 7, 8 (cuerdas, obligatorio), 25, 26, 35, 36, 48, 54, 56, 64, 84-98 (la matriz del usuario), 99-112
(mejoras de entrenadores), 114-117 (las vistas pedidas), 124, 163-198 (la matriz de la literatura), 216 (pendientes de la guía), 235, 236, 254, 255.

**En P0:** cada medida sale en tres sitios, con un solo cálculo (#208):
- en su fase de la lección, si es una clave;
- en «Todas las medidas», plegada;
- en el análisis de cada golpe.

Lo que la tele no mide se dice («no medible desde la tele»); la empuñadura (#7), por ejemplo.

### 2.5 Sus golpes en vídeo (la prueba)
| Peticiones | Qué piden | Hoy | En P0 |
|---|---|---|---|
| 42, 65, 120, 121, 227 | Vídeo y no pantallazos; que funcione; a pantalla completa; capas una a una | Análisis de golpe | Reproductor con capas, velocidad real y lenta, fotograma a fotograma |
| 33, 162 | Los mejores golpes de cada tipo; galerías ordenadas por captura, representatividad y resultado | Videoteca | Videoteca con títulos legibles («2.º set 5-5 30-30 · rápida, corta · abierto») y esos órdenes |
| 114, 115, 116, 117, 54, 56 | La bola y ella, bajar y subir, base, tronco al terminar: fotogramas y medidas reales | Análisis de golpe | Igual |
| 141 | La estroboscópica y «Sus pies en este golpe» no valían | — | No vuelven así |
| 218, 219, 55 | Los dos lados de la pista; casos concretos de bola y apoyo | Videoteca | Filtro por lado y situación |

### 2.6 Comparar y contexto del partido
Peticiones 27 (partido, set, fatiga, ganadores y errores, presión), 59 (diferencias solo por encima del error y en
situaciones equivalentes), 38, 39, 135 (dirección, profundidad, distancia al fondo), 184-188 (bola, peloteo, resultado,
resto), 244 (resultado creíble).

Escenarios ✘: comparar dos jugadores, superficies y temporadas.

**En P0:**
- comparar dos golpes lado a lado, sincronizados en el impacto;
- comparar dos situaciones con el ajuste por bola y partido;
- conclusiones con solo las diferencias reales a la vista;
- comparar jugadores, cuando haya dos análisis del mismo golpe.

### 2.7 Pista, fiabilidad, vista lateral y exportación
| Peticiones | Qué piden | En P0 |
|---|---|---|
| 38, 135 | Dónde golpea y adónde va la bola | Pista |
| 11, 12, 46, 59, 118, 212, 238, 256 | Nada inventado, validación automática, fiabilidad de cada medida, modelo de calidad | Fiabilidad por medida en cada dato; pantalla Calidad con el modelo de calidad (#256) |
| 79, 254, requisito 6 | Vídeos de entrenamiento de lado, aparte y marcados | Vista lateral (entreno), aparte |
| 41, 46 | Exportación: cómo se ven y se graban; sin PDF enorme | Exportar (PDF corto, MP4) |

### 2.8 Transversal: diseño y producto
Peticiones 9, 28 (informe con gráficos y esqueleto), 34 (maqueta con datos, ahora reales), 252 (profesional: UX, usabilidad, aprendizaje, gestión, gráficos de nivel profesional), 53 y 67 (no borrar
nada: lo complejo como extra), 73 (revisar de arriba abajo), 122 (pocas entradas, el resto en «Más»), 208 (un solo
cálculo, en Python), 52 (Brave).

### 2.9 Futuras (paquete P4)
Peticiones 240 (comparar con las profesionales con los golpes ya hechos), 299 (preguntar en lenguaje natural) y 300
(muñeco 3D girable).

### 2.10 Peticiones que no tocan la aplicación
Infraestructura, nube, modelos, rendimiento y forma de trabajar: 1, 3, 13-16, 19-24, 29-31, 37, 40, 43, 44, 47, 49, 51,
58, 61, 62, 63, 66, 74-78, 80-83, 125, 131-140, 142, 144-146, 148-150, 153-155, 157-160, 199-206, 211, 217, 221, 228, 231-234,
237, 239, 243, 247, 248, 250, 251, 253, 257, 259, 260, 264-298. Algunas dejan una huella en la aplicación (el estado de
la nube, por ejemplo) y esa huella está en 2.2.

## 3. Lo que existe y qué se hace con ello

**La aplicación** (`ui.html`, diseño `aplicacion_local.md`):
- Inicio, Análisis, Partidos, Jugadoras, Cola, Calidad, Almacenamiento y Ajustes, más los diálogos «Añadir partido» y
  «Analizar también…».
- **Se queda la estructura:** es la gestión que pide el usuario.
- Se rehace la forma: diseño, componentes y gráficos.
- Cambia en la nube: Cola y Almacenamiento pasan a ser los de la nube (#284, #301).

**El visor de un análisis** (`report_template.html`, diseño `diseno_definitivo.md`):
- Aprende, Videoteca, Análisis de golpe, Comparar, Conclusiones, Datos, Explorador, Vista lateral y Fiabilidad.
- **Se queda la arquitectura de 3 entradas** (Lección, Sus golpes, Más) y sus 15 criterios de aceptación.
- Se rehace la forma.
- Nada se borra: todas las secciones de hoy siguen accesibles, plegadas o en «Más» (#53, #67).

**Las maquetas anteriores:**
- `maqueta_aplicacion.html`: las 8 pantallas con varias jugadoras y golpes. Es la base de la gestión.
- `maqueta-informe.html`: datos inventados. Solo sirve como forma.
- `maqueta_leccion_armado.html`: una fase. Es la base de la lección.

**La maqueta del 15-11 (versiones 1 y 2):** se retira como propuesta.
- **Contradecía el diseño vigente:** 5 secciones frente a las 3 entradas y las 8 pantallas.
- **Le faltaba casi todo:** la gestión; la lección según los criterios (vídeo de la fase, foco, claves, ejercicio
  «N de 10»); la elección de jugadora y golpe; la videoteca con sus órdenes; Más; Calidad; Almacenamiento.
- **Lo único aprovechable:** el generador con datos reales (`design/p0/build_maqueta.py`) y los componentes de
  situación y fiabilidad.

## 4. Pendiente y futuro que el diseño debe dejar previsto

- Más golpes (revés, saque, resto, volea…) y más jugadores, incluido el rival de cada partido. Las medidas de M1-M7, que
  aparecen en la lección y en el análisis de golpe a medida que existan.
- Comparar jugadores (escenario ✘), preguntar en lenguaje natural (#299), muñeco 3D (#300), progresión por etapas
  (#197).
- La cola y el estado son los de la nube; la descarga de resultados al PC (N, `docs/n_web.md`).

## 5. Estado del arte de verdad (hecho el 15-11: `docs/p0_estado_del_arte.md`)

La comparativa del 15-11 se hizo con fichas y prensa, y la del 17-10 con capturas propias y memoria. Falta hacerla mirando
sus pantallas y flujos reales a día de hoy: capturas de sus tiendas de aplicaciones, documentación, vídeos de
demostración y páginas de producto. Referencias:
- de análisis de golpe: Sportsbox, SwingVision, OnForm, Dartfish, Hudl Technique, Kinovea, SportAI;
- de datos del circuito: TennisViz y Hawk-Eye;
- de gestión y vídeo de equipos (lo más parecido a una aplicación de escritorio de análisis): Hudl Sportscode,
  Catapult y Dartfish Pro.

Para cada una se apunta su estructura de pantallas, sus flujos (añadir vídeo, elegir jugador, ver un golpe, comparar,
aprender) y qué patrón concreto se adopta o no, con su motivo.

**Orden:** este inventario → estado del arte de verdad → diseño completo (`p0_pantallas.md` rehecho, todas las
pantallas) → maqueta de todas las pantallas con datos reales y selección genérica → una revisión del usuario.
