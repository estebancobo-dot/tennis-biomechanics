# Toda la aplicación en la nube: análisis (13-11-2026)

Petición del usuario (13-11): «qué habría que hacer para que toda la aplicación corriese en la nube y solo tuviese que
subir los partidos … con todo el estado del arte … tanto en nube pública como de pago … no implementes nada … con los
mismos requisitos». **Solo análisis: no se ha cambiado nada del código ni del PC.**

Antecedentes que este documento actualiza, sin borrarlos:
- `docs/arquitectura_producto.md` §8 (octubre): móvil e informes estáticos (8.1), GPU en la nube por partido (8.2) y las tres opciones A/B/C (8.3).
- **Decisión del usuario del 17-10:** «nada en la nube y nada de pago» (`docs/estado_proyecto.md`, «17-10: decisiones»).
- **Requisito 10 de `CLAUDE.md`:** «móvil/nube al final».

Este análisis reabre esa decisión con datos nuevos. **La decisión es del usuario.**

Cómo leer las cifras:
- Los **tiempos del PC son medidos** (pc-logs: `ritmos.json`, `capturas_diag/tiempos_etapas.md`, R2, R17).
- Los **tiempos en la nube son estimaciones**, con su cuenta a la vista. Se miden en la fase N0 (§8) antes de decidir nada más.
- Todo precio lleva «precio visto el 13-11-2026, cambia». Muchos salen de agregadores de terceros, no de la página oficial; se dice en cada caso.

---

## 1. Resumen ejecutivo

**¿Se puede?** Sí. Todo el motor ya es Python + ONNX + ffmpeg (portable a Linux con GPU NVIDIA cambiando el proveedor de
ONNX Runtime de DirectML a CUDA/TensorRT). Lo que no es portable es lo que rodea al motor en el PC:
- el ciclo de PowerShell y la tarea de Windows;
- la ventana con WebView2 y la copia al móvil por MTP;
- las rutas `C:\tenis\…`;
- la rama `pc-logs` como canal de registros.

Eso se sustituye, no se traduce.

**¿Mejora algo?**

| Qué | Hoy (PC, medido) | En la nube (estimado; se mide en N0) |
|---|---|---|
| Los 6 partidos (715 min de vídeo) | **26-39 h seguidas**: un trabajo pesado cada vez (2,2-3,3 veces la duración del vídeo) | **~1-2 h de reloj** (los 6 a la vez, la pasada fina repartida por ventanas); de 3 a 13 h de GPU en total |
| Una validación F3Set por cambio | **~5 h** (v16, 263) que **bloquean la cola del PC** | ~20-40 min en paralelo, sin parar nada (estimación) |
| Coste de los 6 partidos | ~0 € (luz) | **probable 3-15 $**; peor caso (la GPU no acelera nada) ≈ 40 $ |
| Coste fijo al mes | 0 € | ~0-1 $ (todo se apaga solo; el almacenamiento de ~40 GB) |
| Lo que hace el usuario | Copiar el vídeo a `C:\tenis\videos`, un clic por partido en la ventana del PC | **Subir el vídeo desde una página web (PC o móvil), un clic de identidad en la misma web, aprobar el análisis** |

**Lo que de verdad mejora** no es solo el tiempo por partido:
1. **Validar cada cambio por separado**, en paralelo y en minutos. Es la causa 5 de #267: v16 midió R14 y R16 juntos porque cada validación cuesta 5-12 h de PC.
2. **Desaparece una familia entera de fallos del PC:**
   - el ejecutor muerto sin rastro (R7);
   - la ventana vacía (R12);
   - el ciclo trabajando fuera de la cola (R28);
   - el código nuevo que espera a que la cola quede libre (petición 286);
   - los 10 minutos de cada vuelta del ciclo.
3. **Claude opera la cola directamente** (API con credencial) en vez de por `config/peticion_pc.txt` y `pc-logs`.
4. **Modelos que hoy se descartan por coste se pueden medir** (§6). Solo se adoptan si ganan en F3Set y RacketVision.
5. **El móvil es la misma web** (P6 sin trabajo aparte).

**Lo que no arregla:** los fallos abiertos de la Base son de algoritmo, no de máquina:
- B4: saques en los cambios de juego;
- R29: identidad cuando ropa y marcador discrepan;
- B6: pose en el contacto en los otros 4 partidos;
- B5: exportaciones.

La nube solo los valida más deprisa. Portar todo **ahora** retrasaría la Base.

**Recomendación (detalle en §10):**
1. **Ahora, si el usuario lo aprueba, solo dos piezas que no tocan el PC:**
   - **N0**, la prueba de la GPU: los mismos modelos ONNX en una L4 de alquiler; se miden la velocidad y que salgan los mismos golpes. Coste de unos pocos dólares.
   - **N4**, validaciones F3Set en la nube en paralelo. F3Set es un conjunto académico público, así que se evita subir las retransmisiones.
2. **La nube completa (N1-N3, N5-N6), después de cerrar la Base**, en el lugar del paso 8 del plan:
   - cómputo: **Modal** (Python nativo, se apaga solo, factura por segundo);
   - almacenamiento: **Cloudflare R2** (sin coste de salida);
   - acceso: **Cloudflare Access**.
3. **El PC queda como segundo dispositivo validado**, o se retira (lo decide el usuario).

---

## 2. Requisitos vinculantes y cómo quedan en la nube

