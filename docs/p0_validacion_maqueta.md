# Validación de la maqueta P0 (#305)

Calculada por `design/p0/validar_maqueta.py` sobre la maqueta recorrida en un navegador (`recorrer_maqueta.py`: 35 pantallas y paneles, a 1920, 1280, 1024 y 390 px). ✔ está y se ve (o se abre con un clic); ≈ sus palabras están en una pantalla, pero no su medida (a revisar); ✘ falta; ◇ hueco previsto en un paquete posterior; ⚠ aviso.

## Resumen

| Fuente | Elementos | ✔ | ≈ | ✘ | ◇ / ⚠ | Cobertura |
|---|---|---|---|---|---|---|
| Requisitos de CLAUDE.md (1-10, vistas pedidas, informe, gestión) | 55 | 49 | 0 | 6 | 0 | 89 % |
| Taxonomía de la derecha (`matriz_cobertura.md` §1-§5b) | 110 | 38 | 38 | 34 | 0 | 35 % |
| Tu lista de 15 puntos (`matriz_cobertura.md` §6) | 59 | 33 | 15 | 11 | 0 | 56 % |
| Guía de Ivanovic (20 huecos) | 20 | 11 | 0 | 8 | 1 | 58 % |
| Entrenadores de YouTube (§3, Joel Myers, The Tennis Mentor) | 18 | 11 | 0 | 6 | 1 | 65 % |
| Estado del arte: patrones adoptados (`referencias.yaml`) | 12 | 9 | 0 | 1 | 2 | 90 % |
| Usabilidad y aprendizaje | 18 | 16 | 0 | 1 | 1 | 94 % |

## Frente a cada referencia del estado del arte (`config/referencias.yaml`)

Sus patrones de presentación: los que la maqueta tiene, los adoptados que le faltan, los previstos para después y los descartados a propósito (con su motivo en el catálogo).

