# P0 · Rehacer la aplicación por completo: plan de bajo nivel (P0.1, 11-11)

Paquete P0 del plan (`config/plan_peticiones.yaml`), justo después de la Base (decisión del usuario, 11-11). Peticiones
#256 (modelo de calidad), #257 (comparativa catalogada) y #252 (la aplicación nueva). El análisis y el diseño (P0.1-P0.4)
se adelantan en la nube en paralelo con la Base; la construcción (P0.5) empieza con la Base cerrada.

## 1. Qué hay hoy (punto de partida medido)
- **Dos interfaces separadas que hacen cosas que se solapan:**
  - La **aplicación** (`app/ui.html`, 1187 líneas, una página en una ventana pywebview con API en Python): Inicio,
    Análisis, Partidos, Partido, Jugadoras, Jugadora, Cola, Calidad, Almacenamiento, Ajustes.
  - El **informe** (`report_template.html`, 2890 líneas, un HTML por jugadora y golpe con los datos dentro): Aprende,
    Conclusiones, Videoteca, Explorador, Comparar, Modelo, Pista, Fiabilidad, Vista lateral, Datos, Análisis de golpe.
- **Sin componentes ni sistema de diseño:** HTML y JavaScript a mano, gráficos dibujados a mano en SVG/canvas (los que el
  usuario describe como «de un niño de 5 años»), sin tipado, sin pruebas visuales.
- **Lo que sí sirve y se conserva:** el motor (etapas, pose, bola, medidas, estadística), el registro único y la cola
  (orquestador), el modelo de calidad, la auditoría y los datos por partido.

## 2 ter. Aplicación de escritorio en el PC (15-11, #301: vigente; sustituye a la web de abajo en lo que cambia)

El usuario sube los vídeos desde el PC y ve la aplicación en el PC. Nada de móvil. Lo que cambia frente a la versión web
de abajo:

| Capa | Escritorio (vigente) |
|---|---|
| Ventana | pywebview con WebView2 en el PC (como en la tabla del 13-11), con la misma interfaz React + TypeScript |
| Datos | Los resultados de cada partido se descargan del volumen de Modal a `C:\tenis\output` y se leen de ahí. El vídeo de cada golpe es local |
| API | La de Python dentro de la propia aplicación, con el contrato tipado; no hay servidor (el PC no es servidor, requisito 10) |
| Subida, clic y aprobación | Desde la aplicación: el vídeo al volumen de Modal; el clic y la aprobación, a la cola de la nube |
| Pantalla | **PC primero:** 1280-1920 px de ancho, con un mínimo de 1024; sin diseño para el móvil |
| Pruebas | Las mismas (Playwright sobre la interfaz con datos de ejemplo, en la nube de Claude), a 1280 y 1920 px |

## 2 bis. Arquitectura para la web (15-11, #296: P0 se diseña ya como aplicación web y se construye una sola vez)

La tabla de abajo era para una aplicación local (ventana de escritorio en el PC). Desde el 13-11 la aplicación va a la
nube y desde el 15-11 P0 se diseña directamente como web. Lo que cambia y lo que se queda:

| Capa | Web (vigente) | Por qué |
|---|---|---|
| Interfaz | **React + TypeScript + Vite**, una sola aplicación (aplicación + informe unidos), compilada a ficheros estáticos | Se queda: es lo más extendido, tipado, con componentes de calidad; los estáticos sirven igual en cualquier alojamiento |
| Componentes y diseño | Sistema de diseño propio sobre Tailwind + componentes accesibles (Radix) | Se queda |
| Gráficos | Apache ECharts (u Observable Plot donde baste) | Se queda (a confirmar en P0.3) |
| Vídeo | Reproductor propio sobre `<video>` + capa canvas (esqueleto, raqueta, bola) con los recortes de cada golpe | Se queda; los recortes se sirven desde el almacenamiento privado |
| Ventana | ~~pywebview~~ → **el navegador** (móvil y PC) | La aplicación es una web |
| API | **FastAPI** dentro del alojamiento privado (`docs/n_web.md`: un Space privado de Hugging Face), con el contrato tipado; lee los resultados del conjunto de datos privado y recibe la subida, el clic y la aprobación | El contrato tipado se queda; ahora es el único camino entre la web y los datos |
| Datos | Resultados por partido (JSON y recortes) en el almacenamiento privado; la cola de la nube (`config/cola_nube.yaml`, `nube-logs`) como estado de los trabajos | Una sola fuente de verdad, ya en la nube |
| Trabajos | La cola de la nube (Kaggle, Modal), nunca el PC | #284 |
| Pruebas | Playwright (recorridos), regresión visual por capturas, axe-core, presupuestos de rendimiento en el móvil | Se quedan; el móvil pasa a ser la pantalla principal |

