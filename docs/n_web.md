# N · La aplicación sin web: subida desde el PC, análisis en la nube, resultados en el PC (15-11, #301)

**Decisión vigente (15-11, #301, del usuario).** Los vídeos se suben desde el PC y la aplicación se ve en el PC. Nada
de móvil. La aplicación puede ser de escritorio si es mejor, y lo es:

| | Aplicación de escritorio en el PC (**elegida**) | Web privada (Hugging Face o Cloudflare) |
|---|---|---|
| Subir un vídeo de 5 GB | Desde el disco del PC al volumen de Modal, por partes y reanudable; ya funciona (`scripts/subir_nube.py` subió los 6 partidos) | Desde el navegador: frágil con 5 GB; a un sitio nuevo |
| Ver el vídeo de cada golpe | Desde el disco del PC: avanzar fotograma a fotograma y la cámara lenta son inmediatos | Por internet desde el almacenamiento privado: cada salto espera a la red |
| El clic de identidad | Sobre un fotograma del vídeo que ya está en el PC | Hay que extraer y subir el fotograma |
| Privacidad y coste | Nada público ni alojado; 0 € | Alojamiento privado con su cuenta, su acceso y sus límites gratuitos (el espacio gratis de Hugging Face se duerme) |
| Cuentas nuevas | Ninguna: la clave de Modal y la de GitHub ya están en el PC (`5_conectar_nube.bat`, `4_conectar_github.bat`) | Hugging Face (o Cloudflare) y su token |
| Actualizaciones | Las del PC de hoy: `1_instalar.bat` y el ciclo automático traen el código nuevo | Inmediatas |

**Cómo queda:**
- **Interfaz:** la de P0 (React + TypeScript), compilada a ficheros estáticos y abierta en una ventana del PC (pywebview
  con WebView2, ya instalado).
- **Subir:** la aplicación sube el vídeo al volumen de Modal (lo de `subir_nube.py --que partidos`).
- **Analizar:** la cola de la nube (Kaggle y Modal); el PC no analiza (`config/pausa_pc.txt`, #284) ni es servidor.
- **Clic y aprobación:** se guardan como trabajos de la cola (`config/cola_nube.yaml`).
- **Resultados:** la aplicación descarga los JSON y los recortes de vídeo del partido a `C:\tenis\output`.
- **Borrado:** el vídeo se borra del volumen al aceptar el partido (T22).

**Prueba de concepto (sustituye a la de abajo):**
1. Subir un partido de 5 GB desde el PC con la aplicación: tiempo y reanudación si se corta.
2. Que la cola lance la prueba de 10 min sola.
3. Descargar los resultados de un partido ya analizado (los de la beta) y abrir sus golpes en la ventana: tiempo de la
   descarga y del vídeo.
4. Borrar el vídeo del volumen al aceptar.

**Aceptación:** los 4 pasos a 0 €, y el usuario solo sube, hace el clic y aprueba.

---

**Histórico (15-11 mañana, antes de #301): la versión web, para subir y ver desde el móvil.** Queda como alternativa por
si algún día hiciera falta verla fuera del PC; la interfaz sería la misma.

Lo que no es interfaz (la interfaz es la de P0, diseñada ya como web y construida una sola vez, #296). Qué debe cumplir:
- el usuario solo **sube el vídeo**, hace **el clic de identidad** y **aprueba**; ve los resultados en el móvil;
- **0 € al mes**; **privado** (solo él);
- los vídeos se **borran al aceptar** el partido (T22);
- el análisis sigue en Kaggle y Modal, por la cola; nada depende del PC.

## Opciones (búsqueda del 15-11; datos de proveedores y terceros, a confirmar con su prueba)

| Opción | Web | Vídeos (5 GB) y resultados | Privado | Límites gratis | Lo que hace el usuario |
|---|---|---|---|---|---|
| **A. Hugging Face** | Space privado (CPU gratis) | Conjunto de datos privado; subida desde el navegador | Solo su cuenta | 100 GB privados; sin límite por repositorio | Crear la cuenta y un token |
| **B. Cloudflare** | Pages (ancho de banda ilimitado) | R2 (10 GB gratis, salida gratis) con subidas firmadas por un Worker | Access (gratis < 50 usuarios, código por correo) | R2 10 GB: un partido a la vez | Crear la cuenta, el bucket y un token |
| C. Artefacto de Claude | Página privada en claude.ai | No caben los vídeos (≤ 256 MB por versión) | Su cuenta de Claude | — | Nada |
| D. Modal (función web) | Endpoint de Modal | Volumen de Modal | Clave propia | Gasta el crédito del mes (30 $), compartido con el análisis | Nada |

**Propuesta: A (Hugging Face)**, la de menos piezas: una cuenta, 100 GB privados para los vídeos y los resultados,
subida desde el navegador del móvil o del PC, y Kaggle y Modal descargan con un token. B queda como alternativa si la
subida de 5 GB desde el navegador falla o es lenta en A. C sirve para enseñar maquetas y resultados ya calculados
(pequeños), no como aplicación. D gasta el crédito que hace falta para analizar.

## Prueba de concepto (antes de construir nada)

1. Subir un vídeo de ~5 GB desde el navegador del móvil a un conjunto de datos privado: tiempo y si se corta.
2. Que la cola lo vea solo y lance la prueba de 10 min en Kaggle leyendo el vídeo desde Hugging Face (tiempo de
   descarga en Kaggle).
3. Un Space privado con una página estática que lea un resultado del conjunto de datos privado (solo con su sesión).
4. Borrar el vídeo desde la cola y comprobar que la cuota baja.

Aceptación: los 4 pasos funcionan a 0 €, sin que el usuario toque nada más que la subida, el clic y la aprobación.

## Lo que el usuario tendrá que hacer (una vez, cuando la prueba esté lista)

Crear la cuenta de Hugging Face (si no la tiene) y un token de acceso con permiso de escritura, y guardarlo como
secreto en GitHub y en Kaggle (con la misma guía que se usó para Kaggle, `docs/kaggle.md`). Claude no puede crear
cuentas ni ver los tokens.

Fuentes: [límites de Hugging Face](https://huggingface.co/docs/hub/storage-limits), [Cloudflare Access](https://www.cloudflare.com/en-gb/products/zero-trust/access),
[planes de Cloudflare Zero Trust](https://blog.cloudflare.com/teams-plans), [R2 en Cloudflare](https://blog.cloudflare.com/r2-ga),
[precios de R2 en 2026](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/),
[Pages frente a Vercel](https://deploywise.dev/compare/cloudflare-pages-vs-vercel).
