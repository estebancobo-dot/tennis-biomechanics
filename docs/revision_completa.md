# Revisión completa: alcance, errores, huecos y plan

Estado: octubre 2026. Revisión del código de arriba abajo (fuentes, procesado, algoritmos, modelos,
rendimiento, informe y exportación), con las afirmaciones graves comprobadas en el código.

## 0. Respuesta corta

**No, hoy no cubre toda la casuística, y en algunos puntos da resultados que parecen medidas y no lo son.**
El sistema detecta golpes, los sitúa en la pista y mide bastantes cosas del cuerpo y la raqueta,
pero:

1. Tiene **errores que invalidan parte de los datos** (identidad, cara en el impacto, cadena cinética,
   medidas que mezclan el desplazamiento con la técnica, entrelazado).
2. Cubre **una parte pequeña de la taxonomía** de la derecha (sección 3).
3. **No está preparado para un partido real de principio a fin** en tu PC: un fallo en un golpe tumba
   la etapa, y la pasada fina puede tardar del orden de **10-25 h por partido** (estimación sin medir)
   porque la pose va en CPU.
4. Las conclusiones son **descriptivas y estadísticamente frágiles** (120 comparaciones sin corregir).
5. **No responde a la pregunta que importa**: "¿qué tengo que hacer para pegar una derecha como X?".
   Para eso hace falta un **modelo técnico** (sección 6), que hoy no existe.

Sí: el alcance es enorme. Hay que dividirlo en capas y no fingir precisión donde una cámara de TV no da.

## 1. Veredicto por área

| Área | Nominal | Casos límite | Errores / fallos | Veredicto |
|---|---|---|---|---|
| Gestión de fuentes | 1080p progresivo, MP4 | ✘ 1080i (no se desentrelaza en la pasada fina), VFR, TS con cortes, sin audio, varias pistas de audio, 4K | ✘ ffprobe sin fps o duración rompe; ficheros a medias se reutilizan; vídeo borrado tumba todo | Insuficiente |
| Procesado / incremental | Funciona en clips | ✘ cambiar modelo o parámetros no rehace la pose; un candidato nuevo rehace todas las ventanas | ✘ un golpe que falla tumba la etapa y vuelve a fallar al relanzar | Insuficiente |
| Identidad | Bien si OCR y ropa funcionan | ✘ ropa igual (Wimbledon), nombre no leído, partido sin ella | ✘ los indecisos entran como si fueran ella | **Crítico** |
| Detección de golpes | Validada en 9 clips: P 0,73 / R 0,84 | ◐ red, voleas, aproximaciones se pueden perder | — | Aceptable para fondo de pista |
| Algoritmos de métricas | Parcial | ✘ ver sección 2 | ✘ cara en el impacto, cadena cinética, cadera, cabeza, rotación con zoom | **Crítico en varias métricas** |
| Modelos IA | Pose buena cerca; bola validada | ✘ sin probar en otras cadenas, superficies, resoluciones | ✘ sin modelo de bola sigue sin avisar (F1 ≈ 0,3) | Medio |
| Rendimiento | — | — | Pose en CPU, doble decodificación | **Riesgo alto (sin medir)** |
| Informe y exportación | Bien con datos limpios | ✘ informes que se pisan, ids inestables, móvil sin viewport | ✘ "fuera" cuando es desconocido | Medio |
| Estadística | Diferencias de medias con IC | ✘ sin corrección múltiple, sin ajustar por situación ni partido | ✘ "Probable" entra como conclusión con IC que cruza el 0 | Frágil |
| Utilidad | Describe a la jugadora | — | No prescribe ni modela la técnica | **Falta la pieza principal** |

## 2. Errores confirmados (prioridad alta)

