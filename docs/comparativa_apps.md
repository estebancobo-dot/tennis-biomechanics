# TennisBio frente a aplicaciones reales

Estado: octubre 2026. Las características de terceros salen de sus fichas y notas públicas
(enlaces al final); donde no hay confirmación se indica.

## 1. Con qué se compara
| Producto | Qué es | Fuente de datos | Para quién |
|---|---|---|---|
| **SwingVision** | App de móvil (iOS) con IA | Tu propio móvil grabando tu partido | Jugadores amateur |
| **Hawk-Eye SkeleTRACK + TennisViz** | Sistemas del circuito profesional | Varias cámaras fijas del estadio | Torneos, televisión, entrenadores ATP/WTA |
| **Sportsbox AI** | 3D del cuerpo desde un móvil | Tu propio móvil | Golf sobre todo; tenis sin confirmar |
| **Kinovea / OnForm / Dartfish** | Herramientas de análisis de vídeo manual | Tus vídeos | Entrenadores que analizan a mano |
| **TennisBio (este proyecto)** | Análisis automático por lotes | **Retransmisiones de TV** de partidos profesionales | Tú: estudiar a una jugadora concreta |

## 2. Tabla detallada
Leyenda: ✔ lo hace · ◐ parcial o aproximado · ✘ no · ? no confirmado

| Aspecto | SwingVision | Hawk-Eye / TennisViz | Sportsbox AI | Kinovea / OnForm / Dartfish | **TennisBio** |
|---|---|---|---|---|---|
| Analiza a profesionales en partido real | ✘ (tu juego) | ✔ (con acceso a sus datos) | ✘ | ◐ (a mano, vídeo a vídeo) | **✔ desde la tele** |
| Necesita grabar o instalar cámaras | Sí (móvil) | Sí (estadio) | Sí (móvil) | Sí | **No** |
| Detección automática de golpes | ✔ | ✔ | ✘ | ✘ | ✔ (P 0,73 / R 0,84 sin audio, lado cercano; P 0,89 / R 0,80 lado lejano) |
| Tipo de golpe | ✔ | ✔ (clasificación) | ✘ | ✘ (tú lo marcas) | ✔ derecha/revés/saque; ✘ volea, remate, cortado |
| Velocidad de bola | ✔ | ✔ | ✘ | ◐ (calibrando a mano) | **✘** (no fiable desde la tele) |
| Efecto (rpm) | ? | ✔ | ✘ | ✘ | **✘** |
| Dónde bota la bola (profundidad, dirección) | ✔ | ✔ | ✘ | ✘ | ✔ (por homografía; las muy profundas pueden quedar sin dato) |
| Dentro / fuera, errores, ganadores | ✔ (cantar líneas) | ✔ | ✘ | ✘ | ◐ fuera ✔, red y ganador "probable" |
| Esqueleto del cuerpo | ✘ (no es su foco) | ✔ 29 puntos, varias cámaras | ✔ 3D, un móvil | ◐ (dibujas tú) | ✔ 2D 17 puntos + 3D experimental |
| Ángulos (codo, rodillas, tronco) | ✘ | ✔ (p. ej. flexión de rodilla, hombros en el saque) | ✔ | ◐ (transportador manual) | ✔ automáticos, con fiabilidad declarada por métrica |
| Rotación hombros/cadera, X-factor | ✘ | ✔ | ✔ | ◐ | ◐ 2D (media) y 3D (experimental, parece quedarse corto) |
| Cadena cinética (orden de los picos) | ✘ | ? | ✔ (en golf) | ✘ | ✔ (orden fiable, valores no) |
| Fases del golpe (8 momentos) | ✘ | ✔ (detección de fases) | ✔ | ✘ (marcas tú) | ✔ automáticas |
| Raqueta: velocidad | ◐ (sensor/estimación) | ✔ (7 puntos de raqueta) | ✘ | ✘ | **✘** (borrosa en el impacto) |
| Raqueta: orientación de la cara / cuerdas | ✘ | ? | ✘ | ✘ | ◐ **orientación de las cuerdas por fase** (5 puntos + mano 3D; impacto estimado) |
| Pies: apoyo, base, split step, recuperación | ✘ | ◐ (movimiento) | ✘ | ✘ | ✔ lado cercano · ✘ apoyo lejano |
| Contexto del partido: marcador, presión | ✔ (marcador propio) | ✔ | ✘ | ✘ | ✔ OCR del marcador de TV (presión, sets) |
| Situación de la bola recibida (rápida, abierta, corta, baja) | ✘ | ✔ (calidad de golpe) | ✘ | ✘ | ✔ |
| Comparar golpes **equivalentes** (misma situación) | ✘ | ◐ | ✘ | ✘ | **✔ (núcleo del diseño)** |
| Fatiga (inicio vs final), presión, partido a partido | ◐ | ✔ | ✘ | ✘ | ✔ |
| Incertidumbre y ruido de medida en cada conclusión | ✘ | ✘ (no publicado) | ✘ | ✘ | **✔ (bandas de ruido, IC 95 %, confianza)** |
| Vídeo con esqueleto superpuesto | ✘ (marcador superpuesto) | ✔ (TV) | ✔ | ✔ (dibujas tú) | ✔ cada golpe, cuadro a cuadro, con ángulos, bola, cuerdas y minipista |
| Videoteca y listas de reproducción | ✔ (por partido) | ✔ | ◐ | ◐ | ✔ filtros, "reproducir todos" y cada conclusión abre sus vídeos |
| Estroboscópica, 8 fotogramas clave | ✘ | ? | ? | ✔ (Dartfish *stromotion*; manual) | ✔ automático |
| Lado a lado de dos golpes | ◐ | ? | ✔ | ✔ | **✔ sincronizados en el impacto, lado a lado o superpuestos** |
| Exportar vídeo con datos | ✔ (resúmenes para redes) | ✔ (TV) | ✔ | ✔ | **✘ (pendiente)** |
| Recomendaciones de entrenamiento | ✔ (objetivos semanales) | ✘ (datos) | ✔ | ✘ | **✘** (describe, no prescribe) |
| Escala: miles de golpes de una jugadora | ✘ (tu juego) | ✔ | ✘ | ✘ | **✔** |
| Coste | 96-300 $/año | No accesible a particulares | Suscripción | Gratis (Kinovea) a caro (Dartfish) | Gratis; tu PC |