Las tareas P0.1-P0.4 (este plan, el modelo de calidad, la comparativa y el diseño) se hacen ya en la nube de Claude; la
construcción (P0.5) cuando la Base cierre. La maqueta interactiva se publica como página privada para que el usuario la
revise desde el móvil.

## 2. Arquitectura propuesta (13-11, para una aplicación local: sustituida por la de arriba en lo que cambia)
| Capa | Elección | Por qué |
|---|---|---|
| Interfaz | **Una sola aplicación** (aplicación + informe unidos), React + TypeScript, Vite | Lo más extendido y con más componentes de calidad; tipado; se compila a ficheros estáticos que funcionan sin conexión (también en el móvil, P6) |
| Componentes y diseño | Sistema de diseño propio sobre Tailwind CSS + componentes accesibles (Radix) | Coherencia visual, modo claro/oscuro, accesibilidad por defecto |
| Gráficos | Apache ECharts (o Observable Plot donde baste) | Gráficos de nivel profesional, interactivos, sin conexión |
| Vídeo | Reproductor propio sobre `<video>` + capa canvas/WebGL (esqueleto, raqueta, bola, marcas por fotograma) | Vídeo primero, como las apps profesionales |
| Ventana | pywebview (ya instalado, WebView2) | Sin cambios de instalación |
| API | FastAPI local (contrato tipado OpenAPI/pydantic) en vez de llamadas sueltas a `window.Api` | Un contrato único para la ventana, las pruebas y el móvil |
| Datos | El registro y la cola (SQLite, `datos/tennisbio.db`) + los ficheros de cada partido; vistas de lectura por pantalla | Una sola fuente de verdad (orquestador) |
| Pruebas | Playwright (recorridos de tareas), regresión visual por capturas, axe-core (accesibilidad), presupuestos de rendimiento | Medibles en el modelo de calidad |

