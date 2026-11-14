# Operación en la nube: qué hacer en cada caso y cómo se valida (14-11)

Para cualquier sesión de Claude que retome el trabajo. **Primero:** `docs/estado_proyecto.md`, sección «PLAN ÚNICO A
SEGUIR»: la primera tarea no hecha cuyas dependencias estén hechas. **Después:** el estado real de la nube.

## 1. Dónde mirar

| Qué | Dónde |
|---|---|
| Trabajos, gasto y avisos | Rama `nube-logs`: `cola/estado.md` (resumen), `cola/estado.json`, `cola/gasto.json`, `cola/partidos.json`; los mismos (y `vuelta.json`) en el volumen, `/cola/`, para la auditoría de la nube («Cola de la nube») |
| Resultados de cada trabajo | Volumen de Modal `tennisbio-datos`: `/runs/<carpeta>/estado.json` y `log.txt`; `/output/<partido>/manifest.json` (los trae la acción «recoger» del flujo «Nube») |
| Kaggle | Acción `kaggle_estado`: cuota real, versiones y estado de la sesión; `kaggle_sonda` (¿arranca una GPU?) |
| Modal | `docs/capacidad_nube.md` (gasto); la página Usage, que solo ve el usuario (pedirle la cifra a fin de mes) |
| Lo que cuesta cada parte | `estado.json` (`etapas`, `recursos`) y `docs/nube_nativa.md` |
| **Progreso en vivo** (#291) | `cola/estado.md`, columna «Nota» de lo que está en marcha: la etapa y su % («fine: 63 % (35/55 …) · quedan ≈ 9 min (18:42:10)»). El trabajo (Kaggle o Modal) lo escribe en su `estado.json` cada 2 min; la cola lo lee en cada vuelta (cada 5 min mientras algo corre). También en la página de GitHub Actions de cada vuelta («Cola» → resumen) |

**Cómo sigue todo sin el chat (#281, #291):**
- **La cola** (flujo «Cola» de GitHub Actions) tiene dos trabajos: la vuelta (`cola`, de una en una, nunca se cancela)
  y el latido (`latido`, solo el último: duerme 5 min si algo corre o 25 si solo hay espera, y lanza la vuelta
  siguiente). Un cambio en `config/cola_nube.yaml` o el final de un flujo «Nube» lanzan una vuelta al momento.
- **Claude despierta por eventos, no por sondeo** (#291; el aviso de cada hora se quitó el 14-11): cuando una vuelta ve
  que un trabajo acaba, falla o queda en «revisar», o que Kaggle rechaza un lanzamiento, comenta en el **PR buzón #1**
  (`avisos_pr` en `config/cola_nube.yaml`; rama `nube-avisos`, nunca se fusiona). La sesión de Claude está suscrita a
  ese PR y despierta en ese momento; mientras no pasa nada, no gasta nada. Al despertar: leer `cola/estado.md` y
  seguir este documento y el PLAN ÚNICO. Si la sesión es nueva, volver a suscribirse al PR #1.

## 2. Qué hacer en cada caso

| Caso | Qué hace la cola sola | Qué hace Claude |
|---|---|---|
| Trabajo terminado («hecho») | Lo recoge y lanza el siguiente | Leer su resultado; si es una prueba de 10 min, comparar con la referencia |
| Prueba con un fallo C0 o C1 → «revisar» | No lanza su partido | Encontrar la causa (registro del trabajo); arreglar con prueba; repetir la prueba (job nuevo o `reiniciar`) |
| Kaggle rechaza el lanzamiento («push error») | No lo cuenta; lo dice en el resumen y reintenta en la vuelta siguiente | Si es «Maximum batch GPU session count», mirar `kaggle_estado`: sesiones atascadas |
| Sesión en cola de Kaggle («queued») | Espera: Kaggle la aceptó y busca una GPU libre (R46: relanzarla antes la manda al final). A las 3 h la da por perdida: borra su cuaderno y la relanza en uno nuevo (#290, R45) | Nada, salvo que se repita: avisar al usuario. Para saber si Kaggle tiene GPU libres: acción `kaggle_sonda` («Maximum batch GPU session count of 2» = nuestras 2 plazas ocupadas por sesiones en espera) |
| Kaggle no conoce la sesión (lanzamiento perdido) | Relanza a los 10 min | — |
| Sesión cortada a las 12 h | Relanza: sigue desde lo guardado en Modal | — |
| 4 intentos fallidos | Error con el motivo | Diagnosticar; corregir; `reiniciar: ["<id>#n"]` |
| Modal sin crédito (antes del 1 del mes) | Espera con el motivo | Nada: Kaggle sigue |
| Cuota de Kaggle agotada | Espera con el motivo (se renueva el sábado 00:00 UTC) | Nada |
| La cola no corre (sin vueltas en `nube-logs`) | — | Lanzar «Cola» a mano; ver por qué se cortó la cadena de vueltas |
| Un fallo nuevo del código | — | Apuntarlo como R<n> en `estado_proyecto.md`; prueba que lo reproduce; arreglo; todas las pruebas; subida |
| Petición nueva del usuario | — | `peticiones_usuario.md` + un paquete de `plan_peticiones.yaml` + tarea en el PLAN ÚNICO |
| «comparar» hecho (idéntica o equivalente) | Lo apunta y sigue lo que esperaba por él | Si comprobaba un cambio de código de la pasada fina: poner `comprobado: true` en su entrada de `config/codigo_equivalente.json` (con la comparación de `nube-logs/cola/comparaciones/`) y subirlo; así los partidos ya analizados no repiten la pasada fina |
| «comparar» en «revisar» (distinta) | No sigue nada de lo que espera por él | Leer `nube-logs/cola/comparaciones/<id>.json` (qué etapas y qué medidas cambian); encontrar la causa; arreglar o, si el cambio es de verdad distinto, dejar la entrada sin comprobar: lo ya analizado se rehará con el código nuevo |

## 3. Cómo se valida y se acepta (el modelo de calidad del proyecto)

1. **Pruebas del código:** `uv run pytest -q -n 4`, todas y con 0 fallos antes de cada subida (regla del proyecto).
   Las del navegador usan Chromium.
2. **Pruebas de 10 min (referencia en la nube):** cada partido entero va precedido de la suya. Una prueba con C0 o C1
   no deja pasar al partido (R40).
3. **Equivalencia entre infraestructuras:**
   - El mismo clip y el mismo código deben dar los mismos golpes en cada nube (Modal frente al PC: F3Set 469 frente a
     465 y Osaka 233 = 233; Kaggle frente a Modal: 55 = 55 golpes).
   - Antes de cada versión, además, la **prueba de referencia con GPU** de `analisis_nube.md` §7: el tramo de
     referencia con los mismos golpes, F3Set (467 de 517 y precisión 0,945 con v15), identidad (489 bien y 5 mal) y la
     auditoría de los partidos.
4. **Pruebas de concepto (#288):** una opción gana solo si da igual o mejor calidad con datos anotados (F3Set,
   RacketVision) y menos tiempo o coste. Se escribe en `docs/nube_nativa.md`.
5. **Auditoría en las salidas reales:** `tennisbio audit` sobre los partidos analizados, con comprobaciones ✔/⚠/✘.
   Corre en la nube (acción «informe»).
6. **Aceptación de un paquete:** la calcula `scripts/real_status.py` desde la auditoría, con las comprobaciones de su
   `prueba` en `config/plan_peticiones.yaml`; nunca a mano. El estado queda en `docs/estado_real_peticiones.md`.
7. **Fallos por niveles C0-C4** (`config/fallos.yaml`): C0 para el análisis; C1 marca la prueba «revisar»; C2 dentro
   de presupuesto.

## 4. Riesgos que siguen abiertos (de `analisis_nube.md` §9)

- **Derechos de las retransmisiones y condiciones de uso de cada proveedor:** los vídeos pasan por Modal y por
  sesiones de Kaggle.
- **Privacidad:** región y registros sin datos personales.
- **Licencias:** Ultralytics es AGPL-3.0; vale para uso privado sin distribuir.

Se revisan en la tarea de trazabilidad (T17).
