# Escenarios del producto completo (27-10)

Lista hecha por Claude, sin esperar a que el usuario los pida. El producto es **genérico**: cualquier jugador o
jugadora, cualquier golpe y cualquier partido de TV. Rybakina y su derecha son solo el primer caso.

Cada escenario tiene un estado:
- **✔ probado**: hay una prueba automática o una medida con datos reales.
- **◐ hecho sin validar**: el código lo trata, pero ninguna medida automática lo ha comprobado.
- **✘ falta**.

Todo ✘ y ◐ es trabajo pendiente del plan (`docs/plan_maestro.md`, bloque E1). No se descarta ninguno.

## 1. Jugadores

| Escenario | Estado | Cómo se valida (automático) |
|---|---|---|
| Jugadora diestra, revés a dos manos (Rybakina) | ✔ | Recall F3Set 80 % en partidos bien anotados; 799 golpes en 4 partidos |
| **Jugador masculino** | ◐ el código es el mismo; el detector solo se midió con partidos femeninos | Recall con puntos anotados de partidos masculinos (F3Set u otro conjunto) antes de darlo por bueno |
| Zurdo / zurda | ◐ reflejo de coordenadas probado con datos sintéticos | Recall y medidas con partidos reales de un zurdo |
| Revés a una mano | ◐ ficha `backhand: one_handed` | Revés de un jugador a una mano con golpes anotados |
| Altura desconocida | ◐ usa 1,80 m y lo marca | Prueba de la ficha sin altura |
| Mismo apellido o nombre transliterado (cirílico, acentos) | ◐ alias y transliteración | Prueba con nombres en otros alfabetos |
| Jugador nuevo que no está en la configuración | ✘ hay que crear la ficha a mano | La aplicación la crea desde el partido (nombre del marcador + clic) |
| Juniors, silla de ruedas | ✘ no previsto | Decidir alcance; si entra, conjunto anotado propio |

## 2. Partidos y vídeos

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Retransmisión completa 1080p 50 fps, entrelazada o no | ✔ 4 partidos US Open | Referencia R1 |
| Otros torneos y cadenas (Roland Garros tierra, Wimbledon hierba, Australian Open, WTA/ATP 250-1000) | ◐ F3Set tiene varios torneos; la referencia completa solo US Open | Recall por torneo y superficie |
| 720p, 25-30 fps, vídeo de YouTube recomprimido | ◐ | Recall con esa calidad |
| Partido nocturno, sombras, lluvia | ◐ | Recall por condición |
| Resumen o vídeo corto (no partido completo) | ◐ se acepta y avisa | Prueba con un resumen |
| El mismo vídeo dos veces, renombrado o movido | ✔ huella de contenido | `test_auto_catalog_rename` |
| La misma final de otra cadena | ◐ | Prueba con dos fuentes del mismo partido |
| Dobles o mixtos | ◐ se detectan y se excluyen | Prueba con un partido de dobles |
| Vídeo dañado, sin audio, sin pista visible | ◐ | Pruebas de error por caso |
| Varios partidos añadidos a la vez | ◐ cola | Prueba de la cola con N vídeos |

## 3. Quién es quién

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Un clic por partido en la foto de la persona | ✔ 4 partidos | Identidad equivocada 9 de 648 golpes en F3Set |
| Cambios de lado | ✔ | Ídem |
| Ropa parecida de las dos personas | ◐ | Partido con ropa parecida anotado |
| Clic equivocado: deshacer o cambiar | ✘ | Prueba de la aplicación: cambiar el clic recalcula solo lo afectado |
| Analizar también a la otra persona del partido | ◐ reutiliza la pasada barata | Prueba de extremo a extremo |

## 4. Golpes

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Derecha del lado cercano | ✔ 193 golpes; cadena 79 % en orden; pasos 87 % | Medidas sobre la referencia |
| Derecha del lado lejano (menos detalle) | ✔ detección; ◐ medidas | Recall lejano 64 % (F3Set) |
| Revés | ◐ informe generado; exportación colgada | Recall por tipo (revés 66 %), arreglar la exportación |
| Saque | ◐ | Recall por tipo (saque 58 %) |
| Volea, media volea, remate, dejada, globo, passing | ◐ / ✘ pocos casos | Conjunto anotado con esos golpes |
| Cortado (slice), liftado | ✘ efecto no medible sin bola 3D | Decir «no medible desde la tele» |

## 5. Análisis

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Un jugador y un golpe, todos sus partidos juntos | ✔ | Informe de la referencia |
| Por situación (bola rápida/lenta, alta/baja, corta/profunda, carrera, apoyo) | ◐ | Auditoría: golpes por situación |
| Comparar dos jugadores (su derecha frente a la de otro) | ✘ | Pantalla «Comparar jugadores» + prueba |
| Comparar partidos, superficies, temporadas | ◐ por partido; ✘ por superficie y temporada | Prueba con 2 superficies |
| Fatiga y presión (marcador) | ◐ | Auditoría con datos suficientes |
| Usar su golpe como modelo para el usuario | ◐ «Cópiala» | Auditoría de la lección |

## 6. Aplicación de escritorio

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Añadir uno o varios partidos | ◐ | Prueba de la ventana con capturas |
| Lista de partidos profesional (torneo, ronda, fecha, fotos) | ✔ capturas 25-10 | Prueba `test_app_window` |
| Elegir persona (clic) | ✔ | Ídem |
| Elegir jugador y golpe para ver | ◐ | Prueba con 2 jugadores y 2 golpes |
| Cola, progreso, avisos, parar y reanudar | ◐ | Prueba de la cola |
| Disco lleno, iGPU que falla, falta de memoria | ◐ | Pruebas de error |
| Actualización del cálculo: recalcula solo lo afectado | ✔ huellas por etapa | `test_layout`, `test_stage_code` |
| Exportar (vídeos, PDF), copia al móvil | ◐ exportación del revés colgada; móvil al final | Arreglar y probar |

## 7. Rendimiento

| Escenario | Estado | Cómo se valida |
|---|---|---|
| Un partido en horas, no días | ◐ 2,5-10 h según el partido | `medir_recursos.ps1`: tiempo y uso por etapa |
| Uso de CPU, RAM, iGPU y disco | ◐ se mide desde el próximo trabajo | Resumen por etapa (`resources_summary.py`) |
| Etapa de tomas lenta | ◐ mejorada a la mitad | Leer solo fotogramas clave y medir |
