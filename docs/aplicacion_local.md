# Aplicación local «Tennisbio»: diseño profesional (17-10)

**En qué se basa:**
- los requisitos vinculantes de `CLAUDE.md`;
- las decisiones del usuario: todo en el PC, nada en la nube, nada de pago, 100 % automático y no borrar nunca trabajo hecho;
- `docs/arquitectura_producto.md`, sección «Decisión del usuario»;
- `docs/diseno_definitivo.md`, la web, que se queda;
- las tres auditorías de `docs/auditoria_17_10/`;
- la comparativa con las apps profesionales (`docs/comparativa_apps.md`: Sportsbox, SwingVision, Hudl, OnForm, TennisViz y Hawk-Eye);
- lo aprendido de entrenadores en YouTube (`docs/aprendido_entrenadores.md` y los vídeos nuevos del usuario cuando estén);
- el código que ya existe: etapas, cachés, auditoría y ciclo.

**Regla:** la aplicación no vuelve a hacer el análisis. Envuelve lo que ya funciona (las etapas idempotentes, el informe, la auditoría y la comparación con la ejecución anterior) en un programa que el usuario abre, entiende y no tiene que vigilar.

## 1. Qué es, en una frase

Un programa del PC con ventana propia. Tú le das vídeos y él solo:
- analiza a cada jugadora y cada tipo de golpe;
- guarda los resultados ordenados;
- comprueba que están bien y te avisa si algo falla;
- te deja ver y aprender cada golpe en la web de siempre;
- prepara una copia para el móvil.

Lo que hoy hace Claude a mano (mirar registros, leer la auditoría, comparar con lo anterior, avisar) lo hace la aplicación.

## 2. Cómo se separa todo

Hay cinco objetos.

| Objeto | Qué es | Identidad | Ejemplo |
|---|---|---|---|
| **Vídeo** | El fichero de la retransmisión | Su contenido: tamaño más trozos muestreados (ya hecho, `video.json`) | `2023_AO_F.mp4` |
| **Partido** | Un vídeo con sus datos | Torneo, fecha, ronda y las dos jugadoras | AO 2023, final, Sabalenka – Rybakina, dura |
| **Jugadora** | Su ficha | Nombre, mano, revés a una o dos manos, altura | Rybakina: diestra, revés a dos manos, 1,84 m |
| **Golpe** | Cada impacto detectado | Partido + instante | Derecha, 2.º set 5-5 30-30, cercano |
| **Análisis** | Lo que se enseña | Jugadora × tipo de golpe | «Derecha de Rybakina», «Revés de Rybakina», «Saque de Sabalenka» |

**Cómo se reparte el trabajo, y por qué sale barato:**
- **Por vídeo, una vez:** la pasada barata (planos, audio, pista, marcador, jugadoras). Ya registra todos los impactos de las dos jugadoras.
- **Por partido y jugadora:** la identidad (quién es quién en cada momento) y la pasada fina con pose, bola y raqueta en sus golpes.
  - Analizar también a la rival reutiliza la pasada barata: unas 3 h, en vez de las 4,5 h de empezar de cero.
- **Por tipo de golpe, gratis:** la pasada fina ya clasifica cada golpe en derecha, revés o saque/remate (`stroke_analysis`, votación de varios indicios).
  - El revés y el saque de una jugadora ya analizada son solo otro informe: minutos.
  - Volea y media volea son una clase de contacto dentro del golpe (`contact_type`). Mientras haya pocos casos, salen como filtro dentro de derecha y revés; con suficientes, tendrán su propio análisis.
- **Agregados:** el informe de un análisis junta todos los partidos de esa jugadora y ese golpe. Se recalcula siempre, porque es barato.

