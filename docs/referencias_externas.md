# Referencias externas: cómo se buscan, se leen, se comparan y se usan (02-11)

Regla del plan a corto plazo (`plan_maestro.md`): una referencia externa nunca es trabajo aparte. Entra como
candidato dentro del paso del plan donde se aplica, y solo se adopta si gana **medida con nuestros datos**.

## Procedimiento (el mismo para cada proyecto o artículo)

1. **Buscar.** Al empezar cada bloque del plan, siempre con las mismas búsquedas, y anotar el resultado aquí con su fecha:
   - GitHub, temas: `tennis`, `rtmpose`, `sports-analytics`; "tennis broadcast pose", "tennis stroke detection".
   - arXiv y revistas: "tennis pose estimation", "tennis stroke spotting", "tennis ball tracking", "tennis biomechanics monocular".
   - Lo que el usuario envíe entra en la tabla el mismo día.
2. **Filtrar (15 min por proyecto).** Cinco preguntas, cada una con su respuesta escrita en la tabla:
   - ¿Usa retransmisiones de TV o una cámara de fondo?
   - ¿Hay código, y con qué licencia?
   - ¿Tiene modelos con pesos públicos?
   - ¿Mide su precisión con datos anotados?
   - ¿Qué pieza nuestra podría mejorar?

   Si no cumple ninguna de las cuatro primeras, se descarta con su motivo.
3. **Leer el código** de lo que pasa el filtro. Se descarga aparte (nunca dentro del repositorio). De cada pieza útil sale una línea en la tabla con el paso del plan donde entra:
   - **modelo** → prueba de modelos (Base, paso 2);
   - **algoritmo** → el paso de su pieza (repeticiones, marcador, botes…);
   - **medida** → la matriz de cobertura.
4. **Comparar midiendo, nunca leyendo.** Con el mismo script y los mismos datos que lo nuestro:
   - modelos: `scripts/model_trials.py` y los `scripts/bench_*.py` (precisión con F3Set y RacketVision, fotogramas/s en el PC);
   - medidas: la auditoría, incluida la prueba de la cámara.

   El criterio para adoptarlo se escribe antes de medir.
5. **Usar lo que gana:**
   - El código con licencia MIT o Apache se copia, citando el origen y la licencia en el fichero.
   - Sus modelos se pasan a ONNX para la iGPU, como se hizo con RacketVision.
   - Se deja una prueba automática.
   - Lo que pierde queda anotado aquí con su número, para no volver a probarlo.

## Tabla

| Fuente | Encontrada | Filtro | Código leído | Qué aporta → paso del plan | Medido | Decisión |
|---|---|---|---|---|---|---|
| deep-sports-analysis (off policy), artículo del 22-10 | usuario, 02-11 | TV ✔ · MIT ✔ · pesos ✔ · precisión ✔ | **sí** (02-11, `docs/analisis_referencias.md`) | Modelos WASB, RTMW-x, RF-DETR, TennisCourtDetector y F3ED → paso 2. Regla de 2,5 s → paso 3. Regla de la cámara → B-15 (hecha en la auditoría). 22 medidas → B-15 | Regla de la cámara: 9 de 479 medidas dependen de la cámara. Modelos (petición 75, iGPU): RTMW-x igual precisión y 3 veces más rápido; pista de 14 puntos mejor y más rápida; WASB peor; RF-DETR mejor pero más lento; F3ED peor y más lento | **Pista de 14 puntos adoptada (03-11)**. RTMW-x: adoptado y retirado el mismo día, porque en el análisis real fue más lento (petición 76). WASB, RF-DETR y F3ED no |
| explainx.ai / Roboflow (iPhone) | usuario, 02-11 | móvil ✘ · sin código ✘ · sin medidas ✘ | — | — | — | **descartada** |
| philippdubach/tennis-vision | búsqueda, 02-11 | TV ✔ · licencia por ver | no | Marcador + conciliación por cambios de tanteo → P1 (resultado del punto) | — | se lee al llegar a P1 |
| JustinSongXh/tennisvision | búsqueda, 02-11 | por ver | no | Botes de bola → B-10 | — | se lee en el paso 2 (bote) |
| CalTennis (arXiv 2606.20542) | búsqueda, 02-11 | datos con varias cámaras ✔ | no | Validación automática del 3D y de los pies → B-6 | — | se lee en el paso 2 (3D) |
| Capture4D (Sensors 26-1411) | búsqueda, 02-11 | artículo | no | Confirma que, con una sola cámara, el orden de la cadena cinética es fiable | — | nada que adoptar |
| xiaollz/tennis_analyzer, otros de GitHub con MediaPipe | búsqueda, 02-11 | móvil o clip corto | no | probablemente nada | — | filtrar en la próxima búsqueda |
