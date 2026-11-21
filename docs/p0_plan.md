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
| P0.5b | **Hecho salvo el reproductor (15-11 19:40).** **Visor:** Lección (fases con su vídeo y sus capas en canvas: esqueleto, raqueta, bola), Sus golpes (galería ordenada) y el análisis de cada golpe (8 fotogramas, la bola y ella, bajar y subir, base, tronco, «Cuenta conmigo», avisos, estroboscópica, tira de contactos) | nube |
| P0.5c | **Hecho en lo que dan los datos (15-11 19:40): Táctica con dirección, profundidad, dentro o fuera, presión y cambios de dirección. 22:08: el explorador de medidas (cambio 1). 22:17: la táctica por puntos (cambio 2: largo del punto, errores por golpe, secuencias, el punto en mini-mapa). 22:27: el resto (cambio 3) y el «por qué importa» de cada medida con su fuente.** **Más:** explorador de medidas (cambio 1 de `p0_diseno.md` §10), táctica y partido (2), resto (3), situaciones completas (4), comparar, pista, fiabilidad, vista lateral, datos, exportar | nube |
| P0.5d | **Hecho en la nube (15-11 21:57; diseño y estado en §3 ter).** **Gestión:** Inicio, Partidos (añadir: subida al volumen de Modal, el clic y la aprobación como trabajos de la cola), Personas, Cola, Calidad, Almacenamiento, Ajustes | nube |
| P0.5e | **Primera parte lista (15-11 23:45): `6_aplicacion_nueva.bat`** abre la aplicación nueva en una ventana del PC (`tennisbio.app.p0_ventana`, pywebview como la actual) con los datos del último informe y auditoría del PC (o los de ejemplo, dicho en pantalla), el estado de la cola desde el volumen de Modal y la gestión conectada (clave de `5_conectar_nube.bat`; sin ella, cada botón lo dice); su registro sube solo a `pc-logs` (`aplicacion_nueva.log`). **21-11 (el usuario: «sí»):** la descarga de los resultados de la nube, hecha: el informe y la auditoría se hacen en la nube (también en una sesión de CPU de Kaggle, `correr.report`; en cola `informe_beta2`), que deja la lista de sus ficheros (`/output/resultados_app.json`); la aplicación baja solo lo que cambió al abrirse y con «Traer resultados de la nube» en Inicio (`tennisbio.app.p0_nube`), los muestra antes que el informe del PC y dice de dónde salen. **21-11, D:** el vídeo real de cada golpe con sus capas en el análisis del golpe (`ui/src/pantallas/Reproductor.tsx`: cuerpo, raqueta, bola y dos medidas, dibujados con la serie fotograma a fotograma como el informe; velocidades, fotograma a fotograma, impacto y pantalla completa), probado en el navegador; con los resultados reales lo comprueba `medir_app` en una sesión de CPU de Kaggle (Chrome, H.264), con su regla escrita antes y solo números fuera de la sesión. **21-11 08:45, `medir_app` pasa:** con los resultados reales traídos como los trae el PC (el informe de la nube de los 5 partidos: 387 golpes del lado cercano, los 387 con su vídeo), Chrome abrió los 24 primeros golpes de la galería: los 24 con su vídeo (1920 px) y el cuerpo dibujado en sus puntos en el impacto, sin errores de la página. **Falta:** probarlo con el usuario en el PC. **En el PC:** la ventana (pywebview), la descarga de los resultados de Modal y la prueba de concepto de N (subir, descargar, borrar) | PC (con el usuario) |

**La aplicación real frente a la maqueta** (los datos de la beta; validación de `design/p0/validar_maqueta.py`, que
desde el 15-11 exige un vídeo o un dibujo de verdad en pantalla para el vídeo con capas, la estroboscópica y la tira):

| Fuente | Maqueta | P0.5a | P0.5c (15-11 19:40) | 15-11 22:35 (cambios 1-3 y 9, fuentes) |
|---|---|---|---|---|
| Requisitos | 89 % | 47 % | **96 %** | 96 % |
| Usabilidad | 94 % | 53 % | **100 %** | 100 % |
| Patrones | 9 de 10 | 0 | 9 de 10 | 9 de 10 |
| Entrenadores | 65 % | 35 % | **82 %** | **88 %** |
| Ivanovic | 58 % | 47 % | **79 %** | **89 %** |
| Lista de 15 puntos (por su medida) | 56 % | 76 % | **78 %** | 78 % |
| Taxonomía (por su medida) | 35 % | 46 % | **52 %** | **56 %** (cambio 9) |

La lista de 15 puntos y la taxonomía no suben con pantallas: lo que les falta son medidas que el análisis aún no calcula (paquetes M). Sin errores ni desbordes en escritorio. Lo que falta en las dos es lo mismo: el vídeo real con sus capas, la
estroboscópica y la tira de contactos, que necesitan los fotogramas del PC (P0.5e). Después, el resto de la taxonomía
(cambio 1, explorador) y de la táctica (cambio 2: secuencias, peloteo, el punto con mini-mapa, la recuperación).