| # | Error | Dónde | Efecto | Arreglo |
|---|---|---|---|---|
| 1 | Golpes con identidad indecisa se analizan como de ella y no se guarda la identidad | `stages.py` (filtro de `fine`), `identity.py` | Golpes de la rival en su informe, sin aviso | Guardar identidad por golpe; excluir indecisos por defecto; avisar si su apellido no sale en el marcador |
| 2 | La cara de la raqueta en el impacto la decide una suposición (borrosa ±80 ms → ancla "hacia la red") | `racket_face.py`, `racket3d.py` | `rFaceImp`/`rYawImp` casi constantes, y se interpretan como técnica | Sacarlas de hallazgos; anclar con la dirección real del golpe; destacar armado y terminación |
| 3 | Cadena cinética: argmax de una velocidad sin suavizar sobre un ángulo 2D sin signo | `phases.py` | El orden puede ser un artefacto | Suavizar, ángulos con signo o 3D, separar picos, validar antes de mostrar |
| 4 | Medidas en píxeles: "descenso de cadera", estabilidad de cabeza, rotaciones 2D | `stroke_analysis.py`, `kinematics.py` | Moverse hacia o desde la cámara parece técnica | Escala por fotograma, medidas relativas (cadera–tobillo, cabeza–cadera) |
| 5 | Ventana fija de 1,0 s antes del impacto | `stroke_analysis.py`, `phases.py` | Split step solo con bola rápida → sesgo; takeback largos truncados | Ventana = tiempo disponible + 0,5 s |
| 6 | Ventanas de la pasada fina sin desentrelazar | `stages.py` (`cut_window`) | 1080i a 25 fps con peine: peor muñeca, bola y raqueta | `yadif=1` al cortar si es entrelazado |
| 7 | Un fallo en un golpe tumba `fine`; un partido malo para `run --all` | `stages.py`, `cli.py` | Horas perdidas, se repite en cada relanzamiento | Captura por golpe y partido, `errores.json`, seguir |
| 8 | Ficheros a medio escribir se reutilizan | `cut_window`, cachés `.npz`/`.npy`, JSON | Datos corruptos permanentes tras un corte | Escribir en temporal y renombrar; validar al cargar |
| 9 | La caché de pose ignora modelo y parámetros; los nombres llevan el índice del candidato | `clip_pipeline.py`, `stages.py` | Cambios sin efecto, o rehacer todo por un candidato nuevo | Clave = tiempo + hash del modelo y parámetros |
| 10 | Vídeo borrado → `FileNotFoundError` en todo | `pipeline.py` | Con 500 GB vas a borrar vídeos | Saltar el partido con aviso y conservar resultados |
| 11 | Modelos ausentes: se sigue sin bola/raqueta sin avisar | `stages.py`, `default.yaml` | Detección F1 ≈ 0,3 en silencio | Ruta relativa al repo, aviso, huella con el modelo |
| 12 | Informes y exportaciones se pisan (misma carpeta por defecto, ids por posición) | `cli.py`, `report.py`, `export.py` | Miniaturas y MP4 de otro golpe o jugador | Carpeta por jugador y golpe; ids estables (partido + fotograma de impacto) |
| 13 | Zurdos mal reflejados en el informe del rival | `report.py` | Métricas del rival invertidas | Usar el perfil del jugador analizado |
| 14 | Plantilla sin `doctype`, `charset`, `viewport` | `report_template.html` | Acentos y móvil | Añadir |
| 15 | `shotIn` desconocido se muestra como "fuera" | plantilla | Errores inventados | Distinguir "—" |
| 16 | Hallazgos: 120 comparaciones sin corregir, golpes tratados como independientes, caída silenciosa a "todas las bolas" | `findings.py`, plantilla | Falsos positivos presentados como "diferencia real" | Permutación o FDR, agrupar por partido, ajuste por situación, no mezclar bolas |
| 17 | Lógica duplicada JS/Python ya divergente | plantilla, `findings.py` | El informe y el PDF pueden decir cosas distintas | Calcular una vez en Python e incrustar |
| 18 | "Golpe típico" puede ser lejano o incompleto | `findings.py`, plantilla | El modelo de referencia sería el golpe equivocado | Exigir cobertura de métricas y lado cercano |
| 19 | Pose y detección de la pasada barata en CPU (PyTorch); la iGPU no se usa | `stages.py`, `pose/yolo.py` | Partido de ~3 h: horas en `players` y 10-25 h en `fine` (estimado) | Pose en ONNX con DirectML sobre un recorte; ventanas fusionadas por peloteo; una sola decodificación |

