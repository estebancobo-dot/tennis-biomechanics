# Plan a corto plazo, al detalle (02-11)

Este documento manda sobre el resto del plan. Se actualiza en cada paso con el número medido y se sube con el código.
Lo leen igual el usuario y cualquier sesión de Claude que continúe.

## 1. Cómo se trabaja

### Cuatro formas de ejecutar

| Forma | Qué va ahí | Por qué |
|---|---|---|
| **PC secuencial** | Cada petición de `config/peticion_pc.txt`, una detrás de otra: pruebas desde cero, medidas (`medir`), análisis completo, repeticiones de etapas | El PC tiene una sola iGPU: dos trabajos pesados a la vez van cada uno a la mitad (medido el 29-10) |
| **PC paralelo** | *Dentro* de cada trabajo: la pasada fina en 2 procesos según la memoria libre, la exportación en 5 procesos, el marcador (CPU) junto a los jugadores (iGPU), la bola en la CPU mientras la pose va en la iGPU | Llena la CPU mientras la iGPU trabaja, sin dos trabajos pesados a la vez |
| **Nube secuencial** | Lo que decide sobre lo medido: leer los registros del PC, arreglar la causa, pasar todas las pruebas, subir el código, pedir la siguiente medida | Cada paso depende del número del anterior |
| **Nube paralela** | Lo que no depende de lo que corre en el PC: preparar modelos candidatos (un ayudante en su propia copia del repositorio), comprobaciones automáticas de las peticiones, documentación | Avanza mientras el PC mide |

### Cómo se enlaza

1. Claude sube el código y, si hace falta medir, añade una petición con id nuevo a `config/peticion_pc.txt`.
2. GitHub Actions (o el ciclo de 10 min de respaldo) la ejecuta en el PC y sube los registros a `pc-logs`:
   - `prueba_*.log`, `medir_*.log`, `analisis_completo.log`;
   - manifiestos con el tiempo de cada etapa;
   - `recursos/*.csv`;
   - `auditoria_*.json`;
   - **`estado_real_*.md`**: el estado real de cada petición y de cada paquete.
3. Una revisión programada de Claude lee esos registros. Las revisiones se encadenan solas mientras haya trabajo; ningún paso espera al usuario.
4. Con el número medido se decide lo siguiente. Si el paso se cumple, se cierra y se pasa al siguiente. Si no, se busca la causa, se arregla y se vuelve a medir.
5. Cada código nuevo trae una revisión automática en el PC frente a la ejecución anterior (`revision_automatica.md`: OK, REGRESIÓN o ERROR). Una REGRESIÓN se trata antes que nada nuevo.

### Cómo se valida (todo automático; el usuario no valida, #238)

- **Antes de subir:** la batería completa de pruebas pasa entera (`uv run pytest`, unas 690). Un cambio sin prueba propia no se sube.
- **Cada paso** tiene su criterio de cierre medido en el PC, escrito antes de medir (tabla de abajo).
- **Cada petición del usuario** está en un paquete (`config/plan_peticiones.yaml`; `test_plan_peticiones` impide que quede alguna fuera) y tiene un nivel calculado desde la auditoría sobre las salidas reales:
  - sin construir;
  - construido sin comprobar;
  - comprobación que falla;
  - comprobado en salidas;
  - validado con datos anotados.
- Un paquete se cierra cuando pasa su prueba de cierre y todas sus peticiones están comprobadas o validadas.
- **El plan mismo se valida** con `estado_real_partidos.md` en cada ejecución: el número de peticiones por nivel solo puede subir. Si baja, es una regresión.

### Reglas

- Ningún paso empieza hasta que el anterior se cierra medido.
- Nada nuevo entra mientras tanto. Lo externo (artículos, otros proyectos) solo entra como candidato dentro de su paso, con el procedimiento de `docs/referencias_externas.md`.
- Nunca se borra trabajo hecho.

## 2. Base: tareas al detalle

