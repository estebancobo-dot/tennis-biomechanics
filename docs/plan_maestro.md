# Plan maestro (19-10): todo lo pendiente, en orden

Única lista de trabajo. La mantiene Claude: cada sesión empieza aquí. Cada bloque tiene un **criterio de cierre
medido por un script en el PC** (nunca «revisado en el chat»). Un bloque no se da por hecho sin ese número.
Regla del usuario (19-10): **nada nuevo hasta que la base (golpes que no se pierden e identidad) esté bien.**

## 0. En ejecución ahora
| | Qué | Estado | Siguiente |
|---|---|---|---|
| E1 | Análisis completo de los 4 partidos (petición 32) | Terminado 19-10 13:46 (14 h 15 min). Final: 129 golpes confirmados (muy pocos) | Hecho |
| E2 | Línea base de golpes perdidos e identidad contra F3Set (petición 34, `validate_recall.py`; la 33 la ignoró el ciclo viejo) | En cola desde 19-10 14:28 | Claude lee `recall_validation.md` (lectura programada) |
| E3 | Vigilancia horaria del PC desde la nube | Activa | Se quita al cerrar el bloque 1 (ahorro de tokens) |

## 1. Base: no perder golpes e identidad (PRIMERO)
Criterio de cierre: `recall_validation.md` en el PC con **lado cercano > 90 % (saques incluidos)**, **lado lejano
contado** (todos detectados; medido lo que la distancia permite) e **identidad > 95 %**; y en cada partido real el
número de golpes cuadra con el esperado por el marcador (`point_count.py`; si no, la auditoría lo marca en rojo).

1. Medir la línea base (E2): pérdida por lado, por tipo y por paso donde se pierde.
2. Identidad por ropa (hecho en rama local `fix-identity-clothes`, 13 pruebas): subir y medir contra la línea base.
3. Saques (antes 1 de 15 en F3Set): detección propia del saque (bola lanzada + brazo arriba + silencio previo).
4. Lado lejano: seguimiento continuo de la jugadora lejana; contar cada golpe aunque solo se mida posición/altura.
5. Cámara principal: planos perdidos (Osaka: marcador no leído → arreglado en candidates v8; `diag_scenes.py` para el resto).
6. Atacar las pérdidas en el orden que diga la línea base, volver a medir tras cada arreglo.

## 2. La fuente son los partidos (#218, #219)
Criterio: en los 4 partidos, % de golpes con repetición enlazada y % con otra cámara enlazada, contado por script.
1. Repeticiones a velocidad normal y en cámara lenta: enlazarlas a su golpe en directo, estimar el factor de cámara lenta, usar sus fotogramas extra (impacto menos borroso).
2. Otras cámaras de la emisión (lateral, frontal, primeros planos): clasificar la vista, enlazar a su golpe y medir lo que esa vista permite (empuñadura, cara de la raqueta, impacto delante/detrás).

## 3. Situaciones que faltan (pedidas por el usuario)
Criterio: cada situación aparece en «Aprende» y en la auditoría con su número de golpes (o «sin golpes suficientes»).
1. Golpe angulado. 2. Bola corta baja cerca de la red. 3. Bola corta alta cerca de la red.
4. Volea a media pista con el swing de fondo (derecha o revés). 5. Volea fuera de la línea de saque.
6. Media volea / bote pronto: validarla con casos reales (hoy 0).

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
Nada, salvo conectar el móvil el día que quiera probar la copia. No decide detalles de implementación: Claude
elige la solución que cubre los requisitos y los escenarios, y la valida con números.
