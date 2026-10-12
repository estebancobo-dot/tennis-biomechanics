# Estado del proyecto y contexto para continuar

Este fichero lo mantiene Claude: resume lo hecho, lo decidido con el usuario y lo pendiente, para que
cualquier sesión (en la nube o en el PC) continúe sin perder nada. Los requisitos del usuario y el
plan están en `CLAUDE.md`; la taxonomía en `docs/matriz_cobertura.md`; las validaciones en
`docs/validacion.md`; la revisión de errores en `docs/revision_completa.md`.

## Cómo se trabaja (acordado con el usuario)
- El usuario **no revisa datos, no lee documentos, no copia registros**: todo automático.
- En el PC solo hace doble clic en `1_instalar.bat`, `2_prueba_rapida.bat`, `3_analisis_completo.bat`.
- **Registros del PC → Claude, automáticos:** cada script sube al terminar (o al fallar) sus
  registros a la rama **`pc-logs`** del repositorio (carpeta local `C:\tenis\registros`):
  `instalacion.log`, `prueba_rapida.log`, `analisis_completo.log`, `equipo.txt` (CPU, gráfica,
  RAM, disco) y `partidos/<id>.log` + manifiestos y errores de cada partido.
  Para leerlos desde cualquier sesión: `git fetch origin pc-logs && git show origin/pc-logs:instalacion.log`
  (o `git log origin/pc-logs` para ver cuándo se subieron).
- Código y documentación se desarrollan en la rama `claude/tennis-biomech-setup-jggqb0`. En el PC el
  proyecto está clonado con Git en `C:\tenis\tennis-biomech` y `1_instalar.bat` hace `git pull`.
- El partido completo (los 4 partidos) se ejecuta **una sola vez, al final**, cuando todo funcione.
- Móvil y nube: al final, después de que el PC funcione.

## Estado (octubre de 2026)
Hecho y validado en la nube (ver `docs/validacion.md`):
- Pipeline completo por etapas con caché e idempotente; identidad automática (cambios de lado +
  ropa + saque); marcador por OCR; pista por homografía (comprobada cada ~8 s y en cada impacto).
- Detección de golpes con pose + bola: lado cercano P 0,73 / R 0,84; lado lejano P 0,67 / R 0,73.
- Modelo técnico completo (8 fases, ~200 descriptores, pies, ritmo, raqueta, clases y situaciones)
  con fuentes (`docs/matriz_cobertura.md`); estadística ajustada por situación y partido (OLS
  robusto + Benjamini-Hochberg); pantalla "Su derecha"; videoteca, comparar, exportación MP4/PDF.
- Casos límite de vídeo: sin audio, varias pistas, .ts con saltos, fps variables, 1080i, 4K,
  cortados, rutas con acentos, vacíos (todos probados).
- Escala: 2.400 derechas → informe en 47 s, 6 MB, carga en 2,7 s.

### Primera prueba rápida en el PC (12-10-2026)
- Equipo real: Ryzen 7 8745HS, Radeon 780M (DirectML disponible), 20 GB RAM, Windows 11, ffmpeg 9.0.2.
- Instalación: 88/88 pruebas pasan en Windows (tras arreglar ffmpeg 9, nombres en cirílico y UTF-8).
- **F3Set (Rybakina, Open de Australia 2023, 21 clips; 9 no se descargaron):** precisión 0,92,
  recall 0,65 (golpes de fondo 29/33 = 0,88; saques 1/15, no son el objetivo), derecha/revés 0,97,
  dirección 0,89, subida a la red 0,97, instante ±1 fotograma.
- **Su vídeo (final US Open 2026, retransmisión rusa, 1080p50, 210 min): 0 golpes analizados.**
  Marcador 0 lecturas (sin nombre del rival en el catálogo y el OCR no lo encontró), pista en 3 de
  11 tramos, identidad sin decidir → todo descartado; solo 2 candidatos en 4 min. **Bloqueante.**
  **Causa (imágenes de diagnóstico):** los 4 min elegidos (minuto 30) eran la previa: himno,
  bandera, entrenamientos y un resumen del partido anterior de Sabalenka contra Noskova; no había
  juego. El clasificador de planos tomaba esos planos por "cámara principal". Retransmisión de
  Eurosport con el marcador internacional (latino, legible). Arreglado: la prueba rápida busca
  sola un tramo con juego; jugadores y lectura del rival solo donde se ve la pista.
- Segunda prueba (minuto 121, un juego al saque de Sabalenka desde el fondo): marcador 48 lecturas,
  13 candidatos, pero identidad sin decidir → 0 golpes. Causa: solo se votaba cuando la cercana
  sacaba. Arreglado: si saca la del fondo, la cercana es la que resta (voto de resto).
- Velocidad: YOLO 960 en la iGPU 112 ms/fotograma (CPU 479); decodificación 1080p50 27 fps (CPU),
  40 fps (d3d11va). Estimación lineal 5,6 h por partido sin la pasada fina → ~1 día los 4. La etapa
  de jugadores domina (277 s por 4 min).

- Tercera/cuarta prueba: 10 golpes confirmados (6 derechas), identidad decidida (voto de resto).
  Pasada fina 93 → 26 s por golpe (raqueta en la iGPU en proceso aparte: el controlador DirectML
  dio un 0xC0000005 en el proceso principal). Estimación ~5 h por partido (~2 h jugadores, ~2 h
  pasada fina). Progreso por etapa con % y tiempo restante; hojas de imágenes de cada golpe.
- Revisión a ojo de los 10 golpes: derecha/revés 10/10; apoyo razonable. Corregido: "en el aire"
  (10/10 por la perspectiva al avanzar), terminación de revés, "cómo llega" = velocidad antes del
  swing (en el contacto el cuerpo se mueve 2-3 m/s por el traslado de peso). Pasos uno a uno, apoyos
  y split step NO medibles en esta retransmisión (tobillos de ~190 px a 50 fps tiemblan 0,2-1 m/s):
  se ocultan por golpe cuando un pie no se ve quieto en ≥ 40 % de los fotogramas.

### Pedido por el usuario y pendiente (después de arreglar su retransmisión)
- ✔ Lo que hace respecto a la bola en cada momento (cruza la red, bota, punto más alto; golpea
  subiendo / arriba / cayendo; `ball3d.py`) y curvas de altura sincronizadas con el vídeo (cabeza,
  cadera, mano, raqueta) con su curva típica y su franja por situación (informe: «Análisis de golpe»
  y «Su derecha»). Falta verlo con golpes reales del PC (prueba rápida).
- Auditoría automática de requisitos sobre las salidas reales + hoja de imágenes de golpes al azar.

Pendiente que **solo puede hacerse en el PC**:
1. Instalación (falló la primera vez; ver `pc-logs:instalacion.log`).
2. `2_prueba_rapida.bat`: velocidad real en la iGPU (DirectML) y validación F3Set (30 puntos de
   Rybakina; YouTube bloquea la descarga desde la nube).
3. Ajustes según esos resultados; después los 4 partidos (una vez).

Limitaciones asumidas (no se "arreglan" con falsa precisión): empuñadura exacta, ruido de medida
real (sale de sus golpes en los partidos), apoyo sin validación con datos anotados (ningún conjunto
público lo anota), velocidad absoluta de la raqueta, efecto de la bola.
