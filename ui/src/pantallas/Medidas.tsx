// Design change 1 (docs/p0_diseno.md §10, #305): the measures explorer by family (body, feet, racket, ball, context).
// Every measure the analysis gives (the 26 of the report, the lesson's checkpoints stroke by stroke, the context of each
// stroke), in the chosen situation: how many strokes have it, her typical value and where half of them are, how it is
// spread, how reliable it is and how it is measured; its extreme strokes open with their video. Nothing invented: a
// measure with fewer than MIN_N strokes says so, a measure without data is not listed.
import { Fragment, useMemo, useState } from "react";
import { useApp } from "../App";
import type { Datos, Golpe } from "../contrato";
import { esN, fmt } from "../datos";
import { FichaGolpe, tituloGolpe } from "./Golpe";

type AnyRec = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const MIN_N = 10;
export type Familia = "cuerpo" | "pies" | "raqueta" | "bola" | "contexto";
export const FAMILIAS: [Familia, string][] = [["cuerpo", "Cuerpo"], ["pies", "Pies"], ["raqueta", "Raqueta"], ["bola", "Bola y ritmo"], ["contexto", "Contexto"]];

// a measure's family from its key (checkpoints: «<phase>.<name>», «footwork.*», «class.*»; the report's own short keys)
export function familia(key: string): Familia {
  if (/^footwork\.|base_court|foot_angle|stance|feet_move|base_width|return_|^(split|base|baseM|disp|recov)$/.test(key)) return "pies";
  if (/face|racket|^r[A-Z]|catch_racket|swing|lag/.test(key)) return "raqueta";
  if (/bounce|_vs_net|contact_vs_top|ball_phase|^(shotDepth|ballKmh|shotQ|contactH)$/.test(key)) return "bola";
  return "cuerpo";
}

interface Entrada { key: string; fam: Familia; label: string; sub?: string; unit: string; dec: number; read?: string;
  rel: { tipo: "metric" | "check" | "sin" | "contexto"; v?: string; rel?: number; est?: boolean }; valor: (g: Golpe) => unknown }

const CONTEXTO: [string, string, (g: Golpe) => unknown, string, number][] = [
  ["ctx.tAvail", "Tiempo que tiene (golpe de la rival → su golpe)", (g) => g.tAvail, "s", 2],
  ["ctx.height", "Altura de la bola en el impacto", (g) => g.height, "", 0],
  ["ctx.intent", "Ataque, neutra o defensa", (g) => g.intent, "", 0],
  ["ctx.movement", "Parada, en carrera o en el aire", (g) => g.movement, "", 0],
  ["ctx.stance", "Apoyo en el impacto", (g) => g.stance, "", 0],
  ["ctx.finish", "Terminación", (g) => g.finish, "", 0],
  ["ctx.outcome", "Resultado del golpe", (g) => g.outcome, "", 0],
  ["ctx.pressure", "Bajo presión en el marcador", (g) => g.pressure, "", 0],
];

function entradas(d: Datos): Entrada[] {
  const out: Entrada[] = [];
  const conMetrica = new Set<string>();
  for (const p of d.phases) for (const c of p.checks) {
    const met = c.m ? d.metrics[c.m] : undefined;
    if (met && c.m) conMetrica.add(c.m);
    const r = (d.reliability as AnyRec | undefined)?.[c.key];
    out.push({ key: c.key, fam: familia(c.key), label: c.label, sub: p.title, unit: met?.unit || c.unit || "", dec: met?.dec ?? c.dec ?? 0,
      read: c.read || undefined,
      rel: met ? { tipo: "metric", rel: met.rel, est: met.est } : r?.verdict ? { tipo: "check", v: r.verdict } : { tipo: "sin" },
      valor: met && c.m ? (g) => g.m?.[c.m!] : (g) => (g.lv as AnyRec | undefined)?.[c.key] });
  }
  for (const [k, met] of Object.entries(d.metrics)) {
    if (conMetrica.has(k)) continue;
    out.push({ key: k, fam: familia(k), label: met.name, sub: met.sub, unit: met.unit || "", dec: met.dec ?? 0,
      rel: { tipo: "metric", rel: met.rel, est: met.est }, valor: (g) => g.m?.[k] });
  }
  for (const [k, label, f, unit, dec] of CONTEXTO) out.push({ key: k, fam: "contexto", label, unit, dec, rel: { tipo: "contexto" }, valor: f });
  return out;
}

