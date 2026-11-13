# Prueba de la nube (N0): pasos del usuario y cómo funciona (13-11, #273)

**Qué es:** la misma validación de F3Set que hace el PC, con el mismo código y los mismos modelos, en una GPU NVIDIA L4
de Modal. Se compara golpe a golpe con el resultado del PC (F3Set v17, trabajo 121). Dice dos cosas: si la nube da lo
mismo y cuánto más rápida es (k, por etapa). **Coste: 0 €** (el tope de la cuenta en el crédito gratis de cada mes).
**No toca nada de lo que hace el PC**, salvo una subida de datos de una vez, por la cola, detrás de la validación en curso.

## Pasos del usuario (una sola vez, unos 15 minutos)

### 1. Cuenta de Modal (en el navegador, 5 min)
1. Entra en **modal.com** y pulsa **Get started** (también está en modal.com/pricing).
2. Regístrate. Si te ofrece **GitHub**, usa tu cuenta de GitHub, que es lo más rápido; si no, Google o correo.
   Modal crea tu espacio de trabajo («workspace») con tu nombre de usuario. Queda en el **plan Starter: 0 $ al mes y
   30 $ de crédito gratis cada mes**.
3. Si al registrarte o al entrar en la facturación te pide una **tarjeta**, ponla. Las fuentes no se ponen de acuerdo
   en si hace falta para el crédito gratis (alguna habla de un cargo de verificación de 0,50 $). Con el tope del paso 4
   nunca se cobra nada más.

### 2. Tope de gasto: 0 € (2 min) — imprescindible
1. Ve a **modal.com/settings/usage** (menú **Settings → Usage & Billing**).
2. Pon el **Workspace budget** (también llamado «usage limit») en **30**. Es el límite de uso del mes **antes** de
   descontar el crédito gratis, que son también 30 $.
3. Mira el **Spend limit**: es lo que pagarías tú, **después** del crédito. Por defecto vale el límite de uso menos el
   crédito, así que debe quedar en **0 $**. Si la página deja escribir 0 directamente, escribe **0**.
4. Según la documentación oficial (modal.com/docs/guide/budgets), al llegar al límite **Modal para lo que costaría
   dinero**. Si un mes se gastara el crédito, la prueba espera al mes siguiente.

### 3. La clave (token) de Modal (2 min)
1. Ve a **modal.com/settings/tokens** y pulsa **New Token** (o «Create new token»).
2. Te enseña dos textos: el **Token ID** (empieza por `ak-`) y el **Token Secret** (empieza por `as-`). El secreto solo
   se ve una vez: **deja esa pestaña abierta** hasta terminar los pasos 4 y 5.

### 4. La clave en GitHub (3 min)
1. Entra en **github.com/estebancobo-dot/tennis-biomechanics**.
2. **Settings** (pestaña de arriba a la derecha del repositorio) → en el menú de la izquierda **Secrets and variables →
   Actions** → botón verde **New repository secret**.
3. **Name:** `MODAL_TOKEN_ID` · **Secret:** el Token ID (`ak-…`) → **Add secret**.
4. Otra vez **New repository secret**: **Name:** `MODAL_TOKEN_SECRET` · **Secret:** el Token Secret (`as-…`) →
   **Add secret**.

Con esto, Claude ya puede desplegar y lanzar la prueba desde GitHub (flujo «Nube», `.github/workflows/nube.yml`).

### 5. La clave en el PC (1 min, cuando el PC termine la validación de hoy)
1. Cuando la cola del PC quede libre (hacia las 18:00-18:30 del 13-11), el PC trae el código nuevo y aparece
   **`5_conectar_nube.bat`** en `C:\tenis\tennis-biomech`. Claude avisa cuando esté.
2. Doble clic → pega el **Token ID** y Enter → pega el **Token Secret** (no se ve al pegarlo) y Enter.
3. Debe decir **«Clave correcta»**. La clave se guarda solo en `C:\tenis\secretos\modal.env`, nunca en GitHub.

Eso es todo. **No hay que avisar a Claude:** el doble clic deja una marca, sin la clave, en los registros del PC, y
Claude pone la subida en la cola.

## Lo que hace Claude después (automático)
| Paso | Dónde | Qué | Cómo se comprueba |
|---|---|---|---|
| 1 | GitHub → Modal | Flujo «Nube», acción **comprobar**: despliega la imagen y mira la GPU, ONNX Runtime con CUDA (también en un proceso nuevo, como los de la pasada fina), una sesión real en la GPU y la configuración | Salida del flujo («proceso_nuevo»: `CUDAExecutionProvider`) |
| 2 | PC, por la cola (detrás de lo pedido) | `script subir_nube --pc-tag v17`: sube una vez los modelos del PC, las 4 compilaciones de F3Set (YouTube no deja descargar desde la nube), su configuración (sin rutas) y su informe y tiempos de F3Set v17. **Ningún vídeo de partido** | `capturas_diag/subir_nube.json` en pc-logs |
| 3 | GitHub → Modal | **comprobar** otra vez: los modelos y los datos ya están | Salida del flujo |
| 4 | GitHub → Modal | **f3set** (tag `nube`): la validación desde cero en la L4; el flujo vuelve al momento y la ejecución sigue en Modal | `runs/nube/estado.json` |
| 5 | GitHub → Modal | **recoger**: el estado, el registro y la **comparación con el PC** (`comparacion.md`): golpes encontrados, precisión, golpes falsos, error de instante, golpe a golpe y k por etapa, con el coste | Veredicto «equivalente» o «distinto» con su lista |

**Criterio de «equivalente»** (`cloud/nube.py`):
- ±2 golpes encontrados de 517;
- ±0,005 de precisión;
- ≥ 98 % de los golpes anotados en el mismo paso.

DirectML y CUDA no dan los mismos decimales. Si sale «distinto», se ve qué golpes y por qué antes de decidir nada.

## Cómo está hecho (para no tocar el PC)
- **`cloud/`** (fuera del paquete; nunca corre en el PC):
  - `modal_app.py`: la imagen con las dependencias bloqueadas del proyecto y `onnxruntime-gpu` 1.24.4, la misma versión que la DirectML del PC; las funciones `comprobar` y `f3set`; volumen `tennisbio-datos`.
  - `lanzar.py`.
  - `nube.py`: preparar, comparar y coste.
  - `site/sitecustomize.py`: en la nube, el dispositivo que la configuración llama «dml» pone sus sesiones en CUDA.
- **Así todo el código es el del PC:**
  - la pose en media precisión;
  - dos procesos de pasada fina;
  - lotes fijos de bola;
  - la configuración del PC (`local.yaml` sin rutas ni el decodificador de Windows).
- **Ningún módulo del paquete cambia:** ni huellas, ni versiones de etapa, ni cachés del PC. `tests/test_nube.py` lo comprueba.
- **En el PC solo hay dos cosas nuevas:**
  - `5_conectar_nube.bat` (`scripts/windows/clave_nube.ps1`);
  - `scripts/subir_nube.py`, la única subida permitida (`tests/test_local_only.py`, excepción del paquete N).
- **Coste de la prueba:** una hora de L4 con 8 núcleos y 32 GiB cuesta ~1,43 $. F3Set tarda 5 h en el PC; en la nube, de unos minutos a ~5 h según k. En cualquier caso, dentro de los 30 $ del mes: **0 €**.