Decisión pendiente de la comparativa (#257): confirmar React frente a Svelte y ECharts frente a Plot con los patrones de
las referencias; se decide en P0.3 con sus motivos escritos.

## 3. Tareas
| Tarea | Qué | Carril | Validación |
|---|---|---|---|
| P0.1 | Este plan | nube | — |
| P0.2 | Modelo de calidad completo (#256): métricas para las 7 casillas sin medir (rendimiento y portabilidad de pantallas, exactitud con verdad de taxonomía y situaciones, mantenibilidad de datos, portabilidad del PC), pesos | nube | `tennisbio calidad` sin casillas «sin medir» esperadas |
| P0.3 | Comparativa catalogada (#257): `config/referencias.yaml` y `docs/comparativa_completa.md`; cada hueco → petición | nube (web) | cada referencia con sus casillas puntuadas · **hecha (15-11)**: 15 referencias de su descripción pública; huecos #299 y #300 |
| P0.4 | Diseño: mapa de pantallas (unión de aplicación + informe, sin duplicados, lo que sobra fuera), recorridos de tareas, sistema de diseño, maqueta interactiva | nube | **una revisión del usuario** del prototipo (no de datos) · **maqueta publicada (15-11)**: `docs/p0_pantallas.md`, a la espera de la revisión |
| P0.5 | Construcción por pantallas, cada una con su recorrido de Playwright y su captura de referencia (**15-11, #305: empieza ya, en paralelo con la Base**; pasos en §3 bis) | nube + PC | pruebas en verde, capturas sin cambios no queridos, la validación de `design/p0/validar_maqueta.py` sobre la aplicación real sin bajar nunca |
| P0.6 | Aceptación | PC | modelo de calidad: casillas de pantallas, usabilidad y aprendizaje ≥ umbral |

## 3 bis. Pasos de P0.5 (15-11, #305)

Cada paso termina con su recorrido de Playwright (el de `design/p0/recorrer_maqueta.py`, sobre la aplicación real con
datos de ejemplo), la validación de `validar_maqueta.py` (su cobertura nunca baja) y las pruebas en verde.

| Paso | Qué | Dónde |
|---|---|---|
| P0.5a | **Hecho (15-11 17:50).** **Esqueleto:** `ui/` (React + TypeScript + Vite + Tailwind), compilada a `src/tennisbio/app/p0/` (los estáticos van al repositorio: el PC no tiene Node); el contrato de datos tipado (`ui/src/contrato.ts`) y su adaptador en Python (`tennisbio.app.p0_datos`, de `design/p0/build_app.py`); datos de ejemplo sin nada real; el recorrido y la validación como prueba | nube |
| P0.5b | **Visor:** Lección (fases con su vídeo y sus capas en canvas: esqueleto, raqueta, bola), Sus golpes (galería ordenada) y el análisis de cada golpe (8 fotogramas, la bola y ella, bajar y subir, base, tronco, «Cuenta conmigo», avisos, estroboscópica, tira de contactos) | nube |
| P0.5c | **Más:** explorador de medidas (cambio 1 de `p0_diseno.md` §10), táctica y partido (2), resto (3), situaciones completas (4), comparar, pista, fiabilidad, vista lateral, datos, exportar | nube |
| P0.5d | **Gestión:** Inicio, Partidos (añadir: subida al volumen de Modal, el clic y la aprobación como trabajos de la cola), Personas, Cola, Calidad, Almacenamiento, Ajustes | nube |
| P0.5e | **En el PC:** la ventana (pywebview), la descarga de los resultados de Modal y la prueba de concepto de N (subir, descargar, borrar) | PC (con el usuario) |

**Punto de partida de la aplicación real (P0.5a, con los datos de la beta, validada como la maqueta):**

| Fuente | Maqueta | Aplicación (P0.5a) |
|---|---|---|
| Requisitos | 89 % | 47 % |
| Usabilidad | 94 % | 53 % |
| Patrones | 9 de 10 | 0 |
| Entrenadores | 11 de 17 | 6 de 17 |
| Ivanovic | 11 de 19 | 9 de 19 |
| Lista de 15 puntos (por su medida) | 33 de 59 | 45 de 59 |
| Taxonomía (por su medida) | 38 de 110 | 51 de 110 |

Sin errores y sin desbordes en escritorio. Las cifras de la lista y de la taxonomía ya suben: cada fase enseña todos sus
puntos de control. Lo demás llega con P0.5b-c: la lección, el panel del golpe y «Más». La aceptación de P0.5 pide
superar a la maqueta en todas las fuentes.

## 4. Métricas de aceptación (casillas del modelo de calidad que P0 debe llenar)
- **Usabilidad:** cada tarea principal (añadir un partido, señalar a la jugadora, ver «cómo pega la derecha» en una
  situación, ver un golpe en vídeo con sus medidas, comparar dos golpes, pausar la cola) en ≤ N clics y sin errores de
  página (Playwright); heurísticas de usabilidad revisadas por pantalla.
- **Rendimiento:** primera pantalla < 2 s, cambiar de pantalla < 300 ms, vídeo con capas a 30 fps (presupuestos medidos).
- **Accesibilidad y portabilidad:** 0 errores graves de axe-core; 1280 px y 390 px (móvil) sin desbordes.
- **Funcional:** cada petición de pantallas (#17, #33, #34…) con su comprobación.
- **Nada fijo en el código:** jugadores, golpes y partidos por configuración (#241, prueba existente).

## 5. Dependencias con la Base
- ~~La construcción (P0.5) espera a la Base cerrada~~ **15-11 (#305, decisión del usuario):** P0.5 se construye ya, en
  paralelo, mientras la Base espera horas de GPU; la aplicación actual sigue hasta que la nueva la sustituya (B7, #242,
  se valida con la actual).
- El orquestador (B8) ya es la base de la Cola de la aplicación nueva: no se rehace.