| Requisito (CLAUDE.md y reglas del usuario) | En la nube | Cómo se cumple / qué cambia |
|---|---|---|
| 1. Responder «¿cómo pegar una derecha como X?» con todas sus variantes | Igual | Es el mismo motor; la nube no cambia medidas |
| 2. Información, no tablas; vídeo primero | Igual o mejor | El informe es el mismo HTML, servido por la web; el móvil lo ve sin copias |
| 3. Nada inventado; «no medible desde la tele» | Igual | Mismas comprobaciones y auditoría. **Cambiar de dispositivo exige revalidar**: ONNX en CUDA no da los mismos decimales que en DirectML (§9) |
| 4. Cara de la raqueta (honesta donde es estimación) | Igual | El desenfoque del impacto es de la cámara (25-50 fps), no de la máquina: una GPU no lo arregla |
| 5. 100 % automático; un clic por partido | Mejor | Nada que instalar. Subir, un clic y aprobar en una web. Se avisa al móvil cuando toca el clic |
| 6. Sin fuentes externas (salvo la vista lateral de entreno) | Igual | Nada cambia |
| 7. Partido completo solo con todas las funciones; antes, clips públicos | Igual | F3Set y RacketVision se ejecutan en la nube (más rápido) |
| 8. Cobertura de casos (nominal, límite, esquina, error) | Igual + nuevos | Casos nuevos: subida cortada, GPU interrumpida (las GPU de Modal son interrumpibles), presupuesto agotado, región sin GPU |
| 9. Rendimiento: viable en el Beelink (iGPU, sin CUDA) | **Cambia** | El requisito pasa a ser «viable en el PC **y** en la nube». Mantener el PC (DirectML) obliga a validar los dos dispositivos |
| 10. Orden; móvil/nube al final; el PC no es servidor | **Cambia el orden** si el usuario lo decide | El PC deja de hacer nada: no es servidor en ningún caso, solo sube ficheros (o ni eso: se sube desde el navegador) |
| Orquestador único (misma cola, mismo código y datos para la app y el chat) | Igual en el fondo | Una sola cola en la nube que usan la web y Claude. «Un trabajo pesado cada vez» era por la iGPU: pasa a «N a la vez con un tope de gasto» |
| Análisis completo solo con la aprobación del usuario (#262) | Igual | Botón «Analizar» con el tiempo y el **coste previstos**. Nada arranca sin ese clic. Tope de gasto por trabajo y por mes |
| Nunca un análisis completo con fallos conocidos (#247) | Igual | Misma puerta («Fallos por niveles», la auditoría) |
| Calidad antes que velocidad (#248) | Igual | La nube solo se adopta si F3Set y la auditoría salen iguales o mejores |
| Nunca borrar trabajo; revisiones manuales nunca sobrescritas | Igual | Versionado del almacén; «desde cero» mueve a `archivo/` como hoy; sin reglas de borrado automático |
| Registros sin pedírselos al usuario | Mejor | Los registros van al almacén y a un estado consultable. Claude los lee por API; desaparece el ciclo de git de `pc-logs` |
| Pruebas antes de cada subida (0 fallos) | Igual + una prueba con GPU | `uv run pytest -q -n 4` en CPU como hoy, más una prueba de referencia con GPU antes de cada versión (§7) |
| Privacidad (vídeos de TV, uso privado; datos personales) | **Riesgo nuevo** | Los vídeos salen de casa: almacén privado y cifrado, región UE, sin enlaces públicos, borrado del vídeo a elección del usuario (§9) |

---

## 3. Inventario de lo que hay

### 3.1 Etapas, modelos y tiempos medidos en el PC

Etapas registradas en `pipeline.STAGES` (`stages.py`, `view_stages.py`), con su versión actual y su ritmo medido
(`ritmos.json` en pc-logs, segundos de cálculo por minuto de vídeo). Las últimas medidas son de Osaka (71,4 min,
entrelazado), salvo donde se indica.

| Etapa (versión) | Depende de | Modelo / herramienta | Máquina | s por min de vídeo (PC) | Paralelizable |
|---|---|---|---|---|---|
| probe (2) | — | ffprobe | CPU | ~0 | — |
| scenes (3) | probe | TransNetV2 (ONNX) + histogramas | GPU + decodificación | 7,6-8,3 (Pegula, Zverev) | por tramos del vídeo, con solape |
| audio (2) | probe | librosa (onsets) | CPU | 0,1-0,2 | por tramos |
| court (6) | scenes | TennisCourtDetector de 14 puntos (ONNX) + líneas | GPU | 2,5 (Pegula) | por planos |
| players (6) | scenes, court | YOLO (personas, ONNX) | GPU | 10,1 | por planos |
| score (13) | scenes, court | RapidOCR (ONNX) | CPU/GPU | 6,1 | por planos |
| identity (13) | players, score, court, audio | ropa + cambios de lado + **clic del usuario** | CPU | 1,1 | — (espera el clic) |
| spotting (2) | players, audio, court, scenes, identity | TrackNetV3 de RacketVision (bola en todo el juego) + detector propio entrenado con F3Set | GPU | **17,2-23,8** (con la bola, R17) | por planos de juego |
| candidates (16) | players, audio, identity, court, score | reglas + saque por el marcador | CPU | ~0 | — |
| views (6) / views_link (1) | … | otras cámaras enlazadas | CPU/GPU | 1,9 | por golpe |
| fine (16) | candidates, court, score | RTMPose-x Halpe26 (rtmlib) + YOLO11-pose + raqueta RTMPose-m (RacketVision) + RTMW3D + MotionAGFormer + bola | **GPU** | **133** (232 ventanas, **40,7 s por golpe**) | **por ventana** (ya hay procesos en paralelo: `stages._fine_parallel`) |
| fine_doubtful (1) | candidates, court, score | como fine | GPU | 6,7 | por ventana |
| fine_opponent (9) | candidates, court, score | como fine | GPU | (rival) | por ventana |
| view_clips (1) / slowmo_fine (1) | views, fine | ffmpeg | CPU | 1,2-5 | por golpe |
| informe, auditoría, exportar (fuera de STAGES) | todo | report.py, audit.py, export.py (ffmpeg) | CPU | minutos | por golpe (exportación) |

**Total medido:**
- **2,17 veces** la duración del vídeo en la prueba desde cero de 35 min (76,1 min; `tiempos_etapas.md`).
- **2,16 veces** en Pegula (60 fps, 7,6 h; R2).
- **1,41 veces** en el tramo de la final (antes de que el detector tuviera la bola, R17).
- **~3,3 veces** en Osaka con el código de hoy, entrelazado: suma de los ritmos de arriba, unos 197 s por minuto.

**Los 6 partidos:**
- Duración: 116,7 + 133,4 + 210,4 + 71,4 + 112,2 + 71,0 = **715 min** (11,9 h de vídeo).
- En el PC: 715 × 2,2-3,3 / 60 = **26-39 h** de un solo trabajo seguido.

Dónde se va el tiempo (35 min desde cero, `tiempos_etapas.md`):
- pasada fina 43 % (dentro: pose 34,5 min, bola 11,5, pose del fondo 10, raqueta 8,7);
- detector 17 % (casi todo la bola por todo el juego);
- golpes dudosos 12 %.

La iGPU va al 99 % y el procesador al 30 %. **Más del 80 % del tiempo es inferencia de modelos en GPU**, que es justo lo que una GPU de verdad hace mejor.

### 3.2 Portable tal cual y solo de Windows

| Pieza | ¿Portable a Linux con GPU? | Equivalente en la nube |
|---|---|---|
| Paquete `tennisbio` (etapas, contratos, fallos #265, auditoría, informe, exportación) | **Sí** (ya corre en Linux: las 1200 pruebas pasan en la nube) | Igual |
| Modelos ONNX (`models/*.onnx`) | **Sí** | ONNX Runtime con CUDA o TensorRT en vez de DirectML (`pose/estimator.py`, `pose/backend.py`; en `pyproject.toml` hoy solo hay `onnxruntime-directml` en Windows y `onnxruntime` de CPU en el resto) |
| Ultralytics YOLO (PyTorch, AGPL-3.0) | Sí | Igual. **AGPL**: uso privado de un solo usuario, sin distribuir; si algún día se ofrece a otros como servicio, obliga a publicar el código |
| ffmpeg por tubería (`io/video.py`; `yadif=1` para entrelazado) | Sí | Igual; opcional NVDEC (`-hwaccel cuda`, la L4 tiene decodificadores de vídeo) para la pasada barata |
| `uv`, Python 3.11 | Sí | Imagen de contenedor con `uv sync` y los modelos |
| Cola SQLite con un ejecutor (`orchestrator.py`, `datos/tennisbio.db`) | Sí, pero pensada para una máquina | Cola duradera de la plataforma (Modal Queue/Dict, Postgres, Cloud Tasks) con las mismas órdenes |
| Biblioteca (`library.py`: `C:\tenis\biblioteca`, nombres ASCII, escritura atómica, índice derivado) | Sí en lógica; rutas de Windows por configuración | Prefijos en el almacén (`partidos/<año>/<partido>/…`), mismos nombres |
| Ciclo de PowerShell (`scripts/windows/ciclo_automatico.ps1`, `ciclo_bucle.ps1`, `oculto.vbs`, tarea de Windows) y `pc-logs` | **No** | Sobra: la cola y el estado viven en la nube; los registros, en el almacén |
| Ventana de la aplicación (`app/window.py`: pywebview + WebView2) | **No** | La misma `ui.html` servida por HTTP con las mismas llamadas de `Api` y autenticación |
| Copia al móvil (`app/mobile.py`, `app/phone.py`: MTP con PowerShell) | **No** | Sobra: el móvil abre la web (se conserva desactivada; nunca borrar) |
| Copia a USB (`app/backup.py`), disco (`app/storage.py`) | No / parcial | Versionado del almacén y, si se quiere, una segunda copia en otro proveedor |
| `config/local.yaml` (rutas) | Sí | Variables de entorno o configuración del despliegue |

---

## 4. Arquitectura objetivo

```
  Usuario (navegador del PC o del móvil)
     │ 1. sube el vídeo (subida por partes, reanudable, directa al almacén)
     │ 2. un clic: «¿cuál es ella?»   3. «Analizar» (tiempo y coste previstos)   4. ve el informe
     ▼
┌──────────── Web (plano de control) ────────────┐        ┌──── Claude (chat) ────┐
│ ui.html de hoy + API HTTP (las llamadas de     │◄──────►│ la misma API: enviar, │
│ app.core) · autenticación (Cloudflare Access)  │  API   │ pausar, cancelar,     │
│ · avisos al móvil · tope de gasto              │        │ estado, registros     │
└──────────────┬─────────────────────────────────┘        └───────────────────────┘
               │ envía / pausa / cancela / estado (una sola cola)
               ▼
┌──────────── Cola duradera + orquestador ───────┐
│ trabajos = flujos de config/flujos.yaml        │
│ cada etapa = una función; huellas como hoy     │
└───┬───────────────┬────────────────┬───────────┘
    │ pasada barata │ detector       │ pasada fina: una tarea por ventana (±1 s)
    ▼ (CPU+GPU,     ▼ (GPU, por      ▼ (GPU, N contenedores a la vez, .map)
   por tramos)     planos de juego)
┌──────────────────────────── Almacén de objetos (privado, cifrado, región UE) ─────────┐
│ videos/<contenido>.mkv · partidos/<año>/<partido>/etapas/… (manifiesto, cachés con   │
│ su huella) · analisis/… · informes/… (HTML estático) · registros/… · archivo/…       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Subida
- **Subida por partes y reanudable** desde el navegador (protocolo multipart de S3, que R2 también acepta, con URL firmadas de corta duración). Una subida cortada sigue donde se quedó.
- Con una sola petición de subida, S3 no acepta más de 5 GB; por partes el límite es mucho mayor ([AWS, subida por partes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html), [R2, URL firmadas](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)).
- La huella del vídeo por contenido (`pipeline.video_sample`, 8 trozos de 1 MB) se calcula en el navegador o al llegar: un vídeo ya subido se reconoce y no se sube dos veces.
- Tiempo de subida de 5 GB (5·10⁹ × 8 bits / velocidad de subida):

| Subida de casa | 5 GB | Los 6 partidos (~30-40 GB; los tamaños exactos de los vídeos no están en pc-logs) |
|---|---|---|
| 10 Mbps | 67 min | 7-9 h |
| 50 Mbps | 13 min | 1,3-1,8 h |
| 100 Mbps | 7 min | 40-55 min |
| 300 Mbps | 2,2 min | 13-18 min |

La subida puede ser lo más lento de todo. Se hace una vez por partido; después, cualquier recálculo ya no sube nada.

### 4.2 Almacenamiento
- La estructura de la biblioteca (`docs/almacenamiento.md`) pasa tal cual a prefijos del almacén: nombres ASCII en minúscula y escritura atómica. En un almacén de objetos, un objeto escrito entero es atómico por naturaleza.
- Las cachés siguen con su huella de código, como hoy (R14): la huella no depende de la máquina, pero **sí del dispositivo** (§9). La huella de las cachés de pose y bola debe incluir «cuda/dml».
- Volumen estimado: el vídeo (2-8 GB) más ~0,3-2 GB de resultados por partido. Las carpetas de partido del PC van de 0,33 GB (Osaka) a 1,75 GB (Zheng), sin contar el vídeo; pc-logs no da el tamaño de la biblioteca.
  - Los 6 partidos: **~40 GB**.
  - R2 cobra ~0,015 $/GB-mes y 0 $ por descargar (los primeros 10 GB gratis) → **~0,5 $ al mes**. Backblaze B2 cuesta ~6-7 $/TB-mes ([comparativa R2/B2](https://mecanik.dev/en/posts/cloudflare-r2-pricing-explained-real-costs-vs-s3-and-backblaze/), [infratally](https://infratally.com/articles/cloudflare-r2-vs-aws-s3-vs-backblaze-b2-2026/); precio visto el 13-11-2026, cambia; página oficial: [R2](https://developers.cloudflare.com/r2/pricing/)).

### 4.3 Cola y orquestación
Hoy (`docs/orquestador.md`): un grafo de etapas con cachés por huella, la cola SQLite con un ejecutor y las órdenes
submit/pause/resume/cancel/status. En la nube se conserva **el mismo modelo de trabajos y órdenes**; cambia solo dónde
vive la cola y quién ejecuta:

| Opción | Encaje | Contra |
|---|---|---|
| **Modal** (funciones Python con `gpu=`, `.map()` para repartir, colas y diccionarios duraderos, volúmenes, tareas programadas, endpoints web, secretos) | El más directo: el código sigue siendo `tennisbio`, con una capa fina; se apaga solo | Atado a Modal (mitigable: la capa es fina); GPU interrumpibles; región fija con recargo |
| Temporal / Prefect (orquestador) + contenedores con GPU | Flujos duraderos de verdad (reintentos, pausas largas para el clic) | Un servidor más que mantener; para un usuario sobra |
| AWS Step Functions + Batch (g6 con L4, spot) + S3 | Estándar, región UE, contratos de protección de datos | Más piezas y configuración; la GPU puede tardar en arrancar |
| GCP Workflows + Cloud Run jobs con GPU L4 + GCS | Contenedores que se apagan solos, factura por segundo | GPU solo en algunas regiones (comprobar UE); cuota de GPU a pedir |

La regla del orquestador único se mantiene: **una cola, un código, unos datos** para la web y para Claude. El trabajo
que hoy pide un `paso` del flujo pasa a ser una llamada a la etapa en un contenedor. Las huellas deciden qué se rehace,
como ahora.

### 4.4 Cómputo y paralelismo
- **Proveedor de ONNX Runtime:**
  - CUDA, el directo;
  - TensorRT, más rápido pero hay que validarlo: puede usar FP16 y cambiar decimales, como el FP16 que hoy está apagado hasta validarse (`pose/backend.py`) ([proveedores de ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/)).
- **GPU adecuada:** L4 (24 GB) basta para estos modelos (RTMPose-x, TrackNetV3, YOLO). L40S, A100 o H100 serían para modelos grandes (§6).
- **Paralelismo:**
  - **por partido**: los 6 a la vez;
  - **por ventana en la pasada fina**: 232 ventanas en Osaka; la ventana ya es una unidad aislada en `_fine_parallel`, así que se cambia el ejecutor, no el algoritmo;
  - **por plano de juego en el detector y en la pasada barata**: con solape en los bordes, porque TrackNet usa secuencias de fotogramas y los cortes de plano necesitan contexto.
  - **Con N contenedores, el tiempo de reloj baja aproximadamente N veces; las horas de GPU (el coste) no.**
- **Lo que no se paraleliza:** probe → scenes → court → players → identity (el clic) → candidates. La identidad necesita el clic: el trabajo se detiene en «espera el clic», se avisa al móvil y sigue al recibirlo. Mientras, los otros partidos avanzan.

### 4.5 Interfaz
- **Informe:** el HTML estático de hoy (`report_template.html`), publicado en el almacén detrás de Cloudflare Access (gratis hasta 50 usuarios según §8.1 de `arquitectura_producto.md`; precio a verificar). Los vídeos de cada golpe, a 720p con `faststart`, como ya hace `app/mobile.py`.
- **Aplicación:** la misma `ui.html` con las mismas llamadas, por HTTP: añadir partido (subida), clic de identidad, cola, aprobación con coste, informes, estado.
- **Móvil:** es la misma web, como aplicación instalable (PWA). La copia por cable deja de hacer falta.

### 4.6 Registros, avisos y seguridad
- Registros por trabajo y etapa al almacén. El estado (`orchestrator.status`) queda consultable por la web y por Claude.
- El fallo C0/C1 de #265 se avisa al momento al móvil y a Claude.
- Tope de gasto por trabajo y por mes, con aviso al 50 % y al 80 %, y corte al 100 %.
- Seguridad:
  - todo privado: sin enlaces públicos y URL firmadas de minutos;
  - secretos en el gestor de la plataforma;
  - cifrado en reposo (por defecto en estos proveedores);
  - región UE.

---

## 5. Opciones concretas y coste

### 5.1 Cuánta GPU hace falta: la cuenta

No hay ninguna medida de estos modelos en una GPU NVIDIA: es lo primero que mide N0. Mientras, se parte del tiempo
medido en el PC y de un factor de aceleración **k**, desconocido:

- Horas de PC por partido de 3,5 h (210 min): 210 × 2,2-3,3 / 60 = **7,7-11,6 h**.
- Horas de GPU por partido = horas de PC / k.

Referencias para k:
- La estimación de octubre (`arquitectura_producto.md` §8.2): pose y bola «10 a 15 veces» más rápidas en una L4 o una RTX 4090. **No está medida.**
- Off policy («Claude as a Tennis Coach», `docs/analisis_referencias.md`): unos 50 min de GPU L40S por 26 min de vídeo (1,9 veces el vídeo). Pero sus modelos van en PyTorch y sobre todo el vídeo, no en ventanas: no es comparable 1:1.
- Más del 80 % del tiempo del PC es inferencia en la iGPU (§3.1). El resto (decodificar, CPU) no se acelera con la GPU, pero sí se reparte.

| k (por medir) | GPU por partido de 3,5 h | GPU de los 6 (26-39 h de PC) |
|---|---|---|
| 1 (sin aceleración: cota de seguridad) | 7,7-11,6 h | 26-39 h |
| 3 | 2,6-3,9 h | 8,7-13 h |
| 5 | 1,5-2,3 h | 5,2-7,8 h |
| 10 | 0,8-1,2 h | 2,6-3,9 h |

Coste por hora de un contenedor con L4 (precio visto el 13-11-2026, cambia):

| Proveedor | L4 por hora | Fuente |
|---|---|---|
| Modal | ~0,80 $ (0,000222 $/s; CPU y memoria aparte; región fija con recargo de 1,5-1,75 veces según un agregador) | [morphllm](https://www.morphllm.com/modal-pricing), [beam.cloud](https://www.beam.cloud/blog/modal-pricing-explained); oficial: [modal.com/pricing](https://modal.com/pricing) |
| RunPod sin servidor (Flex, nivel 24 GB) | ~0,69 $ | [blog de RunPod](https://www.runpod.io/blog/runpod-slashes-gpu-prices-more-power-less-cost-for-ai-builders), [memetik, sept. 2026](https://www.memetik.ai/guides/runpod-pricing) |
| Google Cloud Run (GPU sola, sin redundancia zonal) | ~0,67 $ (0,0001867 $/s); ~1,05 $/h con CPU y memoria según Qovery | [Cloud Run pricing](https://cloud.google.com/run/pricing), [usage.ai](https://www.usage.ai/blogs/gcp/cloud-run-pricing/), [Qovery](https://www.qovery.com/blog/cloud-run-gpu-vs-gke-node-pool-self-host-open-weight-model) |
| AWS EC2 g6.xlarge | 0,80 $ bajo demanda (us-east-1), 1,02 $ (París); spot desde ~0,43 $ | [DoiT](https://www.doit.com/compute/compute/aws/us-east-1/g6.xlarge), [París](https://www.doit.com/compute/compute/aws/eu-west-3/g6.xlarge) |
| Vast.ai (mercado) | L4 ~0,33 $; RTX 4090 0,13-0,52 $ | [findstack](https://findstack.com/resources/runpod-vs-vast-ai), [gpu-cost](https://gpu-cost.pages.dev/provider/vast-ai/) |

**Coste estimado** (≈ 1 $/h por contenedor L4 con su CPU y memoria):

| | Probable (k = 3-10) | Peor caso (k = 1) |
|---|---|---|
| Un partido de 3,5 h | **~1-4 $** | ~8-12 $ |
| Los 6 partidos | **~3-13 $** (más ~1-2 $ de contenedores sin GPU para decodificar) | ~26-41 $ |
| Una validación F3Set completa | proporcional a sus 5 h de PC: ~0,5-2 $ | ~5 $ |
| Fijo al mes | ~0,5 $ de almacenamiento; ~0 $ de cómputo parado | |

Conclusión robusta: **el coste no es el problema**. Incluso sin ninguna aceleración, los 6 partidos cuestan unas
decenas de dólares. El crédito gratuito mensual del plan inicial de Modal (30 $ según [morphllm](https://www.morphllm.com/modal-pricing);
por verificar en la página oficial) cubriría el caso probable. Los problemas reales son:
- el trabajo de portar y validar;
- la subida;
- los derechos y la privacidad de los vídeos (§9);
- revertir la decisión del 17-10.

### 5.2 Gratuitas y públicas

| Opción | Qué da (visto el 13-11-2026, cambia) | ¿Sirve para esto? |
|---|---|---|
| Google Colab gratis | GPU (normalmente T4) sin cuota publicada; sesiones de ~12 h; **sin ejecución en segundo plano en el plan gratuito** (se para al cerrar la pestaña) ([gpuperhour](https://gpuperhour.com/blog/google-colab-alternatives); [FAQ oficial](https://research.google.com/colaboratory/faq.html)) | **No**: es interactiva; va contra el «100 % automático» y la cuota no está garantizada |
| Kaggle Notebooks | ~30 h/semana de GPU (T4 ×2 o P100), sesiones de 12 h; la cuota «flota» y no está en su documentación ([gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits)) | **Solo para experimentos con datos públicos** (p. ej., F3Set), lanzados por su API. **No para las retransmisiones** (privacidad, condiciones de uso) ni como servicio fiable. 30 h/semana cubriría en teoría el caso probable de los 6, pero en T4 y sin garantías |
| Hugging Face Spaces / ZeroGPU | Cuenta gratuita: ~5 min de GPU al día; PRO puede pagar el exceso (1 $ por 10 min) ([foro de HF](https://discuss.huggingface.co/t/what-is-the-free-zerogpu-quota-for-1-space/178610), [cambios del 10-04-2026](https://api-inference.huggingface.co/changelog/zerogpu-overquota)) | **No**: pensado para demos cortas |
| Oracle Cloud Always Free | Máquinas ARM sin GPU (por verificar las cifras actuales) | Solo para alojar la web de control; no para el cómputo |
| GitHub Actions (alojado) | CPU | Ya sirve para las pruebas unitarias; no para la inferencia |
| Cloudflare R2 + Access + Pages/Workers | 10 GB y operaciones gratis al mes; descarga gratis | **Sí**, para el almacén y el informe (la opción A de octubre) |

**Conclusión:** lo gratuito vale para guardar y servir el informe (R2, Access) y para experimentos con datos públicos
(Kaggle). **Ninguna GPU gratuita sirve para análisis automáticos de las retransmisiones.**

### 5.3 De pago, sin servidor (se apagan solas, por segundo)

| Proveedor | A favor | En contra |
|---|---|---|
| **Modal** | Python nativo (decoradores sobre funciones), `.map()` para repartir ventanas, volúmenes, colas, tareas programadas, web, secretos; crédito mensual gratis; L4 ~0,80 $/h | GPU interrumpibles (encaja con los reintentos C3 y las cachés); región UE con recargo; plataforma propia |
| RunPod sin servidor | L4 ~0,69 $/h; trabajadores que se apagan; imágenes Docker | Pensado para una función de inferencia; el flujo largo con ffmpeg y cachés hay que montarlo encima |
| Beam, Baseten, Cerebrium, Replicate, fal | Parecidos (imagen + GPU por segundo) | **Precios no verificados hoy**; Replicate y fal están orientados a servir un modelo con API, peor encaje para un análisis de horas por etapas |

### 5.4 GPU por horas (máquina alquilada)

| Proveedor | Precio (visto el 13-11-2026, cambia) | Comentario |
|---|---|---|
| Vast.ai | L4 ~0,33 $/h; 4090 desde 0,13 $/h (mercado) | El más barato, pero **las máquinas son de terceros**: mal sitio para retransmisiones; solo con su nube «segura» |
| Hetzner GEX44 (RTX 4000 Ada 20 GB, dedicado) | 184 €/mes al lanzarse (+79 € de alta); su página de ajuste de precios muestra 232,30 €/mes ([GEX44](https://www.hetzner.com/dedicated-rootserver/gex44/), [ajuste](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)) | En la UE, fijo 24 h: **caro para pocos partidos** (lo que cuestan cientos de partidos sin servidor); sería un «PC en la nube» siempre encendido |
| Lambda, Paperspace, Scaleway, OVH | Sin precio verificado hoy para GPU pequeñas | Mismas cuentas que arriba; sin ventaja clara para un usuario |

### 5.5 Hiperescalares

| Proveedor | Pieza | Precio (visto el 13-11-2026, cambia) | Comentario |
|---|---|---|---|
| AWS | Batch + EC2 g6 (L4) spot + S3 | g6.xlarge 0,80 $/h bajo demanda (us-east-1), 1,02 $/h en París, spot ~0,43 $/h; g6e (L40S) 1,86 $/h ([opslyft](https://www.opslyft.com/blog/aws-gpu-pricing)) | Muy completo, región UE; más configuración (redes, permisos, imagen) |
| Google Cloud | Cloud Run jobs con GPU L4 + GCS + Workflows | 0,0001867 $/s de GPU (~0,67 $/h) más CPU y memoria | Contenedores que se apagan solos; comprobar L4 en región UE y la cuota |
| Azure | Container Apps con GPU sin servidor (T4, A100) | Por segundo; la página oficial no mostró el importe hoy ([precios](https://azure.microsoft.com/en-us/pricing/details/container-apps/), [regiones](https://docs.azure.cn/en-us/container-apps/gpu-serverless-overview): West US 3, Australia East, **Sweden Central**) | Sin L4; T4 más lenta y A100 sobredimensionada |

### 5.6 Híbrido: el PC sigue y la nube ayuda

| Variante | Qué hace la nube | Qué gana | Qué cuesta |
|---|---|---|---|
| H1: validaciones | F3Set y RacketVision por cambio, en paralelo (datos públicos) | Una validación por cambio sin bloquear el PC (causa 5 de #267) | Portar el motor a CUDA + **validar que la nube da lo mismo que el PC** |
| H2: etapas pesadas | El PC sube el vídeo; la nube hace detector + pasada fina; el PC recibe los resultados | Partidos en ~1-2 h | Los vídeos salen de casa; dos dispositivos que deben dar lo mismo |
| H3: informes | Solo publicar el informe (opción A de octubre) | Móvil sin copias | Casi nada |

---

## 6. Qué mejora el estado del arte si hay GPU de verdad

Regla: **calidad antes que velocidad**. Cada modelo se mide frente al actual con datos anotados (F3Set: 517 golpes,
precisión 0,945, 467 encontrados con v15; RacketVision; los partidos con su auditoría) y solo se adopta si gana.

| Candidato | Qué es (fuente, visto el 13-11-2026) | Qué arreglaría aquí | Cómo se validaría | Por qué hoy no |
|---|---|---|---|---|
| Pasada barata a resolución completa + RF-DETR para personas | Detección más fina de la jugadora lejana (~70 px) | **R27**: el detector de golpes nunca tuvo a la jugadora lejana (~0,1 % del juego); con ella, reentrenarlo daría más golpes del fondo (B4) | F3Set por lado (lejano), sin bajar la precisión | Coste: RF-DETR era 2,6 veces más lento para 2 golpes de 517 (R3) |
| Bola: TrackNetV4 (ICASSP 2025; F1 de 97,1 a 97,5 sobre TrackNetV2 en su conjunto de tenis) y TOTNet (2025; con oclusiones; RMSE de 37,3 a 7,19 en 4 conjuntos) ([TrackNetV4](https://arxiv.org/abs/2409.14543), [TOTNet](https://arxiv.org/abs/2508.09650)) | Seguimiento de la bola | Golpes perdidos en oclusión; la «bola y ella»; dirección y profundidad (M5) | Golpes de F3Set y error de posición en los clips de RacketVision | No hay pesos de tenis listos en ONNX; entrenarlos pide GPU |
| Detector de golpes de vídeo de extremo a extremo: F3ED (ICLR 2025, base de F3Set), T-DEED, UMEG-Net (AAAI-26, esqueleto + puntos de objetos en un grafo) ([F3Set](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1c8e2cd11daf2d0a8c68663d504a841d-Abstract-Conference.html), [UMEG-Net](https://arxiv.org/html/2511.14186v1), [2026](https://arxiv.org/pdf/2604.22839)) | Encontrar golpes y su tipo en todo el vídeo | B4 (golpes perdidos, saques en los cambios de juego); tipo de golpe (M6) | F3Set (mismos 517 golpes; Off policy avisa de que F3ED pierde la mitad a 50/60 fps → a 25 fps) | Correr un modelo de vídeo sobre 3,5 h en la iGPU es inviable |
| Pose: Sapiens2 (Meta, ICLR 2026, 0,4-5 mil millones de parámetros, alta resolución) y CIGPose (CVPR 2026, 67,0 AP en COCO-WholeBody) ([Sapiens2](https://www.marktechpost.com/2026/04/27/meta-ai-releases-sapiens2-a-high-resolution-human-centric-vision-model-for-pose-segmentation-normals-pointmap-and-albedo/), [CIGPose](https://openaccess.thecvf.com/content/CVPR2026/html/Li_CIGPose_Causal_Intervention_Graph_Neural_Network_for_Whole-Body_Pose_Estimation_CVPR_2026_paper.html)) | Esqueleto (y manos y pies) más preciso | Pies y apoyos (M2), muñeca y mano (M4), jugadora lejana; pose en el contacto (R10) | Estabilidad entre golpes casi iguales (ruido de medida); CalTennis (multivista) para pies y giros | Un modelo de 1.000 millones en la iGPU, por fotograma, multiplicaría el tiempo; RTMW-x ya no ganaba (R3) |
| 3D del cuerpo en el mundo: GVHMR (SIGGRAPH Asia 2024, marco con gravedad), PromptHMR-Vid, SAM 3D Body (Meta, 19-11-2025, con seguimiento de SAM 3; SAM-Body4D, dic. 2025) ([GVHMR](https://zju3dv.github.io/gvhmr), [PromptHMR](https://alphaxiv.org/overview/2504.06397v2), [SAM 3D Body](https://rerun.io/examples/video-image/sam3d_body), [SAM-Body4D](https://arxiv.org/abs/2512.08406)) | Malla 3D del cuerpo por vídeo | Giros de cadera y hombros, X-factor (fiabilidad «media»); impacto delante/detrás (hoy «mala»); cadena cinética (M1) | CalTennis (multivista, `docs/analisis_referencias.md`) y la vista lateral de entreno (#254): que el 3D coincida con lo visto de lado | Modelos pesados en PyTorch; en la iGPU no son viables por ventana |
| Seguimiento por máscara: SAM 2 / SAMURAI (memoria con movimiento, sin reentrenar), SAM 3 ([SAMURAI](https://arxiv.org/abs/2411.11922)) | Seguir a una persona dentro de un plano aunque se cruce o se tape | R10 (el seguimiento saltaba a la persona de un primer plano); parte de R29 (dentro de un plano). **No** reconoce a la misma persona entre planos (no es reidentificación) | Golpes con su pose en el contacto (≥ 95 %); identidad frente a F3Set (489 bien y 5 mal de 494) | Coste por fotograma |
| Raqueta en el impacto | — | **Nada**: el desenfoque es de la cámara (25-50 fps). La cara en el impacto sigue siendo una estimación marcada como tal | — | — |
| Más validación | F3Set completo (114 partidos, 11.584 clips) en vez de 4 compilaciones; RacketVision entero | Medidas con verdad (nivel 4 de `estado_real_partidos.md`: hoy 0 peticiones) | Es la validación | 5 h de PC por pasada |
| Entrenar con GPU | El detector propio se entrena hoy en CPU (`scripts/train_spotting.py`) | Reentrenarlo con más datos y con la jugadora lejana | F3Set | Lento en CPU |

Ninguna de estas mejoras está medida en este proyecto. La tabla dice qué medir primero, no qué adoptar. Orden por
lo que más pesa en la Base:
1. Detector con la lejana (R27/B4).
2. Seguimiento por máscara (R10).
3. 3D (M1/M3).
4. Bola (M5).
5. Pose grande (M2/M4).

---

## 7. Qué habría que cambiar del código (sin implementarlo)

Tamaño relativo: **S** = un módulo, cambio localizado con su prueba; **M** = varios módulos y pruebas nuevas;
**L** = pieza nueva.

| Módulo | Cambio | Tamaño | Riesgo |
|---|---|---|---|
| `pose/estimator.py`, `pose/backend.py`, `pose/yolo.py`, `pose/rtmw.py`, `pose/wholebody3d.py`, `pose/motionagformer.py`, los de bola, raqueta y pista | Dispositivo `cuda`/`tensorrt` junto a `dml`/`cpu`/`openvino` | S | Decimales distintos: equivalencia obligatoria (§9) |
| `pyproject.toml` | `onnxruntime-gpu` en Linux con GPU (marcador de plataforma o extra `nube`), sin tocar Windows | S | Versiones de CUDA y cuDNN en la imagen |
| `io/video.py` | Opcional: decodificación por NVDEC y desentrelazado en GPU; lectura de un tramo del almacén (rango de bytes) | S-M | Huella WINDOW_CODE: un cambio aquí invalida las cachés (ya pasa hoy) |
| `stages._fine_parallel` / `_fine_worker` | El ejecutor de procesos pasa a ejecutor remoto (una tarea por ventana); el resultado y sus fallos (`r["faults"]`) se juntan igual | M | Que el resultado sea idéntico al serie: prueba de determinismo |
| `ball_features.cached_track`, spotting, scenes, players, score | Repartir por planos de juego con solape | M | Bordes de los tramos: prueba de que el resultado es igual al de una pasada |
| `pipeline.Context.path`, `match_files`, `library.py` | Almacén de objetos (montado o sincronizado por etapa) en vez de disco local | M | Escritura atómica y lecturas a medias; el manifiesto como fuente de verdad |
| `orchestrator.py`, `app/jobs.py`, `app/db.py` | Las mismas órdenes con la cola de la plataforma; estado «espera el clic» | M-L | Una sola fuente de verdad; nada se ejecuta dos veces |
| `app/window.py` → web | `ui.html` y `Api` por HTTP, con autenticación | M | La memoria de la app (R8: 1,45 GB) deja de importar en el servidor, pero sí en el móvil |
| `app/identity_click.py` | La misma página de fotos en la web + aviso al móvil | S | — |
| `app/mobile.py`, `app/phone.py`, `app/backup.py`, `app/storage.py`, `scripts/windows/*` | Desactivados en modo nube (nunca borrados) | S | — |
| `budget.py` | Ritmos por **dispositivo** además de por versión (como R21): «medido en la iGPU» no vale para la L4 | S | Previsión engañosa si se mezclan |
| `stage_code` y huellas de cachés | El dispositivo en la huella de pose y bola | S | Recalcular todo una vez al cambiar de dispositivo (es lo correcto) |
| `config/local.yaml` | Configuración del despliegue (almacén, región, tope de gasto) | S | — |
| Canal de registros (`pc-logs`) | Registros y estado en el almacén; acceso de Claude con credencial | S-M | Nunca registros con datos personales fuera del almacén privado |
| Nuevo: capa de la plataforma (`cloud/…`) | Imagen, funciones por etapa, reparto, tope de gasto, avisos | L | Atadura a la plataforma (mantenerla fina) |

**Lo que queda idéntico:**
- las etapas y sus versiones;
- los contratos de datos (`contracts.py`) y el modelo de fallos C0-C4 (`faults.py`, `config/fallos.yaml`). Las GPU interrumpibles caen en `gpu.perdida` (C3, reintento) y las cachés hacen que se siga donde se quedó;
- la auditoría, el informe, la exportación y los flujos (`config/flujos.yaml`).

**Pruebas:**
- Las 1200 pruebas unitarias siguen en CPU (como hoy en la nube de Claude).
- Se añade una **prueba de referencia con GPU** antes de cada versión, el mismo criterio que la tabla «Referencia (golden)» de `arquitectura_producto.md` §9.1:
  - el tramo de 35 min: mismos golpes;
  - F3Set: 467 de 517, precisión 0,945;
  - identidad: 489 bien y 5 mal;
  - Osaka y Pegula: su auditoría.
- La regla «0 fallos antes de subir» se mantiene.

---

## 8. Plan por fases (sin fechas; cada fase con su prueba de aceptación)

| Fase | Qué | Aceptación (calculada, no a mano) | Tamaño |
|---|---|---|---|
| **N0: medir** | Los modelos ONNX de hoy en una L4 de alquiler (Modal o similar) con el tramo de 35 min y una compilación de F3Set; sin tocar el PC | k medido por etapa; **los mismos golpes** que el PC en el tramo; medidas dentro del ruido (≤ 0,25 px, como se validó el FP16); coste real anotado | S (pocos dólares) |
| **N1: un partido sin interfaz** | Imagen con `tennisbio`, almacén, `tennisbio run` de un partido en la nube, informe estático | La auditoría de Osaka igual que en el PC: identidad, saques ≥ 85 %, bola ≥ 90 % del juego, pose en el contacto, «Fallos por niveles» con 0 C0 y 0 C1; tiempo y coste medidos | M |
| **N2: repartir** | Pasada fina por ventana y detector por planos, en paralelo | `strokes.json` idéntico al de la ejecución en serie (prueba de determinismo); tiempo de reloj medido | M |
| **N3: cola, web y Claude** | Cola duradera, web (subida, clic, aprobación con coste, estado), avisos, tope de gasto; Claude por la API | La prueba de extremo a extremo de B8 en la nube: enviar desde el chat, pausar en la web, reanudar desde el chat; un partido nuevo de principio a fin desde la web (como 10b) | L |
| **N4: validaciones en paralelo** | F3Set y RacketVision por cambio, varias a la vez | Mismo número que en el PC con el mismo código; una validación por cambio en menos de 1 h (por medir) | M |
| **N5: modelos nuevos** | Los candidatos de §6, uno a uno, por N4 | Cada uno adoptado o descartado con su medida (como R3) | por modelo |
| **N6: móvil** | La web como aplicación instalable en el móvil | Capturas automáticas de cada pantalla en ancho de móvil sin fallos (P2/P6) | S-M |

**Encaje en el plan del proyecto** (Base B1-B8 → P0 → M1-M7 → P1-P6, el móvil al final):
- **Sin cambiar el orden** (lo que dice hoy `CLAUDE.md`): N0-N6 van en el paso 8, «Móvil/nube». N6 sustituye a P6.
- **Si el usuario lo decide**, N0 y N4 pueden ir **ya**, en la nube y en paralelo con el PC:
  - no tocan la cola del PC ni los partidos;
  - aceleran el cierre de la Base, porque las validaciones de R26 (F3Set v17: ~5 h) dejan de bloquear el PC.
  - N1-N3 tendrían sentido antes de P0: la aplicación nueva de P0 (#252) se diseñaría ya como web y no como ventana de Windows. Eso cambia el diseño de P0, así que también es decisión del usuario.

---

## 9. Riesgos y limitaciones

| Riesgo | Detalle | Mitigación |
|---|---|---|
| **Derechos de las retransmisiones** | Las grabaciones de TV tienen derechos. Subirlas a un tercero para un análisis privado no es lo mismo que guardarlas en casa; las condiciones de uso de los proveedores prohíben contenidos sin derechos. **No es asesoría legal**: es un riesgo que el usuario debe valorar | Almacén privado y cifrado, nunca público, sin compartir; borrar el vídeo tras el análisis (con el coste de no poder recalcular sin volver a subirlo); empezar por datos públicos (N0, N4) |
| Privacidad (RGPD) | Imágenes de personas identificables y datos del usuario | Región UE, contrato de tratamiento del proveedor, registros sin datos personales fuera del almacén |
| **Mismos resultados que el PC** | CUDA, TensorRT y DirectML no dan los mismos decimales (orden de operaciones, FP16). Hasta el más mínimo cambio puede mover un umbral (un golpe dentro o fuera) | Equivalencia obligatoria antes de adoptar (N0, N1); dispositivo en la huella de las cachés y en los ritmos; si la nube da distinto, se valida con F3Set como un modelo nuevo |
| Atadura a un proveedor | Modal es una plataforma propia | Capa fina (`cloud/…`); el motor sigue siendo `tennisbio` en una imagen Docker que corre en cualquier sitio |
| Gasto descontrolado | Un bucle de reintentos o un reparto mal hecho | Tope por trabajo y por mes; avisos; presupuestos de #265 (`reintentos.agotados`); la aprobación con coste previsto (#262) |
| GPU no disponible o interrumpida | Las de Modal son interrumpibles; las de spot también | Reintento C3 con cachés por etapa; varias GPU posibles (L4, A10G, L40S) |
| Subida lenta | 5 GB a 10 Mbps = 67 min | Subida reanudable; una vez por partido; recalcular no sube nada |
| Coste fijo escondido | Bases de datos o máquinas siempre encendidas | Todo con apagado automático; almacenamiento como único fijo (~0,5 $/mes) |
| Dos dispositivos que mantener | PC (DirectML) y nube (CUDA) | Decidir si el PC se queda; si se queda, la prueba de referencia corre en los dos |
| Licencias | Ultralytics (AGPL-3.0): uso privado sin distribuir | Si algún día lo usan otros como servicio, cambiar de modelo o publicar el código |
| «El PC no puede ser servidor» | Se cumple de sobra: el PC no hace nada | — |

---

## 10. Decisión recomendada y preguntas para el usuario

**Recomendación:**
1. **No mover el análisis de los partidos a la nube antes de cerrar la Base.** Los fallos abiertos son de algoritmo, y portar ahora retrasaría el cierre.
2. **Sí, ya (si el usuario aprueba gastar unos pocos dólares):**
   - **N0**: medir k y la equivalencia en una L4;
   - **N4**: validar F3Set en la nube en paralelo.

   Las dos usan datos públicos, no tocan el PC y atacan la causa principal de la lentitud del proyecto (una validación de 5 h por cambio).
3. **Después de la Base: nube completa** (N1-N3, N6) con **Modal + Cloudflare R2 + Cloudflare Access**:
   - coste probable de 1-4 $ por partido de 3,5 h y de 3-13 $ por los 6;
   - fijo de ~0,5 $ al mes;
   - el usuario solo sube el vídeo, hace un clic y aprueba.

   Alternativa si prefiere un proveedor grande con región UE y contratos: **Google Cloud Run (L4) + GCS**, o **AWS Batch (g6 spot) + S3**.
4. **El PC:** recomiendo mantenerlo como segundo dispositivo validado durante la transición (la prueba de referencia en los dos) y retirarlo cuando la nube haya dado lo mismo en los 6 partidos.

**Preguntas que solo puede decidir el usuario:**
1. ¿Se revisa la decisión del 17-10 («nada en la nube y nada de pago») y el orden del requisito 10? ¿Solo N0 y N4 ahora, o nada hasta el final?
2. ¿Tope de gasto al mes (p. ej. 10, 30 o 50 $)?
3. ¿Se aceptan las retransmisiones en un almacén privado de un tercero, en la UE? ¿Se guardan para poder recalcular o se borran tras cada análisis?
4. ¿El PC se queda como segundo dispositivo o se retira cuando la nube esté validada?

**Respuestas del usuario (13-11, más tarde):**
- La meta es pasar **todo** a la nube.
- Los vídeos **se suben y se borran al terminar**; si hace falta recalcular, se vuelven a subir.
- Motivo: el PC está al límite (iGPU al 99 % durante horas) y no lo puede usar.
- **Por ahora solo análisis: no se cambia nada.** Quedan sin decidir el tope de gasto y si el PC se retira; la tabla de §11 sirve para decidirlo.

---

## 11. Resumen de costes al mes y alternativas (13-11, tras la respuesta del usuario)

### 11.1 De qué depende el coste
- **Cómputo:**
  - Un partido medio de los 6 (119 min de vídeo) cuesta **4,4-6,5 h de PC** (2,2-3,3 veces el vídeo, medido).
  - Una validación de F3Set cuesta ~5 h de PC (v16).
  - En la nube: **horas de GPU = horas de PC / k**. k es la aceleración de una GPU L4 frente a la iGPU; **no está medida** (fase N0). Lo probable es 3-10 y el peor caso es 1.
- **Precio por hora de un contenedor L4 con su CPU y memoria** (visto el 13-11-2026, cambia; casi todo de agregadores, sin la página oficial):
  - **Modal ~1,12 $/h**: L4 0,80 $ + 4 núcleos × 0,047 $ + 16 GiB × 0,008 $. Con la región UE fijada, ×1,5-1,75 según un agregador.
  - **RunPod sin servidor ~0,69-0,75 $/h**: sus fuentes no coinciden.
  - **Google Cloud Run ~1,05 $/h**.
  - **AWS g6 spot ~0,45-0,6 $/h**: bajo demanda, 1,02 $ en París.
  - **Vast.ai ~0,33 $/h**.
- **Almacenamiento**, con «subir y borrar el vídeo al terminar»:
  - solo los resultados, 0,3-2 GB por partido, y los modelos; 10-40 GB en total;
  - R2: 10 GB gratis y 0,015 $/GB-mes después, sin coste por descargar → **0-0,5 $/mes**;
  - un vídeo de 5 GB guardado un día cuesta céntimos.
- **Guardar los vídeos en vez de borrarlos** costaría ~0,08 $/mes por partido en R2: los 6, ~0,45 $/mes. **Borrar es una decisión de derechos y privacidad, no de dinero.**
  - Lo que cuesta borrar es volver a subir el vídeo cuando cambie algo de la pasada barata o del detector: los 6 partidos, 30-40 GB, son ~1,3-1,8 h a 50 Mbps.
  - Lo que solo toca la pasada fina podría hacerse sin el vídeo entero si se guardan las ventanas de ±1 s (a medir cuánto ocupan).

### 11.2 Tres meses tipo (horas de PC → horas de GPU)
| Mes tipo | Qué incluye | Horas de PC | GPU, k = 3-10 | GPU, k = 1 |
|---|---|---|---|---|
| **Ligero** | 4 partidos nuevos | 18-26 h | 1,8-8,7 h | 18-26 h |
| **Uso + recálculo** | 4 nuevos y rehacer los 6 de la biblioteca una vez | 44-65 h | 4,4-22 h | 44-65 h |
| **Desarrollo** (como estas semanas) | 30 validaciones de F3Set (una por cambio), los 6 rehechos dos veces, 4 nuevos | 220-254 h | 22-85 h | 220-254 h |

### 11.3 Coste al mes por alternativa (en dólares; cómputo y almacenamiento; probable k = 3-10, entre paréntesis el peor caso k = 1)
| Alternativa | Fijo al mes | Ligero | Uso + recálculo | Desarrollo | Gratis incluido | Encaje |
|---|---|---|---|---|---|---|
| **Modal + Cloudflare R2 + Access** (recomendada) | 0 $ (plan gratuito) + R2 0-0,5 $ | **0 $** (0 $) | **0 $** (19-43 $) | **0-65 $** (216-254 $) | 30 $/mes de crédito, cada mes (~27 h de L4 con CPU y memoria) | Python nativo, reparto por ventana, se apaga solo, cola y web incluidas. Sin región UE fija; con ella, más caro |
| **RunPod sin servidor + R2** | 0 $ (+2 $ si usa su disco de red de 30 GB) | 1-7 $ (12-20 $) | 3-17 $ (30-49 $) | 15-64 $ (152-190 $) | No | Barato; pensado para una función de inferencia: la cola y los flujos hay que montarlos encima |
| **Google Cloud** (Cloud Run con L4 + almacenamiento GCS) | ~1 $ | 2-9 $ (19-27 $) | 5-23 $ (46-68 $) | 23-89 $ (231-267 $) | 300 $ una sola vez, 90 días. La cuenta de prueba no tiene GPU: hay que pasar a cuenta de pago, y según una guía se conserva el crédito | Región UE posible, contratos de protección de datos; más configuración; cuota de GPU a pedir |
| **AWS** (Batch con g6 spot + S3 + Step Functions) | ~1 $ (+0,09 $/GB descargado a partir de 100 GB) | 1-5 $ (8-16 $) | 2-13 $ (19-39 $) | 10-51 $ (99-152 $) | No (créditos solo por programas) | El más barato de los grandes con spot; el que más piezas y permisos pide |
| **Vast.ai + R2** | 0-0,5 $ | 0,6-3 $ (6-9 $) | 1,5-7 $ (15-21 $) | 7-28 $ (73-84 $) | No | El más barato, pero **las máquinas son de particulares**: mal sitio para retransmisiones; las máquinas desaparecen (menos automático) |
| **Hetzner GEX44** (servidor con GPU propio, UE) | **~200-250 €** (184-232 €/mes + 79 € de alta) | igual | igual | igual | No | Un «PC en la nube» siempre encendido: sin coste por hora, pero una sola GPU (sin reparto) y caro salvo uso intenso |
| **Solo gratis: Kaggle + Cloudflare** | 0 $ | — | — | Las validaciones de F3Set, quizá gratis | ~15-30 h/semana de T4 o P100 (cuota que flota, no publicada) | **Solo para datos públicos (F3Set)**: no para las retransmisiones ni como servicio automático fiable |

Lectura:
- **Con uso normal, la nube sale prácticamente gratis con Modal**: los 30 $ de crédito mensual cubren el cómputo probable de los meses «ligero» y «uso + recálculo».
- **El mes de desarrollo es el caro.** Lo es solo si la GPU acelera poco (k bajo). Por eso N0, medir k, va primero: con k = 5 el desarrollo saldría por ~20-30 $/mes con Modal, crédito ya descontado.
- **Hetzner** solo compensa con un uso muy intenso y continuo, que no es este caso.
- **Ninguna opción gratuita permanente** sirve para analizar las retransmisiones sin intervención:
  - Colab necesita la pestaña abierta.
  - Kaggle sirve para datos públicos.
  - Hugging Face ZeroGPU da minutos al día.
  - Lightning AI pasó en septiembre a un crédito único de 30 créditos.
  - El crédito de Google es único y de 90 días.

### 11.4 Alternativas por pieza (gratis y de pago)
| Pieza | Gratis | De pago | Propuesta |
|---|---|---|---|
| Subida del vídeo | Subida por partes y reanudable a R2 desde el navegador (URL firmadas) | Igual en S3 o GCS (subir no cuesta en ninguno) | R2 |
| Almacén | R2: 10 GB gratis y descargas gratis | R2 0,015 $/GB-mes; S3 ~0,023 $ + 0,09 $/GB descargado; GCS similar; Backblaze B2 ~6-7 $/TB | R2 |
| Cómputo con GPU | Crédito mensual de Modal (30 $); Kaggle solo para F3Set | Modal, RunPod, Cloud Run, AWS Batch, Vast.ai, Hetzner (tabla 11.3) | Modal |
| Cola y orquestación | La de Modal (funciones, colas, tareas programadas) | Temporal Cloud, Prefect Cloud, AWS Step Functions, GCP Workflows | Modal (la misma plataforma; menos piezas) |
| Web (subir, clic de identidad, aprobar, informes) | Endpoints web de Modal, Cloudflare Pages/Workers | Cualquier servidor web | La `ui.html` de hoy servida por Modal o Pages |
| Acceso privado | Cloudflare Access (gratis hasta 50 usuarios, sin tarjeta) | Access desde 7 $/usuario/mes; IAP de Google; Cognito de AWS | Cloudflare Access gratis |
| Avisos al móvil (falta el clic, terminó, fallo C0/C1) | ntfy o un bot de Telegram | Pushover (pago único) | ntfy o Telegram |
| Registros y estado | En el propio almacén (R2) y la consulta de Modal | Grafana Cloud, Datadog | R2 + Modal (Claude los lee por API, sin `pc-logs`) |
| Pruebas | GitHub Actions (CPU) y la nube de Claude, como hoy | Una prueba de referencia con GPU por versión: céntimos en Modal | Igual que hoy + la de GPU |

**Total recomendado (Modal + R2 + Access + ntfy):**
- fijo **0-0,5 $/mes**;
- con uso normal, **0 $/mes de cómputo**, dentro del crédito;
- en un mes de desarrollo intenso, **0-65 $** si k es 3-10, y hasta ~250 $ si la GPU no acelerara nada (k = 1). Lo evita el tope de gasto y se sabe tras N0.

Fuentes añadidas el 13-11-2026:
- Modal: [plan gratuito con 30 $/mes, L4 y CPU/memoria por segundo (morphllm)](https://www.morphllm.com/modal-pricing), [beam.cloud](https://www.beam.cloud/blog/modal-pricing-explained), [usagepricing](https://www.usagepricing.com/blueprint/modal).
- Google Cloud: [prueba de Google Cloud sin cuota de GPU (foro de Google)](https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091), [programa gratuito oficial](https://docs.cloud.google.com/free/docs/free-cloud-features), [GPU en Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/gpu).
- RunPod: [precios oficiales sin servidor](https://docs.runpod.io/serverless/pricing), [producto](https://www.runpod.io/product/serverless).
- Kaggle: [cuota que flota (gpuperhour)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits).
- Lightning AI: [crédito único desde septiembre de 2026 (usagepricing)](https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice).
- Cloudflare: [Access gratis hasta 50 usuarios (blog de Cloudflare)](https://blog.cloudflare.com:8443/teams-plans), [límites del plan gratuito](https://zerometric.net/research/cloudflare-zero-trust-free-plan-limits-2026/), [R2 y su capa gratuita (withorb)](https://www.withorb.com/pricing-atlas/cloudflare).

---

## 12. ¿Cuándo pasar a la nube? (13-11, #271; la decisión es del usuario)

**Recomendación: cerrar la Base en el PC tal como está y pasar a la nube justo después, antes de P0 y de las medidas (M1-M7).**

Motivos:
1. **A la Base le falta poco:** R26 y R29 (hoy) y el análisis de los 6 partidos (26-39 h).
   - Portar ahora retrasaría ese cierre: N0 y N1 piden medir, montar y volver a validar F3Set y los partidos en CUDA.
   - Además mezclaría dos cambios a la vez (algoritmo y máquina), que es justo la causa 5 de #267.
2. **El análisis de los 6 en el PC es la referencia con la que se comprueba la nube** (N1: «la auditoría igual que en el PC»). Sin él, una diferencia en la nube no se sabría si es un fallo o una mejora.
3. **Lo que viene después de la Base es donde más pesa el PC y donde más gana la nube:**
   - P3 (validar cada medida con clips anotados);
   - M2 (ventanas más largas para los pasos tras el golpe);
   - M4, M6 (modelos o detectores nuevos, cada uno con su F3Set de ~5 h);
   - P0: la aplicación nueva nacería como web, en vez de rehacer una ventana de Windows que después sobraría.
4. **Mientras tanto, sin tocar el PC** y solo si el usuario lo aprueba (unos pocos dólares y una cuenta suya): **N0**, medir en una L4 la velocidad y que salgan los mismos golpes, con datos públicos. Así la migración se decide con números.

Lo que no conviene:
- Pasar a la nube **antes** de los 6 partidos: retrasa la Base y se pierde la referencia del PC.
- Hacer P0 y las medidas **con el PC**: lo pesado de esos paquetes (validaciones de ~5 h cada una) es lo que hoy deja el PC inutilizable. El 13-11, en la pasada fina, iba al 76-82 % de procesador y 18 de 19,8 GB de memoria.

**La nube de ahora (la de Claude)** no sirve para el cálculo pesado:
- 4 procesadores, 15 GB de memoria y sin GPU;
- se borra al terminar la sesión;
- no tiene los vídeos ni los datos de los partidos.

Vale para el código, las pruebas, los documentos y lo ligero.

---

## 13. Cómo se trabajaría, de forma autónoma, con 0-10 € al mes (13-11, #272)

Condiciones del usuario:
- todo automático, salvo algún paso puntual obligatorio;
- **no más de 10 € al mes**, y mejor 0.

### 13.1 El día a día
| Quién | Qué | Cómo |
|---|---|---|
| **Claude** | Escribe el código, lo prueba y lo sube a la rama | Como hoy |
| GitHub Actions (automático) | Al subir código, lo publica en Modal (`modal deploy`, unos segundos) | Un flujo de Actions con las claves de Modal guardadas en los secretos de GitHub |
| **Claude** | Lanza trabajos: validación F3Set, un partido, el informe | Dispara un flujo de GitHub Actions con las herramientas de GitHub que ya tiene. Sustituye a `config/peticion_pc.txt` |
| Modal (automático) | Ejecuta el trabajo; reparte la pasada fina por ventanas en varias GPU a la vez; se apaga al acabar | Las mismas etapas, contratos y fallos #265 |
| Modal (automático) | Deja el estado, la auditoría y los registros en una rama `nube-logs` (como `pc-logs` hoy) y en el almacén | Con un token de GitHub guardado en los secretos de Modal |
| **Claude** | Lee el resultado, corrige y vuelve a lanzar | Como hoy con `pc-logs`, sin esperar al ciclo de 10 min ni a que la cola del PC quede libre |
| **Usuario** | Por partido: sube el vídeo desde una web (PC o móvil), hace el clic de identidad y aprueba el análisis (#262) | Una página web privada |
| Móvil (automático) | Avisos: «falta el clic», «terminó», «fallo C0» | ntfy o Telegram, gratis |

No hace falta un conector nuevo: Claude usa GitHub, que ya está conectado. Para hablar directamente con Cloudflare (crear el almacén y las claves), existe el formulario seguro de credenciales de esta sesión: el usuario escribe ahí la clave y Claude nunca la ve.

### 13.2 Lo manual obligatorio (una sola vez, ~20-30 min guiados)
1. **Crear la cuenta de Modal** (con la de GitHub):
   - Las fuentes no coinciden en si pide tarjeta: algunas dicen que solo para pasar del crédito; otra, que los 30 $ se desbloquean con tarjeta y un cargo de verificación de 0,50 $.
   - **Poner el tope de la cuenta** («Workspace budget», en la página oficial de precios): 30 $ para gastar 0 €; ~41 $ para un máximo de ~10 € al mes.
   - Crear una clave de acceso y pegarla en los secretos del repositorio en GitHub.
2. **Crear la cuenta de Cloudflare:**
   - Según la comunidad de Cloudflare, R2 y el plan gratuito de Zero Trust (Access) **piden una tarjeta aunque no se cobre**.
   - Crear la clave del almacén y pegarla en los secretos.
   - Alternativa sin tarjeta: guardar en Modal y entrar con un enlace secreto. Es más sencillo, pero menos seguro y con límites de subida por verificar.
3. **Un token de GitHub** para que Modal suba los registros a `nube-logs`.
4. **ntfy o Telegram en el móvil** (opcional), para los avisos.

### 13.3 Coste con tope
| Pieza | Coste al mes | Por qué |
|---|---|---|
| Cómputo (Modal) | **0 €** hasta 30 $ de uso (crédito mensual); con el tope en 30 $ nunca se pasa | Uso normal: 5-25 $ si k = 3-10 (§11.3) |
| Almacén (R2) | **0 €** hasta 10 GB; después, céntimos | El vídeo se borra al terminar; los resultados ocupan ~0,3-2 GB por partido |
| Acceso privado (Access) | 0 € | Gratis hasta 50 usuarios |
| GitHub Actions | 0 € | Publicar y lanzar gasta pocos minutos. Gratis en repositorios públicos; en privados, ~2000 min/mes según terceros |
| Avisos | 0 € | ntfy o Telegram |
| **Total** | **0 € con el tope en 30 $; como mucho ~10 € con el tope en ~41 $** | |

**Dónde puede no llegar el crédito: un mes de desarrollo intenso** (30 validaciones de F3Set: 22-85 h de GPU si k = 3-10). Para seguir en 0-10 €:
- **Medir k primero (N0).** Cabe en el crédito, así que cuesta 0 €.
- **Validaciones escalonadas:**
  - una compilación de F3Set para comprobar rápido cada cambio;
  - las 4 compilaciones solo antes de aceptar.

  El criterio de aceptación no cambia.
- **F3Set en Kaggle**, gratis (~15-30 h/semana de T4 o P100; cuota que flota). Se lanza por su API (`kaggle kernels push`) desde GitHub Actions. Solo datos públicos; falta confirmar que la licencia de F3Set permite subirlo allí.
- **Si se llega al tope**, el trabajo se para (un C0 nuevo, «presupuesto del mes agotado») y sigue el mes siguiente. Nunca se cobra de más.

### 13.4 Lo que no cambia
- La aprobación del usuario antes de un análisis completo (#262), salvo que él decida otra cosa.
- Las pruebas antes de cada subida.
- El modelo de fallos, la auditoría y los criterios de aceptación.
- La nube se adopta solo si da lo mismo que el PC en F3Set y en los partidos (N0-N1).

Fuentes añadidas el 13-11-2026:
- Modal: [precios oficiales: 30 $ al mes y «Workspace budget»](https://modal.com/pricing); tarjeta: [aicreditmart](https://aicreditmart.com/ai-credits-providers/modal-startup-credits-how-to-get-up-to-25k-2026-guide/), [resourify](https://resourify.com/resources/modal); topes: [costbench](https://costbench.com/software/ai-gpu-cloud/modal/).
- Cloudflare: [R2 pide tarjeta (comunidad)](https://community.cloudflare.com/t/why-using-r2-free-tier-involves-giving-card-info/945179), [Zero Trust gratis con tarjeta (comunidad)](https://community.cloudflare.com/t/choose-the-zero-trust-free-plan-with-no-payment-method/471877).
- Kaggle: [API de kernels (oficial)](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md), [GitHub Actions + Kaggle (dev.to)](https://dev.to/yasumorishima/kaggle-code-competitions-without-a-local-gpu-github-actions-kaggle-api-cloud-workflow-m3).
- GitHub Actions: [minutos gratis (cicdcalculator)](https://cicdcalculator.com/github-actions-free-tier).

---

## 14. Segunda revisión de proveedores (13-11, #273) y la prueba de concepto en paralelo

La primera pasada (§5) **no fue completa**: casi todo salía de agregadores y quedaban proveedores sin mirar. Esta segunda
pasada parte de las condiciones del usuario (0 € al mes, todo automático, algún paso manual de una vez) y mira cuatro
cosas:
- **crédito gratis que se renueva** (no uno de una sola vez);
- **tope que corta de verdad** (no solo un aviso);
- **que se pueda automatizar del todo**;
- **garantías de los datos.**

Los proveedores grandes no dan ningún acuerdo de servicio (SLA) en sus planes gratuitos. Precios y condiciones vistos el
13-11-2026; cambian.

| Proveedor | Gratis que se renueva | Tope que corta | Automático | Datos | Veredicto para 0 € |
|---|---|---|---|---|---|
| **Modal** | **30 $/mes** (página oficial) | **Sí**: el «spend limit» limita el gasto neto tras el crédito; al llegar, Modal para lo que costaría dinero (documentación oficial) | Sí (CLI, API, GitHub Actions) | SOC 2 Type II; DPA con cláusulas tipo de la UE (RGPD). Región solo UE: no confirmada, y fijar región cuesta más | **El único que cumple las tres condiciones** |
| Beam | 30 $/mes según unas fuentes; 3 $/mes o 30 $ al registrarse según otras | Por verificar | Sí | Por verificar | Posible reserva; verificar en su página |
| Kaggle | ~15-30 h/semana de GPU (T4 o P100; cuota que flota) | No hace falta: es gratis | Sí: sesiones de 12 h sin pantalla, por su API | Sus condiciones; solo datos públicos | **Complemento para F3Set**, nunca para las retransmisiones |
| Cerebrium | 10-30 $ una sola vez (sin confirmar) | — | Sí | — | No (una vez) |
| Lightning AI | 30 créditos una sola vez (desde sept. 2026) | — | Parcial | — | No |
| Koyeb | Gratis cerrado a cuentas nuevas (tras su compra por Mistral) | — | — | — | No |
| Northflank | GPU con prepago de 50 $ | — | Sí | — | No |
| RunPod | Sin crédito gratis | Saldo prepagado (corta al acabarse) | Sí | — | No: cuesta dinero |
| Google Cloud | 300 $ una vez, 90 días; la cuenta de prueba no tiene cuota de GPU | **No**: los presupuestos solo avisan, y los topes nuevos (nov. 2026) no cubren cómputo ni almacenamiento | Sí | Región UE, contratos | No para 0 € |
| AWS | 100-200 $ una vez, 6 meses; el plan gratuito no cobra hasta pasar a pago | Sí mientras dura el plan gratuito | Sí | Región UE, contratos | No (temporal; la GPU pide cuota) |
| Azure | No verificado hoy | — | — | — | Sin datos |
| Colab gratis | Interactivo (se para al cerrar la pestaña) | — | **No** | — | No |
| SageMaker Studio Lab | **Cerrado a usuarios nuevos** | — | — | — | No |
| Paperspace gratis | Prácticamente desaparecido | — | — | — | No |
| Scaleway (UE) | No | — | Sí | UE (Francia y Polonia) | De pago: L4 desde 0,79 €/h, por horas enteras (oficial) |
| OVHcloud AI Training (UE) | No | — | Sí | UE | De pago: L4 0,91 $/h, por minutos (oficial) |
| Nebius (UE) | No | — | Sí | UE, RGPD | De pago (precios de terceros) |
| Vast.ai, SaladCloud | No | Saldo prepagado | Parcial | Máquinas de particulares | No para retransmisiones |

**Conclusión:**
- Con 0 € al mes, automático y con un tope que corta, la opción es **Modal**, con **Kaggle** como complemento gratis para las validaciones de F3Set.
- Para guardar y servir los resultados, **Cloudflare R2 y Access** (gratis con tarjeta registrada), o el propio Modal.
- Los proveedores europeos dan más garantías de datos, pero cuestan dinero.

### 14.1 La prueba de concepto (N0), en paralelo y sin tocar el PC
- **Qué:** la misma validación de F3Set v17 que hoy hace el PC (121), en una GPU L4 de Modal, con el mismo código.
- **Qué se mide:**
  - golpe a golpe frente al resultado del PC: los mismos golpes, la misma precisión y el mismo error de instante;
  - el tiempo de cada etapa, es decir, k;
  - el coste.
- **Cómo:**
  1. **Usuario, una vez (~15 min):**
     - cuenta de Modal con la de GitHub;
     - límite de gasto 0 $;
     - una clave en dos secretos de GitHub;
     - la misma clave una vez en el PC con un script de doble clic. Hace falta porque **YouTube no deja descargar desde centros de datos** (`scripts/validate_recall.py`) y las compilaciones de F3Set solo existen en el PC: se suben una vez (unos minutos, por la cola única).
  2. **Claude (~1 día de código):**
     - una carpeta `cloud/` fuera del paquete, que **no cambia nada de lo que corre en el PC**: ni huellas, ni versiones, ni dependencias de Windows. El proveedor CUDA se registra en tiempo de ejecución en `pose.estimator.ORT_PROVIDERS`, sin editar el fichero;
     - un flujo de GitHub Actions que lanza la validación y deja el informe en una rama `nube-logs`;
     - un script que compara la nube con el PC.
  3. **Ejecución:** con el crédito mensual (0 €).
- **Cuándo:** el código, ya, en paralelo; la ejecución, cuando estén la cuenta y la subida de F3Set. La subida va por la cola del PC detrás de la auditoría final (123) y no retrasa los 6 partidos.
- **Qué decide:** si la nube da lo mismo que el PC y con qué k. Con eso, N1 (los partidos en la nube) justo después de los 6.

Fuentes de esta revisión (13-11-2026):
- Modal: [precios oficiales](https://modal.com/pricing), [topes de gasto (oficial)](https://modal.com/docs/guide/budgets), [seguridad (oficial)](https://modal.com/docs/guide/security), [DPA](https://modal.com/legal/dpa), [residencia de datos](https://modal.com/docs/guide/data-residency.md), [SOC 2 Type II](https://modal.com/blog/soc2type2).
- Comparativas: [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits), [spheron](https://www.spheron.network/blog/free-gpu-cloud-credits-2026/), [dev.to: 9 proveedores](https://dev.to/heckno/i-tested-9-serverless-gpu-providers-for-ai-inference-in-2026-heres-what-id-actually-use-4cf4), [awesome-free-compute](https://amitpandeytiktok.github.io/awesome-free-compute-2026/compute.html).
- Beam: [precios](https://beam.cloud/pricing), [getdeploying](https://getdeploying.com/beam).
- Otros proveedores sin servidor: [Cerebrium](https://cerebrium.ai/pricing), [Koyeb](https://www.srvrlss.io/provider/koyeb/), [Northflank](https://www.stork.ai/en/northflank).
- AWS: [AWS Free Tier: 200 $ y plan gratuito](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/), [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).
- Google Cloud: [prueba sin cuota de GPU](https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091), [topes nuevos de Google Cloud (InfoQ)](https://infoq.com/news/2026/11/google-cloud-spend-caps), [presupuestos y topes (oficial)](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).
- Proveedores europeos de pago: [Scaleway GPU (oficial)](https://www.scaleway.com/en/choose-the-right-gpu/), [OVHcloud AI Training (oficial)](https://support.us.ovhcloud.com/hc/en-us/articles/35407103762323-AI-Training-Billing-and-lifecycle), [Nebius](https://gpuperhour.com/providers/nebius).

---

## Fuentes (vistas el 13-11-2026)
- Precios de GPU sin servidor:
  - Modal: [morphllm](https://www.morphllm.com/modal-pricing), [beam.cloud](https://www.beam.cloud/blog/modal-pricing-explained); oficial: [modal.com/pricing](https://modal.com/pricing).
  - RunPod: [blog](https://www.runpod.io/blog/runpod-slashes-gpu-prices-more-power-less-cost-for-ai-builders), [memetik](https://www.memetik.ai/guides/runpod-pricing).
  - Google Cloud Run: [precios](https://cloud.google.com/run/pricing), [usage.ai](https://www.usage.ai/blogs/gcp/cloud-run-pricing/), [Qovery](https://www.qovery.com/blog/cloud-run-gpu-vs-gke-node-pool-self-host-open-weight-model).
  - Azure: [precios](https://azure.microsoft.com/en-us/pricing/details/container-apps/), [GPU sin servidor](https://docs.azure.cn/en-us/container-apps/gpu-serverless-overview).
- Máquinas por horas:
  - AWS: [DoiT g6.xlarge](https://www.doit.com/compute/compute/aws/us-east-1/g6.xlarge), [París](https://www.doit.com/compute/compute/aws/eu-west-3/g6.xlarge), [opslyft](https://www.opslyft.com/blog/aws-gpu-pricing).
  - Vast.ai: [findstack](https://findstack.com/resources/runpod-vs-vast-ai), [gpu-cost](https://gpu-cost.pages.dev/provider/vast-ai/).
  - Hetzner: [GEX44](https://www.hetzner.com/dedicated-rootserver/gex44/), [ajuste de precios](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/).
- Gratuitas:
  - Colab y Kaggle: [gpuperhour (Colab)](https://gpuperhour.com/blog/google-colab-alternatives), [gpuperhour (gratis)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits), [FAQ de Colab](https://research.google.com/colaboratory/faq.html).
  - Hugging Face ZeroGPU: [foro](https://discuss.huggingface.co/t/what-is-the-free-zerogpu-quota-for-1-space/178610), [cambios](https://api-inference.huggingface.co/changelog/zerogpu-overquota).
- Almacenamiento:
  - R2 y B2: [mecanik](https://mecanik.dev/en/posts/cloudflare-r2-pricing-explained-real-costs-vs-s3-and-backblaze/), [infratally](https://infratally.com/articles/cloudflare-r2-vs-aws-s3-vs-backblaze-b2-2026/), [R2 oficial](https://developers.cloudflare.com/r2/pricing/).
  - Subida por partes: [AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html), [R2 URL firmadas](https://developers.cloudflare.com/r2/api/s3/presigned-urls/).
  - ONNX Runtime: [proveedores de ejecución](https://onnxruntime.ai/docs/execution-providers/).
- Modelos:
  - bola: [TrackNetV4](https://arxiv.org/abs/2409.14543), [TOTNet](https://arxiv.org/abs/2508.09650);
  - golpes: [F3Set/F3ED](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1c8e2cd11daf2d0a8c68663d504a841d-Abstract-Conference.html), [UMEG-Net](https://arxiv.org/html/2511.14186v1), [detección con pocos ejemplos 2026](https://arxiv.org/pdf/2604.22839);
  - pose: [Sapiens2](https://www.marktechpost.com/2026/04/27/meta-ai-releases-sapiens2-a-high-resolution-human-centric-vision-model-for-pose-segmentation-normals-pointmap-and-albedo/), [CIGPose](https://openaccess.thecvf.com/content/CVPR2026/html/Li_CIGPose_Causal_Intervention_Graph_Neural_Network_for_Whole-Body_Pose_Estimation_CVPR_2026_paper.html);
  - 3D: [GVHMR](https://zju3dv.github.io/gvhmr), [PromptHMR](https://alphaxiv.org/overview/2504.06397v2), [OnlineHMR](https://arxiv.org/abs/2603.17355), [SAM 3D Body](https://rerun.io/examples/video-image/sam3d_body), [SAM-Body4D](https://arxiv.org/abs/2512.08406);
  - seguimiento: [SAMURAI](https://arxiv.org/abs/2411.11922).
- Del repositorio:
  - `docs/arquitectura_producto.md` §8-9;
  - `docs/analisis_referencias.md` (Off policy, CalTennis);
  - `docs/estado_proyecto.md` (R2, R3, R10, R17, R21, R27, R28);
  - pc-logs: `ritmos.json`, `capturas_diag/tiempos_etapas.md`, `equipo.txt`, `prevision.md`.
