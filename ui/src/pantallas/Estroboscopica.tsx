// 21-11 (P0.5e, what was left of the strobe image): the swing's whole path drawn from the stroke's own frame series over
// its real impact frame, for every stroke with a video (before, only the example data had one). As the report's strobe
// (tennisbio/report_template.html, renderStrobe): four real silhouettes of the same stroke (loaded, acceleration, impact,
// finish) and the hand's path in that stretch; and as the short the user chose (#306, Trayectoria.tsx): the racket tip's
// path coloured by its rhythm with the ball (back to its highest point, before and after the bounce when the bounce was
// seen, contact and finish), faded where the racket is blurred on TV. Nothing is filled in: a frame without the racket
// or the hand is left out, and an isolated jump (a lost or swapped point) is not drawn.
import { useEffect, useRef, useState } from "react";
import type { Golpe } from "../contrato";
import { cargarSerie, HUESOS, punto, type Serie } from "./Reproductor";
import { COLOR_TRAMO, NOMBRE_TRAMO, type Tramo } from "./Trayectoria";

const SILUETAS: [string, string, string][] = [["loaded", "armado", "#5fd3e6"], ["acceleration", "aceleración", "#9be37b"],
  ["impact", "impacto", "#ffd166"], ["finish", "terminación", "#ff9f43"]];
const ORDEN: Tramo[] = ["atras", "antes_bote", "tras_bote", "sin_bote", "contacto"];
type P2 = [number, number];
export interface PuntoPunta { f: number; xy: P2; tramo: Tramo; borroso: boolean }

