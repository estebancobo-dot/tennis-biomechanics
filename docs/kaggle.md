# Kaggle: la segunda nube gratuita (paso 8b, #283, #285)

Estado: **cuenta creada por el usuario (14-11: cuaderno `tennisbio-cola` con los secretos e internet); paso 8b en curso**: `cloud/kaggle/correr.py` (lo que corre en Kaggle), `cloud/kaggle/cuaderno.py` (lo lanza y lo lee desde GitHub), acciones `kaggle_comprobar` y `kaggle_prueba` del flujo «Nube», `tests/test_kaggle.py`. Nada de esto está medido todavía en Kaggle: lo
que dice «por medir» se mide con la prueba de 10 minutos antes de mandar ningún partido entero.

## 1. Qué hace el usuario (una sola vez, ~10 minutos)

1. **Cuenta.** En https://www.kaggle.com → «Register» (con Google o con correo). Gratis, sin tarjeta.
2. **Teléfono.** https://www.kaggle.com/settings → «Phone verification» → el número y el código del SMS. Kaggle lo pide
   para usar la GPU y para que el cuaderno tenga internet (hace falta: baja el código de GitHub y los datos de Modal).
3. **Token de la API.** https://www.kaggle.com/settings/api → «Generate New Token» → copiar el token (empieza por
   `KGAT_`). **No pegarlo en el chat.**
4. **Guardarlo en GitHub.** En el repositorio → «Settings» → «Secrets and variables» → «Actions» → «New repository
   secret»: nombre `KAGGLE_API_TOKEN`, valor el token. Otro secreto igual con nombre `KAGGLE_USERNAME` y valor el nombre
   de usuario de Kaggle (el que sale en la dirección de tu perfil).
5. **El cuaderno con la clave de Modal.** En Kaggle → «Create» → «New Notebook». Ponerle de título exactamente
   `tennisbio-cola`. Dentro del cuaderno: menú «Add-ons» → «Secrets» → «Add secret» dos veces: `MODAL_TOKEN_ID` y
   `MODAL_TOKEN_SECRET` con los mismos valores que ya están en GitHub (salen en https://modal.com/settings → «API
   Tokens»; se puede crear uno nuevo) y marcar las dos casillas para que el cuaderno las use. En el panel de la derecha
   («Session options»): «Internet» encendido. Guardar («Save Version» → «Quick save»).
6. Decir a Claude «Kaggle hecho». Claude hace el resto: la cola lanza el cuaderno con la API, mira su estado y recoge
   lo que deja.

## 1b. Lo medido en la primera sesión (14-11 10:04, `kaggle_comprobar`)

- **Máquina:** 2 × Tesla T4 (15 GB cada una), **4 núcleos**, 31 GB de memoria, **966 GB libres en /tmp** (temporal),
  19,5 GB en /kaggle/working (lo que se guarda), Python 3.13 (el análisis usa su propio 3.11, como Modal), ffmpeg ya
  instalado, internet bien (bajó el código de GitHub).
- **Los secretos del cuaderno no llegan a una ejecución lanzada por la API** («ConnectionError» al pedirlos): la clave
  de Modal va entonces en un **conjunto de datos privado de la cuenta**, `tennisbio-clave` (solo lo ve el usuario), que
  GitHub escribe desde sus propios secretos antes de cada lanzamiento (`cuaderno.py clave`); el cuaderno lo lee solo si
  los secretos faltan. Los secretos del cuaderno se pueden dejar o quitar: ya no hacen falta.

**Segunda y tercera sesión (14-11):** con la clave en el conjunto de datos privado, la sesión de las 10:18 se quedó
**en cola 1 h sin arrancar** (la API no dice por qué); la misma sin el conjunto de datos arrancó al momento (11:29); la
de las 11:34, ya con el conjunto de datos creado hacía más de una hora, arrancó al momento y salió bien: **clave de
Modal sí, bajar de Modal la configuración, los clics y los 44 ficheros de modelos 23 s, el entorno (Python 3.11 y las
mismas versiones que Modal) 45 s, la GPU con CUDA** (`['TensorrtExecutionProvider', 'CUDAExecutionProvider',
'CPUExecutionProvider']`), 0,02 h de la cuota. Pendiente (8b, al unir Kaggle a la cola): una sesión que se quede en
cola más de un tiempo se relanza.

## 2. ¿Cumple los requisitos? (lo que se sabe y lo que falta medir)

| Requisito | Kaggle | Cómo se sabe |
|---|---|---|
| 0 € al mes | Sí: GPU gratis, sin tarjeta | Kaggle; bajar los datos de Modal no gasta crédito de cálculo (leer y escribir en un volumen de Modal no cuenta como salida de red, y la cuenta Starter incluye 1 TiB de salida al mes) |
| 100 % automático | Sí, tras el paso 1 (una vez) | La API lanza el cuaderno (`kaggle kernels push`), da su estado y su salida |
| Que no se pare | ~30 h de GPU por semana, se renuevan cada semana; Modal sigue con su crédito de cada mes; la cola usa la que tenga sitio | La cifra exacta sale en tu cuenta; **por medir**: horas por partido |
| Un partido en horas | Probablemente sí (sesiones de hasta 12 h, dos T4) | **Por medir** con la prueba de 10 min: Kaggle tiene menos procesador que Modal (según las fuentes, 4 núcleos frente a los 16 que usaba Modal; se mide) y lo que va en el procesador irá más lento |
| Mismo código y mismos resultados | Mismo código, mismos modelos, misma tarjeta (T4) que Modal | **Por comprobar**: la prueba de 10 min de Gauff en Kaggle tiene que dar los mismos golpes que en Modal |
| Los datos de Modal sin repetir nada | Sí (ver §3) | — |

Comprobado el 14-11: los secretos del cuaderno no valen cuando la cola lo lanza por la API (ver §1b): la clave va en
el conjunto de datos privado `tennisbio-clave`.

## 3. Los datos: Modal sigue siendo el único almacén

- En el volumen de Modal están los 6 vídeos (23 GB), los modelos, los clics de identidad, la configuración del PC y
  los resultados de Osaka, Pegula y Zheng. **No se mueve ni se repite nada de eso.**
- Cada sesión de Kaggle baja de Modal solo lo de su partido (su vídeo, los modelos, la configuración y el clic), lo
  analiza con el mismo código y **sube el resultado a la misma carpeta de Modal** (`output/<partido>/`) donde están los
  otros tres. Mientras trabaja sube lo hecho cada cierto tiempo: si una sesión se corta (12 h como mucho), la siguiente
  sigue desde ahí (las etapas y las ventanas ya hechas no se repiten).
- El informe y la auditoría de la Base siguen en Modal (solo CPU, céntimos) y leen los 6 partidos juntos.
- Kaggle no guarda nada fijo: lo que queda en la sesión se borra al acabar.

## 4. Lo que hace Claude cuando el usuario diga «Kaggle hecho» (paso 8b)

1. `cloud/kaggle/`: el cuaderno (prepara el mismo entorno que la imagen de Modal, con el mismo arranque de la GPU),
   la entrada y salida de datos con Modal, y su prueba sin Kaggle.
2. Kaggle como fuente en la cola (`cloud/cola.py`): lanzar, mirar el estado, recoger; las horas de la semana en la
   cuenta del gasto.
3. Prueba de 10 min de Gauff en Kaggle frente a la de Modal (golpes, tiempo por etapa). Solo si da lo mismo, los
   partidos enteros de la cola pasan a Kaggle.
