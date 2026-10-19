# Almacenamiento definitivo (especificación, 19-10)

Aprobada por el usuario («con que cubra los requisitos y escenarios vale»). Se implementa en el bloque 4 de
`docs/plan_maestro.md`, antes de la pasada definitiva de los 4 partidos. Hoy la aplicación usa todavía las carpetas
del proceso (`output\<id-del-fichero>\`, pruebas mezcladas con lo real, informes sueltos).

## Árbol
```
C:\tenis\
  videos\                         del usuario; la aplicación nunca los mueve ni borra
  biblioteca\
    datos\tennisbio.db            índice; se reconstruye desde las carpetas
    jugadoras\<jugadora>\ficha.yaml   mano, revés, altura, alias (marcador, otros alfabetos)
    partidos\<año>\<partido>\
      partido.json                torneo, fecha, ronda, superficie, jugadoras, cadena, emisiones (huella + ruta)
      etapas\                     pasada barata: planos, sonido, pista, marcador, jugadoras, identidad
      golpes\<jugadora>\          pasada fina por jugadora: golpes, series, ventanas de vídeo
      repeticiones\  tomas\       repeticiones y otras cámaras, enlazadas a su golpe en directo
    analisis\<jugadora>\<golpe>\  actual\, v1..vN\, pendiente\
    exportar\<jugadora>\<golpe>\  movil\  copias\  diagnostico\
    pruebas\                      ejecuciones del ciclo y validaciones (nunca junto a lo real)
```

## Nombres
- Jugadora: `apellido-nombre`, minúsculas ASCII, transliterado (`rybakina-elena`).
- Partido: `AAAA-MM-DD_torneo_ronda_jugadoraA-jugadoraB` (jugadoras en orden alfabético por apellido, ≤ 80 caracteres).
- Golpe (tipo): `forehand`, `backhand`, `serve`, `volley`, `overhead`. Golpe concreto: partido + tiempo de impacto en ms.
- Vídeo: su huella de contenido (no el nombre ni la ruta).
- Solo `[a-z0-9_-]`; nunca dos nombres que difieran solo en mayúsculas.

## Reglas
- Entradas inmutables; cada fichero de salida guarda la huella de sus entradas, ajustes y código.
- Escritura atómica (temporal + renombrado); todo idempotente; nada se borra (versiones).
- Rutas relativas dentro de `biblioteca\` (se puede copiar a otro disco); ruta total < 240 caracteres.
- El índice es derivado: si se pierde o se daña, se reconstruye.

## Casos
| Tipo | Caso | Respuesta |
|---|---|---|
| Nominal | Partido nuevo | Carpeta por año y nombre; análisis de cada jugadora |
| Nominal | Analizar a la rival | `golpes\<rival>\` del mismo partido, sin repetir la pasada barata |
| Límite | Vídeo renombrado o movido | Misma huella → mismo partido; se actualiza la ruta, no se recalcula |
| Límite | Vídeo borrado / USB desconectado | Resultados conservados, «vídeo no disponible» |
| Límite | Partido en varios ficheros | Un partido, varios segmentos |
| Límite | Resumen o partido incompleto | Se acepta y se marca |
| Esquina | Misma final de otra cadena | Mismo partido, dos emisiones; repeticiones de ambas |
| Esquina | Dos partidos iguales en fecha/torneo/ronda/jugadoras | Sufijo `-2` |
| Esquina | Fecha desconocida | `sin-fecha_<6 de la huella>` |
| Esquina | Mismo apellido | Se añade el nombre |
| Esquina | Nombres no latinos o largos | Transliteración; recorte + huella |
| Esquina | Ruta larga en Windows | Nombres acotados; aviso si la raíz es demasiado profunda |
| Error | Disco lleno a mitad | Nada a medias (atómico); se reanuda |
| Error | Fichero dañado | Se recalcula esa etapa |
| Error | Índice dañado | Se reconstruye |
| Error | Migración cortada | Diario de migración; se reanuda sin duplicar |
| Error | Sin permisos | Aviso claro; nada a medias |

## Migración
Lo actual (`output\<id>\`, `output\analisis\`, `informe_*`, `exportar_*`, `_poc*`/`_smoke`) se traslada sin
recalcular: partidos a `partidos\`, pruebas a `pruebas\`; las carpetas viejas se dejan hasta comprobar la copia.