## 3 ter. P0.5d: la gestión de verdad (diseño, 15-11 21:40)

Lo que el usuario hace en la aplicación (#301: sube el vídeo desde el PC, hace el clic, aprueba y ve los resultados en el
PC) pasa por **la misma cola** que los trabajos de Claude (`config/cola_nube.yaml`, `cloud/cola.py`): una sola cola, un
solo estado (`nube-logs:cola/estado.md` y `/cola/` del volumen), los mismos topes (0 €). Nada nuevo que vigilar.

**El canal: peticiones en el volumen.** La aplicación no toca el repositorio (el PC no hace subidas al código: chocarían
con las de Claude). Cada acción del usuario es un fichero propio en el volumen de Modal, `/app/peticiones/<fecha>_<tipo>_<partido>.json`,
escrito por el puerto de almacenamiento (`tennisbio.infra.storage`; en el PC, su adaptador de Modal con la clave de
`5_conectar_nube.bat`). Nunca se sobrescribe ni se borra (es el registro de lo que pidió y cuándo, como las revisiones).
La cola los lee en cada vuelta (cada 30 min) y los convierte en trabajos con los campos que ya existen.

| Petición | Qué escribe la aplicación | Qué hace la cola |
|---|---|---|
| `alta` | el vídeo en `/videos/` y su ficha en `/biblioteca/<partido>/partido.json` (jugadoras, torneo, fecha, superficie, ronda) | `app_prueba_<partido>` (10 min) y después `app_preparar_<partido>`: la pasada barata hasta `identity` en una sesión de **CPU** (no gasta horas de GPU) y las dos fotos de «¿Cuál es ella?» |
| `clic` | `/biblioteca/<partido>/etapas/identidad_clic.json` (el mismo fichero que hoy) | nada que lanzar: el partido queda «listo para aprobar» |
| `aprobar` | la aprobación con lo que se le enseñó (horas y coste previstos) | por partes (T24, adoptado el 15-11): `app_fina_<partido>` (la pasada fina, en GPU) y `app_<partido>` (vistas y recortes, en CPU), con `aprobado: true`, tras la preparación y con el clic; #262: solo con este botón o con `aprobado: true` de Claude tras el visto bueno del usuario en el chat |
| `pausar` / `reanudar` | — | en pausa no lanza nada nuevo (lo que corre termina); el estado lo dice con la hora |
| `cancelar` | el trabajo | el mismo camino que la cancelación de Claude (se registra el motivo «desde la aplicación») |
| `borrar_video` | — | borra el vídeo del volumen **solo** si el partido está analizado y la aplicación confirmó la descarga de sus resultados (CLAUDE.md, requisito 10: «se borran al terminar»); si no, lo rechaza con el motivo |
| `persona` | su ficha (`name`, `hand`, `backhand`, `height_m`) en `/biblioteca/personas/<id>.json` | el catálogo de la nube la junta con `config/players/` (la del repositorio manda si están las dos) |

**Reglas.** Los ids de la aplicación llevan `app_` (nunca chocan con los de Claude); `check_queue` valida las dos fuentes
igual; una petición mal formada se queda en el estado con su motivo (no para la cola). La aplicación lee el estado de
`/cola/` del volumen (no del repositorio) y enseña en cada partido en qué paso está y qué falta («falta el clic», «falta
tu aprobación», «en cola: sin horas de GPU hasta el sábado»).

**Construido (15-11 21:57, nube, sin el PC; 1-5 hechos con sus pruebas):** (1) el puerto de almacenamiento con `list` y `delete` (y su contrato
en los dos adaptadores); (2) `tennisbio.infra.peticiones`: de las peticiones a trabajos y a la pausa, funciones puras con sus
pruebas, y su lectura en cada vuelta de `cloud/cola.py`; (3) las fotos del clic en la nube tras la preparación;
(4) `tennisbio.app.p0_api`: lo que llama la ventana (subir, clic, aprobar, pausar, cancelar, borrar, estado), probado con
el adaptador local; (5) los botones de Gestión llamándolo (`ui/src/api.ts` y `p0_api.ApiVentana`, con los mismos nombres, comprobado; en
el navegador, sin la ventana, salen desactivados con «Se hace en la aplicación del PC»). Las fotos del clic se hacen en
Kaggle tras la parte con `identity` (`nube.CLICK_PHOTOS`, el código del PC). Las horas que se enseñan son solo las
medidas (prueba de 10 min 0,45 h; partido 5-6,5 h): lo que gasta aparte la pasada hasta el clic no está medido aún y no
se pone. **15-11 22:51:** el alta lleva el id de la ficha de la jugadora (`config/players/<id>.yaml`, buscada por su nombre;
el catálogo de la nube carga la ficha por id) y la cola rechaza, con su motivo, un partido de alguien sin ficha; una
persona añadida en la aplicación va a `/app/personas.json` y cada sesión de la nube la convierte en su ficha
(`nube.write_app_players`, nunca encima de una del repositorio). **En el PC (P0.5e, con el usuario):** la ventana, la clave de Modal y la primera subida de verdad.

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
