# Revisión automática: OK

250 cumplidos · 0 no cumplidos · 126 sin golpes suficientes · 26 avisos (antes: 237 cumplidos, 0 no cumplidos)

## Mejora

- #76 «Un 50 % de golpes dudosos»: aviso → ok
- #101 Mejora 3: altura y separación del codo: aviso → ok
- #103 Mejora 5: transferencia de peso en una frase: aviso → ok
- #105 Mejora 7: ritmo con la bola (caída al subir la bola): aviso → ok
- #106 Mejora 8: frenado de los hombros antes del contacto: aviso → ok
- #110 Mejora 12: «Lo que la distingue» (2-3 rasgos frente a la literatura, con vídeo): aviso → ok
- #112 Mejora 14: clase descriptiva de estilo (`fh_style`): aviso → ok

## Comprobaciones nuevas

- #118 Validar cada medida de forma automática, no a mano: ¿técnica o ruido?: ok (1 comprobaciones: 1 ok)
- #119 Automatizar todo el ciclo en el PC: el usuario no lanza pruebas ni avisa: ok (no se comprueba en las salidas: ciclo automático del PC: revision_automatica.md en pc-logs (estado: HECHO))
- #120 Vídeo a pantalla completa: ok (9 comprobaciones: 9 ok)
- #121 Ver lo que se pinta por separado, por grupos o una a una: ok (9 comprobaciones: 9 ok)
- #122 Web en 2 vistas principales y el resto en «Más», en dos grupos (funcional y técnico), sin perder datos: ok (9 comprobaciones: 9 ok)
- #123 Lo que se aprende en una sesión: plan de 3 prioridades en orden, foco externo por fase, detalle plegado: ok (1 comprobaciones: 1 ok)
- #124 Hacia dónde mira el tronco y las manos en la espera, medidas fiables: aviso (sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok)
- #125 Velocidad, rendimiento y algoritmia antes del tramo largo nocturno: aviso (sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 aviso; la peor: «Tiempo: smoke_tennis-yusipopen-final-s)

## Fiabilidad de las medidas

- ahora: 59 medidas: 5 dudosa, 26 fiable, 4 no comprobable, 2 ruido, 3 sesgo, 19 sin juzgar. No se dan como valor suyo (ruido): impact.face_tilt ±5.45, loaded.racket_head_lateral ±2.9. No coinciden con el segundo método (3D), no se dan: loaded.shoulder_turn 2D 57.3° / 3D 12.4°, stroke.shoulders_open_first 2D 57.3° / 3D 12.4°, stroke.shoulder_brake 2D 57.3° / 3D 12.4°. «no comprobable»: no depende del instante de las fases (esta prueba no la valida). Con menos de 5 golpes no se juzga
- antes: 59 medidas: 6 dudosa, 25 fiable, 4 no comprobable, 2 ruido, 3 sesgo, 19 sin juzgar. No se dan como valor suyo (ruido): impact.face_tilt ±8.27, loaded.racket_head_lateral ±2.9. No coinciden con el segundo método (3D), no se dan: loaded.shoulder_turn 2D 57.3° / 3D 12.4°, stroke.shoulders_open_first 2D 57.3° / 3D 12.4°, stroke.shoulder_brake 2D 57.3° / 3D 12.4°. «no comprobable»: no depende del instante de las fases (esta prueba no la valida). Con menos de 5 golpes no se juzga
