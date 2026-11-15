# Lo que la nube hereda del PC, y qué se hace con cada cosa (T23, 14-11)

Petición del usuario (14-11 23:45): que nada del código ni de la configuración que corre en la nube esté decidido por el
PC (sus condiciones, sus medidas, sus ficheros), y que no se haya descartado ninguna opción por información antigua del
PC. Regla: cada cosa heredada se **mantiene solo con una medida hecha en la nube**, se **cambia** o se **mide** con una
prueba de concepto (#288). Lo que cambia resultados se decide con «calidad antes que velocidad» (#248).

## 1. Condiciones del código ligadas al PC

| Dónde | Qué hacía | Estado |
|---|---|---|
| `device: dml` y `== "dml"` en 20 sitios | La nube corría con «dml» y un parche la llevaba a CUDA | **Cambiado** (T4): `device: auto` y `is_gpu()`; comprobado idéntico (v19) |
| `_fine_workers`: un proceso por cada 4 núcleos | Kaggle (4 núcleos) con un solo proceso y su 2.ª T4 parada | **Cambiado** (T8): 2 núcleos por proceso (medido en Kaggle) y cada proceso en su GPU |
| `models/seg_gpu_falla.txt` | El fallo de la iGPU del PC apagaba la GPU de la nube para la raqueta (68 % de la pasada fina) | **Cambiado** (R48): el aviso es por dispositivo; se comprueba con la v20 |
| `io.video.auto_hwaccel`: d3d11va solo en Windows | En la nube se decodifica en la CPU | **Medido en la nube** (T7): la CPU gana a NVDEC y a todo en la GPU |
| `fine_ahead`: la bola en paralelo | — | **Medido en la nube**: con 4 núcleos, 4 veces más lento; apagado con menos de 8 núcleos |
| `ocr5`: `use_dml` solo con DirectML | En la nube el marcador se lee en la CPU (etapa `score`, ~110 s cada 10 min, CPU al 96 %) | **Por medir**: RapidOCR con CUDA (`use_cuda`) |
| `bounce_ctb`: en la CPU con cualquier GPU | Decidido para DirectML | **Por medir** en CUDA (solo si se usa el modelo CTB; hoy el bote es `own`) |
| `estimator`: recuperar la iGPU perdida | Solo actúa con errores de DirectML | Sin efecto en CUDA: se queda |
| `available_ram_gb`, aplicación, orquestador, ventanas | Windows frente a Linux | No deciden nada del análisis: se quedan |

## 2. Ajustes decididos con medidas del PC (heredados por la nube)

| Ajuste | Por qué se decidió en el PC | En la nube |
|---|---|---|
| `racket_face.fp16: true` | Raqueta y 3D más rápidos en la iGPU; «cambia los puntos muy poco, pero cambia» | **Por medir** (calidad): precisión completa, `prueba_gauff_v21_calidad` |
| `racket_face.hand3d_step: 2` | El 3D de la mano, uno de cada 2 fotogramas, por tiempo en el PC | **Por medir** (calidad): cada fotograma, la misma prueba |
| `fp16: true` (pose YOLO) | 2,2 veces más rápido en la iGPU; puntos a 0,25 px | **Por medir** (calidad): la misma prueba |
| `ball.fp16: true` | 16 → 25 fotogramas/s en la iGPU; 0 px de diferencia | La misma prueba (no debería cambiar nada) |
| RTMPose en precisión completa | En media precisión era más lento en DirectML | **Por medir** (velocidad), después |
| `ball.static_batch: false` | En DirectML no era más rápido | **Por medir** (velocidad) en CUDA, después |
| `pose_ranges: false` (lado lejano por tramos) | Más lento en el PC | Solo velocidad: por medir si la pose vuelve a pesar |
| `fine_gate` (la cascada que salta ventanas) | Ahorro de tiempo en el PC | **Por medir** su efecto en los golpes encontrados (F3Set) en la nube (fase C) |
| Pasada barata (fps y tamaño) | Tiempo del PC | Por medir con F3Set en la nube (fase C) |
| `export.encoder: libx264` | El PC solo tenía AMD (h264_amf) | NVENC de la T4 sin probar: con T13 |
| `fine_speed.worker_ram_gb: 6` | Memoria del PC | **Medido en la nube**: 11 GB con 2 procesos (≈ 5,5 cada uno): vale |

## 3. Ficheros del PC que llegan a la nube

- `models/`: los modelos (los mismos ficheros: bien) y el aviso de la iGPU (R48, ya no cuenta en la nube). No hay más
  ficheros de estado en `models/` (revisado: solo los de la raqueta y los del OCR).
- `pc/local.yaml`: la nube toma los ajustes del PC menos rutas y `hwaccel`. **Desde el 14-11 cada ejecución guarda los
  ajustes que usó de verdad** (`config_local` en `nube-logs/cola/ejecuciones/`), para revisarlos uno a uno aquí.

## 4. Decisiones de documentos con medidas del PC

- `docs/estado_del_arte.md` y los bancos de modelos del PC (`scripts/model_trials.py`, `bench_*`): elegidos por tiempo
  en el PC. La fase C (T15) vuelve a comparar cada modelo con datos anotados en la nube.
- Las medidas de rendimiento (B1) del PC ya no cuentan: B1 se mide en la nube (`Tiempo desde cero`, «Uso de la nube
  por etapa»).

## Orden

1. `prueba_gauff_v20` (la raqueta en la GPU) y `prueba_gauff_v21_calidad` (precisión completa, 3D en cada
   fotograma), en las dos sesiones a la vez. Los partidos esperan a decidirlo (`partidos_en_espera`).
2. Decidir (criterio escrito antes de medir): si la calidad completa cuesta ≤ 15 % más de tiempo total, se adopta.
3. Después, sin bloquear los partidos: el OCR con CUDA, RTMPose en media precisión, la bola por lotes y el NVENC.
