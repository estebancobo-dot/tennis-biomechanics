// P0.5e (21-11, #301; the user: «sí», part D): a stroke's real video with its layers, drawn from the stroke's frame
// series as the report draws them (tennisbio/report_template.html, drawFrame): the body (her 17 points), the racket
// (its 5 points, where the racket model saw it), the ball and its trail, and two measures of the frame. The video and
// its series are the report's (its «video» and «series», relative to the report page); `d.medios` is where that page is
// from the application's page (the cloud's results brought to the PC, or the PC's own report).
import { useEffect, useRef, useState } from "react";
import type { Golpe } from "../contrato";
import { fmt } from "../datos";

export type Serie = {
  fps: number; first: number; impact: number; n: number;
  kp: (number | null)[][]; conf?: (number | null)[][]; box?: (number[] | null)[];
  ball?: ([number | null, number | null] | null)[] | null;
  ang?: Record<string, (number | null)[]>;
  face?: { keypoints?: Record<string, [number, number][]> } | null;
};
declare global { interface Window { SERIES?: Record<string, Serie> } }

// COCO17 pairs (the series' «kp»: 17 points, x y each); the dominant arm brighter (config/players: hand)
export const HUESOS: [number, number][] = [[5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4]];
const RAQUETA: [number, number][] = [[0, 3], [3, 1], [1, 4], [4, 0], [1, 2]];
const VELOCIDADES: [string, number][] = [["Velocidad real", 1], ["½", 0.5], ["¼", 0.25], ["⅛", 0.125]];
const CAPAS: [string, string][] = [["cuerpo", "Cuerpo"], ["raqueta", "Raqueta"], ["bola", "Bola"], ["medidas", "Medidas"]];

export function cargarSerie(id: string, src: string): Promise<Serie | null> {
  return new Promise((res) => {
    window.SERIES = window.SERIES || {};
    if (window.SERIES[id]) return res(window.SERIES[id]);
    const el = document.createElement("script");
    el.src = src;
    el.onload = () => res((window.SERIES || {})[id] || null);
    el.onerror = () => res(null);
    document.head.appendChild(el);
  });
}

export const punto = (k: (number | null)[] | undefined, i: number): [number, number] | null =>
  k && k[2 * i] !== null && k[2 * i] !== undefined && k[2 * i + 1] !== null ? [k[2 * i] as number, k[2 * i + 1] as number] : null;

export function dibujar(cx: CanvasRenderingContext2D, ser: Serie, f: number, capas: Record<string, boolean>, zurda: boolean, vk = 1) {
  const W = cx.canvas.width, lw = Math.max(2, W / 400), P = (p: [number, number]) => [p[0] * vk, p[1] * vk] as [number, number];
  cx.clearRect(0, 0, W, cx.canvas.height);
  if (f < 0 || f >= ser.n) return;
  const k = ser.kp[f], dom = zurda ? [5, 7, 9] : [6, 8, 10];
  if (capas.cuerpo && k) {
    cx.lineCap = "round";
    for (const [a, b] of HUESOS) {
      const pa = punto(k, a), pb = punto(k, b);
      if (!pa || !pb) continue;
      const brazo = dom.includes(a) && dom.includes(b);
      cx.strokeStyle = brazo ? "#d4f03a" : "rgba(233,238,242,.85)";
      cx.lineWidth = brazo ? lw * 1.6 : lw;
      cx.beginPath(); cx.moveTo(...P(pa)); cx.lineTo(...P(pb)); cx.stroke();
    }
    cx.fillStyle = "#5fd3e6";
    for (let i = 0; i < 17; i++) { const p = punto(k, i); if (p) { cx.beginPath(); cx.arc(...P(p), lw * 1.3, 0, 7); cx.fill(); } }
  }
  const fk = ser.face?.keypoints?.[String(f + ser.first)];
  if (capas.raqueta && fk && fk.length >= 5) {
    cx.strokeStyle = "#ff5fd2"; cx.lineWidth = lw; cx.beginPath();
    for (const [a, b] of RAQUETA) { cx.moveTo(...P(fk[a])); cx.lineTo(...P(fk[b])); }
    cx.stroke();
  }
  if (capas.bola && ser.ball) {
    const nt = Math.max(3, Math.round(0.25 * (ser.fps || 50)));
    for (let g = Math.max(0, f - nt); g <= f; g++) {
      const b = ser.ball[g];
      if (!b || b[0] === null || b[1] === null) continue;
      cx.fillStyle = g === f ? "#ffd166" : `rgba(255,209,102,${0.15 + 0.6 * (g - f + nt) / nt})`;
      cx.beginPath(); cx.arc(...P([b[0], b[1]]), g === f ? lw * 3 : lw * 1.6, 0, 7); cx.fill();
    }
  }
  if (capas.medidas && ser.ang) {
    const txt = Object.entries(ser.ang).map(([n, v]) => (v[f] === null || v[f] === undefined ? null : `${n} ${fmt(v[f] as number)}°`))
      .filter(Boolean).join(" · ");
    if (txt) {
      cx.font = `600 ${Math.max(14, lw * 8)}px JetBrains Mono, monospace`;
      const w = cx.measureText(txt).width;
      cx.fillStyle = "rgba(10,13,16,.8)"; cx.fillRect(12, 12, w + 20, lw * 12);
      cx.fillStyle = "#f1f4f6"; cx.fillText(txt, 22, 12 + lw * 8.5);
    }
  }
}

