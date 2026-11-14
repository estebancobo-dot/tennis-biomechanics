# Kaggle: la segunda nube gratuita (paso 8b, #283, #285)

Estado: **guía lista; espera a que el usuario cree la cuenta** (14-11). Nada de esto está medido todavía en Kaggle: lo
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

## 2. ¿Cumple los requisitos? (lo que se sabe y lo que falta medir)

| Requisito | Kaggle | Cómo se sabe |
|---|---|---|
| 0 € al mes | Sí: GPU gratis, sin tarjeta | Kaggle; bajar los datos de Modal no gasta crédito de cálculo (leer y escribir en un volumen de Modal no cuenta como salida de red, y la cuenta Starter incluye 1 TiB de salida al mes) |
| 100 % automático | Sí, tras el paso 1 (una vez) | La API lanza el cuaderno (`kaggle kernels push`), da su estado y su salida |
| Que no se pare | ~30 h de GPU por semana, se renuevan cada semana; Modal sigue con su crédito de cada mes; la cola usa la que tenga sitio | La cifra exacta sale en tu cuenta; **por medir**: horas por partido |
| Un partido en horas | Probablemente sí (sesiones de hasta 12 h, dos T4) | **Por medir** con la prueba de 10 min: Kaggle tiene menos procesador que Modal (según las fuentes, 4 núcleos frente a los 16 que usaba Modal; se mide) y lo que va en el procesador irá más lento |
| Mismo código y mismos resultados | Mismo código, mismos modelos, misma tarjeta (T4) que Modal | **Por comprobar**: la prueba de 10 min de Gauff en Kaggle tiene que dar los mismos golpes que en Modal |
| Los datos de Modal sin repetir nada | Sí (ver §3) | — |

Lo que no está documentado y se comprueba en la primera prueba: que los secretos del cuaderno valen cuando la cola lo
lanza por la API. Si no valieran, el plan B no necesita la clave de Modal en Kaggle: GitHub baja de Modal lo que hace
falta, se lo da a Kaggle como conjunto de datos privado, y sube a Modal lo que Kaggle deja.

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