Hay más fallos de prioridad media y baja (marcador que no se relocaliza, ffprobe frágil, rutas con acentos
en OpenCV, repeticiones lentas que pasan por cámara principal, apoyo neutro confundido con cerrado,
"armado" detectado como pausa de la muñeca y no como máxima rotación, terminación por "muñeca más alta",
homografía única por plano, 3D con altura fija 1,8 m, empuñadura supuesta y no medida, "ganador"
que incluye errores forzados…). Están en el apéndice A.


## 3. Taxonomía completa de la derecha y qué cubre hoy

Leyenda: ✔ medido · ◐ parcial/aproximado · ○ no medido pero factible desde TV · ✘ no factible desde una cámara de TV

### A. La bola que recibe (contexto)
| Dimensión | Variantes | Estado | Cómo / qué falta |
|---|---|---|---|
| Velocidad (tiempo disponible) | muy rápida / rápida / media / lenta | ◐ | Intervalo golpe rival → golpe (bola + audio). Solo 2 clases (umbral 1,15 s fijo, no por jugadora ni superficie) |
| Altura en el contacto | rodilla / cadera / pecho / hombro / por encima | ◐ | Altura relativa al cuerpo; 3 clases (baja/media/alta) |
| Profundidad (dónde golpea) | dentro de pista / sobre la línea / 1-3 m detrás / muy atrás | ◐ | Homografía; hoy solo "corta" sí/no |
| Anchura | centrada / abierta / muy abierta (estirada) / tiene que rodear la bola (invertida) | ◐ | Desplazamiento entre golpes; no distingue rodear el revés |
| Bote | profundidad del bote, tiempo bote→impacto | ✔ | Bola en el suelo: homografía exacta |
| Efecto recibido | liftado / plano / cortado | ✘ | Necesita bola nítida y rápida (Hawk-Eye) |

### B. Intención y tipo de derecha
| Variante | Estado | Cómo / qué falta |
|---|---|---|
| Cruzada / paralela / al centro | ✔ | Bote de su bola en campo rival |
| Invertida (inside-out) / inside-in | ○ | Combinar posición en el impacto (lado del revés) + dirección |
| Profundidad de su bola | ✔ | Distancia del bote al fondo rival |
| Ataque / neutra / defensa | ◐ | Hoy solo "neutra" como combinación; falta la clase completa |
| Resto | ○ | Primer golpe tras el saque rival (marcador + audio) |
| Aproximación (sube a la red) | ○ | Desplazamiento hacia delante tras el golpe |
| Passing, globo | ○ | Rival en la red + trayectoria de su bola |
| Derecha cortada | ○ | Trayectoria de la muñeca alto→bajo (está en el plan, no hecho) |
| Media volea | ◐ | Solo "candidata" a revisión |
| Dejada | ○ | Bote muy corto en campo rival |

### C. Organización del cuerpo
| Dimensión | Variantes | Estado |
|---|---|---|
| Apoyo | abierto / semiabierto / neutro (cuadrado) / cerrado | ◐ hoy 3 clases; falta "neutro" y apoyo en un pie |
| Tipo de golpe por movimiento | parada / en carrera / en salto / deslizando (tierra) / sobre el pie de atrás | ○ falta clasificarlo (tobillos + velocidad de cadera + pies en el aire) |
| Anchura de la base | m y % de altura | ✔ (solo lado cercano) |
| Carga de piernas | descenso de cadera | ✔ (relativo; rodilla 2D poco fiable) |
| Equilibrio en el impacto | tronco vertical / inclinado; centro de masas sobre la base | ○ inclinación lateral del tronco está en el plan; falta el centro de masas respecto a la base |
| Transferencia de peso | atrás→delante / rotacional | ○ trayectoria de la cadera en pista |

### D. Juego de pies
| Dimensión | Estado | Cómo / qué falta |
|---|---|---|
| Split step (momento) | ✔ | Aterrizaje respecto al golpe rival |
| Primer paso (dirección, tipo: pivote, cruzado, lateral) | ○ | Tobillos en pista tras el split step |
| Número de pasos y pasos de ajuste | ○ | Contactos de pie (velocidad del tobillo ≈ 0) en pista |
| Patrón (shuffle, carrera, cruce) | ○ | Secuencia de pasos |
| Pie de carga | ○ | Pie con más peso en el armado (altura del tobillo / cadera encima) |
| Recuperación (tiempo, distancia, tipo de paso) | ◐ | Tiempo al primer paso; falta distancia y tipo |

