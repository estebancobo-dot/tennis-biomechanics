# Revisión de toda la Base, 11-11 (#260, tarea 10d de B8)

La anterior, del 27-10 (`revision_base.md`), revisó componentes y velocidad. Esta revisa **cada petición** de B1-B8 y la
prueba que la da por buena.

**Por qué:** el 11-11 aparecieron dos comprobaciones que daban por bueno algo que no lo era:
- la del tiempo de análisis, que sumaba etapas que solo releían datos guardados;
- la de «un partido nuevo de principio a fin», que pasó con el partido de otro jugador.

El usuario no se fía de que el resto de la Base esté mejor validado, con razón. El análisis completo (tarea 11) espera a
que se cierre lo que sale aquí.

## Resumen

**La Base no está cerrada.** De las 78 peticiones de B1-B8:
- **43 son válidas.** Su prueba mide lo pedido o es una propiedad del código probada en el PC.
- **8 son válidas, pero con una prueba que hay que cambiar.** Lo pedido se cumple según los datos, pero su comprobación
  mira otra cosa o no se ha visto nunca fallar.
- **15 pasan de HECHO a PARCIAL.** Su prueba mide otra cosa, o los datos reales la contradicen.
- **12 siguen abiertas como estaban** (PARCIAL o FALTA).

**Lo que más pesa:**
- **Velocidad (B1).** Su prueba principal era falsa. Desde cero, un tramo de 35 min tarda hoy 76 min: 2,2 veces el
  vídeo, unas 7,6 h para un partido de 3,5 h. El límite es 8 h. Hay alternativas sin perder calidad que no se han
  medido (§B1).
- **Modelos (B3).** Una decisión fue contra la regla del usuario «calidad antes que velocidad»: RF-DETR encuentra a la
  jugadora del fondo en el 100 % de los casos frente al 90 %, y se descartó por lento. Otra quedó sin resolver: RTMW
  («se adopta» el 07-11 y no está en uso).
- **Datos de referencia viejos (B4, B6).** Las cifras de los 4 partidos son del 09-11. Después cambiaron la identidad y
  el marcador.
- **Datos del registro de partidos (B7).** En el registro real ningún partido tiene rival (6 de 6 vacíos en
  `registro_partidos.json`) y las 6 carpetas de la biblioteca están en «sin-fecha». La prueba de #226 pasaba con datos
  inventados.
- **Ejecutor (B8).** El 11-11, tras un reinicio por código nuevo, estuvo 18 min sin arrancar (20:54-21:13). Dos
  trabajos esperaron hasta 11 min.

## Medida transversal: ¿cada comprobación sabe fallar?

Se ejecutaron todas las pruebas (1006) registrando qué comprobaciones de la auditoría producen y con qué estado. Se
compararon con las de la auditoría real del PC (`auditoria_partidos.json`, 11-11 17:09).

**Resultado.** La auditoría real tiene 544 comprobaciones distintas:
- **63 no las ejecuta ninguna prueba.** Por ejemplo:
  - «Tomas de cámara», de la prueba principal de B1;
  - las 9 pantallas;
  - los vídeos de cada golpe;
  - la vista lateral;
  - «Exportación».
- **20 se ejecutan, pero nunca se ven fallar.** Entre ellas:
  - «Tiempo» (la de B1, la que falló);
  - «Golpes que fallaron al procesarse» (B2, B6);
  - «Nada pide revisión manual» (B7);
  - «Golpes dudosos»;
  - 11 de la taxonomía.

En total, **83 comprobaciones (15 %) no tienen ninguna prueba que demuestre que fallan cuando deben**. La lista está en `revision_base_11-11_comprobaciones.json` (allí salen 68 y 21: 5 y 1 de ellas son el mismo «Partido …» con otro nombre de partido, no comprobaciones distintas); la medida, en `scripts/dev/rec_audit_items.py`. Así pasó lo del
tiempo. Arreglo: tarea R1.

## Hallazgos por paquete

Veredictos: **V** válida · **V·p** válida, pero hay que cambiar su prueba · **P** pasa a PARCIAL · **=** sigue como
estaba.

### B1 · velocidad y uso del PC (10)

