# P0 · Diseño completo de la aplicación de escritorio (P0.4 rehecho, 15-11, #252, #301, #302)

**De dónde sale (nada inventado):**
- `docs/p0_inventario.md`: las 301 peticiones por función y lo que ya existe;
- `docs/aplicacion_local.md` (17-10): los objetos, las 8 pantallas de gestión, el flujo y los casos;
- `docs/diseno_definitivo.md` (17-10): el visor de un análisis en 3 entradas y sus 15 criterios;
- `docs/p0_estado_del_arte.md`: los patrones leídos en las fuentes oficiales;
- #301: aplicación de escritorio del PC, sin web ni móvil; análisis en la nube.

Cada pantalla dice qué peticiones cubre. **Nada se borra:** todo lo de hoy sigue accesible (#53, #67).

## 1. Principios

1. **Genérica:** jugadora o jugador, golpe y partido se eligen del catálogo. Ninguna pantalla nombra a nadie por
   código (#241). Hombres y mujeres igual (#242).
2. **Vídeo primero** y **cada número abre sus golpes**, como la matriz de Sportscode (#9, #42).
3. **Fiabilidad siempre a la vista:**
   - fiable, media, estimada o «no medible desde la tele»;
   - las diferencias solo si superan el error (requisito 3, #59).
4. **Aprender con pocas cosas:** ≤ 3 claves por fase, un foco externo y un ejercicio «N de 10»
   (`diseno_definitivo.md`, auditoría 3).
5. **100 % automático:** el usuario solo sube el vídeo, hace el clic de identidad y aprueba (requisito 5).
6. **Escritorio:** de 1280 a 1920 px de ancho, mínimo 1024. Navegación a la izquierda, zona central y panel lateral
   para el detalle.

## 2. Los objetos (los de `aplicacion_local.md`, más el torneo)

| Objeto | Qué es | Se identifica por |
|---|---|---|
| Vídeo | El fichero de la retransmisión | Su contenido; renombrarlo no rompe nada (#229) |
| Partido | Un vídeo con sus datos: torneo, ronda, fecha, superficie, las dos personas | Su vídeo |
| Torneo | Nombre, categoría, superficie, fechas | Ficha pública (#258) |
| Persona | Jugadora o jugador: nombre, mano, revés, altura, foto, alias del marcador | Ficha (#258, #156) |
| Golpe | Cada impacto de una persona: partido, instante, tipo, lado, situación | Partido + instante |
| Análisis | Persona × tipo de golpe, con todos sus partidos | «Derecha de Rybakina», «Saque de Sinner» |

## 3. Navegación

Una columna a la izquierda, en tres grupos:

```
VER         Inicio · Análisis
GESTIONAR   Partidos · Personas
SISTEMA     Cola · Calidad · Almacenamiento · Ajustes
```

Al abrir un análisis, la zona central pasa al **visor del análisis**, con sus 3 entradas (Lección, Sus golpes, Más) y
«‹ Análisis» para volver. Es lo de `diseno_definitivo.md`.

## 4. Pantallas de gestión

### 4.1 Inicio (#50, #10, #262, #291)
- **Ahora:** qué trabajo corre en la nube, partido, etapa, % y hora estimada de fin. Varios a la vez si los hay.
- **Necesita algo de ti:** la casi única interacción del usuario.
  - un clic de identidad pendiente;
  - una aprobación con el tiempo y la cuota previstos.
- **Lo último terminado:** cada análisis actualizado, con su semáforo de calidad y «qué cambió».
- **Tus análisis:** accesos grandes a los análisis, con su número de golpes y de partidos.

### 4.2 Análisis (#242, #161, #32, #130)
- **Una tarjeta por análisis** (persona × golpe): nombre, golpes (cercanos y lejanos), partidos, última actualización
  y semáforo de la auditoría.
- **Filtros:** persona, golpe y estado.
- **«Analizar también…»:**
  - otra persona de un partido ya subido: reutiliza la pasada barata, unas 3 h;
  - otro golpe de una persona ya analizada: minutos.
  - Los golpes sin casos suficientes salen con su número: «Volea: 6 golpes, se enseña con ≥ 12».

### 4.3 Partidos (#226, #245, #258, #229, #218, #219)
- **Lista:** torneo, ronda, fecha, superficie, las dos personas con su foto, duración, estado por etapa (línea de
  puntos) y golpes por persona y tipo.
  - Filtros: persona, torneo, superficie, año y estado.
- **Ficha del partido:**
  - datos y fuente de cada dato;
  - las dos personas, con «Analizar a…»;
  - golpes por tipo y lado;
  - marcador leído (sets);
  - fallos por niveles (#265);
  - acciones: «Reanalizar con la versión nueva», «Cambiar el clic de identidad» (escenario ✘ hoy) y «Archivar».
- **Añadir partidos** (flujo de la sección 6.1).

### 4.4 Personas (#156, #258, #242, escenarios)
- **Lista con foto:** el fotograma más nítido suyo de sus partidos.
- **Ficha:** nombre, alias del marcador, mano, revés, altura (y su fuente), partidos en los que sale, golpes por tipo
  y lado, análisis hechos y «Analizar sus golpes».
- **Persona nueva:** se crea sola desde el partido (nombre del marcador y ficha pública); el usuario solo confirma. Si
  falta la altura, se usa 1,80 m y se marca.

### 4.5 Cola (#246, #249, #262, #301, #284)
- **La cola de la nube:**
  - en curso, con su progreso en vivo;
  - pendientes, con su porqué («partido nuevo», «versión nueva de las medidas»);
  - hechos y con error, con su explicación.
- **Acciones:** pausar, parar y relanzar.
- **Cuota:** horas de Kaggle de la semana y crédito de Modal del mes, con su tope.
- **Descarga de resultados al PC:** qué falta por bajar.

### 4.6 Calidad (#256, #11, #118, #238, #264, #265)
- **Modelo de calidad:**
  - la puntuación;
  - las casillas por dominio, característica y capa;
  - lo que no está medido, con cómo se medirá.
- **Auditoría por análisis:** cumplidas, faltas y pocos datos.
- **Qué empeoró** respecto a la versión anterior, en rojo y con su explicación.
- **Historial de versiones:** qué mejoró y qué se recalculó.
- **Fiabilidad de las medidas:** la pantalla de hoy, que se queda.

### 4.7 Almacenamiento (#220, `arquitectura_producto.md` §6)
- Espacio en el PC por partido y por clase: imprescindible, regenerable o temporal.
- Qué se puede liberar sin perder nada.
- Los vídeos en la nube, que se borran al aceptar el partido (T22).
- Copia de seguridad.

### 4.8 Ajustes (pocos: el resto es automático)
- Carpetas del PC.
- Avisos de Windows.
- Claves de Modal y GitHub: si están puestas, nunca su valor.
- La altura del usuario, para traducir a sus centímetros (#126).

## 5. El visor de un análisis (lo de `diseno_definitivo.md`, con la forma nueva)

**Cabecera:**
- «Derecha de Elena Rybakina · 387 golpes cercanos en 5 partidos · todas las situaciones [Cambiar ▾]»;
- 6 atajos de situación: rápida, lenta, alta, baja, en carrera, abierta.
- [Cambiar] abre el selector completo, en filas por eje (las 2000 y pico combinaciones, #70), con el recuento de cada
  nivel. Una combinación con pocos golpes lo dice y no inventa nada.

### 5.1 Lección (entrada; #4, #17, #68-#72, #110, #111, #123, #126-#128, #189, #194, #195, #213, #215)
1. **Tira de fases 1-8 + Pies,** cada una con la miniatura real del golpe más representativo. Las 3 del plan llevan
   «empieza por aquí».
2. **El vídeo en bucle de la fase:**
   - la mitad del ancho o más, a 1/4 y a velocidad real;
   - su marca dibujada encima: línea, ángulo o base;
   - «otro golpe suyo» y «el golpe entero».
3. **Foco:** una frase de foco externo o analogía, sin cifras. Si la regla general de los entrenadores no es lo que
   hace ella, se dice.
4. **≤ 3 claves:**
   - nombre;
   - su valor en tus unidades, con el número de golpes;
   - una línea de «Cómo»;
   - la fiabilidad;
   - «cambia con la bola» solo si supera el error.
5. **Cuerdas en cada fase** (#8): hacia dónde miran y en qué %; en el impacto, «estimación».
6. **Practica:** un ejercicio con criterio «8 de 10» y el botón «Conseguido» (se guarda en el PC). Los demás, plegados.
7. **‹ Fase anterior · Fase siguiente ›**
8. **Plegado:**
   - Lo que la distingue;
   - Su ritmo y su cadena cinética;
   - Qué cambia según la bola;
   - Tu plan completo;
   - Si te pasa…;
   - Lo que la tele no mide (empuñadura, #7);
   - Todas las medidas;
   - Glosario;
   - Fuentes.

**Forma de cada clave (de los shorts de Joel Myers, `aprendido_entrenadores.md` §5):**
- **un vídeo:** su fase en bucle, a velocidad real y lenta;
- **un dibujo automático:** el que sale de la medida;
- **una frase:** con la palabra clave en color;
- **el problema que resuelve.**

Contrastes con sus propios golpes, lado a lado. «Cuenta conmigo»: un punto desde la cámara de la tele con cada apoyo
marcado.

### 5.2 Sus golpes (#33, #42, #65, #114-#117, #120, #121, #162, #55)
- **Videoteca:** cuadrícula con avance al pasar el ratón.
  - Títulos legibles: «Frente a Osaka · 2.º set 5-5 30-30 · rápida, corta · abierto».
  - Filtros: situación (la misma de la cabecera), partido, set, resultado, presión y lado.
  - Órdenes: captura, representatividad, resultado y tiempo (#162).
  - «Reproducir todos» como lista de reproducción ordenable (patrón de Sportscode).
- **Análisis de un golpe:**
  1. **Reproductor:**
     - velocidad real, 1/2, 1/4 y 1/8, fotograma a fotograma, pantalla completa;
     - capas una a una: cuerpo, raqueta, bola, medidas.
  2. **Línea de tiempo con las 8 fases** y sus miniaturas; un clic lleva a cada fase.
  3. **La bola y ella**, Bajar y subir, Base y Tronco al terminar: fotogramas reales y medidas (#114-#117).
  4. **Plegado:** su cuerpo, sus pies (huellas numeradas, #236), métricas frente a lo habitual (solo si supera el
     error), gráficas, raqueta por fase y recorrido del brazo.
  5. **El punto:** sus otros golpes de ese punto, golpe a golpe (patrón de SwingVision), con el marcador.

### 5.3 Más
- **Comparar** (#59, escenario de comparar jugadores):
  - dos golpes lado a lado, uno encima de otro o superpuestos con transparencia, sincronizados en el impacto y con el
    avance enlazado (Kinovea, OnForm);
  - las frases de lo que cambia a la vista y la tabla plegada.
  - Más adelante, dos análisis del mismo golpe (dos personas).
- **Conclusiones** (#27):
  - a la vista, solo las diferencias reales, con su ajuste por la bola y el partido;
  - por partido y set, fatiga, presión, ganadores y errores;
  - lo no concluyente, plegado.
- **Comparar situaciones:** una matriz situación × clase (apoyo, terminación, resultado). Cada celda, con su número y
  sus golpes (patrón de Sportscode).
- **Pista** (#38, #135): dónde golpea y adónde va la bola, con filtros.
- **Tabla de golpes y Explorador:** como hoy.
- **Vista lateral (entreno):** aparte y marcada (requisito 6, #79).
- **Fiabilidad y Datos:** como hoy.
- **Exportar** (#41, #46): PDF corto y MP4 de los golpes o de una lista.

## 6. Flujos

### 6.1 Añadir partidos (#242, #258, #222, #301)
1. **«Añadir partidos»:** se eligen o se arrastran uno o varios vídeos del disco.
2. **Propuesta por vídeo:**
   - se leen la duración, las imágenes por segundo y si es entrelazado;
   - se proponen el torneo, la ronda, la fecha, la superficie y las dos personas, sacados del nombre del fichero, la
     ficha pública y el marcador, con la fuente de cada dato.
   - El usuario corrige solo si algo está mal.
3. **Subida a la nube** por partes y reanudable, con su progreso. El vídeo se queda en el PC para verlo.
4. **Prueba corta automática** de 10 min en la nube.
5. **El clic de identidad:** la aplicación enseña las dos personas con su foto (sacadas del propio vídeo) y un clic en
   la que se quiere analizar.
6. **Aprobar:** el tiempo y la cuota previstos, frente a lo que queda esta semana → [Aprobar]. La previsión sale de lo
   medido: Gauff usó 5,0 h de Kaggle y la final 6,5 h.
7. **Al terminar:** aviso de Windows; los resultados se descargan solos al PC; Inicio dice qué cambió.

### 6.2 Ver cómo pega en una situación (≤ 2 clics)
Inicio → el análisis → la situación → la fase.

### 6.3 Ver un golpe en vídeo con sus medidas (1-2 clics)
Cualquier número o conclusión → sus golpes → el golpe.

### 6.4 Analizar también a la rival u otro golpe (2 clics)
Ficha del partido o de la persona → «Analizar…» → [Aprobar].

### 6.5 Casos límite, esquina y error
Los de `aplicacion_local.md` §5.2-5.4: disco, dobles, dañados, misma final de dos cadenas, identidad dudosa, versión
nueva. Cada uno tiene su estado visible en la ficha del partido.

## 7. Sistema de diseño

- **Color:**
  - azul de pista dura como acento;
  - neutros con un leve sesgo azul;
  - el amarillo de bola solo para el impacto;
  - estados: bien, aviso y mal;
  - fiabilidad: fiable, media, estimada y no medible;
  - modo claro y oscuro.
- **Letra:**
  - Barlow Condensed para títulos y cifras grandes (estilo de los rótulos de la tele);
  - Inter para el texto;
  - cifras tabulares.
- **Componentes:**
  - navegación lateral y cabecera de análisis con la situación;
  - tarjeta de análisis y fila de partido con fotos;
  - ficha de persona;
  - tira de fases con miniaturas y reproductor con capas;
  - clave (valor, rango, fiabilidad, cómo);
  - matriz con celdas que abren golpes;
  - comparador de dos vídeos;
  - progreso de un trabajo;
  - semáforo de calidad;
  - diálogo de aprobación con tiempo y cuota.
- **Gráficos** (ECharts):
  - pocos y con su lectura en una frase;
  - ritmo (mediana y mitad central);
  - cadena cinética (orden de los picos);
  - pista a escala.
  - Nada de gráficas de muchas líneas (#57).

## 8. Criterios de aceptación (automáticos)

- **Del visor:** los 15 de `diseno_definitivo.md` §5, medidos a 1280 y 1920 px.
  - Ejemplos: el vídeo de la lección en la primera pantalla; ≤ 3 claves y ≤ 120 palabras por fase; ningún nombre de
    fichero; ninguna medida de ruido como hallazgo; nada borrado.
- **De la gestión:**
  - cada recorrido de la sección 6 en sus clics, con Playwright y datos de ejemplo de varias personas y golpes;
  - 0 errores de página;
  - sin desbordes a 1024, 1280 y 1920 px.
- **Del modelo de calidad (#256):**
  - pantallas: primera pantalla < 2 s y cambio < 300 ms;
  - usabilidad: los recorridos;
  - portabilidad: Windows (WebView2).
- **Nada fijo:** con un catálogo de prueba de otras personas y golpes, todas las pantallas funcionan igual.

## 9 bis. La maqueta (15-11, versión 3)

Maqueta navegable de todas las pantallas: <https://claude.ai/artifact/Vi3ags11xK2ap6gSAJvt6N> (privada). Se rehace con
`python design/p0/build_app.py <informe> <auditoría> <cola_estado.md> <partidos.json> <salida>`, con la plantilla
`design/p0/aplicacion.html`, sin datos.

**Lleva los datos reales:**
- el catálogo: 3 fichas, los rivales sin ficha y los 6 partidos;
- la cola de la nube del momento;
- el modelo de calidad sobre la auditoría beta;
- la lección con sus 9 fases y todas sus claves, consignas, errores típicos y ejercicios;
- las medianas por situación;
- los 387 golpes con su cuerpo, sus pies y la bola y ella;
- las conclusiones;
- el ritmo, la cadena, el glosario, «Si te pasa…» y lo que la tele no mide.

**Recuadros marcados:**
- los fotogramas y los vídeos;
- las fotos;
- la subida;
- el uso del disco.

Las versiones 1 y 2 (`maqueta.html`, `build_maqueta.py`) quedan como histórico.

## 9. Lo que sigue

1. Maqueta navegable de **todas** las pantallas de las secciones 4-6. Tiene que enseñar el contenido de
   `p0_cobertura_listas.md`: la matriz de 15 puntos, la guía de Ivanovic, el juego de pies, las alturas, la bola y ella
   y los demás golpes con su estado, sin esconder lo que falta, con los datos reales de la beta y el catálogo
   real: las 3 fichas de personas, los 6 partidos (5 analizados y Zverev–Sinner pendiente), un análisis hecho (la
   derecha de Rybakina) y los demás como «se puede analizar».
2. Una revisión del usuario de esa maqueta.
3. La construcción (P0.5).

## 10. Validación de la maqueta (15-11, #305) y lo que cambia en el diseño

**Cómo se valida.** Por cálculo, no a ojo:
- `design/p0/recorrer_maqueta.py` recorre en un navegador las 35 pantallas y paneles, a 1920, 1280, 1024 y 390 px;
- `design/p0/validar_maqueta.py` comprueba cada elemento de cada fuente frente a lo que se ve.
- Fuentes: los requisitos de CLAUDE.md, la matriz de cobertura (taxonomía y tu lista de 15 puntos), los 20 huecos de
  Ivanovic, lo aprendido de los entrenadores, los patrones del catálogo de referencias y la usabilidad.
- Resultado completo: `docs/p0_validacion_maqueta.md`.

**Resultado** (✔ se ve o se abre con un clic):

| Fuente | Cobertura |
|---|---|
| Requisitos de CLAUDE.md | 49 de 55 (89 %) |
| Usabilidad y aprendizaje | 16 de 17 (94 %) |
| Patrones del estado del arte adoptados | 9 de 10; chat y muñeco 3D, para P4 |
| Entrenadores | 11 de 17 |
| Ivanovic | 11 de 19 (más 1 opcional) |
| Tu lista de 15 puntos | 33 de 59 por su medida; 15 más solo por palabras |
| Taxonomía completa | 38 de 110 por su medida; 38 más solo por palabras |

- Sin errores y sin nada que se salga de la pantalla a 1920, 1280 y 1024 px.
- A 390 px (móvil) se salen 28 de 35 pantallas. La aplicación es de escritorio (#301): para revisar desde el móvil se
  publica la validación como página legible en el teléfono.

**Qué dice:** la estructura está (requisitos, usabilidad, patrones), pero **no cubre todo lo escrito**. Lo que falta es
sobre todo **amplitud**: medidas, táctica y vistas que el análisis ya calcula y la maqueta no enseña en ninguna parte.
Cambios del diseño, por orden:

1. **Explorador de medidas por familia** (cuerpo, pies, raqueta, bola, contexto).
   - Cada medida de la taxonomía con su fiabilidad, cómo se mide, su reparto y sus golpes.
   - Hoy la maqueta solo enseña los 90 puntos de control de la lección y 26 medidas del informe.
   - **Hecho en la aplicación (15-11 23:00, «Más → Medidas»):** las 107 medidas que da el análisis (los 90 puntos de
     control golpe a golpe, que el informe ya guardaba en `lv` y la aplicación no recibía; las medidas del informe que no
     son un punto de control; 8 del contexto), por familia (cuerpo 46, pies 26, raqueta 16, bola y ritmo 11, contexto 8)
     y en la situación elegida: golpes con la medida, valor típico y la mitad de sus golpes, fiabilidad, cómo se mide; al
     abrirla, su reparto y los 3 golpes más bajos y más altos con su vídeo. Con menos de 10 golpes lo dice. La cobertura
     de la taxonomía no sube con esto (52 %): lo que falta son medidas que el análisis aún no calcula.
2. **Táctica y partido.**
   - Bote: profundidad, anchura, dentro o fuera. Golpe angulado. Dirección y sus cambios. Secuencias de 2-3 golpes.
     Longitud del peloteo. Puntos en ataque y en defensa. «Cómo usa su derecha». Bajo presión, también dirección y
     profundidad.
   - Un punto entero con mini-mapa numerado y «lo que hace bien / dónde pierde» (The Tennis Mentor).
   - La táctica dibujada sobre la pista: las opciones del rival y su punto de recuperación.
3. **Resto:**
   - cómo se reconoce;
   - el saque recibido (abierto, al cuerpo o a la T);
   - el lado (iguales o ventaja);
   - la posición de espera.
4. **Situaciones completas:** faltan «bola profunda» y «en salto».
5. **Empuñadura en la fase 1** (estimación o «no medible desde la tele»), y la lección empieza por ella.
6. **El análisis de cada golpe:**
   - avisos de técnica (Ivanovic 6);
   - «Cuenta conmigo»: un punto entero con el apoyo de cada golpe;
   - golpes con dudas marcados (requisito 5);
   - imagen estroboscópica;
   - tira de contactos con sus impactos superpuestos;
   - el vídeo con capas (esqueleto, raqueta, bola). En la maqueta es un recuadro y solo la aplicación real lo enseña.
7. **Lo que aún falta de Ivanovic:**
   - terminación hacia adelante y mano libre que recoge (9);
   - mano libre en la aceleración y el impacto (10; su medida no existe: #193, paquete M);
   - último apoyo frente al bote (12);
   - sus principios (13);
   - fuentes citadas (17).
8. **Junto a cada medida, cómo se mide y su fiabilidad** (hoy, cómo se mide solo está en «Lo que la tele no mide»).
9. **Lo no medible completo:** cada fila ✘ de la matriz dicha en «Lo que la tele no mide» (faltan, por ejemplo, la
   mirada, las fuerzas y el bisel de la empuñadura).

Lo medible que aún no se calcula (◐ y ✘ medibles de la matriz) es trabajo de los paquetes de medidas M, no del diseño.

**Decisión propuesta: no seguir iterando la maqueta; construir la aplicación (P0.5) con este validador como su prueba
de aceptación.**
- La maqueta ya hizo su trabajo: la estructura y los recorridos están comprobados.
- Lo que falta es amplitud con datos que ya existen. Construirlo una vez en la aplicación real cuesta menos que copiarlo
  en una maqueta estática.
- Lo más importante no se puede validar en una maqueta: el vídeo primero con sus capas, la velocidad real de la
  interacción y si de verdad se aprende con ella.
- El validador pasa a recorrer la aplicación real en cada versión: cada hueco sigue medido hasta cerrarse.

## 11. La trayectoria del swing sobre su vídeo (15-11, #306)

Del short que eligió el usuario (`aprendido_entrenadores.md` §7):
- **Qué se dibuja:** sobre el vídeo real del golpe, toda la trayectoria de la raqueta a la vez en puntos, con cuatro
  colores que marcan **su ritmo con la bola** (corrección del usuario, 15-11):
  1. **amarillo:** hacia atrás hasta su punto más alto;
  2. **blanco:** la caída y el swing antes del bote;
  3. **verde:** el swing tras el bote;
  4. **rojo:** el contacto y la terminación.
  Además, un recuadro en su zona de contacto.
- **De dónde sale:**
  - la serie fotograma a fotograma de cada golpe, que ya existe en el PC: la cabeza de la raqueta (5 puntos) o, si no
    se ve, la muñeca;
  - el punto más alto de la raqueta;
  - el bote de la bola recibida y el impacto, que ya se miden con la bola.
- **Sin el bote visto:** el blanco y el verde no se separan (un solo color, «bote no visto»); nunca se inventa el bote.
- **Honestidad:**
  - donde la raqueta sale borrosa (aceleración e impacto) los puntos van más tenues y dice «estimado»;
  - un fotograma sin raqueta no se dibuja; nunca se inventa.
- **Dónde va:**
  - en el análisis de cada golpe, como su imagen estroboscópica;
  - en la fase de la lección, sobre su golpe más representativo.
- **Estado:** el dibujo ya está en la aplicación (`ui/src/pantallas/Trayectoria.tsx`), probado con datos de ejemplo. Los
  datos reales entran con el reproductor en el PC (P0.5e).