### E. Preparación y empuñadura
| Dimensión | Estado | Cómo / qué falta |
|---|---|---|
| Empuñadura (continental / este / semioeste / oeste) | ○ difícil | Ángulo entre antebrazo y cara de la raqueta en el armado (5 puntos de raqueta + mano 3D); hay un parámetro fijo `forehand_grip_close_deg`, no se estima |
| Empuñadura en espera | ✘ casi | Mano pequeña a 1080p; como mucho "mano libre en el cuello" sí/no |
| Posición de espera (raqueta delante, altura, flexión) | ○ | Pose en la fase 1 |
| Giro unitario (hombros + raqueta juntos) | ◐ | Rotación de hombros; falta el momento relativo de raqueta y hombros |
| Forma del armado (bucle / recto / alto) | ○ | Trayectoria de la cabeza de la raqueta en el armado |
| Altura de la raqueta en el armado | ✔ | |
| Brazo libre | ✔ | Extensión en el armado |
| Caída de la raqueta (lag) | ✔ | |

### F. Aceleración e impacto
| Dimensión | Estado | Nota |
|---|---|---|
| Cadena cinética (orden) | ✔ | Orden fiable, valores no |
| Separación cadera-hombros (X-factor) | ◐ | 2D media; 3D experimental |
| Trayectoria bajo→alto (plano del swing) | ◐ | Altura de la cabeza respecto a la muñeca; falta el ángulo del plano |
| Codo (brazo recto / doble flexión) | ✔ | Falta clasificar el estilo |
| Punto de impacto lateral | ✔ | |
| Punto de impacto delante/detrás | ✘/◐ | Eje de profundidad; solo con 3D estimado |
| Altura del impacto | ✔ | |
| Cara de la raqueta en el impacto | ◐ | Estimada (desenfoque) |
| Velocidad de la raqueta / bola, efecto | ✘ | |

### G. Terminación y recuperación
| Dimensión | Estado |
|---|---|
| Tipo: limpiaparabrisas / sobre el hombro / invertida / alrededor del cuerpo | ○ (en el plan, no hecho: dirección final de la muñeca y la raqueta respecto al hombro) |
| Altura de la terminación | ✔ |
| Equilibrio al terminar | ○ |
| Recuperación | ◐ |

### H. Ritmo
| Dimensión | Estado |
|---|---|
| Duración de cada fase y proporciones (preparación/aceleración) | ○ los momentos existen; falta medirlo y compararlo |
| Momento del inicio de la preparación respecto al bote | ○ |

## 4. Rendimiento y velocidad

No hay medidas en tu PC todavía (es el primer paso pendiente). Estimación para un partido de ~3 h a 1080p50:

| Etapa | Estimación | Motivo |
|---|---|---|
| Cortes de plano | 30-60 min | Decodificación completa por software |
| Audio | 5-10 min | |
| Jugadores | 3-5 h | Otra decodificación completa + YOLO pose en CPU |
| Marcador | 20-40 min | Cientos de ffmpeg sueltos |
| Pista | 10-15 min | |
| **Pasada fina** | **10-25 h** | 400-700 ventanas × YOLO pose a 1280 en CPU + raqueta + 3D + bola |

Con 4 partidos serían días. Mejoras, por impacto:
1. Pose en ONNX con DirectML (la iGPU) sobre un recorte alrededor de la jugadora, no el fotograma entero.
2. Fusionar las ventanas que se solapan (golpes del mismo peloteo): ~50 % menos de trabajo.
3. No procesar golpes de identidad indecisa.
4. Una sola decodificación con aceleración por hardware para cortes, jugadores y marcador.
5. Raqueta solo en ±0,5 s del impacto.

Objetivo razonable: **2-4 h por partido**. Hay que medirlo antes de prometerlo.

## 5. Frente a otras aplicaciones (sincero)