**Tiempo desde cero.** Prueba de la aplicación del 11-11, petición 207: Rybakina-Pegula, 35 min a 60 fps, 119 golpes con
ventana.

| Etapa | min | Lo que tarda dentro |
|---|---|---|
| Pasada fina | 33,6 (43 %) | pose 19 (cerca y lejos) + 15 (RTMPose-x cerca del impacto) · bola 11,5 · pose de medida del fondo **10 min para 14 golpes** · raqueta 8,7 (1.248 fotogramas, 0,4 s cada uno) |
| Detector de golpes | 13,0 (17 %) | bola por todo el juego 12,9 |
| Golpes dudosos | 9,9 (12 %) | pose 10,3, raqueta 4,1 |
| Jugadoras | 7,6 (10 %) | |
| Planos | 5,0 (6 %) | |
| Resto | 7 | recortes de repeticiones 3,1, marcador 2,7, pista 1,5 |
| **Total** | **76 min** | **2,2 veces el vídeo** (≈ 7,6 h por partido de 3,5 h) |

Durante esa prueba la iGPU estuvo al 99-100 % y el procesador al 30 %.

**Historia desde cero, mismo tramo de 35 min de la final:**
- 18-10: 62 min;
- 29-10: 117 min (llega el detector aprendido);
- 02-11: 83 min;
- 03-11: 44-47 min.

Después no se volvió a medir desde cero hasta hoy. La petición 211 repite ese tramo con el código de hoy, para comparar
igual con igual.

| # | Petición | Qué mira su prueba | Hallazgo | Veredicto |
|---|---|---|---|---|
| 10 | Ver los cambios sin 1 h | que los vídeos del informe se reproducen | Lo pedido se cumple (06-11: medidas nuevas en 5,7 min sin rehacer el vídeo), pero la prueba no mide ese tiempo. | V·p |
| 14 | Un partido en horas, no días | «Tiempo» | La prueba era falsa (sumaba etapas que solo releían datos). Desde cero: 7,6 h. | **P** |
| 29 | Fase 0: fps reales | instalación | Histórica; el banco de modelos del 07-11 mide velocidades actuales. | V |
| 75 | «10 golpes en 5 horas es absurdo» | «Tiempo» | Igual que #14. | **P** |
| 77 | No lanzar pruebas de 6 h | la previsión se niega por encima de 6 h | Probado con un caso que debe fallar. | V |
| 125 | Velocidad antes del tramo largo | «Tiempo» | Igual que #14. | **P** |
| 137 | ¿Se puede paralelizar? | «Etapas a la vez» | Procesador libre (70 %) con la iGPU llena. La bola se calcula dos veces (detector 12,9 min y pasada fina 11,5 min). Sin medir: repartir más trabajo al procesador. | **P** |
| 230 | Uso del PC por etapa y aprovechar el equipo | que existe la medida de recursos | Medir sí; aprovechar no (iGPU 99 %, procesador 30 %). | **P** |
| 231 | No tardar el doble sin saber la causa | tiempo de cada etapa frente a su ritmo | Mide etapas que calcularon de verdad. Ahora además hay desglose dentro de la pasada fina (`scripts/tiempos_etapas.py`). | V |
| 237 | El PC empieza cada trabajo al momento | lo que tarda en arrancar el trabajo de GitHub Actions | Caso real del 11-11: dos trabajos esperaron 5-11 min porque el ejecutor no estaba vivo (§B8). | **P** |

**Alternativas sin perder calidad, a medir en la tarea 10c.** Cada una se mide con la prueba desde cero y la calidad de
siempre (F3Set, medidas de los golpes, auditoría):
1. **Usar en la pasada fina la bola que ya calculó el detector.** Podría ahorrar unos 11 min por cada 35 min de vídeo.
   Hay que comprobar el instante del impacto: la pasada fina la calcula a más fotogramas.