**En disco, todo bajo `C:\tenis\` y sin YAML a mano:**
```
datos\tennisbio.db                 catálogo, cola, histórico, fichas (un fichero)
videos\<huella>.<ext>              el vídeo, con nombre estable
partidos\<partido>\                etapas del vídeo (pasada barata) + manifest + video.json
partidos\<partido>\<jugadora>\     pasada fina de esa jugadora: strokes.json, series\, ventanas y cachés
analisis\<jugadora>_<golpe>\       la web de ese análisis (index.html), su auditoría y sus capturas
copias\                            copias de seguridad (opcional, a un USB)
movil\<jugadora>_<golpe>\          la copia que funciona sin conexión para el teléfono
```
- La base de datos es un índice. Si se pierde, se reconstruye recorriendo las carpetas.
- `config/matches.yaml` y `players/*.yaml` pasan a exportarse desde ella, para que el código y los scripts actuales sigan funcionando.

## 3. La web HTML: se queda

La web actual es el visor de cada análisis y no se rehace:
- la lección;
- sus golpes;
- comparar;
- conclusiones;
- la vista lateral;
- fiabilidad.

La aplicación es la capa de alrededor: elegir qué análisis ver, lanzar trabajo y ver el estado. Al abrir un análisis, la aplicación muestra su web en la misma ventana, con un botón «‹ Volver a Tennisbio».

## 4. Pantallas de la aplicación

1. **Inicio**
   - Qué está pasando ahora: barra de progreso, etapa y hora a la que termina.
   - Lo último que ha terminado, con su semáforo de calidad.
   - Avisos que requieren algo de ti (casi nunca).
   - Accesos grandes a los análisis.
2. **Análisis**
   - Una tarjeta por jugadora y golpe: nombre, nº de golpes, partidos, fecha de la última actualización y semáforo de la auditoría.
   - Al pulsarla se abre su web.
   - Botón «Analizar también…» para añadir otra jugadora o golpe.
3. **Partidos**
   - Lista de partidos con su estado por etapa, en una línea de puntos con colores, y el espacio que ocupa cada uno.
   - Botón «Añadir partido»: arrastrar el vídeo o elegirlo.
   - Cada partido: sus datos, sus jugadoras, sus golpes por tipo y qué falta. Botones «Reanalizar» y «Archivar».
4. **Jugadoras**
   - Fichas: datos, foto (el fotograma más nítido suyo), partidos en los que sale, golpes analizados por tipo y botón «Analizar sus golpes».
5. **Cola**
   - Trabajos pendientes, en curso y hechos, cada uno con su porqué («partido nuevo», «cambió el cálculo de las medidas»).
   - Prioridad, pausar y reanudar.
   - Franja horaria opcional, por ejemplo solo de noche.
6. **Calidad**
   - El resultado de la auditoría de cada análisis: cumplidos, faltas, pocos datos.
   - Lo que empeoró respecto a la vez anterior, en rojo y con la explicación.
   - El historial de versiones.
7. **Almacenamiento**
   - Espacio por partido y por tipo: imprescindible, regenerable o temporal.
   - Qué se puede liberar sin perder nada y con qué botón.
   - Copia de seguridad a USB.
8. **Ajustes, pocos:**
   - carpetas;
   - franja horaria;
   - avisos;
   - copia al móvil;
   - modo «desarrollo», que sigue usando el ciclo con Claude.

## 5. Casos de uso: nominales, límite, esquina y error

Cada caso tiene su respuesta automática y su prueba. Ningún caso deja la aplicación colgada ni borra trabajo.

### 5.1 Nominales

| Caso | Qué hace el usuario | Qué hace la aplicación |
|---|---|---|
| Añadir un partido | Arrastra el vídeo | Lee duración, imágenes por segundo y si es entrelazado. Propone torneo, superficie y jugadoras (nombre del fichero y marcador por OCR). El usuario confirma con un clic, el trabajo se encola y aparece la hora a la que termina. |
| Ver un análisis | Pulsa la tarjeta | Abre la web en la lección. |
| Analizar a la rival | «Analizar también a Sabalenka» | Reutiliza la pasada barata y encola solo su pasada fina, unas 3 h. |
| Analizar el revés | «Analizar su revés» | Informe nuevo a partir de los mismos golpes, en minutos. |
| Mejora del cálculo de medidas (nueva versión) | Nada | Detecta qué etapas cambian, encola el recálculo desde las cachés y avisa: «Nueva versión: mejora X; recalcula 4 partidos ≈ 1 h 40 min esta noche». |
| Copia al móvil | «Copiar al móvil» | Hace la carpeta sin conexión (clips a 720p) y dice dónde está. |
| Fin de un trabajo | Nada | Pasa la auditoría y la compara con la vez anterior. Aviso de Windows: «Derecha de Rybakina actualizada: 336 ✔, 0 ✘». |

### 5.2 Límite

| Caso | Respuesta |
|---|---|
| Poco espacio en disco | Aviso por debajo de 40 GB. Por debajo de 20 GB libera solo lo regenerable (recortes y temporales) si el vídeo existe. No empieza un partido si no cabe (vídeo × 1,1 + 6 GB). |
| Partido muy largo (más de 4 h) o muy corto (menos de 20 min) | Lo acepta. Si es corto pregunta «¿es un resumen?», porque puede no ser la cámara principal. |
| Pocos golpes de una jugadora o un golpe | El análisis se hace y la web dice «provisional» y cuántos faltan. Nada inventado. |
| Jugadora sin altura | Usa 1,80 m (±5 %) y lo marca. La ficha pide la altura con un aviso. |
| Zurda | La ficha dice la mano. Las medidas se reflejan para que sean comparables (ya está en el código). |
| PC apagado o suspendido a mitad | Al volver reanuda donde se quedó: cachés por ventana y manifiesto. |
| Dos partidos a la vez | Cola: uno pesado cada vez en la iGPU; informes y auditoría en paralelo en la CPU. |

### 5.3 Esquina

| Caso | Respuesta |
|---|---|
| El mismo vídeo dos veces, o movido o copiado | Lo reconoce por su contenido. No duplica ni recalcula. |
| La misma final, de otra cadena o en otro idioma | Detecta mismo torneo, fecha y jugadoras, y pregunta cuál usar. |
| Partido de dobles | Se detecta (dos personas en la mitad cercana) y se excluye con su motivo. |
| La jugadora objetivo no sale en el vídeo | La identidad no la encuentra y el partido queda «sin la jugadora», con su motivo. No se analiza a otra persona. |
| Identidad dudosa (confianza baja, p. ej. 0,52) | Semáforo ámbar. El partido se analiza, pero entra en las comparativas solo si la confianza supera el umbral. |
| Vídeo entrelazado, con cortes o saltos | Se desentrelaza y se limpia (ya está en el código). |
| Repeticiones, planos de otras cámaras o publicidad | Se descartan (ya está). |
| Nombre de jugadora distinto en el marcador | La ficha guarda los alias que lee el OCR. |
| Cambio de modelo que obliga a recalcular todo | Plan con su coste antes de lanzarlo («≈ 13 h, 2 noches») y confirmación con un clic. |

### 5.4 Errores

| Error | Respuesta |
|---|---|
| Vídeo dañado, sin audio o sin pista | El partido queda «con aviso» y dice qué falta, en español. Sin reintentos inútiles. |
| Fallo de la iGPU (DirectML) | Reintenta 2 veces y después pasa a la CPU, más lento pero con el mismo resultado validado. |
| Falta de memoria | Libera memoria, baja el tamaño de los lotes y reintenta. |
| Disco lleno a mitad | Para el trabajo, libera lo regenerable y reanuda. Si no hay espacio, avisa. |
| Excepción del código | El trabajo queda en «error» con su explicación y un fichero de diagnóstico. Los demás siguen. El aviso dice «lo arregla una actualización». |
| Auditoría con regresión | En rojo en «Calidad», con qué empeoró. El análisis anterior se conserva hasta que el nuevo sea correcto (versiones). |
| Base de datos dañada | Se reconstruye desde las carpetas. |
| Navegador o motor de la ventana ausente | La web se abre en el navegador del sistema. |

## 6. Lanzamiento, monitorización, validación y distribución

- **Lanzar:** un acceso directo, «Tennisbio». La ventana se abre y la cola arranca sola. Hay un icono junto al reloj de Windows con el estado.
- **Monitorizar:**
  - el panel de Inicio y la Cola, con ritmos medidos en este PC para la hora de fin;
  - avisos de Windows al terminar, al fallar o con poco disco;
  - un histórico de cada ejecución: versión, tiempos, resultado y auditoría.
- **Validar:**
  - tras cada trabajo, la auditoría completa (≈ 400 comprobaciones de los requisitos, del diseño y del vídeo real) y la comparación con la vez anterior;
  - una versión nueva no sustituye a la anterior si empeora (se queda «pendiente de revisar»);
  - las pruebas del código (≈ 380) se pasan antes de cada versión.
- **Distribuir:** la copia al móvil (carpeta sin conexión) y la exportación PDF/MP4, que ya existe. Nada sale del PC por sí solo.
- **Actualizar:**
  - canal estable para el usuario y canal de desarrollo para Claude (el ciclo actual);
  - cada actualización dice qué mejora y qué recalcula, con su coste.

## 7. Qué se construye y en qué orden

1. **Núcleo (sin ventana):**
   - base de datos e importación del catálogo actual;
   - cola con reanudación;
   - trabajo por partido y jugadora;
   - auditoría y comparación al terminar;
   - todo probado con los casos de la sección 5.
2. **Ventana:** las 8 pantallas, servidas solo para el propio PC y sin puertos abiertos. La web de cada análisis se abre dentro.
3. **Avisos y almacenamiento:** avisos de Windows, guardián de disco y copia a USB.
4. **Copia al móvil e instalador** de un clic.

Cada parte se valida sola: pruebas con datos sintéticos de cada caso de la sección 5, más la ejecución real en el PC con su auditoría. El usuario solo prueba a usarla cuando cada parte cumple.

## 8. Lo que no hace (y lo dice)

- **No arregla su propio código:** detecta y explica; el arreglo llega con una actualización.
- **No mide lo que la tele no permite:** empuñadura, rpm, velocidad de bola, fuerzas.
- **No usa vídeos externos como datos de la jugadora** (requisito 6).

## 9. Estado (18-10): parte 1, núcleo, hecha

**Código:** `src/tennisbio/app/`.

| Módulo | Qué hace |
|---|---|
| `db` | El índice: SQLite en `C:\tenis\datos\tennisbio.db`. |
| `index` | Reconstrucción desde las carpetas, importación de `matches.yaml` y de las fichas, alta de jugadoras y alias. |
| `videos` | Añadir vídeo con sus preguntas. |
| `storage` | Disco: aviso, liberar lo regenerable y no empezar si no cabe. |
| `quality` | Versiones, auditoría y comparación, con la misma revisión que el ciclo automático. |
| `jobs` | Cola, reanudación y respuesta a cada error. |
| `engine` | Llama a las etapas, al informe y a la auditoría de siempre. |
| `core` | Lo que llaman la ventana y la línea de órdenes. |

**Órdenes:** `tennisbio app status | add | also | plan | work | pausa | seguir | franja | rebuild`.

**Pruebas:** `tests/test_app_core.py`, con 31 casos de la sección 5. Todos pasan, con un motor falso que falla a voluntad.

**Motor real:** probado con datos sintéticos. Hace el informe, la auditoría con capturas (≈ 5 min) y publica la versión 1 con su revisión.

**En el PC:** la petición «app» crea el índice con sus datos reales y dice qué recalcularía. No ejecuta la cola.

**Diferencias con el diseño (decididas al construir):**
- **Carpetas:** se quedan donde las escribe hoy el análisis (`output\<partido>`). La base de datos es un índice y no hace falta mover nada. Solo es nueva `output\analisis\<jugadora>_<golpe>\` (`actual`, `v1…`, `pendiente`).
- **Informes y auditorías:** van antes que los trabajos pesados por prioridad, pero no a la vez. Es un solo proceso; el trabajo en paralelo en la CPU llega con la ventana (parte 2).
- **Pendiente para las partes 2-4:**
  - la ventana;
  - los avisos de Windows (hoy son avisos en el índice);
  - la copia a USB;
  - la copia al móvil;
  - el instalador;
  - el caso «navegador ausente», que es de la ventana.

## 10. Estado (18-10): parte 2, la ventana

**Código:**

| Fichero | Qué hace |
|---|---|
| `src/tennisbio/app/ui.html` | El diseño de la maqueta validada: estilos, iconos y menú. Las pantallas las genera el código con el índice real. |
| `state.py` | Lo que pinta cada pantalla, en una sola lectura. |
| `window.py` | La ventana WebView2 con `pywebview`, la cola en un hilo y el navegador si falta el motor. |
| `check.py` | La comprobación de todas las pantallas. |

**Abrirla:** doble clic en `Tennisbio.vbs` (sin consola) o `tennisbio app ventana`.

**Instalación:** el extra `app` (`pywebview`) se instala con el instalador y en cada ciclo del PC.

**Pruebas** (`tests/test_app_window.py`):
- todas las pantallas con los casos de la sección 5 (dobles, error, regresión, plan pendiente, poco disco, zurda sin altura), a 1280 y en el móvil, sin errores ni desplazamiento lateral;
- los botones conectados al `Api` real cambian el índice: pausar, reintentar, confirmar el plan, analizar también, añadir partido y archivar;
- la web del análisis se abre dentro, con «Volver»;
- la vista de solo lectura no cambia nada;
- sin el motor de la ventana, se abre en el navegador.

**En el PC:** la petición «ventana» pinta las pantallas con el índice real y sube las capturas a `pc-logs:capturas_app`. También abre la ventana real oculta, sin que el usuario la vea, y prueba su puente con el núcleo.

**Diferencias con la maqueta:**
- **Añadir partido:** se elige el vídeo con el diálogo de Windows; WebView2 no da la ruta de un fichero arrastrado.
- **Pendiente para la parte 3:**
  - los avisos de Windows;
  - el icono junto al reloj;
  - la copia a USB.
- **Pendiente para la parte 4:**
  - la copia al móvil;
  - el acceso directo en el escritorio.
- **Hasta entonces,** esas pantallas lo dicen en lugar de enseñar botones que no hacen nada.

## 11. Estado (18-10): parte 3, avisos, icono, disco y copia

**Avisos de Windows** (`app/notify.py`):
- Los hace el propio Windows (WinRT a través de su PowerShell), sin instalar nada y sin abrir consola.
- Cada aviso del índice sale una sola vez, y otra solo si cambia su texto.
- En Ajustes se eligen: al terminar, al fallar y con poco disco.

**Icono junto al reloj** (`pystray`, gratis):
- Su menú: abrir la ventana, pausar o reanudar la cola, salir.
- Su etiqueta dice qué hace y a qué hora termina.
- Cerrar la ventana la esconde y la cola sigue trabajando. Solo «Salir» la para; el trabajo en curso sigue al volver.
- Un segundo doble clic no arranca otra cola: avisa de que ya está abierto.

**Disco:** el guardián corre antes de cada trabajo en el bucle de la cola (aviso por debajo de 40 GB, liberación de lo regenerable por debajo de 20 GB). Sus avisos llegan también como avisos de Windows.

**Copia a USB** (`app/backup.py`, pantalla Almacenamiento):
- **Qué copia:** a `<USB>\tennisbio_copia\` van el índice, las fichas, el catálogo, cada partido (resultados, cachés y recortes) y los análisis en uso.
- **Los vídeos:** solo si se marca la casilla.
- **Cómo:** es incremental, comprueba que cabe antes de empezar y nunca borra nada, ni en el PC ni en el USB.

**Pruebas:** `tests/test_app_extras.py`.

**En el PC:** la petición «ventana» comprueba, sin enseñar nada, que Windows puede crear el aviso, que el icono se puede crear y qué copiaría la copia.

## 12. Estado (18-10): parte 4, copia al móvil y acceso directo

**Copia al móvil** (`app/mobile.py`; en la ventana, pantalla Análisis, «Copiar al móvil»):
- **Dónde:** `C:\tenis\movil\<jugadora>_<golpe>\` y el mismo contenido en un `.zip` al lado, para llevarlo al teléfono por cable, USB o tarjeta. Nada sale del PC por sí solo.
- **Qué lleva:**
  - la web en uso (`actual`), la misma página;
  - el vídeo de cada golpe convertido a 720p (H.264 y AAC, se reproduce mientras carga);
  - las series del esqueleto, las fotos, la vista lateral de entrenamiento y el resumen PDF.
  - Todas las rutas son relativas a la carpeta.
- **El esqueleto sigue cuadrando:** la página dibuja en los píxeles del vídeo original y solo escala la imagen (`vk` por golpe en `report_template.html`). Las medidas no cambian.
- **Una segunda vez:** solo convierte lo que cambió y quita de la copia lo que ya no está en el análisis. Un golpe cuyo clip falta sale «sin vídeo», nunca con un enlace roto.
- **Sin espacio, o sin análisis publicado:** no empieza y lo dice.
- **Al terminar:** avisa de dónde está la copia y de cuántos golpes llevan vídeo.

**Acceso directo «Tennisbio» en el escritorio** (`app/shortcut.py`):
- **Qué abre:** `Tennisbio.vbs` a través de wscript, sin consola, con el icono «TB».
- **Quién lo crea:**
  - el instalador (`1_instalar.bat`);
  - el ciclo del PC, si falta. No hay que reinstalar nada.

**Pruebas:** `tests/test_app_mobile.py`.
- La copia completa, a 720p y con su `.zip`.
- Una segunda copia, cuando falta un clip y cuando una conversión falla.
- Sin espacio.
- La prueba en un navegador real a tamaño de móvil: el punto de la muñeca cae sobre la jugadora en el clip a 720p y, sin el factor de escala, no cae.
- El botón de la ventana.
- El icono y el guion del acceso directo.

**En el PC:** la petición «movil» (`tennisbio app comprobar-movil`):
- hace la copia de cada análisis real y la abre en el navegador del PC a tamaño de móvil;
- compara el golpe dibujado desde la copia con el de la web del PC;
- crea el acceso directo.

## 13. Carpetas: qué va dónde

```
C:\tenis\
  videos\                     los vídeos de entrada, como quieras (subcarpetas incluidas)
  output\
    <partido>\                un partido: etapas, golpes, cachés, recortes (lo escribe el análisis)
    analisis\<jugadora>_<golpe>\
        actual\               la web en uso (index.html) y su auditoría
        v1, v2…\              versiones anteriores (las dos últimas se guardan)
        pendiente\            una versión que empeoró, a la espera
    _smoke\, _poc9_largo\     pruebas del ciclo automático (las mantiene el ciclo)
  movil\<jugadora>_<golpe>\    la copia para el teléfono (y su .zip al lado)
  datos\
    tennisbio.db              el índice (se reconstruye solo desde las carpetas)
    diagnostico\              ficheros de los errores
  tennis-biomech\             el programa
    config\players\*.yaml     las fichas de las jugadoras
```

**Los vídeos no se ordenan por jugadora.** Un partido tiene dos jugadoras: la final Sabalenka – Rybakina sirve para el análisis de las dos. Si el vídeo estuviera en `elena_rybakina\`, el de Sabalenka no estaría en su carpeta, y copiarlo duplicaría 5 GB. La relación vídeo → partido → jugadoras la guarda el índice.

**Si quieres orden, ordénalos por torneo o por año.** Por ejemplo `videos\2023\AO_final_Sabalenka_Rybakina.mkv`. La aplicación los encuentra en subcarpetas y los reconoce por su contenido: moverlos o renombrarlos no recalcula nada.

**Las salidas y las fichas no se tocan a mano:**
- cada partido tiene su carpeta y cada análisis la suya;
- la ficha de una jugadora la crea y la edita la aplicación (pantalla Jugadoras);
- la base de datos es solo un índice: si se pierde, se rehace.