export function Reproductor({ s, medios, zurda, t }: { s: Golpe; medios?: string | null; zurda?: boolean; t?: number | null }) {
  const caja = useRef<HTMLDivElement>(null), vid = useRef<HTMLVideoElement>(null), lienzo = useRef<HTMLCanvasElement>(null);
  const [ser, setSer] = useState<Serie | null | undefined>(undefined);
  const [vel, setVel] = useState(1);
  const [paso, setPaso] = useState(t !== undefined && t !== null);       // from a phase's moment: paused there
  const [capas, setCapas] = useState<Record<string, boolean>>({ cuerpo: true, raqueta: true, bola: true, medidas: false });
  const [fallo, setFallo] = useState(false);
  const video = s.video as string | undefined, series = s.series as string | undefined;
  const vImpact = (s.vImpact as number | undefined) ?? null;
  useEffect(() => {
    let vivo = true;
    setSer(undefined);
    if (medios && series) cargarSerie(s.id, medios + series).then((x) => vivo && setSer(x));
    else setSer(null);
    return () => { vivo = false; };
  }, [s.id, medios, series]);
  useEffect(() => {                                     // draw on every shown frame, while the panel is open
    let h = 0;
    const V = vid.current, C = lienzo.current;
    const tick = () => {
      if (V && C && ser) {
        if (V.videoWidth && C.width !== V.videoWidth) { C.width = V.videoWidth; C.height = V.videoHeight; }
        const cx = C.getContext("2d");
        // as the report: the impact's moment in the video (vImpact) is the series' impact frame; the loop runs over
        // the series' stretch (from before the opponent's hit to the recovery) unless frame by frame
        const ti = vImpact ?? ser.impact / ser.fps;
        const t0 = ti + (ser.first - ser.impact) / ser.fps, t1 = ti + (ser.first + ser.n - 1 - ser.impact) / ser.fps;
        if (!paso && !V.paused && (V.currentTime > t1 || V.ended)) V.currentTime = Math.max(0, t0);
        if (cx) dibujar(cx, ser, Math.round((V.currentTime - ti) * ser.fps) + ser.impact - ser.first, capas, !!zurda,
          (s.vk as number) || 1);
      }
      h = requestAnimationFrame(tick);
    };
    h = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(h);
  }, [ser, capas, paso, zurda, s.vk, vImpact]);
  useEffect(() => { if (vid.current) vid.current.playbackRate = vel; }, [vel]);
  const alImpacto = () => { const V = vid.current; if (V && vImpact !== null) { V.pause(); V.currentTime = vImpact; } };
  const mover = (n: number) => { const V = vid.current; if (V && ser) { V.pause(); V.currentTime = Math.max(0, V.currentTime + n / ser.fps); } };
  if (!medios || !video) {
    return (
      <div data-reproductor="sin-video" data-golpe={s.id}>
        <div className="frame"><span className="tag">Vídeo real del golpe con capas · captura {fmt(100 * (s.quality ?? 0))} %</span></div>
        <p className="sub" style={{ marginTop: 6 }}>{medios ? "Este golpe no tiene vídeo en los resultados." :
          "Los vídeos llegan con los resultados de la nube: «Traer resultados de la nube» en Inicio."}</p>
      </div>
    );
  }
  return (
    <div data-reproductor={ser ? "listo" : ser === null ? "sin-serie" : "cargando"} data-golpe={s.id}>
      <div ref={caja} style={{ position: "relative", background: "#000", borderRadius: 8, overflow: "hidden" }}>
        <video ref={vid} src={medios + video} muted playsInline preload="auto" style={{ width: "100%", display: "block" }}
          onLoadedMetadata={() => {
            const V = vid.current;
            if (!V) return;
            V.playbackRate = vel;
            if (vImpact !== null) V.currentTime = Math.max(0, vImpact + (t ?? -1.2));
            if (t === undefined || t === null) V.play().catch(() => undefined);
          }}
          onError={() => setFallo(true)} />
        <canvas ref={lienzo} data-capas style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} />
      </div>
      {fallo ? <p className="pill crit" style={{ marginTop: 6 }}>No se pudo abrir el vídeo de este golpe ({video}).</p> : null}
      {ser === null && !fallo ? <p className="sub" style={{ marginTop: 6 }}>Sin la serie del golpe: el vídeo, sin capas.</p> : null}
      <div className="controls">
        {VELOCIDADES.map(([t, v]) => <button className="chip" type="button" key={t} data-vel={v} aria-pressed={!paso && vel === v}
          onClick={() => { setPaso(false); setVel(v); vid.current?.play().catch(() => undefined); }}>{t}</button>)}
        <button className="chip" type="button" data-paso aria-pressed={paso} onClick={() => { setPaso(true); vid.current?.pause(); }}>Fotograma a fotograma</button>
        {paso ? <><button className="chip" type="button" data-mover="-1" onClick={() => mover(-1)}>◀</button>
          <button className="chip" type="button" data-mover="1" onClick={() => mover(1)}>▶</button></> : null}
        <button className="chip" type="button" data-impacto disabled={vImpact === null} onClick={alImpacto}>Impacto</button>
        <button className="chip" type="button" onClick={() => caja.current?.requestFullscreen?.().catch(() => undefined)}>Pantalla completa</button>
        <span className="sub" style={{ marginLeft: 8 }}>Capas:</span>
        {CAPAS.map(([k, t]) => <button className="chip" type="button" key={k} data-capa={k} aria-pressed={capas[k]}
          onClick={() => setCapas({ ...capas, [k]: !capas[k] })}>{t}</button>)}
      </div>
    </div>
  );
}