const dist = (a: P2, b: P2) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** The torso's length at a frame (shoulders' midpoint to hips' midpoint), the scale of what counts as a jump. */
export function tronco(k: (number | null)[] | undefined): number | null {
  const ls = punto(k, 5), rs = punto(k, 6), lh = punto(k, 11), rh = punto(k, 12);
  if (!ls || !rs || !lh || !rh) return null;
  return dist([(ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2], [(lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2]);
}

/** The racket tip's frames between the stroke's start (takeback, else the series' start) and its finish, each with its
 *  stretch of the swing. `ph`: the stroke's phases (s from the impact), `bote`: the ball's bounce (s), when seen. */
export function puntaPorTramos(ser: Serie, ph: Record<string, unknown>, bote: number | null): PuntoPunta[] {
  const idx = (t: unknown) => (typeof t === "number" && Number.isFinite(t) ? Math.round(t * ser.fps) + ser.impact - ser.first : null);
  const imp = ser.impact - ser.first;
  const f0 = Math.max(0, idx(ph.takeback) ?? idx(ph.loaded) ?? 0);
  const f1 = Math.min(ser.n - 1, idx(ph.finish) ?? idx(ph.recovery) ?? ser.n - 1);
  const raw: { f: number; xy: P2 }[] = [];
  for (let f = f0; f <= f1; f++) {
    const fk = ser.face?.keypoints?.[String(f + ser.first)];
    if (fk && fk.length >= 5 && fk[0]) raw.push({ f, xy: [fk[0][0], fk[0][1]] });
  }
  const tl = tronco(ser.kp[imp]) ?? tronco(ser.kp[f0]);
  const pts = raw.filter((p, i) => {            // an isolated jump: far from both neighbours (a lost or swapped point)
    if (!tl) return true;
    const a = raw[i - 1], b = raw[i + 1];
    return !((!a || dist(a.xy, p.xy) > 1.2 * tl) && (!b || dist(b.xy, p.xy) > 1.2 * tl) && (a || b));
  });
  const antes = pts.filter((p) => p.f < imp);
  const alto = antes.length ? antes.reduce((m, p) => (p.xy[1] < m.xy[1] ? p : m)).f : null;   // image y down: highest
  const fb = bote === null ? null : Math.round(bote * ser.fps) + imp;
  const ba = idx(ph.acceleration), be = idx(ph.extension), cerca = Math.max(2, Math.round(0.08 * ser.fps));
  return pts.map((p) => {
    const tramo: Tramo = p.f >= imp ? "contacto" : alto !== null && p.f <= alto ? "atras"
      : fb === null ? "sin_bote" : p.f < fb ? "antes_bote" : "tras_bote";
    const borroso = ba !== null && be !== null ? p.f >= ba && p.f <= be : Math.abs(p.f - imp) <= cerca;
    return { ...p, tramo, borroso };
  });
}

/** The dominant hand from loaded to finish, smoothed over 5 frames and broken where it jumps (the report's rule). */
export function caminoMano(ser: Serie, ph: Record<string, unknown>, zurda: boolean): (P2 | null)[] {
  const idx = (t: unknown) => (typeof t === "number" && Number.isFinite(t) ? Math.round(t * ser.fps) + ser.impact - ser.first : null);
  const a = idx(ph.loaded), b = idx(ph.finish);
  if (a === null || b === null || b <= a) return [];
  const w = zurda ? 9 : 10, raw: (P2 | null)[] = [];
  for (let f = Math.max(0, a); f <= Math.min(ser.n - 1, b); f++) raw.push(punto(ser.kp[f], w));
  return raw.map((p, i) => {
    if (!p) return null;
    const nb = raw.slice(Math.max(0, i - 2), i + 3).filter(Boolean) as P2[];
    return [nb.reduce((s, q) => s + q[0], 0) / nb.length, nb.reduce((s, q) => s + q[1], 0) / nb.length];
  });
}

export function Estroboscopica({ s, medios, zurda }: { s: Golpe; medios?: string | null; zurda?: boolean }) {
  const vid = useRef<HTMLVideoElement>(null), lienzo = useRef<HTMLCanvasElement>(null);
  const [ser, setSer] = useState<Serie | null | undefined>(undefined);
  const [tramos, setTramos] = useState<Tramo[]>([]);
  const [estimado, setEstimado] = useState(false);
  const [cuenta, setCuenta] = useState({ puntos: 0, siluetas: 0, mano: 0 });     // what was drawn (medir_app reads it)
  const video = s.video as string | undefined, series = s.series as string | undefined;
  const vImpact = (s.vImpact as number | undefined) ?? null;
  const ph = (s.phases as Record<string, unknown>) || {};
  const bote = (((s.ball as { k?: string; t?: number }[]) || []).find((m) => m.k === "ball_bounce") || {}).t ?? null;
  useEffect(() => {
    let vivo = true;
    setSer(undefined);
    if (medios && series) cargarSerie(s.id, medios + series).then((x) => vivo && setSer(x));
    else setSer(null);
    return () => { vivo = false; };
  }, [s.id, medios, series]);
  const pintar = () => {
    const V = vid.current, C = lienzo.current;
    if (!V || !C || !ser || !V.videoWidth) return;
    C.width = V.videoWidth; C.height = V.videoHeight;
    const cx = C.getContext("2d");
    if (!cx) return;
    const vk = (s.vk as number) || 1, P = (p: P2): P2 => [p[0] * vk, p[1] * vk], lw = Math.max(2, C.width / 400);
    cx.clearRect(0, 0, C.width, C.height);
    cx.fillStyle = "rgba(0,0,0,.35)"; cx.fillRect(0, 0, C.width, C.height);
    const tl = tronco(ser.kp[ser.impact - ser.first]);
    cx.lineWidth = lw * 2; cx.strokeStyle = "rgba(212,240,58,.9)"; cx.lineJoin = "round"; cx.beginPath();
    let prev: P2 | null = null, siluetas = 0;
    const mano = caminoMano(ser, ph, !!zurda);
    for (const w of mano) {
      if (!w) { prev = null; continue; }
      const salto = prev && tl ? dist(w, prev) > tl * 0.8 : false;
      if (prev && !salto) cx.lineTo(...P(w)); else cx.moveTo(...P(w));
      prev = w;
    }
    cx.stroke();
    const pts = puntaPorTramos(ser, ph, bote), r = Math.max(2.5, C.width / 260);
    for (const p of pts) {
      cx.globalAlpha = p.borroso ? 0.35 : 0.95;
      cx.beginPath(); cx.arc(...P(p.xy), r, 0, 2 * Math.PI);
      if (p.tramo === "contacto") { cx.fillStyle = COLOR_TRAMO[p.tramo]; cx.fill(); }
      else { cx.strokeStyle = COLOR_TRAMO[p.tramo]; cx.lineWidth = Math.max(1.5, r / 2); cx.stroke(); }
    }
    cx.globalAlpha = 1;
    cx.font = `600 ${Math.max(16, lw * 9)}px Archivo, sans-serif`;
    const rotulos: [number, number, number, number][] = [];       // the labels drawn, so none covers another
    for (const [key, nombre, col] of SILUETAS) {
      const t = ph[key];
      if (typeof t !== "number") continue;
      const k = ser.kp[Math.round(t * ser.fps) + ser.impact - ser.first];
      if (!k) continue;
      siluetas++;
      cx.globalAlpha = key === "impact" ? 1 : 0.8; cx.strokeStyle = col; cx.lineWidth = key === "impact" ? lw * 2 : lw * 1.3;
      for (const [a, b] of HUESOS) {
        const pa = punto(k, a), pb = punto(k, b);
        if (pa && pb) { cx.beginPath(); cx.moveTo(...P(pa)); cx.lineTo(...P(pb)); cx.stroke(); }
      }
      cx.globalAlpha = 1;
      const w = punto(k, zurda ? 9 : 10);
      if (w) {
        const [x, y] = P(w), tw = cx.measureText(nombre).width, rw = tw + lw * 5, rh = lw * 14;
        cx.fillStyle = col; cx.beginPath(); cx.arc(x, y, lw * 3, 0, 7); cx.fill();
        let ry = y - lw * 11;
        const tapa = (q: number) => rotulos.some(([X, Y, W, H]) => x + lw * 5 < X + W && X < x + lw * 5 + rw && q < Y + H && Y < q + rh);
        while (tapa(ry) && ry + 2 * rh < C.height) ry += rh + lw;
        if (tapa(ry) || ry + rh > C.height) { ry = y - lw * 11; while (tapa(ry) && ry > rh) ry -= rh + lw; }   // else upwards
        rotulos.push([x + lw * 5, ry, rw, rh]);
        cx.fillStyle = "rgba(10,13,16,.8)"; cx.fillRect(x + lw * 5, ry, rw, rh);
        cx.fillStyle = col; cx.fillText(nombre, x + lw * 7.5, ry + lw * 11);
      }
    }
    setTramos(ORDEN.filter((k) => pts.some((p) => p.tramo === k)));
    setEstimado(pts.some((p) => p.borroso));
    setCuenta({ puntos: pts.length, siluetas, mano: mano.filter(Boolean).length });
  };
  useEffect(pintar, [ser]);                            // eslint-disable-line react-hooks/exhaustive-deps
  if (!medios || !video || vImpact === null) {
    return <p className="sub">Se dibuja sobre su vídeo, que llega con los resultados de la nube («Traer resultados de la nube» en Inicio).</p>;
  }
  if (ser === null) return <p className="sub" data-estrobo="sin-serie">Este golpe no tiene su serie fotograma a fotograma: no se dibuja.</p>;
  return (
    <div style={{ display: "grid", gap: 8 }} data-estrobo={ser && cuenta.siluetas ? "listo" : ser ? "sin-fases" : "cargando"}
      data-golpe={s.id} data-puntos={cuenta.puntos} data-siluetas={cuenta.siluetas} data-mano={cuenta.mano}>
      <div className="frame" style={{ background: "#000", aspectRatio: "16 / 9" }}>
        <video ref={vid} src={medios + video} muted playsInline preload="auto"
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
          onLoadedMetadata={() => { if (vid.current) vid.current.currentTime = Math.max(0, vImpact); }} onSeeked={pintar} />
        <canvas ref={lienzo} role="img" aria-label="Imagen estroboscópica: cuatro siluetas del golpe, el camino de la mano y la punta de la raqueta"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", pointerEvents: "none" }} />
        <span className="tag">Sobre el fotograma de su impacto</span>
      </div>
      <div className="chips">
        {SILUETAS.map(([k, n, c]) => typeof ph[k] === "number" ? <span className="chip" key={k}><span style={{ color: c, fontWeight: 700 }}>━</span> {n}</span> : null)}
        <span className="chip"><span style={{ color: "#d4f03a", fontWeight: 700 }}>━</span> camino de la mano</span>
        {tramos.map((k) => <span className="chip" key={k}><span style={{ color: COLOR_TRAMO[k], background: "var(--frame-a)", borderRadius: 4, padding: "0 4px", fontWeight: 700 }}>{k === "contacto" ? "●" : "○"}</span> punta: {NOMBRE_TRAMO[k]}</span>)}
        {estimado ? <span className="pill est">tenue = estimado (raqueta borrosa en la tele)</span> : null}
      </div>
    </div>
  );
}
