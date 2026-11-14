# Capacidad de la nube a 0 € (R35, #278-#280)

Estado: **en curso** (14-11). Primero se mide; no se cambia nada del análisis hasta tener los números.

## 1. Lo medido (Osaka entero, 14-11, Modal T4 + 8 núcleos reservados)

**Coste por hora del contenedor** (precios de Modal): T4 0,59 $ · CPU 16 núcleos usados de media × 0,047 $ = 0,75 $ ·
memoria 32 GiB × 0,008 $ = 0,26 $ → **≈ 1,6 $/h**. La CPU es casi la mitad; la tarjeta se usa un 27-30 % de media.

**Osaka: ≈ 3,8 $** (pasada barata 28 min + resto 1 h 53 min). Unos **0,054 $ por minuto de vídeo**. A ese precio el crédito
mensual (30 $) da para ~550 min de vídeo (unos 4-5 partidos), y menos si hay pruebas o F3Set.

**Gasto real de noviembre (página Usage de Modal, 14-11 08:20, captura del usuario):** usado **28,05 $** de los 30 $ de
crédito; gasto **0,00 $** (todo cubierto por el crédito). Quedan **≈ 1,95 $ hasta el 1-12**. La suma de nuestras
estimaciones era ≈ 27 $: el cálculo de `nube.cost` se queda ~4 % corto (se corrige con este dato). Con ese saldo, en
noviembre solo van ejecuciones baratas de CPU (informe y auditoría ≈ 0,08 $; medidas desde la caché). Las pruebas A/B/C
de §3 (≈ 0,5 $ cada una) pasan al crédito de diciembre o a Kaggle.

**Pasada fina, nube frente al PC (Osaka, segundos sumados de las ventanas):**

| Parte | Nube (T4) | PC (iGPU 780M) | Nube / PC |
|---|---|---|---|
| raqueta | 6174 | 6508 | 0,95 |
| pose (total) | 3384 | 1732 | 2,0 |
| pose, modelo híbrido | 2549 | 1620 | 1,6 |
| bola | 929 | 159 | 5,8 |
| pose, modelo YOLO | 810 | 84 | 9,6 |
| cuerdas y 3D | 571 | 113 | 5,1 |
| pose de la lejana | 518 | 35 | 14,8 |
| recorte | 228 | 28 | 8,1 |

Una T4 no debería ser 5-15 veces más lenta que la iGPU del PC en los modelos pequeños. La pasada barata, en cambio,
va más rápida en la nube (cortes 216 s frente a 421; jugadoras 423 frente a 722; marcador 231 frente a 435).

## 2. Sospechas (a confirmar midiendo, en este orden)

1. **Devolver la memoria de la tarjeta tras cada inferencia** (`cloud/arranque/nube_gpu.py`, puesto el 13-11 por la memoria
   llena): cada inferencia vuelve a pedir memoria a CUDA. En modelos pequeños, fotograma a fotograma (YOLO, bola, la lejana)
   ese coste puede dominar. Encaja con que lo más lento sean justo esos.
2. **Decodificar el vídeo en la CPU**: el PC usa su decodificador (`hwaccel`, d3d11va); en la nube se quitó. Encaja con
   «recorte» 8 veces más lento y con los 16 núcleos ocupados.
3. Ajustes de CUDA (búsqueda de algoritmos de cuDNN «HEURISTIC»; modelos en media precisión).

## 3. Cómo se mide (prueba corta de 10 min de Osaka, ~0,5 $ cada una)

- A: como hoy. B: devolver memoria solo en el proceso principal (las ventanas en paralelo guardan la suya).
  C: B + decodificar en la tarjeta (NVDEC). Para cada una: tiempo por parte de la pasada fina, memoria máxima de la T4,
  núcleos usados, y **los mismos golpes y medidas que A** (si cambian los fotogramas o las medidas, no vale).
- Se acepta un cambio solo si da lo mismo que antes (golpes, derechas, medidas de la prueba) y es más barato.

## 4. Segunda nube gratuita: Kaggle (comprobar en su página al crear la cuenta)

Lo que dicen las fuentes de 2026: **~30 h de GPU por semana** (se renueva cada semana), sesiones de **hasta 12 h**,
GPU T4 ×2 o P100, sin tarjeta; hace falta verificar el teléfono para GPU e internet. Se lanzaría desde GitHub igual que
Modal (API de Kaggle: subir el cuaderno y leer su salida). Menos CPU que Modal: cada partido tardaría más.
Fuentes: [Kaggle, consejos de GPU](https://www.kaggle.com/page/GPU-tips-and-tricks),
[resumen 2026](https://fastero.com/blog/kaggle-notebooks).

## 5. Capacidad (se rellena con lo medido)

| Opción | Partidos de ~90 min al mes | Coste |
|---|---|---|
| Modal hoy (0,054 $/min) | ~4 | 0 € (crédito) |
| Modal tras los arreglos de §3 | por medir | 0 € |
| Kaggle (30 h/semana) | por medir | 0 € |

Objetivo del usuario: **≥ 10 partidos al mes a 0 €** (#279).
