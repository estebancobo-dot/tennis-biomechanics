# Comparativa catalogada para el rediseño (P0.3, #257; 15-11)

El catálogo completo, con fuentes, está en `config/referencias.yaml`: 15 referencias de 7 tipos (sistemas
profesionales, rótulos de retransmisión, aplicaciones de aficionado, herramientas de vídeo para entrenadores,
laboratorio, GitHub y entrenadores de YouTube). La comparativa anterior, con las cifras de detección, sigue en
`docs/comparativa_apps.md`.

**Límite honesto:** las notas salen de la descripción pública de cada producto (su ficha, su web o la prensa), no de
usarlos. Solo los vídeos de YouTube se analizaron fotograma a fotograma (`docs/investigacion_youtube_usuario.md`). Una
nota de «3» quiere decir que lo describen así, no que se haya comprobado.

## 1. Notas por criterio (0-3)

| Referencia | Vídeo | Fases | Pocos números | Comparar | Explica | Fiabilidad | Móvil | Automático |
|---|---|---|---|---|---|---|---|---|
| Entrenadores de YouTube | 3 | 3 | 3 | 3 | 3 | 0 | 2 | 0 |
| Sportsbox AI (golf) | 2 | 3 | 2 | 2 | 1 | 0 | 3 | 3 |
| SportAI | 2 | 1 | 2 | 2 | 2 | 0 | 2 | 3 |
| SwingVision | 3 | 0 | 2 | 1 | 1 | 0 | 3 | 3 |
| OnForm | 3 | 1 | 1 | 3 | 2 | 0 | 3 | 0 |
| Dartfish | 3 | 2 | 1 | 3 | 1 | 0 | 1 | 0 |
| IBM Serve Quality (US Open 2026) | 1 | 0 | 2 | 0 | 1 | 0 | 3 | 3 |
| TennisViz Shot Quality | 1 | 0 | 3 | 1 | 1 | 0 | 2 | 3 |
| Laboratorio (Theia3D, Vicon) | 1 | 2 | 1 | 2 | 1 | 2 | 0 | 2 |
| **TennisBio hoy (informe beta)** | 3 | 3 | 1 | 2 | 2 | 3 | 1 | 3 |
| **TennisBio en P0 (objetivo)** | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

**Lo que se ve en la tabla:**
- Nadie junta las dos columnas que más importan aquí:
  - los entrenadores de YouTube explican mejor que nadie (fases, pocos datos, lado a lado), pero a mano;
  - las aplicaciones son automáticas, pero explican poco.
  - P0 tiene que hacer las dos cosas: **explicar como un entrenador, de forma automática**.
- **Nadie enseña la fiabilidad de lo que mide.** Es la ventaja propia (requisito 3) y se queda en primer plano.
- Los puntos débiles de hoy son **pocos números** (la lección de «Aprende» mide pantalla y media, R53) y el **móvil**.

## 2. Patrones: qué se adopta y qué no

| Patrón | Quién lo usa | En P0 |
|---|---|---|
| Vídeo con capas sobre la imagen real | Dartfish, HawkAR, GitHub | **Sí** (ya está): esqueleto, raqueta y bola sobre el recorte del golpe |
| Fotogramas clave por fase | Sportsbox (posiciones), YouTube (3-4 fotos) | **Sí**: las 8 fases, una tarjeta por fase con su fotograma real |
| Lado a lado sincronizado por el impacto | OnForm, Dartfish, Hudl, YouTube | **Sí**: comparar dos situaciones o dos golpes, el impacto alineado |
| La medida dibujada sobre el fotograma | Kinovea, Dartfish | **Sí**: el arco del ángulo o la regla de la base sobre la foto, no en una tabla |
| Cadena cinética en el tiempo | SportAI, laboratorio | **Sí**, con el orden de los picos (fiable) y sin sus valores (no fiables desde la tele) |
| Mapa de pista | SwingVision, TennisViz, YouTube | **Sí** (ya está) |
| Resumen en tarjetas | IBM, SwingVision | **Sí**: cada conclusión, una tarjeta con su frase, su dato, su confianza y su vídeo |
| Un círculo y una frase sobre el vídeo | YouTube | **Sí**: lo que importa de cada fase, señalado en su fotograma |
| Primero a velocidad real, después lento | YouTube, OnForm | **Sí**: el vídeo arranca a velocidad real; lento y fotograma a fotograma con un toque |
| «Lo que puedes copiar» en 3-4 puntos | YouTube | **Sí**: el cierre de «Su derecha» |
| Una nota única del golpe (0-10, 0-100, parecido) | TennisViz, IBM, sevensix | **No**: no está validada para vídeo de TV; una nota daría una precisión que no hay |
| Comparar con un profesional | SportAI, sevensix | **No**: la profesional es la analizada; no se usan vídeos del usuario (requisito 6) |
| Dibujo y voz del entrenador | OnForm, Dartfish | **No**: 100 % automático (requisito 5) |
| Gráficos en directo | HawkAR | **No**: el análisis es posterior |
| Preguntar en lenguaje natural | IBM Match Chat, SportAI | **Hueco → petición #299** |
| Muñeco 3D girable | Sportsbox | **Hueco → petición #300**, solo como estimación marcada |

## 3. Lo que hace falta para que el diseño cumpla el objetivo
1. **Móvil primero:** cada pantalla cabe en 390 px sin desbordes (P0, métricas de aceptación).
2. **Una pantalla, una pregunta:** «¿cómo pega la derecha en esta situación?» se responde con 8 tarjetas de fase.
   Cada tarjeta lleva su fotograma real, 1-3 claves medidas con su arco dibujado, la consigna, el error típico y el
   ejercicio. Las tablas van a un desplegable.
3. **Cada dato abre su vídeo:** como ya hace el informe; en el móvil, el vídeo se abre a pantalla completa con las
   capas.
4. **La fiabilidad, siempre visible y discreta:** una marca por dato («fiable», «media», «estimada»,
   «no medible desde la tele»).

## Fuentes
Las de cada referencia en `config/referencias.yaml` (consultadas el 15-11-2026).