**Mejores:**
- Única forma de estudiar a una profesional concreta en partidos reales sin datos privados.
- Contexto del partido (marcador, presión, fatiga) junto a la técnica.
- Comparar golpes en situaciones equivalentes (cuando se arregle la estadística).
- Orientación de las cuerdas por fase (armado y terminación; el impacto, no).
- Escala: cientos de golpes de la misma jugadora.

**Iguales:**
- Detección de golpes, posición en pista, dónde bota la bola (como SwingVision, pero desde la tele).
- Vídeo con esqueleto, fases, comparación lado a lado y superpuesta, exportar MP4 (como OnForm o Dartfish, pero automático).

**Peores:**
- Precisión 3D y rotaciones (Hawk-Eye SkeleTRACK y Sportsbox usan varias cámaras o un móvil cercano).
- Bola: sin velocidad ni efecto. Raqueta: sin velocidad.
- Golpes: sin volea, cortado, resto, globo… clasificados.
- Robustez: no probado en partidos completos ni en otras cadenas.
- **No dice qué hacer.** SwingVision y Sportsbox dan objetivos y ejercicios; nosotros solo describimos.
- Validación: la de un producto comercial no está; aquí solo la detección de golpes y la raqueta tienen cifras.

## 6. Lo que pides de verdad: el modelo técnico "pegar una derecha como X"

Una tabla de datos no responde a eso. Hace falta convertir cientos de golpes en un **modelo técnico**:
qué hace siempre (su técnica), qué cambia según la bola (sus adaptaciones) y cómo se ve cada momento,
explicado para que cualquiera lo pueda usar.

### 6.1 Qué contendría (por jugadora y golpe)

1. **Núcleo invariante** (lo que hace en casi todos sus golpes). Se calcula por descomposición de la
   variabilidad: una métrica con poca dispersión y que apenas depende de la situación es "su técnica".
   Ejemplo: "arma con la raqueta por encima de la muñeca", "termina sobre el hombro".
2. **Adaptaciones por situación**, como reglas: "con bola rápida acorta el armado (−X°) y abre el apoyo";
   "con bola baja baja la cadera X % de su altura". Salen de una regresión de cada métrica sobre la
   situación (tiempo disponible, altura, posición, desplazamiento), con efecto fijo de partido.
3. **8 posiciones clave** (espera → recuperación), cada una con:
   - el **esqueleto medio** de ese momento (alineado y normalizado por altura, zurdos reflejados), dibujado;
   - el golpe real más representativo en vídeo;
   - rangos (p25-p75) de lo que se mide en esa fase y su fiabilidad;
   - **puntos de control en lenguaje llano**: "hombros girados ~90° respecto a la red", "brazo libre
     extendido señalando la bola", "raqueta 20-30 cm por encima de la muñeca";
   - tiempos: "arma a −0,35 s, empieza a acelerar a −0,08 s".
4. **Variantes de su derecha** (cada una con su mini-modelo y sus vídeos): de fondo neutra, con bola
   rápida, abierta en carrera, bola corta de ataque, invertida, bola alta, bola baja, defensiva.
   Solo las que tengan suficientes golpes.
5. **Qué es transferible a un jugador cualquiera** y qué no. Transferible: posiciones, orden, ritmo
   relativo, apoyos. No transferible: velocidad absoluta, fuerza, la bola que recibe una profesional.
   Todo normalizado por altura y reflejado si el usuario es zurdo.
6. **Referencia**: el mismo modelo para 3-5 jugadoras más, para saber si un valor es "mucho" o "poco"
   y qué es estilo propio de X frente a lo común del circuito.
7. **Tu propio golpe frente al modelo**: grabas tu derecha con el móvil y el sistema la compara con
   la variante equivalente de X: las 3 diferencias principales, ordenadas por tamaño y fiabilidad,
   con vídeo superpuesto. Aviso honesto: tu cámara no es la de la tele; las medidas cambian con el
   ángulo, así que se graba desde detrás y elevado, como la tele.
8. **Ejercicios**: cada punto de control enlazado a ejercicios de un catálogo **revisado por un
   entrenador** (configuración, no generado), ordenados de la base a la raqueta (apoyos antes que la
   muñeca).

### 6.2 Qué no puede hacer, por honestidad