## 3. Dónde es igual, mejor y peor
**Mejor que todos:**
- Es la única opción para estudiar la **técnica de una profesional concreta en partidos reales** sin acceso a datos privados.
- Compara **golpes en la misma situación** (bola rápida/lenta, abierta, corta, presión) y dice cuándo una diferencia supera el ruido de medida. Ninguna app de consumo hace esto.
- **Orientación de las cuerdas por fase.** Ninguna herramienta pública la da desde vídeo, aunque aquí no está validada con referencia 3D.

**Parecido:**
- Detección y clasificación automática de golpes, posición en pista, dónde bota la bola: al nivel de SwingVision, pero desde la tele.
- Ángulos y fases automáticas, como Sportsbox o SkeleTRACK, pero solo en 2D y desde una cámara.

**Peor:**
- **Bola:** sin velocidad ni efecto; Hawk-Eye y SwingVision los dan.
- **Raqueta:** sin velocidad de cabeza; SkeleTRACK la mide con varias cámaras.
- **Precisión 3D:** una cámara de TV detrás y elevada frente a varias cámaras de estadio. Las rotaciones y el impacto delante/detrás del cuerpo son mucho menos fiables.
- **Golpes:** sin volea, remate ni cortado todavía.
- **Lado lejano:** detalle reducido.
- **Producto:** sin exportar clips (previsto al final) y sin recomendaciones.

