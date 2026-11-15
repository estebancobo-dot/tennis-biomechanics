# N · La aplicación en la web: alojamiento, vídeos y acceso privado a 0 € (15-11, #296-#298)

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