- No dice "la técnica correcta": describe la de X. Copiar a X no es siempre lo mejor para otra persona.
- Lo que la tele no mide (empuñadura exacta, impacto delante/detrás, velocidades, efecto) aparece como
  "estimado" o "no medible", nunca como dato.
- Las recomendaciones salen de su patrón, no de un estudio validado.

### 6.3 Requisitos previos

El modelo solo vale si los datos de base son buenos: primero los arreglos de la sección 2, la
anotación de 30-50 golpes para medir el error real de cada métrica, y la taxonomía de la sección 3
(sobre todo tipo de golpe, apoyo neutro, en carrera, pies y terminación).

## 7. Plan propuesto (en orden)

| Bloque | Contenido | Necesita tu PC |
|---|---|---|
| A. Base sólida | Errores 1-18 de la sección 2: identidad, cara, cadena, escalas, ventana, entrelazado, robustez, cachés, informes | No |
| B. Velocidad | Pose en ONNX/DirectML, ventanas fusionadas, una decodificación | Para medir sí |
| C. Prueba real | Instalación, benchmark, un partido completo | **Sí** |
| D. Validación | Herramienta para anotar 30-50 golpes (fases, apoyo, tipo); error real por métrica; recall en un partido entero | Anotar: tú o datos públicos |
| E. Taxonomía | Tipo de golpe (cortado, resto, aproximación, invertida…), apoyo neutro, en carrera/salto, pasos, primer paso, terminación, inclinación del tronco, ritmo de fases | No |
| F. Estadística | Una sola lógica en Python; ajuste por situación y partido; corrección por comparaciones múltiples | No |
| G. Modelo técnico | Sección 6: núcleo, adaptaciones, 8 posiciones con esqueleto medio, variantes, puntos de control | No |
| H. Tu golpe frente al modelo | Análisis de un vídeo tuyo y comparación | Grabar un vídeo |
| I. Referencias | 3-5 jugadoras más | Vídeos |
| J. Entrega | Móvil y nube | Al final |


## Apéndice A. Fallos de prioridad media y baja

**Fuentes y procesado**
- ✔ ffprobe: `avg_frame_rate=0/0`, sin duración o sin moov rompen con errores en inglés; falta comprobar ffmpeg al arrancar. *(mensajes en español y respaldos de fps/duración; probado con ficheros vacíos, cortados, sin vídeo)*
- ✔ VFR y TS con saltos de tiempo: el corte no fuerza fps constante; los tiempos derivan. *(se detectan leyendo las marcas de tiempo; .ts y saltos → copia limpia sin recodificar; VFR → ventanas a fps constante)*
- ✔ Audio: sin pista no avisa; varias pistas (comentario / ambiente) no se pueden elegir; en el lado lejano cada transitorio del comentario abre una ventana cara. *(aviso; se analizan todas las pistas y se queda la que suena con sus golpes)*
- Repeticiones lentas con ángulo parecido y animaciones del Hawk-Eye pueden pasar por cámara principal (duplicados). Pista: en directo el marcador está visible.
- ✔ Dobles: CLAUDE.md dice que se excluyen; las etapas no lo hacen (solo el script de validación).
- Marcador: se localiza una vez; si se equivoca (panel de estadísticas) o cambia de sitio, falla todo el partido; nombres compuestos o abreviados ("RYB", "Zheng Qinwen") no se reconocen; "BREAK" en rótulos de estadísticas.
- ✔ Identidad: un brazo levantado celebrando cuenta como saque; un recogepelotas cerca de la cámara puede ganar a la jugadora. *(el saque exige swing rápido y pies en el fondo; el seguimiento empieza en quien está dentro de la pista)*
- ✔ DirectML sin respaldo automático a CPU; `device: openvino` no funciona con bola y raqueta. *(con openvino, bola y raqueta corren en la CPU con aviso; nunca se para)*
- ✔ Rutas con acentos: OpenCV falla en Windows (0 fotogramas); YAML con comillas convierte `\t` en tabulador. *(ruta corta de Windows para OpenCV; ids de partido en ASCII; local.yaml con comillas simples)*
- ✔ La huella no incluye rival, mano ni altura: corregirlos no rehace nada.
- ✔ El manifiesto no comprueba que las salidas existan; ventanas viejas no se borran; no se mira el espacio libre.
- ✔ Cambiar una fórmula de métrica sin subir la versión deja datos viejos *(huella del código)*; ◐ la pasada fina es monolítica, pero la pose, la bola y la raqueta de cada ventana quedan en caché.
- ◐ `auto_catalog.py` borra los comentarios de `matches.yaml` y asigna todos los vídeos a Rybakina. *(el rival se lee del marcador; ids en ASCII)*
- ✔ Mensajes: trazas en inglés; sin progreso durante horas; sin log propio de Python. *(registro.log por partido, progreso por golpes)*
- ✔ Rendimiento menor: el modelo YOLO se carga en cada fotograma o ventana en algunos caminos.