| Tarea | Forma | Depende de | Qué | Cierra cuando | Estado |
|---|---|---|---|---|---|
| **Paso 1 · B1 velocidad de un partido nuevo** | | | **Objetivo: la prueba de 35 min desde cero en ≤ 45 min (hoy 1 h 29), con los mismos golpes** | | **en curso** |
| 1.1 | PC sec. | — | Petición 71: prueba desde cero 4 + 35 min con todos los modelos en fp16 y los tiempos por parte del detector | Medido | **hecho**: 35 min en **1 h 28**; detector 43 min, de ellos **bola 42 min**; pasada fina 16,5 min |
| 1.2 | PC sec. | 1.1 | Petición 72: bola con lote fijo frente a variable, fp16 (`bench_ball`) | Medido | **hecho**: lote fijo o variable da igual (5-7 fotogramas/s), pero la misma medida dio 16-25 el 29-10 y la lectura del vídeo 59 s frente a 16: **todo el PC ~3 veces más lento**, con la CPU al 8-22 % → la tarea de Windows corre a prioridad baja |
| 1.3 | Nube sec. | 1.2 | Prioridad normal para el ciclo, su tarea de Windows (ciclo v5) y todo lo que lancen; el bucle no se arranca desde GitHub Actions | Subido | **hecho** |
| 1.3b | PC sec. | 1.3 | Petición 73: la misma medida de la bola | Vuelve a 16-25 fotogramas/s → causa probada | **hecho**: fp16 24-26 fotogramas/s, lectura 16,7 s (antes 5-7 y 59 s): **probado** |
| 1.3c | PC sec. | 1.3b | Petición 74: prueba desde cero de 35 min con la prioridad corregida | Medido | en cola |
| 1.4 | PC sec. | 1.3 | Nueva prueba desde cero (poc) | Detector de golpes ≤ 15 min en 35 min de vídeo | — |
| 1.5 | Nube sec. | 1.4 si no basta | Calcular la bola de todo el juego a la vez que el marcador (CPU) y en lotes; o en la CPU en paralelo con la iGPU | Ídem | — |
| 1.6 | PC sec. | 1.4/1.5 | Prueba desde cero final | **≤ 45 min en 35 min de vídeo; mismo número de golpes ±5 %** → cierra B1 | — |
| **Paso 2 · B3 mejores modelos** | | | **Cada candidato medido frente al actual** | | **preparándose en paralelo** |
| 2.1 | Nube par. | — | Ayudante: WASB, RTMW-x 2D, TennisCourtDetector, RF-DETR y F3ED a ONNX, con prueba ONNX = PyTorch y su script de medida | Ficheros y pruebas en su rama | en marcha |
| 2.2 | Nube sec. | 2.1 | Revisar lo del ayudante, unirlo, batería completa | Subido | — |
| 2.3 | PC sec. | paso 1 cerrado, 2.2 | **Una sola tanda** en el PC: precisión con F3Set y RacketVision, y fotogramas/s, cada candidato frente al actual. También PP-OCRv5 (#201) y MotionAGFormer o CalTennis para el 3D (#203, #206) | Tabla medida | — |
| 2.4 | Nube sec. | 2.3 | Adoptar los que ganan (mejor o igual precisión y no más lentos en un partido nuevo), cada uno detrás de su opción de configuración y con su prueba | Decisión de cada candidato en `docs/referencias_externas.md` → cierra B3 | — |
| **Paso 3 · B4 no perder golpes** | | | | | |
| 3.1 | Nube sec. | paso 2 | Regla de repeticiones (descarta de más: F3Set 11 %, Gauff 30 %) + regla de 2,5 s entre golpes del artículo, con pruebas | Subido | — |
| 3.2 | PC sec. | 3.1 | Petición `recall` (detector: sí) en F3Set | **recall sube sin bajar la precisión**, por lado y tipo → cierra B4 (#155, #205, #218, #219, #151, #23) | — |
| **Paso 4 · B5 exportación** | | | | | |
| 4.1 | Nube sec. | — (puede ir en paralelo con 3) | Medir dónde se va el tiempo por vídeo; codificar en la iGPU (AMF) si da la misma imagen; solo lo que cambió (ya hecho) | Prueba | — |
| 4.2 | PC sec. | 4.1 | Exportación completa medida | **≤ 20 min sin cuelgues** → cierra B5 | — |
| **Paso 5 · B6 referencia definitiva** | | | | | |
| 5.1 | PC sec. | pasos 1-4 | Una sola pasada de los 4 partidos con todo lo adoptado (`repetir` o `completo`) | **0 etapas con error, auditoría y estado real subidos** → cierra B6 (#1, #233, #234, #134) | — |
| **Paso 6 · B7 autonomía** | | | | | |
| 6.1 | Nube sec. | paso 5 | La aplicación procesa un partido nuevo con su cola, sin el ciclo, recuperando errores | Pruebas | — |
| 6.2 | PC sec. | 6.1 | Petición `app` y `ventana` con un partido de la referencia como nuevo | **De principio a fin sin el ciclo; capturas sin fallos** → cierra B7 | — |
| **Siempre · B2 robustez** | Nube sec. | cualquier fallo | Cada fallo o cuelgue que aparezca → causa, arreglo y prueba que lo reproduce | 0 etapas con error en el paso 5 | continuo |
| **Siempre · P3 comprobaciones** | Nube par. | — | Subir las peticiones «construidas sin comprobar» a una comprobación automática, paquete por paquete en el orden del plan (Base primero) | Más peticiones comprobadas en cada `estado_real` | en curso: rendimiento, tomas, golpes frente al marcador, errores de proceso |

## 3. Después de la Base (mismo método: tareas al detalle cuando llegue su turno)

Orden: M1 → M2 → M3 → M4 → M5 → M6 → M7 → P1 → P2 → P3 → P4 → P5 → P6 → D.
Cada paquete se cierra con su prueba (columna «Cierre»). El estado real de cada paquete está en `estado_real_*.md`.

| Paquete | Nombre | Peticiones | Cierre |
|---|---|---|---|
| B1 | Base · velocidad y uso del PC | #10, #14, #29, #75, #77, #125, #137, #230, #231, #237 | Prueba desde cero de 35 min en ≤ 45 min; CPU/iGPU por etapa medidas en cada ejecución |
| B2 | Base · robustez (nada se cuelga, todo se recupera) | #13, #225, #232 | Prueba por cada caso de error y cuelgue; 0 etapas con error en la referencia |
| B3 | Base · mejores modelos (estado del arte medido) | #30, #58, #138, #199, #200, #201, #202, #203, #204, #221 | Cada candidato medido frente al actual (precisión con datos anotados y fotogramas/s en el PC) |
| B4 | Base · no perder golpes | #23, #151, #155, #205, #218, #219 | Recall F3Set y RacketVision por lado y tipo, sin bajar la precisión |
| B5 | Base · exportación | #41 | Vídeos por golpe en ≤ 20 min sin cuelgues |
| B6 | Base · referencia definitiva de los 4 partidos | #1, #134, #233, #234 | 4 partidos sin errores de etapa; auditoría generada |
| B7 | Base · aplicación autónoma e infraestructura | #18, #19, #20, #21, #22, #31, #32, #37, #40, #43, #45, #49, #50, #51, #52, #66, #80, #81, #82, #83, #119, #136, #139, #144, #145, #146, #152, #160, #161, #220, #222, #226, #227, #229, #241, #242 | Un partido nuevo de principio a fin sin el ciclo ni el chat; capturas de cada pantalla sin fallos |
| M1 | Medidas · fases, cadena cinética y ritmo | #25, #26, #84, #97, #106, #163, #164, #165, #166, #168, #180, #235 | Cada medida: fiable en la auditoría (ruido < variación) y sin depender de la cámara |
| M2 | Medidas · pies y apoyos | #6, #64, #87, #88, #103, #104, #108, #116, #169, #170, #171, #172, #173, #174, #175, #176, #177, #178, #196, #236 | Pasos y apoyos medidos en la mayoría de golpes; fiables en la auditoría |
| M3 | Medidas · cuerpo | #48, #54, #56, #85, #92, #95, #101, #114, #115, #117, #124, #167, #192, #193 | Fiables en la auditoría y sin depender de la cámara |
| M4 | Medidas · raqueta, mano y empuñadura | #7, #8, #35, #36, #86, #100, #102, #107, #179, #181, #182, #183, #190, #191, #206, #211, #212, #216 | Fiables o «no medible desde la tele» dicho; cara del impacto marcada como estimación |
| M5 | Medidas · bola y situación del golpe | #5, #27, #38, #39, #55, #59, #69, #70, #90, #91, #105, #131, #132, #135, #157, #158, #184, #215 | Cada situación con golpes suficientes o «pocos datos» dicho; diferencias solo por encima del ruido |
| M6 | Medidas · tipos de golpe | #16, #89, #130, #159, #186, #188, #207, #209, #210, #223, #224 | Recall por tipo con datos anotados |
| M7 | Medidas · contexto del punto | #24, #98, #185, #187, #198, #244, #245 | Resultado del punto coherente con el marcador; nombres y fechas correctos |
| P1 | Producto · contenido para copiar su golpe (Cópiala / Aprende) | #4, #9, #15, #44, #46, #47, #57, #68, #71, #72, #79, #93, #94, #96, #99, #109, #110, #111, #112, #113, #123, #126, #143, #147, #150, #153, #189, #194, #195, #197, #213, #214 | Cada consigna con su medida, su fuente y su vídeo; examen interno R1-R25 pasado |
| P2 | Producto · pantallas e informe | #17, #28, #33, #34, #42, #53, #65, #67, #73, #120, #121, #122, #127, #128, #141, #148, #162, #208 | Capturas automáticas de todas las pantallas sin fallos; nada borrado de lo anterior |
| P3 | Producto · validación automática | #11, #12, #76, #118, #149, #238 | Cada medida y cada petición con una prueba automática y su umbral |
| P4 | Producto · comparación con las apps profesionales | #74, #142, #240 | Cada diferencia con su decisión y su prueba |
| P5 | Producto · escenarios y genericidad | #78, #140, #156, #243 | Cada escenario de docs/escenarios_producto.md con su prueba |
| P6 | Producto · móvil (al final) | #2, #154 | Copia al móvil comprobada |
| D | Documentación y reglas de trabajo | #217, #239 | Documentos al día con el código (prueba de enlaces y fechas) |

## 4. Estado de partida (02-11, `docs/estado_real_peticiones.md`)

237 peticiones:
- 24 sin construir;
- 108 construidas sin comprobar;
- 59 con una comprobación que falla;
- 46 comprobadas en las salidas;
- 0 validadas con datos anotados.

Lo medido con datos anotados hasta hoy, sin umbral acordado:
- detección de golpes: 80 % de los anotados en F3Set;
- identidad: 9 errores en 648 golpes.