| Referencia | Tipo | Tiene | Le falta | Después | Descartado |
|---|---|---|---|---|---|
| Hawk-Eye SkeleTRACK | profesional | — | — | — | — |
| IBM Serve Quality y Match Chat (aplicación del US Open 2026) | retransmision | resumen_tarjetas | — | chat | puntuacion_unica |
| TennisViz (Ellipse) · Shot Quality en ATP y Tennis Data Inno | retransmision | mapa_pista | — | — | puntuacion_unica |
| HawkAR (Hawk-Eye) y rótulos ATP Media + Deltatre 2026 | retransmision | — | video_capas | — | realidad_aumentada |
| SwingVision | aficionado | mapa_pista, resumen_tarjetas | — | — | — |
| SportAI (tenis y pádel) | aficionado | cadena_cinetica | — | chat | comparar_con_profesional |
| sevensix (entrenador de tenis con IA) | aficionado | cadena_cinetica | — | — | puntuacion_unica, comparar_con_profesional |
| Sportsbox AI (golf; tenis sin confirmar) | aficionado | fotogramas_clave | — | avatar_3d | — |
| OnForm | entrenador | lado_a_lado, real_y_lento | — | — | dibujo_y_voz |
| Dartfish | entrenador | lado_a_lado, angulo_dibujado | video_capas | — | dibujo_y_voz |
| Kinovea | entrenador | angulo_dibujado, lado_a_lado | — | — | — |
| Hudl Technique | entrenador | lado_a_lado, real_y_lento | — | — | — |
| Proyectos de GitHub de análisis de tenis (abdullahtarek/tenn | github | mapa_pista | video_capas | — | — |
| Laboratorio (Theia3D sin marcadores; Vicon y Qualisys con ma | laboratorio | cadena_cinetica | — | — | — |
| Entrenadores en YouTube (Meike Babel, Intuitive Tennis, Tenn | youtube | fotogramas_clave, lado_a_lado, circulo_y_frase, real_y_lento, lo_que_copiar, mapa_pista | — | — | — |

## Requisitos de CLAUDE.md (1-10, vistas pedidas, informe, gestión): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ✘ | Empuñadura (en espera y al golpear, si se puede ver) |  |  |
| ✘ | Bola corta / profunda |  |  |
| ✘ | En carrera / parada / en salto |  |  |
| ✘ | Nada pide revisión: los dudosos se marcan |  |  |
| ✘ | Imagen estroboscópica (esqueletos superpuestos y trayectoria de la muñeca) |  |  |
| ✘ | Tira de contactos |  |  |

## Taxonomía de la derecha (`matriz_cobertura.md` §1-§5b): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ≈ | Golpe del rival → split step | leccion_fase_0 | sin medida con clave |
| ≈ | Inicio del giro de bloque (preparación) | leccion_fase_6 | sin medida con clave |
| ≈ | Final del armado (máximo giro, raqueta más atrás) | leccion_fase_8 | sin medida con clave |
| ≈ | Inicio del swing hacia delante | leccion_fase_0 | sin medida con clave |
| ✘ | Impacto |  | sin medida con clave |
| ≈ | Final de la extensión | leccion_fase_8 | sin medida con clave |
| ≈ | Final de la terminación | leccion_fase_8 | sin medida con clave |
| ≈ | Primer paso de recuperación | leccion_fase_0 | sin medida con clave |
| ≈ | Mano libre en la garganta de la raqueta en la espera / giro de bloque | leccion_fase_2 | su medida no está en la lección |
| ≈ | Momento del armado respecto al bote ("armado completo al botar") | leccion_fase_1 | su medida no está en la lección |
| ✘ | Peso entre los pies / equilibrio |  | su medida no está en la lección |
| ≈ | Cadena cinética (orden pelvis → tronco → brazo → antebrazo) | leccion_fase_0 | sin medida con clave |
| ✘ | Rotación interna del hombro, pronación, desviaciones de la muñeca |  | no medible y no lo dice |
| ≈ | Cabeza estable en el impacto | leccion_fase_3 | su medida no está en la lección |
| ≈ | Cabeza quieta tras el impacto | leccion_fase_3 | su medida no está en la lección |
| ✘ | Mirada |  | no medible y no lo dice |
| ✘ | Terminación sobre el hombro / limpiaparabrisas / alrededor / invertida |  | sin medida con clave |
| ✘ | "3 × 90°" al final |  | su medida no está en la lección |
| ✘ | Paso adelante de la pierna trasera tras el impacto |  | su medida no está en la lección |
| ≈ | Altura y separación del codo (armado e impacto) | leccion/Todas las medidas | su medida no está en la lección |
| ≈ | Transferencia de peso del armado al impacto | leccion_fase_0 | su medida no está en la lección |
| ≈ | Empuje de piernas («bajar y subir») | leccion/Lo que la tele no mide | su medida no está en la lección |
| ✘ | Fuerzas, momentos articulares |  | no medible y no lo dice |
| ≈ | Split step: aterrizaje respecto al golpe del rival | leccion_fase_0 | su medida no está en la lección |
| ✘ | Presencia del split |  | sin medida con clave |
| ≈ | Velocidad 0,2 s antes y después del split | leccion_fase_0 | su medida no está en la lección |
| ✘ | Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral) |  | sin medida con clave |
| ✘ | Primer paso: dirección correcta respecto a la bola |  | su medida no está en la lección |
| ✘ | Número de pasos hasta la bola |  | su medida no está en la lección |
| ✘ | Longitud de cada paso; anchura del primero |  | su medida no está en la lección |
| ≈ | Pasos de ajuste | leccion_fase_7 | su medida no está en la lección |
| ≈ | Pierna que carga | leccion/Tu plan completo | su medida no está en la lección |
| ✘ | En carrera, en salto, a un pie, deslizando |  | sin medida con clave |
| ✘ | Última zancada más larga en carrera |  | su medida no está en la lección |
| ≈ | Recuperación: distancia, dirección, tiempo | leccion/Lo que la tele no mide | su medida no está en la lección |
| ≈ | Frenado: último paso largo con caída de la velocidad | leccion_fase_1 | su medida no está en la lección |
| ≈ | Patada atrás (tijera) tras el impacto | leccion_fase_2 | su medida no está en la lección |
| ≈ | Orientación del pie (talón → dedo gordo respecto a la línea de fondo) en el armado y el impacto | leccion_fase_0 | su medida no está en la lección |
| ✘ | Forma del armado: bucle, recto, "pat the dog" |  | su medida no está en la lección |
| ≈ | Raqueta al lado del cuerpo o por detrás de la espalda en el armado (debate WTA/ATP) | leccion_fase_2 | su medida no está en la lección |
| ≈ | Inicio de la aceleración respecto al bote; girar mientras se desplaza | leccion_fase_8 | su medida no está en la lección |
| ✘ | Retraso de la muñeca (lag) |  | su medida no está en la lección |
| ✘ | Trayectoria de abajo arriba (signo) / liftado-plano-cortado |  | su medida no está en la lección |
| ✘ | Cara en el impacto |  | sin medida con clave |
| ≈ | Velocidad de la raqueta relativa entre golpes | leccion_fase_0 | su medida no está en la lección |
| ✘ | Posición de la mano en el mango |  | su medida no está en la lección |
| ✘ | Empuñadura (bisel) |  | no medible y no lo dice |
| ✘ | Empuñadura: "compatible con este / semioccidental-occidental" |  | su medida no está en la lección |
| ✘ | Pronación, contribución de cada segmento, punto en el cordaje, presión de agarre |  | no medible y no lo dice |
| ✘ | Bote: profundidad, anchura, dentro/fuera |  | su medida no está en la lección |
| ≈ | Dirección cruzada, paralela, al centro, invertidas | leccion/Lo esencial | su medida no está en la lección |
| ✘ | Golpe angulado (cruzado, corto y junto al lateral) |  | su medida no está en la lección |
| ≈ | Bola corta cerca de la red: baja, media, alta | leccion_fase_0 | su medida no está en la lección |
| ≈ | Velocidad media de la bola en pista | leccion_fase_0 | su medida no está en la lección |
| ✘ | Altura de la bola en su vuelo, bote, punto más alto; contacto subiendo / arriba / cayendo |  | su medida no está en la lección |
| ✘ | Curvas de altura (cabeza, cadera, mano, cabeza de la raqueta) a lo largo del golpe, con su curva típica y su f |  | su medida no está en la lección |
| ≈ | Fase ataque / neutra / defensa | leccion_fase_0 | sin medida con clave |
| ≈ | Calidad del golpe (sustituto: profundidad, anchura, velocidad media) | leccion_fase_0 | su medida no está en la lección |
| ≈ | Puntos ganados en ataque / en defensa | mas_conclusiones | su medida no está en la lección |
| ✘ | Longitud del peloteo |  | su medida no está en la lección |
| ✘ | Resto, globo, dejada, volea, subida a la red |  | su medida no está en la lección |
| ≈ | Ganador / error (forzado o no) | leccion/Lo esencial | sin medida con clave |
| ✘ | Presión, set, fatiga |  | sin medida con clave |
| ✘ | Resto: reconocerlo (saca la rival y es su primer golpe del punto) |  | su medida no está en la lección |
| ≈ | Resto de primer o de segundo saque | leccion/Lo que la tele no mide | su medida no está en la lección |
| ✘ | Dirección del saque recibido: abierto, al cuerpo, a la T |  | su medida no está en la lección |
| ✘ | Lado del resto: iguales / ventaja |  | su medida no está en la lección |
| ✘ | Resto: posición de espera |  | su medida no está en la lección |
| ≈ | Resto: entrar hacia la bola | leccion/Lo esencial | su medida no está en la lección |
| ≈ | Resto: armado corto (bloqueo) o swing completo; terminación | leccion_fase_2 | su medida no está en la lección |
| ≈ | Resto: dirección y profundidad de su resto | leccion/Lo esencial | su medida no está en la lección |
| ≈ | Resto: tiempo que tiene desde el saque | leccion/Lo que la tele no mide | su medida no está en la lección |

## Tu lista de 15 puntos (`matriz_cobertura.md` §6): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ✘ | Rotación pélvica |  | su medida no está en la lección |
| ✘ | Retraso de la muñeca (lag) y su liberación |  | su medida no está en la lección |
| ≈ | Inclinación lateral del tronco | golpe | su medida no está en la lección |
| ✘ | Pie de arrastre (pie trasero que se arrastra) |  | su medida no está en la lección |
| ≈ | Bucle de la preparación (forma) | leccion/Lo que la tele no mide | su medida no está en la lección |
| ≈ | Caída de la raqueta por debajo de la bola | leccion_fase_0 | su medida no está en la lección |
| ≈ | Trayectoria vertical del swing (de abajo arriba) | leccion/Tu plan completo | su medida no está en la lección |
| ✘ | Apoyo en suspensión (salto) |  | sin medida con clave |
| ≈ | Pasos de ajuste | leccion_fase_7 | su medida no está en la lección |
| ≈ | Paso de ataque hacia dentro de la pista (step-in) | leccion_fase_8 | su medida no está en la lección |
| ✘ | Golpe plano, liftado o cortado |  | sin medida con clave |
| ✘ | Botepronto (media volea) |  | su medida no está en la lección |
| ✘ | Volea de derecha |  | su medida no está en la lección |
| ≈ | Terminación sobre el hombro contrario | leccion_fase_0 | sin medida con clave |
| ≈ | Terminación en látigo sobre el mismo hombro (buggy whip) | leccion_fase_0 | sin medida con clave |
| ✘ | Terminación baja, a la cintura contraria |  | sin medida con clave |
| ≈ | Adaptación a bola rápida, corta, alta, abierta | leccion_fase_0 | su medida no está en la lección |
| ≈ | Dirección: cruzado, paralelo, dentro-fuera, dentro-dentro | leccion/Lo que la tele no mide | su medida no está en la lección |
| ≈ | Zona de impacto: delante de la cadera | leccion_fase_0 | su medida no está en la lección |
| ✘ | Equilibrio al terminar |  | su medida no está en la lección |
| ✘ | Liberación anticipada de la muñeca («casting») |  | su medida no está en la lección |
| ≈ | Fuerza en dirección incorrecta (horizontal o descendente) | leccion/Lo que la tele no mide | su medida no está en la lección |
| ≈ | Ángulo real del swing de abajo arriba (+10° a +45°) | leccion/Tu plan completo | su medida no está en la lección |
| ≈ | Rodilla de atrás en la carga (110–130°) y de delante en el impacto | leccion_fase_0 | su medida no está en la lección |
| ≈ | Inclinación del tronco hacia delante o atrás en el impacto | leccion_fase_5 | su medida no está en la lección |
| ✘ | Superficie de la pista |  | sin medida con clave |

## Guía de Ivanovic (20 huecos): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ✘ | Avisos de técnica por golpe |  |  |
| ✘ | Terminación hacia adelante, la mano libre recoge la raqueta, codo al terminar |  |  |
| ✘ | Mano libre en la aceleración y el impacto |  |  |
| ✘ | Último apoyo frente al bote |  |  |
| ✘ | Sus principios y lo que la distingue |  |  |
| ✘ | Táctica medida: cambios de dirección, secuencias, «cómo usa su derecha» |  |  |
| ✘ | Bajo presión también dirección y profundidad |  |  |
| ✘ | Fuentes citadas (Elliott, Knudson, Landlinger…) |  |  |
| ◇ | Rutina entre puntos bajo presión |  | opcional (#198) |

## Entrenadores de YouTube (§3, Joel Myers, The Tennis Mentor): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ◇ | Plano vertical junto al cuerpo («a wall here») |  | M (no medible de frente; vista lateral) |
| ✘ | Todos sus impactos superpuestos en un fotograma |  |  |
| ✘ | «Cuenta conmigo»: un punto entero con cada golpe y su apoyo |  |  |
| ✘ | Siempre: qué hace, por qué importa, error típico, cómo se nota en sus golpes |  |  |
| ✘ | Táctica dibujada en la pista: opciones del rival y su punto de recuperación |  |  |
| ✘ | Análisis de partido: punto entero con mini-mapa numerado y «lo que hace bien / dónde pierde» |  |  |
| ✘ | Lección por etapas empezando por la empuñadura |  |  |

## Estado del arte: patrones adoptados (`referencias.yaml`): lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ✘ | Vídeo con capas (esqueleto, raqueta, bola) |  |  |
| ◇ | Preguntar en lenguaje natural |  | P4 (#299) |
| ◇ | Muñeco 3D que se gira |  | P4 (#300) |

## Usabilidad y aprendizaje: lo que falta o hay que mirar

| | Elemento | Dónde | Nota |
|---|---|---|---|
| ✘ | Ayuda: cómo se mide cada medida, junto a ella |  |  |
| ⚠ | Nada se sale de la pantalla a 390 px (móvil: solo para revisar, #301) | 28 de 35 pantallas |  |