function q(xs: number[], p: number) {
  const i = (xs.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
  return xs[lo] + (xs[hi] - xs[lo]) * (i - lo);
}

interface Resumen { n: number; tipo: "num" | "cat"; med?: number; p25?: number; p75?: number; xs?: number[]; cats?: [string, number][] }

function resumen(e: Entrada, a: Golpe[]): Resumen {
  const vs = a.map(e.valor).filter((v) => v !== null && v !== undefined && v !== "");
  const nums = vs.filter(esN) as number[];
  if (vs.length && nums.length === vs.length) {
    const xs = [...nums].sort((x, y) => x - y);
    return { n: xs.length, tipo: "num", med: q(xs, 0.5), p25: q(xs, 0.25), p75: q(xs, 0.75), xs };
  }
  const c: Record<string, number> = {};
  for (const v of vs) { const k = typeof v === "boolean" ? (v ? "sí" : "no") : String(v); c[k] = (c[k] || 0) + 1; }
  return { n: vs.length, tipo: "cat", cats: Object.entries(c).sort((x, y) => y[1] - x[1]) };
}

function Fiab({ r }: { r: Entrada["rel"] }) {
  if (r.tipo === "metric") {
    if (r.est) return <span className="pill est">estimada</span>;
    return (r.rel ?? 0) >= 3 ? <span className="pill good">fiable</span> : r.rel === 2 ? <span className="pill warn">media</span> : <span className="pill crit">baja</span>;
  }
  if (r.tipo === "check" && r.v) return <span className={`pill ${/fiable/.test(r.v) && !/no fiable/.test(r.v) ? "good" : /ruid|sesgo|no fiable/.test(r.v) ? "crit" : "warn"}`}>{r.v}</span>;
  return r.tipo === "contexto" ? <span className="pill mute">del contexto</span> : <span className="pill mute">fiabilidad sin calcular</span>;
}

function Tipico({ e, s }: { e: Entrada; s: Resumen }) {
  if (s.n < MIN_N) return <span className="sub">{s.n} golpes: pocos</span>;
  if (s.tipo === "num") return <span className="num">{fmt(s.med!, e.dec)} {e.unit}<span className="sub"> · la mitad entre {fmt(s.p25!, e.dec)} y {fmt(s.p75!, e.dec)}</span></span>;
  const [k, n] = s.cats![0];
  return <span>{k} <span className="sub">({fmt((100 * n) / s.n)} %)</span></span>;
}

function Reparto({ e, s }: { e: Entrada; s: Resumen }) {
  if (s.tipo === "cat") return (
    <div style={{ display: "grid", gap: 6 }}>{s.cats!.map(([k, n]) => (
      <div className="hbar" key={k}><span>{k}</span><div className="track"><i style={{ left: 0, width: `${(100 * n) / s.n}%` }} /></div><span className="num">{fmt((100 * n) / s.n)} %</span></div>))}</div>);
  const xs = s.xs!, lo = xs[0], hi = xs[xs.length - 1], B = 14, w = (hi - lo) / B || 1;
  const bins = Array.from({ length: B }, () => 0);
  for (const x of xs) bins[Math.min(B - 1, Math.floor((x - lo) / w))]++;
  const top = Math.max(...bins);
  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${B * 10} 44`} role="img" aria-label={`Reparto de ${e.label}`} style={{ width: "100%", maxWidth: 560, height: 120, display: "block" }}>
        {bins.map((b, i) => <rect key={i} x={i * 10 + 1} y={40 - (36 * b) / top} width={8} height={(36 * b) / top} fill="var(--accent, #2563eb)" opacity={0.8} />)}
        <line x1={((s.med! - lo) / w) * 10} x2={((s.med! - lo) / w) * 10} y1={0} y2={40} stroke="currentColor" strokeDasharray="2 1" />
      </svg>
      <figcaption className="sub">{fmt(lo, e.dec)} — {fmt(hi, e.dec)} {e.unit} · la línea es su valor típico ({fmt(s.med!, e.dec)} {e.unit}) · {s.n} golpes</figcaption>
    </figure>
  );
}

export function Explorador({ d, a }: { d: Datos; a: Golpe[] }) {
  const { abrir } = useApp();
  const todas = useMemo(() => entradas(d), [d]);
  const [fam, setFam] = useState<Familia | "todas">("todas");
  const [busca, setBusca] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const filas = todas.map((e) => ({ e, s: resumen(e, a) })).filter(({ e, s }) => s.n > 0 && (fam === "todas" || e.fam === fam)
    && (!busca || `${e.label} ${e.sub || ""}`.toLowerCase().includes(busca.toLowerCase())));
  const cuantas = (f: Familia) => todas.filter((e) => e.fam === f && resumen(e, a).n > 0).length;
  const extremos = (e: Entrada) => {
    const con = a.filter((g) => esN(e.valor(g))).sort((x, y) => (e.valor(x) as number) - (e.valor(y) as number));
    return con.length >= MIN_N ? [["Los más bajos", con.slice(0, 3)], ["Los más altos", con.slice(-3).reverse()]] as [string, Golpe[]][] : [];
  };
  return (
    <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
      <div className="card"><h3>Todas sus medidas, por familia</h3>
        <p className="sub">Cada medida del análisis en la situación elegida ({a.length} golpes): cuántos golpes la tienen, su valor típico, cómo se reparte y cuánto fiarse. Con menos de {MIN_N} golpes se dice en vez de dar un valor. Lo que la tele no permite medir está en «No medible desde la tele».</p>
        <div className="chips" style={{ marginTop: 8 }}>
          <button className="chip" type="button" data-fam="todas" aria-pressed={fam === "todas"} onClick={() => setFam("todas")}>Todas</button>
          {FAMILIAS.map(([k, t]) => <button className="chip" type="button" key={k} data-fam={k} aria-pressed={fam === k} onClick={() => setFam(k)}>{t}<span className="c num">{cuantas(k)}</span></button>)}
          <input placeholder="Buscar una medida" value={busca} onChange={(e) => setBusca(e.target.value)} aria-label="Buscar una medida"
            style={{ padding: "4px 10px", border: "1px solid var(--line)", borderRadius: 8 }} />
        </div>
      </div>
      <div className="card scroll">
        <table className="t">
          <thead><tr><th>Medida</th><th>Familia</th><th>Golpes</th><th>Su valor típico</th><th>Fiabilidad</th></tr></thead>
          <tbody>{filas.map(({ e, s }) => (
            <Fragment key={e.key}>
              <tr className="clickable" data-medida={e.key} aria-expanded={e.key === sel} onClick={() => setSel(e.key === sel ? null : e.key)}>
                <td><b>{e.label}</b>{e.sub ? <div className="sub">{e.sub}</div> : null}</td>
                <td>{FAMILIAS.find(([k]) => k === e.fam)?.[1]}</td>
                <td className="num">{s.n}</td>
                <td><Tipico e={e} s={s} /></td>
                <td><Fiab r={e.rel} /></td>
              </tr>
              {e.key === sel ? <tr><td colSpan={5} data-medida-detalle style={{ background: "var(--bg-2, transparent)" }}>
                <p className="sub">{e.read ? `Cómo se mide: ${e.read}` : e.sub || ""}</p>
                {d.why?.[e.key] ? <p className="sub" data-fuente>Por qué importa: {d.why[e.key][0]} <i>({d.why[e.key][1]})</i></p> : null}
                {s.n >= MIN_N ? <Reparto e={e} s={s} /> : <p className="sub">{s.n} golpes con esta medida: pocos para dar su reparto.</p>}
                <div className="grid2" style={{ marginTop: 8 }}>{extremos(e).map(([t, gs]) => (
                  <div key={t}><b className="sub">{t} (con su vídeo)</b>
                    <div className="list">{gs.map((g) => (
                      <button className="row clickable" type="button" style={{ width: "100%", textAlign: "left" }} key={g.id} data-medida-golpe onClick={() => abrir(<FichaGolpe s={g} />)}>
                        <span>{tituloGolpe(g)}</span><span className="num">{fmt(e.valor(g) as number, e.dec)} {e.unit}</span></button>))}</div></div>))}
                </div></td></tr> : null}
            </Fragment>))}</tbody>
        </table>
      </div>
    </div>
  );
}
