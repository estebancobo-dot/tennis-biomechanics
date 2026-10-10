# tennis-biomech

Análisis biomecánico **cinemático 2D** de golpes de tenis a partir de retransmisiones de TV.
Centrado en **1 jugador y 1 tipo de golpe** por análisis, parametrizable.
Primer caso: **derecha de Elena Rybakina** en 4 partidos completos.
Después: revés, saque, volea y otros jugadores.

## Rutas (Windows, fuera del repo)
- Vídeos: `C:\tenis\videos\` (~5 GB por partido, retransmisión completa). **Nunca a git.**
- Salidas (datos extraídos, recortes, informes): `C:\tenis\output\`.
- Repo: `C:\tenis\tennis-biomech\` — solo código y configuración.
- Las rutas se leen de `config/local.yaml` (no versionado); nada de rutas absolutas en el código.

## Equipo y restricciones técnicas
- Beelink SER5 MAX: Ryzen 7 7735U (8C/16T), 24 GB RAM, SSD 500 GB, iGPU Radeon 680M. Windows 11.
- **Sin NVIDIA / sin CUDA / sin WSL.** Inferencia con ONNX Runtime: `onnxruntime-directml`
  (iGPU) o CPU. Todo el código debe funcionar nativo en Windows (ojo con rutas, `multiprocessing` con `spawn`).
- Python 3.11 gestionado con `uv`. ffmpeg en el PATH.
- Librerías base: OpenCV, numpy, pandas, librosa, onnxruntime(-directml).
- Pose: RTMPose (o YOLO-pose) exportado a ONNX. Detección de personas ligera (YOLO/RTMDet ONNX).
- Disco limitado (500 GB): no extraer fotogramas del partido entero; guardar solo clips/ventanas.

## Estrategia: dos pasadas (NO pasar pose por el partido entero)
1. **Pasada barata** (todo el partido, baja resolución/fps):
   - Cortes de plano → quedarse solo con la cámara principal (fuera repeticiones y primeros planos).
   - Impactos de bola por **audio** (onsets/transitorios).
   - Detección ligera de jugadores → lado de pista y quién golpea.
   - El usuario confirma **con un clic** quién es la jugadora al inicio de cada partido;
     el seguimiento tiene en cuenta los cambios de lado.
   - (Fase 3) OCR del marcador de TV: set/juego/tanteo, situaciones de presión.
2. **Pasada fina**: pose a máxima calidad y fps completos solo en ventanas de **±1 s**
   alrededor de cada golpe de la jugadora objetivo.

## Métricas por golpe (derecha)
- Tipo de apoyo (abierto / semiabierto / cerrado), anchura de la base, flexión de rodillas.
- Rotación de cadera y hombros y su separación (X-factor).
- Ángulo del codo; punto de impacto respecto al cuerpo.
- Secuencia de la cadena cinética (orden de los picos de velocidad angular/lineal).
- Posición en pista (homografía a partir de las líneas).
- Fases: preparación, armado, aceleración, impacto, terminación.
- Agregados: por partido/set, inicio vs final (fatiga), ganadores vs errores, presión.
- Salida: **informe HTML** con gráficos y fotogramas con el esqueleto dibujado.

## Limitaciones asumidas (no "arreglarlas" con falsa precisión)
- 2D desde una sola cámara; cualquier 3D es estimación.
- Desenfoque en el impacto a 25-50 fps: velocidades absolutas no fiables, **comparaciones relativas sí**.
- La jugadora del fondo sale pequeña: prioridad a los golpes del **lado cercano**.
- Solo cinemática, no fuerzas.
- Modo **semiautomático**: el usuario revisa los golpes dudosos (umbral de confianza → cola de revisión).

## Fases del proyecto
0. Entorno + medir fps reales de inferencia en este equipo.
1. Prototipo 1 partido, solo lado cercano: lista de derechas con vídeo y pose.
2. Métricas e informe básico.
3. Los 4 partidos + OCR de marcador y contexto: comparativas, fatiga, presión.
4. Otros golpes y jugadores; lado lejano con menos detalle.

## Convenciones
- Código en inglés (nombres, docstrings); comunicación y docs para el usuario en español.
- Cada etapa del pipeline es un comando CLI idempotente que lee/escribe en
  `C:\tenis\output\<match_id>\` (parquet/JSON), para poder relanzar etapas sueltas.
- Jugador y golpe son parámetros (`config/players/*.yaml`, `config/strokes/*.yaml`), nunca constantes.
- Antes de escribir mucho código, enseñar el plan y esperar confirmación.
