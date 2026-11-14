# Índice de documentos (11-11)

Cada documento tiene **un solo papel**. Si dos dicen cosas distintas, manda el **vigente** de su papel. Nada se borra
(decisión del usuario): lo sustituido lleva al principio «Histórico: sustituido por …».

## Vigentes: los que se siguen y se actualizan en cada cambio
| Papel | Documento | Qué contiene |
|---|---|---|
| Reglas | `../CLAUDE.md` | Requisitos del usuario, forma de trabajar de Claude, glosario (plan → paquete → tarea) |
| Estado y tarea actual | `estado_proyecto.md` (sección «Estado», arriba) | El paquete en curso, sus tareas en orden, qué hace el PC y qué hace Claude |
| Plan (todos los paquetes, en orden) | `../config/plan_peticiones.yaml` | Base B1-B8 → Medidas M1-M7 → Producto P1-P6; cada petición en un paquete y su prueba de cierre |
| Peticiones del usuario | `peticiones_usuario.md` | Las 251 peticiones con su estado y lo que falta (comprobado por `scripts/check_requests.py`) |
| Aceptación (calculada) | `pc-logs:estado_real_partidos.md` (de `scripts/real_status.py`) | Nivel real de cada petición y «¿Cerrado?» de cada paquete, desde la auditoría del PC |
| Taxonomía de la derecha | `matriz_cobertura.md` | Cada elemento del golpe con su fuente y si se mide (§6: la matriz del usuario de 15 puntos) |
| Diseño del orquestador | `orquestador.md` | Registro único, ejecutor único, flujos, órdenes desde la aplicación y el chat |
| Revisión de toda la Base (11-11) | `revision_base_11-11.md` | Por cada petición de B1-B8: si su prueba mide lo pedido, si falla cuando debe, datos desde cero y alternativas medidas (#260) |
| Flujos de trabajo del PC | `../config/flujos.yaml` | Los pasos de cada flujo (completo, informe, previsión, pruebas) |
| Aplicación | `aplicacion_local.md` | Pantallas, casos y comportamiento de la aplicación del PC |
| Almacenamiento | `almacenamiento.md` | Árbol de la biblioteca de partidos |
| Validación | `validacion.md`, `validacion_detector.md` | Cómo se valida cada medida y el detector con datos anotados |
| Velocidad | `pruebas_velocidad.md` | Cambios de velocidad, sus escenarios y lo medido |
| Plan de P0 (rehacer la aplicación) | `p0_plan.md` | Punto de partida, arquitectura, tareas P0.1-P0.6 y métricas de aceptación |

## Referencia: fuentes que alimentan las peticiones (se consultan; sus huecos ya son peticiones)
| Documento | Dónde están sus puntos en el plan |
|---|---|
| `comparacion_guia_ivanovic.md` (guía «Derecha estilo Ivanovic») | Peticiones #143 y #189-#198 → paquetes M2, M3, M4, M7 y P1 (después de la Base) |
| Matriz del usuario (15 puntos), `matriz_cobertura.md` §6 | Peticiones #84-#98 → paquetes M1-M7 y P1 (después de la Base) |
| `aprendido_entrenadores.md`, `investigacion_youtube_usuario.md`, `analisis_referencias.md`, `referencias_externas.md` | Contenido de «Cópiala/Aprende» (paquete P1) |
| `estado_del_arte.md`, `comparativa_apps.md` | Modelos (B3) y comparación con las apps profesionales (P4) |
| `escenarios_producto.md`, `arquitectura_producto.md`, `diseno_definitivo.md` | Producto (P2, P5) |
| `analisis_nube.md` (13-11, #268, #271-#273) | Toda la aplicación en la nube: análisis, costes, proveedores; decisión del usuario: paquete N tras los 6 partidos, 0 €/mes |
| `nube_n0.md` (13-11, #273) | Prueba de la nube (N0): pasos de una vez del usuario (Modal, GitHub, PC) y cómo se hace sin tocar el PC |
| `capacidad_nube.md` (14-11, R35, #278-#280) | Capacidad de la nube a 0 €: coste medido por partido, por qué la pasada fina va más lenta que en el PC, cómo se mide cada arreglo y Kaggle como segunda nube |
| `kaggle.md` (14-11, paso 8b, #283, #285) | Kaggle como segunda nube gratuita: guía para el usuario (una vez), qué requisitos cumple y cuáles faltan por medir, y cómo usa los datos de Modal sin repetir nada |
| `nube_nativa.md` (14-11, #287) | Rehacer para la nube lo que se decidió para el PC: dónde va el tiempo, infraestructura nativa de GPU (decodificar en la GPU, TensorRT, lotes, 2 T4) y cada modelo frente al estado del arte, medido con datos anotados |
| `estado_del_arte_nube.md` (14-11, #287, #289) | Revisión del estado del arte por capas (infraestructura, orquestación, vídeo en GPU, ejecución de modelos, modelos por tarea, datos, configuración, observabilidad, pruebas), con fuentes, candidatos y la prueba de concepto que decide cada uno; primera vuelta, con lo que falta |
| `operacion_nube.md` (14-11) | Para retomar en cualquier caso: dónde mirar, qué hace la cola sola y qué hace Claude ante cada fallo (Kaggle, Modal, pruebas en «revisar»), el modelo de validación y aceptación, y los riesgos abiertos |
| `maqueta-informe.html`, `maqueta_leccion_armado.html`, `maqueta_aplicacion.html` | Maquetas de diseño (datos inventados) |
| `matriz_en_la_web.md` | Generado por `scripts/matrix_in_web.py`: qué punto de la matriz se ve en la web |
| `como_ejecutar.md` | Instrucciones de instalación en el PC |

## Históricos: sustituidos (no se siguen; se conservan)
| Documento | Sustituido por |
|---|---|
| `plan_maestro.md` (19-10) | `config/plan_peticiones.yaml` + `estado_proyecto.md` |
| `plan_corto_plazo.md` (02-11) | `estado_proyecto.md` (sección «Estado») |
| `estado_real_peticiones.md` (copia del 07-11) | `pc-logs:estado_real_partidos.md` (se regenera en cada auditoría) |
| `revision_completa.md`, `revision_base.md`, `revision_peticiones_19-10.md`, `auditoria_17_10/` | Sus hallazgos ya son peticiones de `peticiones_usuario.md` |
