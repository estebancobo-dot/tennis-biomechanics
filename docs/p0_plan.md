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

## 2. Arquitectura propuesta (estado del arte para una aplicación local, sin nube ni pago)
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
| P0.3 | Comparativa catalogada (#257): `config/referencias.yaml` y `docs/comparativa_completa.md`; cada hueco → petición | nube (web) + PC (fotogramas de YouTube) | cada referencia con sus casillas puntuadas |
| P0.4 | Diseño: mapa de pantallas (unión de aplicación + informe, sin duplicados, lo que sobra fuera), recorridos de tareas, sistema de diseño, maqueta interactiva | nube | **una revisión del usuario** del prototipo (no de datos) |
| P0.5 | Construcción por pantallas, cada una con su recorrido de Playwright y su captura de referencia | nube + PC | pruebas en verde, capturas sin cambios no queridos |
| P0.6 | Aceptación | PC | modelo de calidad: casillas de pantallas, usabilidad y aprendizaje ≥ umbral |

## 4. Métricas de aceptación (casillas del modelo de calidad que P0 debe llenar)
- **Usabilidad:** cada tarea principal (añadir un partido, señalar a la jugadora, ver «cómo pega la derecha» en una
  situación, ver un golpe en vídeo con sus medidas, comparar dos golpes, pausar la cola) en ≤ N clics y sin errores de
  página (Playwright); heurísticas de usabilidad revisadas por pantalla.
- **Rendimiento:** primera pantalla < 2 s, cambiar de pantalla < 300 ms, vídeo con capas a 30 fps (presupuestos medidos).
- **Accesibilidad y portabilidad:** 0 errores graves de axe-core; 1280 px y 390 px (móvil) sin desbordes.
- **Funcional:** cada petición de pantallas (#17, #33, #34…) con su comprobación.
- **Nada fijo en el código:** jugadores, golpes y partidos por configuración (#241, prueba existente).

## 5. Dependencias con la Base
- La construcción (P0.5) espera a la Base cerrada: B7 (#242) todavía se valida con la aplicación actual.
- El orquestador (B8) ya es la base de la Cola de la aplicación nueva: no se rehace.
