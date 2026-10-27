# Revisión de la base (27-10): qué existe, si está bien, qué mejorar y qué falta

Hecha por Claude con datos reales: tiempos de los registros de los 4 partidos (26-27 octubre), uso de recursos
medido por `medir_recursos.ps1` (27-10, pasada fina de 3 partidos) y el código. Cada fila termina en una
decisión con su criterio automático. Es el bloque **1. Base** de `docs/plan_maestro.md`, que va antes que todo lo
demás.

## 1. Medido

**Tiempo por etapa (partido más largo, la final; Osaka entre paréntesis):**

| Etapa | Tiempo |
|---|---|
| Cortes de plano | 28 min (7) |
| Jugadores | 32 min (11), en parte a la vez que el marcador |
| Marcador (OCR) | 22 min (9) |
| Pista | 10 min (5) |
| Audio, detector, candidatos, identidad | < 5 min |
| **Tomas de cámara** | **310 min** (52) |
| **Pasada fina, primera vez** | **150-180 min** (90) |
| Pasada fina, desde las cachés | 12-25 min |
| **Vídeos de la derecha** (exportación) | **100 min** |

**Uso del PC en la pasada fina:**
- CPU: 15-20 % de media, máximo ~40 %.
- iGPU: 14-16 % de media, con picos de 85-100 %.
- RAM: 9 de 20 GB.
- Disco: ~0 %.

**Conclusión:** el trabajo va en serie y el equipo se usa a una quinta parte.

## 2. Componentes

| Componente | Qué hay | ¿Está bien? | Qué hacer | Criterio automático |
|---|---|---|---|---|
| Lectura de vídeo | ffmpeg por tubería, aceleración por hardware, saltos o tramos | Mejorable: lee a resolución completa todo lo que hay entre muestras; 26 llamadas a ffmpeg sin tiempo límite | Tiempo límite en todas; fotogramas clave donde vale cualquier fotograma de la toma; reducir en el decodificador cuando no hace falta la resolución completa | Ninguna llamada sin límite (prueba que recorre el código); tiempo por etapa |
| Cortes de plano | TransNetV2 + líneas | Bien (41 retransmisiones sin pérdidas) | Solapar con audio y jugadores | Tiempo; mismos planos |
| Tomas de cámara (`views`) | 1-3 fotogramas por toma, lectura por tramos | **Lenta (5 h en la final)** | Fotogramas clave; repartir entre núcleos | < 15 min por partido; misma clasificación de tomas |
| Marcador | rapidocr, OCR solo cuando cambia | Aceptable (9-22 min) | Probar PP-OCRv5 (#201) | Lecturas iguales o mejores; tiempo |
| Pista | Líneas propias + homografía | Bien en la referencia | Probar el detector de 14 puntos (#200) donde falla | Ajuste en pistas difíciles |
| Jugadores | YOLO en la pasada barata | Bien | — | — |
| Detector de golpes | CNN temporal (ONNX) con bola, entrenada con F3Set | Bien (80 %), pero las repeticiones descartan de más | Arreglar la regla de repeticiones; probar E2E-Spot/F3ED (#204) | Recall F3Set sin bajar precisión |
| Identidad | Ropa + clic + cambios de lado | Bien (9 de 648 mal) | Deshacer clic | Prueba de la aplicación |
| Pasada fina: pose | YOLO11 + RTMPose-x (pies), iGPU, FP16 | Precisión bien; **iGPU al 15 % de media** | Lotes de varias ventanas; solapar pose y CPU; varios procesos | iGPU > 60 % de media; mismos puntos |
| Pasada fina: bola | TrackNetV3 (RacketVision) | Bien; en CPU paralela | Probar WASB (#202) | Recall de golpes y botes |
| Pasada fina: raqueta | YOLO-seg + RacketPose | Lenta, solo cerca del impacto | Solapar | Tiempo |
| Pasada fina: 3D | RTMW3D | Muy ruidoso y disperso (cada 4 fotogramas): no sirve para la cadena | Probar MotionAGFormer (#203) o quitarlo de la cadena | Rotaciones 3D coherentes con el 2D |
| Medidas: cadena cinética | v2 (anchuras) | Corregida: 79 % en orden | Validar con vídeos laterales de entreno | Concordancia lateral y tele |
| Medidas: pies | Puntos del pie, un pie quieto | Corregida: 87 % medidos | Validar pasos con vídeos laterales | Concordancia |
| Resultado del punto | Bola + marcador | **No creíble** (2 ganadores en 191) | Rehacer con el marcador | Ganadores y errores coherentes con el marcador |
| Exportación | Un vídeo por golpe, ffmpeg en serie | **Lenta (100 min) y el revés se cuelga** | Varios procesos; encontrar el golpe que cuelga | < 20 min; ningún cuelgue |
| Robustez | Vigilancia en la exportación y la app | Parcial | Tiempo límite y reintento en todo; prueba por cada cuelgue | Prueba que recorre todas las llamadas externas |
| Orquestación | Etapas con huellas, caché, una tarea pesada a la vez | Bien en lo funcional; en serie | Paralelo dentro de la etapa (ventanas) y entre etapas independientes | Tiempo total por partido |
| Ejecución en el PC | GitHub Actions + ciclo de respaldo | Bien desde el 27-10 | — | — |
| Autonomía (producto) | Aplicación con cola y avisos | Parcial: el desarrollo depende del ciclo con Claude | La aplicación final sin Claude: cola, reintentos, actualizaciones por versión estable | Prueba de extremo a extremo sin red |
| Registro de recursos | `medir_recursos.ps1` | Nuevo (27-10) | Guardarlo junto a cada análisis | Resumen por etapa en cada ejecución |

## 3. Orden de trabajo (base)

1. **Robustez:** tiempo límite en las 26 llamadas externas sin límite, y el cuelgue de la exportación del revés. Es rápido y quita bloqueos.
2. **Rendimiento:**
   - tomas con fotogramas clave;
   - pasada fina en paralelo (lotes en la iGPU y CPU solapada);
   - exportación en paralelo.

   Cada cambio se mide en el PC con recursos y tiempos, y debe dar los mismos resultados.
3. **Modelos:** probar los candidatos #199-#204 con medida automática (`scripts/model_trials.py`, `validate_recall.py`) y adoptar solo los que mejoren.
4. **Detección:** regla de repeticiones y NMS vacío. Se mide con F3Set.
5. **Autonomía:** la aplicación final sin Claude.
