# Plan maestro (19-10): todo lo pendiente, en orden

Única lista de trabajo. La mantiene Claude: cada sesión empieza aquí. Cada bloque tiene un **criterio de cierre
medido por un script en el PC** (nunca «revisado en el chat»). Un bloque no se da por hecho sin ese número.
Regla del usuario (19-10): **nada nuevo hasta que la base (golpes que no se pierden e identidad) esté bien.**

## Estado y orden vigente (26-10) — leer primero

**Regla (26-10, tras el retrabajo):** primero una **referencia completa y medida** de los 4 partidos; nada que
cambie golpes se toca mientras se calcula; los cambios que obligan a rehacer la pasada fina se juntan en **una
sola tanda**; el resto (informe, medidas, aplicación) se valida contra la referencia y se recalcula desde la caché.
Un solo trabajo pesado del PC a la vez; la nube solo hace lo que no toca lo que corre.

| # | Qué | Dónde | Depende de | Criterio de terminado | Estado |
|---|---|---|---|---|---|
| R1 | Referencia: pasada definitiva de los 4 partidos con el detector (petición 55; la 54 se paró por la etapa `views` lenta) | PC | — | 4 partidos sin errores de etapa; golpes por partido | en marcha (Osaka hecho: 143 confirmados, 6 dudosos, 0 errores, 2,5 h) |
| R2 | Auditoría de la referencia: golpes por partido y situación, qué falta | PC (solo) + nube | R1 | `auditoria.md` leída; lista de huecos con números | — |
| N1 | Estudio de golpes perdidos en F3Set (petición 52: 64 % recall, 88 % precisión) | Nube (solo lectura) | — | % de la pérdida que es fallo nuestro, por causa | en paralelo |
| N2 | Lentitud de `score` y `court` (un salto por fotograma, como `identity` y `views`) | Nube | — (se aplica tras R1) | sin repetir esas etapas en los 4 partidos; tiempo medido en un partido nuevo | en paralelo |
| D1 | Una sola tanda de mejoras de detección, si R2 la pide | Nube + PC | R2, N1 | recall F3Set sube sin bajar precisión; una sola ejecución |pendiente. Incluye: (a) repeticiones que descartan de más (F3Set: 58 golpes, 11 %; Gauff: 144 de 488 candidatos, Zheng/Osaka 6-8 %); (b) `pose/yolo_onnx.py` NMS vacío → `IndexError` (1 golpe de Gauff); (c) etapa `views` aún lenta (final: 2991 fotogramas a ~11,7 s cada uno): medir antes con `medir_recursos.ps1` y desglosar lectura / modelo / pista |
| P1 | Peticiones pendientes por bloques (95 hechas, 94 a medias, 20 sin hacer) | Nube + PC (desde la caché) | R1 (y D1) | auditoría en verde por petición | — |
| A1 | Aplicación con los datos reales | PC (comprobación automática con capturas) | P1 | 0 fallos en todas las pantallas | — |
| M1 | Móvil (opcional, solo si lo pide el usuario) | — | A1 | — | — |

Conexión con el PC (27-10): el PC pasa a ser ejecutor de GitHub Actions (`4_conectar_github.bat` una vez,
`.github/workflows/pc.yml`): cada petición empieza al subirla y su registro está en Actions. El ciclo de cada
10 min (ahora mira GitHub cada minuto cuando está libre) sigue debajo como respaldo y para las paradas.

Validación (siempre automática): detección contra 648 golpes anotados de F3Set; partidos reales por golpes y
errores por partido; informe y medidas por la auditoría; aplicación por capturas en el PC; código por la batería
de pruebas antes de subir.

## Historial

## 0. En ejecución ahora
| | Qué | Estado | Siguiente |
|---|---|---|---|
| E1 | Análisis completo de los 4 partidos (petición 32) | Terminado 19-10 13:46 (14 h 15 min). Final: 129 golpes confirmados (muy pocos) | Hecho |
| E2 | Línea base F3Set con el código viejo (petición 34) | 0 de 613 golpes (0 %); 420 perdidos por «identidad sin decidir» | Hecho |
| E3 | F3Set con identidad por ropa y golpes dudosos (petición 35, sin el clic) | Terminado 20-10 02:43: 10 de 642 suyos (2 %) + 74 dudosos (13 % con ellos); pérdidas: identidad 299 (241 sin decidir, 58 equivocada), cámara principal 89, repetición 56, sin candidato 55, sin confirmar 34 | Base para medir el clic y el detector entrenado |
| E4 | Datos para entrenar el detector (petición 36, `entreno`): 4 partidos de prueba + 16 de entrenamiento de F3Set, solo números | En cola tras la 35 | La revisión horaria entrena en la nube en cuanto lleguen (`scripts/train_spotting.py`) |
| E5 | Vigilancia horaria del PC y del plan desde la nube | Activa; entrena y pide al PC lo siguiente sola | Se quita al cerrar el bloque 1 |

