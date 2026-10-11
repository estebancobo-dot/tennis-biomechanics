# Cómo ejecutarlo en tu PC (Windows)

**Primera vez (sin Git):** pega esta línea en PowerShell (tecla Windows, escribe PowerShell, Intro):
```
irm https://raw.githubusercontent.com/estebancobo-dot/tennis-biomechanics/claude/tennis-biomech-setup-jggqb0/scripts/windows/bootstrap.ps1 | iex
```
Descarga el proyecto en `C:\tenis\tennis-biomech` e instala todo. Después, todo es con doble clic.

**Después: tres ficheros con doble clic**, en `C:\tenis\tennis-biomech`:
1. `1_instalar.bat` — actualiza el proyecto a la última versión e instala lo que falte (ffmpeg, uv,
   Python, librerías, modelos); lo comprueba todo.
2. `2_prueba_rapida.bat` — mide la velocidad del equipo y analiza 4 minutos de un partido de
   `C:\tenis\videos` de principio a fin; abre el informe.
3. `3_analisis_completo.bat` — todos los vídeos de `C:\tenis\videos`, todas las etapas y los
   informes de derecha, revés y saque. Se puede cortar y relanzar.

No hay que editar nada: el catálogo se crea solo y el rival se lee del marcador. Cada script
guarda su registro en `C:\tenis\output\*.log`; si algo falla, pasa ese fichero a Claude.

Lo que sigue es lo mismo paso a paso, por si hiciera falta.

## 0. Requisitos (una vez)
- Python 3.11 y `uv` instalados; `ffmpeg` en el PATH (`ffmpeg -version` responde).
- `git pull` para tener la última versión de la rama.

## 1. Instalar y preparar los modelos (una vez, ~15 min)
```
uv sync --extra yolo --extra ocr --extra dev
uv run python scripts/setup_models.py
```
Al final: `balltrack.onnx OK`, `racketpose.onnx OK`, `rtmw3d-x.onnx OK`.
Si falla una descarga, repite el comando: solo baja lo que falta.

## 2. Comprobar el entorno (1 min)
```
uv run python scripts/check_env.py "C:\tenis\videos\partido1.mp4"
```
Debe salir `ORT providers: [... 'DmlExecutionProvider' ...]` (la iGPU) y los tres modelos en OK.
Si no aparece `DmlExecutionProvider`, pon `device: cpu` en `config/local.yaml` (irá más lento).

## 3. Medir la velocidad (5 min)
```
uv run python scripts/benchmark.py "C:\tenis\videos\partido1.mp4"
```
Da los milisegundos de cada modelo y una proyección del tiempo por partido. Pásame la salida.

## 4. Prueba de 4 minutos de partido (10-30 min)
```
uv run python scripts/smoke_test.py "C:\tenis\videos\partido1.mp4" --opponent "Aryna Sabalenka" --start 1800 --minutes 4
```
Ejecuta todas las etapas sobre un trozo y genera el informe en
`C:\tenis\output\_smoke\informe\index.html` (ábrelo con Chrome o Edge). Al final estima cuánto
tardará el partido entero. Pásame el resumen de etapas que imprime.

## 5. Catálogo de partidos
Copia `config\matches.example.yaml` a `config\matches.yaml` y rellena una entrada por vídeo:
`id`, `video` (nombre del fichero en `C:\tenis\videos`), `player: rybakina`, `opponent` (como
sale en el marcador), y si quieres analizar también a la rival, `opponent_id`.

## 6. Partidos completos
```
uv run tennisbio run --all
uv run tennisbio status
```
Solo ejecuta lo que falta o ha cambiado; se puede interrumpir y relanzar. `status` muestra cada
etapa por partido (`ok`, `missing`, `stale`).

## 7. Informe
```
uv run tennisbio report                      # derechas de Rybakina, todos los partidos
uv run tennisbio report --stroke backhand    # reveses
uv run tennisbio report --stroke overhead    # saques y remates
uv run tennisbio report --player sabalenka   # la rival (con analyze_opponent: true)
```
Sale en `C:\tenis\output\informe\index.html`.

## Si algo falla
- Copia el error completo (las últimas 20 líneas) y pásamelo.
- `uv run pytest` comprueba el código (debe salir todo en verde).
- Para repetir una etapa: `uv run tennisbio run --match <id> --stages fine --force`.
