// #306 (15-11): the swing's whole path over the stroke's video, as the short the user chose (docs/aprendido_entrenadores.md
// §7), with its colour code as the user explained it: the racket's path coloured by its rhythm with the ball —
// yellow back to its highest point, white the drop and swing before the bounce, green the swing after the bounce, red the
// contact and the finish — and a box on her contact zone. Where the racket is blurred on TV (acceleration, impact) the
// dots are faded and the legend says «estimado»; without the bounce seen, white and green are one colour (never a
// made-up bounce). Data: each stroke's frame series (in video pixels), its highest racket point, the bounce and the impact.
import { useEffect, useRef } from "react";

export type Tramo = "atras" | "antes_bote" | "tras_bote" | "sin_bote" | "contacto";
export interface PuntoTrayectoria { t: number; tramo: Tramo; xy: [number, number]; borroso?: boolean }
export interface Trayectoria { ancho: number; alto: number; puntos: PuntoTrayectoria[]; contacto?: [number, number, number, number] | null }

export const COLOR_TRAMO: Record<Tramo, string> = {
  atras: "#f2d64b", antes_bote: "#f4f7fb", tras_bote: "#7cf06a", sin_bote: "#b9c4cf", contacto: "#d83a3a",
};
export const NOMBRE_TRAMO: Record<Tramo, string> = {
  atras: "hacia atrás, hasta lo más alto", antes_bote: "caída y swing antes del bote", tras_bote: "swing tras el bote",
  sin_bote: "caída y swing (bote no visto)", contacto: "contacto y terminación",
};
const ORDEN: Tramo[] = ["atras", "antes_bote", "tras_bote", "sin_bote", "contacto"];
// the legend's sample on the video's own dark ground, so the light colours (white) show on a light chip
const MUESTRA = (c: string) => ({ color: c, background: "var(--frame-a)", borderRadius: 4, padding: "0 4px", fontWeight: 700 });

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
    const c = COLOR_TRAMO[p.tramo] || "#ffffff";
    ctx.globalAlpha = p.borroso ? 0.35 : 0.95;
    ctx.beginPath();
    ctx.arc(p.xy[0] * sx, p.xy[1] * sy, r, 0, 2 * Math.PI);
    if (p.tramo === "contacto") {                 // as in the short: contact and finish in filled dots
      ctx.fillStyle = c;
      ctx.fill();
    } else {
      ctx.strokeStyle = c;
      ctx.lineWidth = Math.max(1.5, r / 2);
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
  const tramos = ORDEN.filter((k) => tr.puntos.some((p) => p.tramo === k));
  const estimado = tr.puntos.some((p) => p.borroso);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="frame" style={{ aspectRatio: `${tr.ancho} / ${tr.alto}` }}>
        <canvas ref={ref} data-trayectoria style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
          role="img" aria-label={titulo || "Trayectoria del swing coloreada por su ritmo con la bola"} />
        <span className="tag">Trayectoria del swing y su ritmo con la bola</span>
      </div>
      <div className="chips">
        {tramos.map((k) => <span className="chip" key={k}><span style={MUESTRA(COLOR_TRAMO[k])}>{k === "contacto" ? "●" : "○"}</span> {NOMBRE_TRAMO[k]}</span>)}
        {tr.contacto ? <span className="chip"><span style={MUESTRA("#7cf06a")}>□</span> su zona de contacto</span> : null}
        {estimado ? <span className="pill est">tenue = estimado (raqueta borrosa en la tele)</span> : null}
      </div>
    </div>
  );
}
