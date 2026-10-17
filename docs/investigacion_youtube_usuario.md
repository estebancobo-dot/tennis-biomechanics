# Vídeos de análisis elegidos por el usuario (17-10)

Tres vídeos de entrenadores sobre la derecha de otros jugadores, analizados en el PC (petición 17: texto y unos 90 fotogramas de cada uno; `pc-logs:investigacion_17/`). Solo sirven para aprender cómo analizan y explican; nada de ellos entra en el informe (requisito 6).

| Vídeo | Entrenador | Vista |
|---|---|---|
| Ash Barty Tennis Forehand | Meike Babel (ex top 30 WTA) | De frente (entreno) y lado a lado de dos golpes suyos |
| Arthur Fils Heavy Topspin Forehand | Intuitive Tennis | El entrenador repite el gesto junto a un recuadro con el jugador |
| Sinner's Forehand: Complete Analysis | Jason Frausto (TennisUnleashed) | Lateral y desde detrás (como la tele), lado a lado con Jack Sock |

## Qué miran y en qué orden

1. **Contexto:** dónde juega (Barty: el 51 % de sus derechas desde la línea de fondo o dentro).
2. **Empuñadura:** la estiman con un plano cercano a cámara lenta.
3. **Preparación:** el giro con la mano libre; las manos se separan a la altura de la cabeza.
4. **Armado:** su altura, que cambia según la bola recibida. También la raqueta de lado con las cuerdas hacia la valla del fondo, y el codo separado «1-2 pelotas».
5. **Carga:** bajar y cargar la pierna de fuera.
6. **Aceleración:** la cadera antes que la raqueta; el extremo del mango apunta a la bola (lag); la cara mira al suelo.
7. **Impacto:** delante del cuerpo; la cara, neutra o algo cerrada.
8. **Terminación y salto:** despega como consecuencia, no a propósito.
9. **Variantes:** el apoyo según la bola; dos golpes suyos lado a lado (más tiempo: armado más alto).
10. **Resumen:** «lo que puedes copiar», en 4 puntos.

## Cómo lo enseñan (gráficos)

- **Secuencias de 3-4 fotos reales** del jugador, una al lado de otra (Fils, Barty).
- **Lado a lado sincronizado:** dos golpes o dos jugadores.
- **Avance fotograma a fotograma**, parando en cada posición.
- **Un círculo** sobre la parte que importa (punta de la raqueta, muñeca, bola) y **una frase corta** sobre el vídeo.
- **Mapa de pista** con el % de golpes desde dentro (Barty).
- **Sin esqueletos, ángulos ni gráficas.** Primero el golpe a velocidad real, después lento.

## Frente a la aplicación

**Medidas.** Todo lo que se puede ver desde la tele ya está en `learn.py` o en la matriz:

| Punto de los entrenadores | Dónde está |
|---|---|
| Golpea desde dentro de la pista | clase `depth` |
| Altura del armado | `loaded.wrist_dom_vs_shoulder` y «Cambia con la bola» |
| Giro con la mano libre | `takeback.hands_apart` |
| Bajar y cargar la pierna de fuera | «Bajar y subir», `loaded.com_over_feet` |
| Cadera antes que la raqueta | `chain.proximal_to_distal` |
| Despega del suelo | `movement` «en el aire» |
| Apoyo según la bola | apoyo por situación |
| Lag | `racket_lag_deg` |
| Cuerdas | línea de cuerdas por fase |
| Codo separado | `loaded.elbow_dom_lateral` |
| Split step | fase 1 |

Fuera de alcance:
- **Empuñadura:** «lo que la tele no mide».
- **Punta por delante de la mano y su recorrido («tip flip»):** es profundidad desde detrás; no medible desde la tele.
- **Comparar con otro jugador:** excluido por el requisito 6.

**Presentación.** Ya estaban:
- el lado a lado (Comparar y «Cambia con la bola»);
- la marca dibujada sobre el vídeo de cada fase, que equivale a su círculo;
- el mapa de pista;
- el botón de velocidad real.

Añadido el 17-10 en la lección:
- **Tira de fases con una foto real de su golpe más representativo en cada fase:** la secuencia de los entrenadores, con sus propios golpes. En el móvil siguen los botones de texto, para no bajar el vídeo de la primera pantalla.
- **‹ ›: avance fotograma a fotograma** dentro de la fase.
- La auditoría comprueba la tira: «La tira de fases enseña su golpe en fotos reales».

No se cambia:
- **La frase sobre el vídeo:** el foco ya está al lado, y repetirlo encima tapa la imagen.
- **El orden «real y luego lento»:** se queda el lento con el botón de velocidad real. La lección es para mirar una fase, no el golpe entero.
