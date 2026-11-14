# Trazabilidad de la nube (T17, 14-11)

Cada requisito de `CLAUDE.md` y cada petición de la nube (#268-#291), frente al plan (`docs/estado_proyecto.md`,
«PLAN ÚNICO A SEGUIR»). Para cada uno: dónde se cumple, cómo se comprueba (prueba del código o comprobación de la
auditoría) y lo que falta. **Lo que falta se convierte en tarea del plan.** Se revisa en cada cambio de la nube.

## Requisitos de CLAUDE.md, en lo que toca a la nube

| Requisito | Dónde se cumple en la nube | Cómo se comprueba | Lo que falta |
|---|---|---|---|
| 1-2. Producto profesional, información y no tablas | El mismo código de análisis e informe que el PC (puertos y adaptadores: nada cambia según la máquina) | La auditoría de la nube (T11) con todas sus comprobaciones; la equivalencia entre infraestructuras | La pantalla nueva es P0, después de la Base |
| 3. Nada inventado; diferencias solo por encima del error | Un cambio de cómo o dónde corre un modelo solo se adopta si da lo mismo (`tennisbio.infra.equivalence`) | «Equivalencia entre infraestructuras»; `comparar_*` en la cola | — |
| 4. Cuerdas y cara de la raqueta | La raqueta es el modelo que más tarda: TensorRT FP16 solo si no mueve sus puntos (T6) | T6 mide los puntos movidos frente a CUDA FP32 | Leer T6 |
| 5. 100 % automático (y el clic de identidad) | La cola de GitHub lanza, vigila, relanza y cuenta el gasto; Claude retoma solo cada hora; el progreso se ve en vivo (#291) | «Cola de la nube», «Progreso visible», «Nada pide revisión manual» | Subir los vídeos y el clic, desde la web (paquete N) |
| 6. Sin fuentes externas | Los vídeos viven solo en el volumen privado de Modal; los cuadernos de Kaggle son privados (`is_private`) y la clave va en un conjunto de datos privado | `tests/test_kaggle.py` (metadatos del cuaderno) | — |
| 7. Partido completo solo con todo listo | `partidos_en_espera` hasta la fase B; cada partido tras su prueba de 10 min; aprobación del usuario (#262, `aprobado`) | `tests/test_cola.py` | — |
| 8. Cobertura de casos | Fallos por niveles C0-C4 (T12) también en la nube; contratos por etapa; pruebas de cada adaptador | `tests/test_faults.py`, `tests/test_cloud_checks.py`, `tests/test_discovery.py` | Pruebas de contrato por adaptador (T4: vídeo, almacenamiento, modelos) |
| 9. Rendimiento; código híbrido (#287-#289) | Descubrimiento de capacidades y puerto de inferencia (`device: auto`); pruebas de concepto medidas (T6, T7); recursos por etapa y por GPU (T2) | «Uso de la nube por etapa», «Prueba de concepto medida», «Tiempo desde cero» (B1: ≤ 8 h por partido de 3,5 h) | Fase B (T6-T9, T19); puertos de vídeo, almacenamiento y modelos |
| 10. Orden; nube a 0 €/mes; el usuario solo sube (se borran al terminar) | Topes de la cola (Modal 29,5 $ del crédito de 30 $; Kaggle 28 h de 30 h); el PC no se usa (#284) | `tests/test_cola.py` (gasto); `docs/capacidad_nube.md` | **Borrar el vídeo del volumen al aceptar el partido** (nueva tarea T22) |

## Peticiones de la nube

| # | Lo pedido | Dónde está | Comprobación | Estado |
|---|---|---|---|---|
| 268 | Analizar la aplicación entera en la nube | `docs/analisis_nube.md`, `docs/nube_nativa.md` | — | hecho (plan) |
| 270-271 | Qué queda de la Base; cuándo pasar a la nube | `docs/estado_proyecto.md` | — | hecho |
| 272, 280 | 0 € al mes | Topes de la cola; Kaggle gratis | `tests/test_cola.py` | se comprueba cada mes con la página de uso de Modal |
| 273 | Proveedores revisados a fecha de hoy | `docs/estado_del_arte_nube.md` §1 (segunda vuelta, 14-11) | — | hecho |
| 275, 284 | El PC parado; todo en la nube | `config/pausa_pc.txt`; la cola no ofrece el PC | `tests/test_cola.py` | hecho |
| 276 | R22 escrito como diferencia conocida | El informe | Auditoría | con los 6 partidos (T11) |
| 277 | Prueba corta antes de cada partido | `prueba_*` en la cola; C0/C1 → «revisar» | `tests/test_cola.py` | hecho |
| 278, 282 | Nada parado | Cola con latido; 2 sesiones de Kaggle (T20); Claude retoma cada hora | «Cola de la nube» | hecho en el código |
| 279, 283 | Un partido en horas, no 1-2 al mes | Kaggle (≈7 partidos por semana con las 28 h) + fase B | «Tiempo desde cero» | fase B en curso |
| 281 | Cola de trabajos en GitHub | `cloud/cola.py`, flujo «Cola» | `tests/test_cola.py` | hecho |
| 285 | Guía de Kaggle | `docs/kaggle.md` | — | hecho |
| 286 | B1, B7 y B8 para la nube | `config/plan_peticiones.yaml` | `tests/test_plan_peticiones.py` | hecho |
| 287 | Nube nativa, estado del arte | `docs/nube_nativa.md`, `docs/estado_del_arte_nube.md` | «Prueba de concepto medida» | fase B en curso |
| 288 | Decidir por pruebas de concepto medidas | T6, T7; acción «medir» | «Prueba de concepto medida» | en curso |
| 289 | Código híbrido, N infraestructuras | `tennisbio.infra` (descubrimiento, inferencia, equivalencia) | `tests/test_discovery.py`, `tests/test_equivalence.py` | en curso (T4) |
| 290 | Borrar los cuadernos atascados | `cuaderno.py borrar` | `tests/test_kaggle.py` | hecho |
| 291 | Cola asíncrona; progreso y estado en tiempo real | T21; latido separado de la vuelta | `tests/test_cola.py`, `tests/test_kaggle.py` | hecho en el código |

## Documentos internos

| Documento | Qué exige | Dónde está en el plan |
|---|---|---|
| `analisis_nube.md` §2 (requisitos) | Los de arriba | Esta tabla |
| `analisis_nube.md` §6-§8 (fases N0-N6) | Prueba de referencia con GPU antes de cada versión; repartir la pasada fina | T18, T19 |
| `analisis_nube.md` §9 (riesgos) | Derechos, privacidad, licencias | Abajo |
| `orquestador.md` | Una sola cola para todo | La cola de la nube es la única entrada (B8, «Cola de la nube») |
| `plan_maestro.md` bloque 1 | Detección de golpes con modelos entrenados con golpes anotados | Fase C (T15) |
| `matriz_cobertura.md` | Cada medida con su fuente | No cambia con la nube; la equivalencia garantiza las mismas medidas |
| `validacion.md` | Validación con clips públicos anotados | T15 (RacketVision y F3Set en Modal) |

## Riesgos (de `analisis_nube.md` §9)

- **Derechos de las retransmisiones:** los vídeos solo están en el volumen privado de Modal y pasan, de uno en uno, por
  sesiones privadas de Kaggle que se borran al acabar; nada se publica. Falta borrarlos del volumen una vez aceptado
  el partido (T22).
- **Privacidad:** ningún dato personal en los registros (`nube-logs` solo lleva estados, tiempos y gastos); la clave de
  Modal no sale del conjunto de datos privado de Kaggle ni de los secretos de GitHub.
- **Licencias:** Ultralytics (YOLO) es AGPL-3.0: vale para uso privado sin distribuir. Si la aplicación pasa a ser un
  servicio para otros, hay que cambiar ese modelo (RTMPose/RTMO son Apache-2.0; candidatos de la fase C).