## 1. Base: no perder golpes e identidad (PRIMERO) — cambio de enfoque del 19-10
Decisión del usuario (19-10): hacerlo **como las aplicaciones profesionales**: modelos **entrenados con golpes
anotados**, no reglas escritas a mano; y **un clic por partido** para la identidad (excepción al «100 % automático»).

Criterio de cierre: `recall_validation.md` en el PC con **lado cercano > 90 % (saques incluidos)**, **lado lejano
contado** e **identidad > 95 %**, medido en partidos de F3Set que **no** se usaron para entrenar; y en cada partido
real el número de golpes cuadra con el esperado por el marcador (`point_count.py`).

1. **Identidad con un clic:** al añadir un partido, la aplicación enseña una foto de cada jugadora (los dos grupos
   de ropa del partido) y el usuario toca la suya. Se guarda en el catálogo (`config/matches.yaml`) y la etapa
   `identity` la usa como ancla; la ropa decide cada plano. En el banco de F3Set el clic se simula con un punto anotado.
2. **Detector de golpes entrenado (petición #204):** un modelo pequeño de detección de eventos sobre la secuencia del
   esqueleto de cada jugadora y la trayectoria de la bola (lo que el proceso ya calcula), entrenado en el procesador
   del PC con los golpes anotados de F3Set (instante, jugadora, tipo: saque / derecha / revés / volea). Separación
   por partidos: unos para entrenar y otros solo para medir. Sustituye a «candidatos + confirmación» (las reglas a mano).
3. **Saques, lado lejano y repeticiones** dentro del mismo detector (el saque y el golpe lejano son clases y lados
   del modelo); repeticiones y cámara principal se miden aparte con el mismo banco.
4. Medir tras cada paso contra F3Set y contra el marcador de los 4 partidos; nada se da por bueno sin ese número.

Hecho (19-10): el clic (`identidad_clic.json`, `identity.apply_pick`, panel «¿Cuál es ella?» en cada partido de la
aplicación; el banco lo simula); la recogida de datos en el PC (`scripts/spotting_data.py`, acción `entreno`) y el
entrenamiento en la nube (`tennisbio.spotting`, `scripts/train_spotting.py` → `models/spotting.onnx`).
Hecho (20-10): etapa `spotting` en el proceso, **apagada por defecto** (`spotter.enabled: false` en
`config/default.yaml`): con ella encendida, los candidatos de los dos lados salen del modelo (`spotting.json`) en vez
de las reglas, con la identidad de siempre (planos + clic); apagada, nada cambia (mismas huellas).
Pendiente: medirla de punta a punta en el PC (`validate_recall.py --spotter`, petición `recall` con `detector: si` →
`recall_validation_detector.md`) y, si supera a las reglas, encenderla por defecto.

## Plan en paralelo (20-10, «base completa acelerada»)

Tres carriles a la vez. El PC hace un trabajo pesado cada vez; la nube desarrolla y entrena mientras tanto.

| Id | Tarea | Carril | Depende de | Estado |
|---|---|---|---|---|
| P1 | Datos de entrenamiento a 10 fps (petición 38) | PC | — | en marcha |
| P2 | Datos a 25 fps + sonido completo (petición 39) | PC | P1 (compilaciones ya bajadas) | hecho: no mejora (63 % / 52 %), descartado |
| P3 | Diagnóstico de la cámara principal (cuartos AO 2023) | PC | C2 (cola) | hecho (41): la cámara se reconoce bien; el fallo es otro (¿anotaciones desfasadas?) |
| P4 | Medida de golpes F3Set de principio a fin con detector + clic simulado | PC | C1, C2, modelo ≥ 90 % (o el mejor) | pendiente |
| P5 | Pasada definitiva de los 4 partidos | PC | C1-C5 integrados, P4 en verde | pendiente |
| N1 | Reentrenar y medir cada vez que llegan datos (revisión cada 4 h) | Nube | P1/P2 | activo (cercano 62 %) |
| N2 | Bola como señal del detector (P2 no bastó: 25 fps dio 63 % cercano, 52 % lejano) | Nube + PC | N1 con P2 | en marcha (24-10): `ball_features`, petición 43 |
| C1 | Detector dentro del proceso (etapa `spotting`, apagado hasta pasar la medida) | Nube (agente) | — | en marcha |
| C2 | Cola de peticiones del PC | Nube (agente) | — | en marcha |
| C3 | Situaciones que faltan (bloque 3) | Nube (agente) | — (se validan con P5) | en marcha |
| C4 | Repeticiones y otras cámaras enlazadas (bloque 2) | Nube (agente) | — (se validan con P4/P5) | en marcha |
| C5 | Estructura de carpetas definitiva (bloque 4) | Nube (agente) | — | en marcha |
| I1 | Juntar C1-C5, pruebas completas, subir | Nube (Claude) | cada C al terminar | — |
| I2 | Cambio a la estructura nueva + migración | Nube → PC | C5, antes de P5 | conectada (24-10); se activa con la petición `migrar` antes de P5 |
| A1 | Aplicación y móvil con los 4 partidos reales (bloque 6) | Nube + PC | P5 | — |
| V1 | Velocidad (bloque 7) | Nube | — (tras P5 para medir) | — |
| R1 | Resto de peticiones (bloque 8), por tandas | Nube | según la petición | — |

Camino crítico: P1 → P2 → N1 (≥ 90 % cercano) → P4 → P5 → A1. Lo demás va en paralelo y se integra antes de P5.

## 2. La fuente son los partidos (#218, #219)
Criterio: en los 4 partidos, % de golpes con repetición enlazada y % con otra cámara enlazada, contado por script.
Hecho (20-10): etapas `views` (clasifica y enlaza cada toma que no es juego; `views.json`) y `views_link` (`views` y `slowmo_view` en `strokes.json`); la auditoría da el % por partido («Repeticiones y otras cámaras enlazadas»). Falta: validar los umbrales con los partidos reales, la pasada fina en la cámara lenta (`views.fine_on_slowmo`) y medir en las otras cámaras.
1. Repeticiones a velocidad normal y en cámara lenta: enlazarlas a su golpe en directo, estimar el factor de cámara lenta, usar sus fotogramas extra (impacto menos borroso).
2. Otras cámaras de la emisión (lateral, frontal, primeros planos): clasificar la vista, enlazar a su golpe y medir lo que esa vista permite (empuñadura, cara de la raqueta, impacto delante/detrás).

## 3. Situaciones que faltan (pedidas por el usuario)
Criterio: cada situación aparece en «Aprende» y en la auditoría con su número de golpes (o «sin golpes suficientes»).
1. Golpe angulado. 2. Bola corta baja cerca de la red. 3. Bola corta alta cerca de la red.
4. Volea a media pista con el swing de fondo (derecha o revés). 5. Volea fuera de la línea de saque.
6. Media volea / bote pronto: validarla con casos reales (hoy 0).

**Estado (20-10):** 1-5 construidos en `src/tennisbio/situations.py` y `technique.contact_type` (clases `shot_angle`,
`net_ball` y dos niveles nuevos de `contact_type`), cada uno condición de «Aprende», filtro de la videoteca y
ítem de la auditoría con su número de golpes (`audit.situation_items`); umbrales y por qué en el docstring de
`situations.py`; pruebas en `tests/test_situations.py`. Se corrigió la línea de saque (`technique.SERVICE_LINE_M`:
5,485 m desde su fondo, no 6,40). Falta: casos reales (pasada definitiva; la volea a media pista necesita rehacer
la pasada fina para tener la medida «bola seguida») y, para la media volea, clips reales anotados: la regla es
una sola y está probada con trayectorias sintéticas, pero la bola no deja ver un bote a menos de 0,06 s del impacto.

## 4. Almacenamiento definitivo
Especificación: `docs/almacenamiento.md` (árbol, nombres, colisiones, casos nominales/límite/esquina/error).
Criterio: pruebas automáticas de cada caso de la tabla + migración de lo existente sin recalcular.
Se hace antes del bloque 5 para que la pasada definitiva caiga ya en la estructura final.

## 5. Pasada definitiva de los 4 partidos
Con los bloques 1-4 cerrados; Osaka forzado (`rehacer`). Criterio: auditoría OK y recall por partido en verde.

## 6. Aplicación y móvil
1. Comprobar la aplicación con los 4 partidos reales (no con pruebas): cada pantalla, automático (`check.py`).
2. Móvil: opcional y al final, solo cuando el usuario lo pida (24-10: «nada de móvil todavía»). No se toca antes.

## 7. Velocidad
Hoy 67 min por 35 min de vídeo. Pose en la iGPU y menos trabajo repetido. Criterio: tiempo por partido en `pruebas_velocidad.md`.

## 8. Resto de la revisión de peticiones
`docs/revision_peticiones_19-10.md`: 112 PARCIAL y 25 FALTA. Los que no caen en los bloques 1-3 se cierran aquí;
la auditoría del PC los enseña siempre primero («Peticiones del usuario SIN TERMINAR»).

## Lo que el usuario tiene que hacer
Un clic por partido para decir cuál es ella (19-10) y conectar el móvil el día que quiera probar la copia. No decide detalles de implementación: Claude
elige la solución que cubre los requisitos y los escenarios, y la valida con números.
