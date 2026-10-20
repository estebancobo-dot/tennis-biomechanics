# Plan maestro (19-10): todo lo pendiente, en orden

Única lista de trabajo. La mantiene Claude: cada sesión empieza aquí. Cada bloque tiene un **criterio de cierre
medido por un script en el PC** (nunca «revisado en el chat»). Un bloque no se da por hecho sin ese número.
Regla del usuario (19-10): **nada nuevo hasta que la base (golpes que no se pierden e identidad) esté bien.**

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
| P2 | Datos a 25 fps + sonido completo (petición 39) | PC | P1 (compilaciones ya bajadas) | en cola |
| P3 | Diagnóstico de la cámara principal (cuartos AO 2023) | PC | C2 (cola) | pendiente |
| P4 | Medida de golpes F3Set de principio a fin con detector + clic simulado | PC | C1, C2, modelo ≥ 90 % (o el mejor) | pendiente |
| P5 | Pasada definitiva de los 4 partidos | PC | C1-C5 integrados, P4 en verde | pendiente |
| N1 | Reentrenar y medir cada vez que llegan datos (revisión horaria) | Nube | P1/P2 | activo (cercano 60 %) |
| N2 | Bola como señal del detector (si P2 no basta) | Nube + PC | N1 con P2 | preparado si hace falta |
| C1 | Detector dentro del proceso (etapa `spotting`, apagado hasta pasar la medida) | Nube (agente) | — | en marcha |
| C2 | Cola de peticiones del PC | Nube (agente) | — | en marcha |
| C3 | Situaciones que faltan (bloque 3) | Nube (agente) | — (se validan con P5) | en marcha |
| C4 | Repeticiones y otras cámaras enlazadas (bloque 2) | Nube (agente) | — (se validan con P4/P5) | en marcha |
| C5 | Estructura de carpetas definitiva (bloque 4) | Nube (agente) | — | en marcha |
| I1 | Juntar C1-C5, pruebas completas, subir | Nube (Claude) | cada C al terminar | — |
| I2 | Cambio a la estructura nueva + migración | Nube → PC | C5, antes de P5 | — |
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
2. Copia directa al Pixel 8: la prueba el usuario cuando quiera (único paso que necesita su mano: conectar el cable).

## 7. Velocidad
Hoy 67 min por 35 min de vídeo. Pose en la iGPU y menos trabajo repetido. Criterio: tiempo por partido en `pruebas_velocidad.md`.

## 8. Resto de la revisión de peticiones
`docs/revision_peticiones_19-10.md`: 112 PARCIAL y 25 FALTA. Los que no caen en los bloques 1-3 se cierran aquí;
la auditoría del PC los enseña siempre primero («Peticiones del usuario SIN TERMINAR»).

## Lo que el usuario tiene que hacer
Un clic por partido para decir cuál es ella (19-10) y conectar el móvil el día que quiera probar la copia. No decide detalles de implementación: Claude
elige la solución que cubre los requisitos y los escenarios, y la valida con números.