// One still frame of a stroke's video at `t` seconds from its impact, with her body drawn on it (the ball and her, the
// contact strip). Without the video, the placeholder frame with its label.
export function Fotograma({ s, medios, t, etiqueta, zurda }: { s: Golpe; medios?: string | null; t: number; etiqueta?: string;
  zurda?: boolean }) {
  const vid = useRef<HTMLVideoElement>(null), lienzo = useRef<HTMLCanvasElement>(null);
  const [ser, setSer] = useState<Serie | null>(null);
  const video = s.video as string | undefined, series = s.series as string | undefined;
  const vImpact = (s.vImpact as number | undefined) ?? null;
  useEffect(() => {
    let vivo = true;
    if (medios && series) cargarSerie(s.id, medios + series).then((x) => vivo && setSer(x));
    return () => { vivo = false; };
  }, [s.id, medios, series]);
  const pintar = () => {
    const V = vid.current, C = lienzo.current;
    if (!V || !C || !ser || !V.videoWidth) return;
    C.width = V.videoWidth; C.height = V.videoHeight;
    const cx = C.getContext("2d"), ti = vImpact ?? ser.impact / ser.fps;
    if (cx) dibujar(cx, ser, Math.round((V.currentTime - ti) * ser.fps) + ser.impact - ser.first,
      { cuerpo: true, raqueta: true, bola: true, medidas: false }, !!zurda, (s.vk as number) || 1);
  };
  useEffect(pintar, [ser]);                            // eslint-disable-line react-hooks/exhaustive-deps
  if (!medios || !video || vImpact === null) {
    return <div className="frame"><span className="tag">{etiqueta || "fotograma"}</span></div>;
  }
  return (
    <div className="frame" data-fotograma style={{ background: "#000", aspectRatio: "16 / 9" }}>
      <video ref={vid} src={medios + video} muted playsInline preload="auto"
        style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
        onLoadedMetadata={() => { if (vid.current) vid.current.currentTime = Math.max(0, vImpact + t); }}
        onSeeked={pintar} />
      <canvas ref={lienzo} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain",
        pointerEvents: "none" }} />
      {etiqueta ? <span className="tag">{etiqueta}</span> : null}
    </div>
  );
}