2. **Pose de medida del fondo** (10 min para 14 golpes, desde el 09-11, #219): ver por qué repite la pose y si puede
   reutilizar la primera.
3. **RTMW-x en lugar de RTMPose-x.** El banco del 07-11 dice «3 veces más rápido, igual de preciso, se adopta»; la
   prueba real del 03-11 decía «más lento». Hay que resolverlo con una prueba A/B desde cero.
4. **Repartir con el procesador.** Pasar a la CPU, en paralelo, lo que no necesite la iGPU: la bola, la raqueta, la
   pose de los golpes dudosos.
5. **Golpes dudosos** (10 min). Contar cuántos hay y por qué después de la identidad v12.

**Descartadas antes, con su medida:**
- la mitad de fotogramas (10-11: cambia las medidas del impacto);
- WASB para la bola (F1 0,863 frente a 0,906);
- RTMPose más ligero, raqueta en FP16 o menos resolución (14-10: pierden calidad).

### B2 · robustez (3)

| # | Petición | Qué mira su prueba | Hallazgo | Veredicto |
|---|---|---|---|---|
| 13 | Casos nominales, límite, esquina y error | que las pruebas pasan | Que las pruebas pasen no dice qué casos cubren. 83 comprobaciones de la auditoría nunca se han visto fallar. | **P** (R1) |
| 225 | La aplicación no se cuelga ni ralentiza el PC | pruebas de la ventana | Nunca se ha medido lo que consume la aplicación en el PC (la nota de la petición lo pedía). | **P** (R8) |
| 232 | Ningún proceso que se pueda colgar sin probar | revisión del código: toda llamada externa con tiempo límite; las exportaciones terminan | Mide lo pedido; las 3 exportaciones terminaron (09-11). | V |

### B3 · mejores modelos (10)

Cada candidato se midió en el PC: precisión con datos anotados y velocidad (`bench_candidates.md`, 07-11). Es el paquete
mejor validado.

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 30 | Estado del arte frente a otras apps | La prueba mira que el documento esté al día con los modelos. La comparativa de producto es #257 (P0). | V |
| 58 | La IA más moderna posible | La lista de candidatos es del 13-10 y no se ha renovado. La precisión del esqueleto no tiene verdad anotada (F1 de golpes 0,667 en los dos modelos: no distingue). RTMW sin resolver. RF-DETR descartado por velocidad con +10 puntos de calidad, contra «calidad antes que velocidad». | **P** (R3) |
| 138 | Modelos híbridos | En uso: YOLO11 + RTMPose-x. | V |
| 199 | Bote | Modelo propio: F1 0,884 frente a 0,594 de la regla, en partidos no vistos. | V |
| 200 | Pista de 14 puntos | 95,6 % frente a 91 %, en uso. | V |
| 201 | Marcador PP-OCRv5 | Peor (0,44 frente a 0,52): descartado con su medida. | V |
| 202 | Bola WASB | Peor (F1 0,863 frente a 0,906): descartado. | V |
| 203 | 3D MotionAGFormer | 58 % a ≤ 15° frente a 13 %, en uso. Validado de lado (CalTennis), no desde la cámara de la tele (dicho). | V |
| 204 | Detector aprendido (F3Set) | F3ED medido: 0,994 frente a 0,997 y 5 veces más lento: descartado. | V |
| 221 | Golpes con modelos entrenados | F3Set: 466 de 517 (90 %), precisión 0,94. | V |

### B4 · no perder golpes (6)

Es el método más sólido: comprueba frente a golpes anotados (F3Set) y frente al marcador. Pero las cifras de los 4
partidos son del 09-11, con la identidad y el marcador anteriores. Se recalculan en la tarea 11.

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 23 | Seguirla en los cambios de lado | Frente a F3Set: 99 %. Pegula: ropa igual dentro de un juego 92 % (< 95 %). | = (abierta) |
| 151 | Cómo se separan derecha, revés, saque y volea | La prueba solo cuenta golpes. Hay verdad sin usar: F3Set da derecha/revés bien en 327 de 334 (97,9 %) y saques en 129 de 130. Ninguna comprobación lo mira. | **P** (R4) |
| 155 | No perder golpes | Osaka: saques encontrados 76 % (< 85 %). La prueba principal de B4 falla, como ya decía la tabla de cierre. | = (abierta) |
| 205 | Unos 400 golpes | 561 derechas. | V |
| 218 | Fondo, repeticiones y otras cámaras | Fondo frente a F3Set: 88 % frente al 93 % del lado cercano; repeticiones enlazadas. | V |
| 219 | Golpes del fondo contados | Igual que #218. | V |

**Además:** la prueba principal de B4 incluye «Validación con clips anotados (F3Set)». Esa comprobación mide el
**camino antiguo**: 51 golpes, recall 0,647, aprobada con F1 ≥ 0,6. No mide el detector actual (R4).

### B5 · exportación (1)

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 41 | Exportación: cómo se ven y se graban | La prueba es «el PDF existe y tiene 6 páginas». Se cuenta que hay un vídeo por golpe (540/540), pero no se mira si se reproduce, si dura lo que debe ni si lleva el esqueleto. | **P** (R5) |

### B6 · referencia de los 4 partidos (4)

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 1 | Su derecha en los 4 partidos completos | Completo (todas las etapas, 0 errores), pero con el código del 09-11. | V·p (tarea 11) |
| 134 | Referencia completa antes de más golpes | Igual que #1. | V·p (tarea 11) |
| 233 | Referencia medida antes de validar | Igual que #1. | V·p (tarea 11) |
| 234 | Prueba de valor con los datos reales | La prueba cuenta caracteres, vídeos y gráficos de 2 pantallas: volumen, no valor. El usuario la juzgó insuficiente. Pasa a P0 (#252, #256). | **P** |

### B7 · aplicación autónoma e infraestructura (36)

**Propiedades del código probadas en el PC.** Son válidas (V): #18, 19, 20, 21, 31, 32, 37, 40, 43, 49, 52, 80, 81, 82, 83,
136, 139, 144, 145, 146, 152, 161, 220, 222, 227, 229, 241.
- Son decisiones de diseño y su prueba automática las comprueba: rutas fuera del repo, sin servidor, nada fijo en el
  código, Windows nativo, almacenamiento, etc.
- En #18, #19, #21 y #37 la comprobación asociada de la auditoría no tiene que ver («golpes analizados»): solo se
  corrige el enlace.

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 22 | Solo la cámara principal | Su comprobación es «golpes analizados». La verdad está en F3Set (0-1 golpes perdidos por repeticiones de cada tipo), pero ninguna comprobación la mira. | V·p |
| 45 | Todo automático | «Nada pide revisión manual» nunca se ha visto fallar en las pruebas. | V·p (R1) |
| 50 | Progreso visible | Bien en el análisis normal. El progreso de la prueba de la aplicación no se ve desde fuera: el 11-11 no se pudo seguir. | V·p |
| 51 | El código de la prueba es el de los casos reales | La aplicación no lanza la etapa del rival (`app/engine.py`, MAIN_STAGES) y el ciclo sí. La auditoría pide su fichero, y el partido nuevo suspende por eso. | **P** (R6) |
| 66 | Fechas y duración en los registros | Suspende con un registro que se está escribiendo (en la prueba de la aplicación). | V·p (R6) |
| 119 | Todo el ciclo automático en el PC | Tras un reinicio, el ejecutor queda parado hasta el ciclo de 10 min (§B8). | **P** (R7) |
| 160 | ¿Se puede usar la aplicación? | La prueba del partido nuevo era débil (corregida el 11-11). | = (tarea 10b) |
| 226 | Lista de partidos profesional (nombres, torneo, ronda, fecha, fotos) | La prueba pasa con datos inventados; en el registro real los 6 partidos tienen el rival vacío y su carpeta en «sin-fecha». | **P** (R6, con #258) |
| 242 | Flujo de la aplicación | La petición 207 pasa en tiempo e identidad. Su auditoría dice «FALLOS» por 32 comprobaciones, pero 20 son peticiones que aún no tocan (fuera de la Base). Las del propio partido que fallan son 4: inicio de preparación 40 %, registros, «sin terminar» porque se mira a sí misma, y el fichero del rival (#51). | = (tarea 10b) |

### B8 · orquestador (7 + #259, #260)

| # | Petición | Hallazgo | Veredicto |
|---|---|---|---|
| 246 | Un único orquestador | Pruebas del PC hechas (184, 187, e2e 205). Pero su prueba principal («Orquestador: …») no existe en la auditoría: «sin medir». **Caso real del 11-11:** el ciclo pidió reiniciar el ejecutor con el código nuevo y el ejecutor se cerró. El ciclo de GitHub Actions no arranca otro, y el siguiente ciclo de Windows (21:00) tampoco lo hizo: 18 min parado. | = (R7) |
| 247 | No lanzar con fallos conocidos | Se cumple: la tarea 11 espera. | = |
| 248 | Velocidad sin perder calidad (≤ 8 h) | 7,6 h desde cero (§B1); alternativas en 10c. | = |
| 249 | Parar el PC al momento | «Parar ya» por la cola probado de extremo a extremo (205). | = (prueba en R7) |
| 250 | Seguir sin perder nada si se acaban los tokens | Estado en el repositorio y cola en la base de datos. | = |
| 251 | Tareas encadenadas sin olvidarse | Tabla al día, pero hoy hubo tres errores de proceso (§«Forma de trabajar»). | = |
| 259, 260 | Velocidad medida y esta revisión | En marcha. | = |

### Forma de trabajar (errores del 11-11, con su arreglo)

1. **Una subida con 2 pruebas fallando.** La subida dependía de que terminara la salida, no de su resultado. Ahora lleva
   `pipefail`.
2. **Un documento sobrescrito sin mirarlo** (`revision_base.md`). Recuperado al momento de git.
3. **El script de tiempos buscaba solo en la carpeta de salidas.** Los partidos están en la biblioteca. Corregido antes de
   ejecutarse, con su prueba.
4. **Dos veces se dijo al usuario que la última medida desde cero era del 18-10 o del 26-27-10.** Hubo más: 29-10,
   02-11 y 03-11. Corregido aquí.

## Tareas que salen de la revisión (en este orden, antes de la tarea 11)

| Tarea | Qué | Cómo se acepta |
|---|---|---|
| R1 | Toda comprobación con un caso que la haga fallar: `tennisbio.check_coverage` (lo medido aquí) con las pruebas del PC y en cada auditoría («Comprobaciones que saben fallar»), y pruebas para las 83, primero las de las pruebas principales de B1-B8 | 0 comprobaciones de las pruebas principales sin caso que falle; el número total, en la auditoría |
| R2 | B1: la prueba «Tiempo» solo con ejecuciones desde cero; alternativas 1-5 medidas (tarea 10c) | prueba desde cero ≤ 8 h por partido de 3,5 h y cada alternativa adoptada o descartada con su medida de calidad |
| R3 | B3: RF-DETR medido en la pasada real (coste frente a +10 puntos); RTMW resuelto con A/B desde cero; lista de candidatos renovada (modelos de 2025-2026) | cada candidato con su medida y una decisión por «calidad antes que velocidad» |
| R4 | B4: la prueba principal con el detector actual frente a F3Set (no el camino antiguo); comprobación nueva «Tipo de golpe frente a F3Set» (≥ 95 %) | las dos en la auditoría, con su caso que falla |
| R5 | B5: cada vídeo exportado se reproduce, dura lo de su ventana y lleva el esqueleto (muestra por exportación) | comprobación en la auditoría con su caso que falla |
| R6 | B7: la aplicación lanza las mismas etapas que el ciclo; la lista de partidos con rival, torneo, ronda y fecha en el registro real (con #258); los registros que se están escribiendo no suspenden; el partido nuevo se juzga con sus propias comprobaciones | partido nuevo (app_nuevo) sin fallos propios; registro real con los campos llenos |
| R7 | B8: el ejecutor se reinicia solo con el código nuevo, sin esperar al ciclo; comprobaciones «Orquestador: …» (prueba e2e, ejecutor vivo, espera de los últimos trabajos) | 0 min sin ejecutor tras un reinicio; prueba principal de B8 medida |
| R8 | B2: lo que consume la aplicación en el PC (CPU, RAM) abierta y con un análisis en marcha | medida en `recursos/` y comprobación en la auditoría |
| 11 | Análisis completo de los 6 partidos | auditoría, `calidad.md` y tabla de cierre |
