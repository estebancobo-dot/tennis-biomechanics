// Which strokes each situation keeps (the same fields as the analysis' situations; tennisbio.report).
import type { Golpe } from "./contrato";

export const SITUACION: Record<string, (s: Golpe) => boolean> = {
  todas: () => true, rapida: (s) => s.fast === true, lenta: (s) => s.fast === false, alta: (s) => s.height === "alta",
  baja: (s) => s.height === "baja", abierta: (s) => s.wide === true, corta: (s) => s.short === true, profunda: (s) => s.short === false,
  carrera: (s) => s.movement === "en carrera", parada: (s) => s.movement === "parada", salto: (s) => s.movement === "en el aire",
  ataque: (s) => s.intent === "ataque", defensa: (s) => s.intent === "defensa",
};