**Algoritmos**
- Apoyo: neutro y cerrado se confunden (no se conserva el signo); se mide en el impacto, no al armar; con los pies en el aire la homografía falla; umbrales 20°/55° sin calibrar; la pose es COCO-17 (sin puntera ni talón), no Halpe26.
- ◐ Fases: "armado" = pausa de la muñeca (no máxima rotación de hombros) *(contrastado: 0,08 s de diferencia mediana)*; extensión fija a +50 ms; terminación = muñeca más alta (falla con limpiaparabrisas y cortados); el split step usa la media de los tobillos (cualquier paso cuenta).
- Lado lejano: split step y recuperación no son fiables a ~70 px pero se muestran.
- ✔ Homografía: una por plano (un zoom dentro del plano la invalida); sin error de reproyección; giro de cámara supuesto nulo. *(se comprueba cada ~8 s y en el fotograma de cada impacto; si no encaja, se reajusta o no se usa)*
- 3D: mezcla unidades de RTMW3D con píxeles convertidos suponiendo 1,8 m.
- Empuñadura: supuesta en la configuración, condiciona la cara estimada.
- Altura de la raqueta respecto a la muñeca en el plano de imagen: con la cámara inclinada, "hacia la red" parece "alta"; su fiabilidad está sobrevalorada.
- "Ganador probable" incluye errores forzados del rival.
- Golpes cerca de la red y voleas: umbrales en fracción de imagen pensados para el fondo de pista.
- Derecha alta por encima de la cabeza puede clasificarse como saque/remate; saque y remate mezclados.

**Informe y exportación**
- Cero golpes: los botones anterior/siguiente fallan.
- Sin `probe.json` todos los golpes caen en el "primer tercio".
- Saque: nunca hay golpes "neutros"; se muestran apoyos y bola rápida sin sentido.
- "Partido a partido": sin mínimo de golpes por partido.
- ✔ Escala: el cálculo de pares usa una matriz n×n (≈1 GB con 6.000 golpes); los ficheros de series se reescriben enteros y nunca se borran los huérfanos.
- Referencias de YouTube fijas de Rybakina en todos los informes.
- ✔ Exportación: los MP4 no se rehacen cuando cambian la mediana o el ruido; si falla a medias queda un `.part.mp4`; rutas con `'` rompen los montajes; OpenCV con acentos en Windows.
- El "ruido de medida" no es ruido de medida: es variabilidad golpe a golpe (incluye técnica real). Falta la anotación manual prevista.
- Móvil: el HTML local con vídeos no funciona en iOS/Android; en el móvil sirven el MP4 y el PDF.

## Apéndice B. Validación existente y pendiente

| Qué | Estado |
|---|---|
| Detección de golpes lado cercano (pose + bola) | 9 clips: P 0,73 · R 0,84 · instante ±1 fotograma |
| Lado lejano | En curso (clips con seguimiento correcto: casi todos los golpes; clips con seguimiento perdido: nada) |
| Raqueta 5 puntos | PCK 74-93 % |
| Destino del golpe | 3 golpes a ojo |
| Derecha/revés, fases, apoyo, ángulos, X-factor, split step, identidad, OCR, resultado, homografía | **Sin validar** |
| Recall en un partido completo (pasada barata a 10 fps) | **Sin medir** |
| Ruido de medida real (30-50 golpes anotados) | **Sin hacer** |