## 4. ¿Son útiles los informes? Valoración sincera
**Qué dan de verdad (información, no solo datos):**
- **Conclusiones en frases con su confianza**: "apoyo más frecuente…", "las cuerdas apuntan en el armado hacia…", "con bola rápida su X-factor baja X° (diferencia real / dentro del ruido)".
- **Diferencias que importan:** fatiga, presión, bola rápida y errores frente a ganadores, siempre dentro de situaciones equivalentes y descartando lo que no supera el ruido.
- **Ver el golpe:** el vídeo real con el esqueleto, las 8 fases, la estroboscópica y las curvas. Sirve para comprobar con los ojos cualquier número.

**Qué les falta para ser un análisis "de entrenador":**
1. **Interpretación.** El informe dice *qué* cambia, no *por qué* ni *qué hacer*. Una frase como "en los errores la cara llega X° más abierta y el impacto más atrasado" sí se puede generar con los datos; la recomendación ("adelanta el punto de impacto") exige criterio técnico y hoy no la da.
2. **Referencias.** Sin comparación con otras jugadoras (la mediana del circuito o una referencia de técnica), "X-factor 20°" no dice si es mucho o poco. Se resolvería analizando a varias jugadoras con el mismo sistema.
3. **Volumen.** Con un clip de 3 golpes casi todo sale "orientativo". Con 4 partidos (unos 400 golpes) las comparativas y el ruido de medida ya tienen sentido.
4. **Validación.** Cuerdas y 3D no tienen referencia real. Las demás métricas tienen validación parcial.

**Conclusión:** como **herramienta de estudio de una jugadora a escala** es útil y no tiene equivalente accesible. Como **informe de entrenador listo para usar** todavía no: le faltan interpretación y referencias.

## 5. Cómo se ven y cómo se guardan
- **Formato:** una página HTML sin conexión. Se abre con doble clic en Chrome o Edge; no necesita internet ni servidor.
- **Dónde:**
  - Informes: `C:\tenis\output\informe_derecha\index.html` (y `informe_reves`, `informe_saque`). Cada informe tiene su carpeta `series\`, con los datos fotograma a fotograma.
  - Vídeos de cada golpe: `C:\tenis\output\<partido>\windows\*.mp4`. Son recortes de unos 3,6 s; el partido completo no se copia.
  - Datos: `C:\tenis\output\<partido>\strokes.json` y el resto de ficheros por etapa.
- **Compartir:** comprimir `C:\tenis\output` entero. El informe enlaza los vídeos con rutas relativas, así que la carpeta del informe sola no basta.
- **Grabar:**
  - Hoy no se puede exportar un vídeo con el esqueleto superpuesto. Se puede hacer captura de pantalla del navegador o grabar la pantalla.
  - Los recortes `.mp4` de cada golpe son vídeo normal, sin superposición.
  - Exportar MP4 con esqueleto y datos sería la mejora natural (como SwingVision o Dartfish).

## Fuentes
- SwingVision, ficha de la App Store: <https://apps.apple.com/us/app/swingvision-tennis-pickleball/id989461317>
- Hawk-Eye, SkeleTRACK en tenis: <https://www.hawkeyeinnovations.com/news/4243365/skeletrack-a-new-era-of-data-in-tennis> · datos: <https://www.hawkeyeinnovations.com/data>
- TennisViz / Tennis Data Innovations (ATP): <https://www.atptour.com/en/news/insights-introduction> · nota de prensa: <https://www.atptour.com/-/media/sites/atp-tour/press/press-releases/tennis-data-innovations-tennisviz-unveil-new-fan-insights-announce-partnership-8-august.pdf>
- Sportsbox AI (perfiles de terceros; tenis sin confirmar): <https://craft.co/sportsbox-ai>
- Kinovea, documentación: <https://www.kinovea.org/documents/kv-ov-2.html> · <https://kinovea.readthedocs.io/>
- Herramientas de vídeo (OnForm, Dartfish; listados de terceros): <https://gitnux.org/best/tennis-analysis-software/>
