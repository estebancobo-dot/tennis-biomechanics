// #306 (15-11): the swing's whole path over the stroke's video, as the short the user chose (docs/aprendido_entrenadores.md
// §7): the hand's path in hollow dots, one colour per phase; the racket tip's path in filled dots; a box on her contact
// zone. Where the racket is blurred on TV (acceleration, impact) the dots are faded and the legend says «estimado». A frame
// without the racket is not drawn: nothing is invented. Data: each stroke's frame series (in video pixels).
import { useEffect, useRef } from "react";

export interface PuntoTrayectoria { t: number; fase: string; mano?: [number, number] | null; punta?: [number, number] | null; borroso?: boolean }
export interface Trayectoria { ancho: number; alto: number; puntos: PuntoTrayectoria[]; contacto?: [number, number, number, number] | null }

export const COLOR_FASE: Record<string, string> = {
  takeback: "#f2d64b", loaded: "#f4f7fb", acceleration: "#7cf06a", impact: "#7cf06a", extension: "#6fd3ff", finish: "#6fd3ff",
};
export const NOMBRE_FASE: Record<string, string> = {
  takeback: "preparación", loaded: "bucle y armado", acceleration: "caída y aceleración", impact: "impacto",
  extension: "extensión", finish: "terminación",
};
const PUNTA = "#d83a3a";
// the legend's sample on the video's own dark ground, so the light colours (the loop's white) show on a light chip
const MUESTRA = (c?: string) => ({ color: c || "#fff", background: "var(--frame-a)", borderRadius: 4, padding: "0 4px", fontWeight: 700 });

export function dibujar(ctx: CanvasRenderingContext2D, tr: Trayectoria, w: number, h: number) {
  const sx = w / tr.ancho, sy = h / tr.alto, r = Math.max(2.5, w / 200);
  ctx.clearRect(0, 0, w, h);
  if (tr.contacto) {
    const [x, y, cw, ch] = tr.contacto;
    ctx.strokeStyle = "#7cf06a";
    ctx.lineWidth = 2;
    ctx.strokeRect(x * sx, y * sy, cw * sx, ch * sy);
  }
  for (const p of tr.puntos) {
    ctx.globalAlpha = p.borroso ? 0.35 : 0.95;
    if (p.punta) {
      ctx.fillStyle = PUNTA;
      ctx.beginPath();
      ctx.arc(p.punta[0] * sx, p.punta[1] * sy, r, 0, 2 * Math.PI);
      ctx.fill();
    }
    if (p.mano) {
      ctx.strokeStyle = COLOR_FASE[p.fase] || "#ffffff";
      ctx.lineWidth = Math.max(1.5, r / 2);
      ctx.beginPath();
      ctx.arc(p.mano[0] * sx, p.mano[1] * sy, r, 0, 2 * Math.PI);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
}

export function TrayectoriaSwing({ tr, titulo }: { tr: Trayectoria; titulo?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const pinta = () => {
      const w = c.clientWidth || 640, h = Math.round((w * tr.alto) / tr.ancho);
      c.width = w;
      c.height = h;
      dibujar(ctx, tr, w, h);
    };
    pinta();
    window.addEventListener("resize", pinta);
    return () => window.removeEventListener("resize", pinta);
  }, [tr]);
  const fases = [...new Set(tr.puntos.filter((p) => p.mano).map((p) => p.fase))];
  const estimado = tr.puntos.some((p) => p.borroso);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="frame" style={{ aspectRatio: `${tr.ancho} / ${tr.alto}` }}>
        <canvas ref={ref} data-trayectoria style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
          role="img" aria-label={titulo || "Trayectoria del swing: la mano por fases y la punta de la raqueta"} />
        <span className="tag">Trayectoria del swing</span>
      </div>
      <div className="chips">
        {fases.map((f) => <span className="chip" key={f}><span style={MUESTRA(COLOR_FASE[f])}>○</span> mano: {NOMBRE_FASE[f] || f}</span>)}
        <span className="chip"><span style={MUESTRA(PUNTA)}>●</span> punta de la raqueta</span>
        {tr.contacto ? <span className="chip"><span style={MUESTRA("#7cf06a")}>□</span> su zona de contacto</span> : null}
        {estimado ? <span className="pill est">tenue = estimado (raqueta borrosa en la tele)</span> : null}
      </div>
    </div>
  );
}
