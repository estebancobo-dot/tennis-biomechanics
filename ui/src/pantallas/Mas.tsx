// P0.5c (15-11): «Más», from the validated mockup (#305) plus the design's change 2 (docs/p0_diseno.md §10): Táctica, with
// what the data already give (direction, depth, in or out, under pressure, changes of direction within a game). Every
// figure with its number of strokes; below MIN_N strokes it says so instead of a percentage.
import { useState } from "react";
import { useApp } from "../App";
import type { Datos, Golpe } from "../contrato";
import { esN, fmt } from "../datos";
import { SITUACION } from "../situaciones";
import { FichaGolpe, tituloGolpe } from "./Golpe";
import { Explorador } from "./Medidas";

type AnyRec = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const MIN_N = 10;
const sgn = (v: number, d = 0) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);
const pct = (n: number, de: number) => (de >= MIN_N ? `${fmt((100 * n) / de)} %` : `${n} de ${de} (pocos golpes)`);
export const MAS: [string, string][] = [["medidas", "Medidas"], ["comparar", "Comparar"], ["conclusiones", "Conclusiones"], ["situaciones", "Situaciones"], ["tactica", "Táctica"],
  ["pista", "Pista"], ["tabla", "Tabla de golpes"], ["lateral", "Vista lateral (entreno)"], ["fiabilidad", "Fiabilidad"], ["datos", "Datos"], ["exportar", "Exportar"]];

function Rel({ d, k }: { d: Datos; k: string }) {
  const m = d.metrics[k] || {};
  if (m.est) return <span className="pill est">estimada</span>;
  return (m.rel ?? 0) >= 3 ? <span className="pill good">fiable</span> : m.rel === 2 ? <span className="pill warn">media</span> : <span className="pill crit">baja</span>;
}

function Comparar({ d, a }: { d: Datos; a: Golpe[] }) {
  const A = a[0], B = a.find((s) => s.stance !== A?.stance) || a[1];
  const keys = ["sh", "xf", "elbow", "contactH", "lat", "baseM", "head", "finishH"].filter((k) => d.metrics[k]);
  const filas = keys.map((k) => {
    const va = A?.m[k], vb = B?.m[k], met = d.metrics[k];
    if (!esN(va) || !esN(vb)) return null;
    const dv = vb - va;
    return Math.abs(dv) > (met.noise || 0) ? (
      <div className="row" key={k}><div>{met.name}: B {sgn(dv, met.dec ?? 0)} {met.unit} frente a A ({fmt(va, met.dec ?? 0)} → {fmt(vb, met.dec ?? 0)})</div><Rel d={d} k={k} /></div>
    ) : null;
  }).filter(Boolean);
  return (
    <>
      <div className="grid2" style={{ marginTop: 12 }}>
        {[A, B].map((s, i) => s ? (
          <div className="card" key={s.id}>
            <div className="frame"><span className="tag">{i ? "B" : "A"} · {tituloGolpe(s)}</span></div>
            <div className="controls">
              <button className="chip" type="button" aria-pressed="true">Lado a lado</button>
              <button className="chip" type="button">Uno encima del otro</button>
              <button className="chip" type="button">Superpuestos</button>
              <button className="chip" type="button" aria-pressed="true">Enlazados en el impacto</button>
            </div>
          </div>
        ) : null)}
      </div>
      <div className="card"><h3>Lo que cambia (solo por encima del error)</h3>
        <div className="list">{filas.length ? filas : <p className="sub">Nada supera el error de medida entre estos dos golpes.</p>}</div></div>
    </>
  );
}

function Conclusiones({ d }: { d: Datos }) {
  const F = (d.findings as AnyRec[]) || [], real = F.filter((f) => (f.v || [])[0] === "good"), rest = F.filter((f) => (f.v || [])[0] !== "good");
  return (
    <>
      <div className="card" style={{ marginTop: 12 }}><h3>Diferencias reales (ajustadas por la bola y el partido)</h3>
        <div className="list">{real.length ? real.map((f, i) => (
          <div className="row" key={i}><div><div className="t">{f.t}</div><div className="s">{f.c}{f.e ? ` · ${sgn(f.e.d, 1)} (${f.e.na} frente a ${f.e.nb} golpes)` : ""}</div></div><span className="pill good">diferencia real</span></div>
        )) : <p className="sub">Ninguna.</p>}</div></div>
      <details className="fold"><summary>No concluyentes o dentro del ruido ({rest.length})</summary>
        <div className="list">{rest.map((f, i) => <div className="row" key={i}><div><div className="t">{f.t}</div><div className="s">{f.c}</div></div><span className="pill warn">{(f.v || [])[1] || ""}</span></div>)}</div></details>
    </>
  );
}

const APOYOS = ["abierto", "semiabierto", "neutro", "cerrado"];

function Situaciones({ d, onCelda }: { d: Datos; onCelda: (sit: string, apoyo: string) => void }) {
  return (
    <div className="card scroll" style={{ marginTop: 12 }}><h3>Apoyo en el impacto según la situación</h3>
      <p className="sub">Cada celda abre sus golpes.</p>
      <table className="t matrix"><tbody>
        <tr><th>Situación</th>{APOYOS.map((c) => <th key={c}>{c}</th>)}<th>Total</th></tr>
        {d.situations.map((s) => {
          const g = d.strokes.filter(SITUACION[s.id] || SITUACION.todas);
          return (
            <tr key={s.id}><td><b>{s.label}</b></td>
              {APOYOS.map((c) => {
                const n = g.filter((x) => x.stance === c).length;
                return <td className="cell" key={c} data-cell={`${s.id}|${c}`} onClick={() => onCelda(s.id, c)}>{n}<div className="sub">{g.length ? fmt((100 * n) / g.length) + " %" : ""}</div></td>;
              })}
              <td className="num">{g.length}</td></tr>
          );
        })}
      </tbody></table></div>
  );
}

function reparto(a: Golpe[], campo: string): [string, number][] {
  const c: Record<string, number> = {};
  for (const s of a) { const v = s[campo]; if (typeof v === "string" && v) c[v] = (c[v] || 0) + 1; }
  return Object.entries(c).sort((x, y) => y[1] - x[1]);
}

function Tactica({ a }: { a: Golpe[] }) {
  const conDir = a.filter((s) => typeof s.shotDir === "string" && s.shotDir);
  const presion = conDir.filter((s) => s.pressure), resto = conDir.filter((s) => !s.pressure);
  const visto = a.filter((s) => typeof s.shotIn === "boolean");
  // changes of direction: her consecutive strokes of one game, in the order of the data (the match's order)
  let pares = 0, cambios = 0;
  const porJuego: Record<string, Golpe[]> = {};
  for (const s of conDir) (porJuego[`${s.match}|${s.set}|${s.game}`] ||= []).push(s);
  for (const g of Object.values(porJuego)) for (let i = 1; i < g.length; i++) { pares++; if (g[i].shotDir !== g[i - 1].shotDir) cambios++; }
  const prof = (xs: Golpe[]) => { const v = xs.map((s) => s.m.shotDepth).filter(esN).sort((x, y) => x - y); return v.length >= MIN_N ? fmt(v[Math.floor(v.length / 2)], 1) + " m" : "pocos golpes"; };
  const tabla = (xs: Golpe[]) => reparto(xs, "shotDir").map(([k, n]) => <tr key={k}><td>{k}</td><td className="num">{pct(n, xs.length)}</td></tr>);
  return (
    <>
      <div className="grid3" style={{ marginTop: 12 }}>
        <div className="card stat"><b className="num">{pct(visto.filter((s) => s.shotIn === false).length, visto.length)}</b><span>fuera, de {visto.length} golpes con bote visto</span></div>
        <div className="card stat"><b className="num">{pct(cambios, pares)}</b><span>de las veces cambia de dirección respecto a su golpe anterior del mismo juego ({pares} pares)</span></div>
        <div className="card stat"><b className="num">{prof(a)}</b><span>profundidad mediana de su golpe (desde la línea de fondo rival)</span></div>
      </div>
      <div className="grid2">
        <div className="card"><h3>Dirección de su golpe</h3><table className="t"><tbody>{tabla(conDir)}</tbody></table><p className="sub">{conDir.length} golpes con dirección medida.</p></div>
        <div className="card"><h3>Bajo presión: dirección y profundidad</h3>
          <div className="grid2"><div><b>Con presión</b><table className="t"><tbody>{tabla(presion)}</tbody></table><p className="sub">Profundidad: {prof(presion)}</p></div>
            <div><b>Sin presión</b><table className="t"><tbody>{tabla(resto)}</tbody></table><p className="sub">Profundidad: {prof(resto)}</p></div></div>
          <p className="mock" style={{ marginTop: 8 }}>Diferencias en bruto: el ajuste por la bola y el partido de las conclusiones aún no se aplica a la táctica.</p></div>
      </div>
      <p className="mock">Lo que falta de la táctica (#14 de Ivanovic, The Tennis Mentor): secuencias de 2-3 golpes, longitud del peloteo, el punto entero con mini-mapa y su punto de recuperación frente a las opciones de la rival.</p>
    </>
  );
}

function Pista({ a }: { a: Golpe[] }) {
  const HL = 11.885, SW = 4.115, DW = 5.485, SL = 6.4;
  const pos = a.filter((s) => esN(s.x) && esN(s.y)), shots = a.filter((s) => esN(s.shotX) && esN(s.shotY));
  return (
    <div className="grid2" style={{ marginTop: 12 }}>
      <div className="card court">
        <svg viewBox="-6.5 -13.5 13 31" role="img" aria-label="Pista: dónde golpea (abajo) y dónde bota su golpe (arriba)">
          <rect className="outer" x={-6.5} y={-13.5} width={13} height={31} />
          <rect className="surf" x={-DW} y={-HL} width={2 * DW} height={2 * HL} />
          <rect className="ln" x={-DW} y={-HL} width={2 * DW} height={2 * HL} />
          <line className="ln" x1={-SW} x2={-SW} y1={-HL} y2={HL} /><line className="ln" x1={SW} x2={SW} y1={-HL} y2={HL} />
          <line className="ln" x1={-SW} x2={SW} y1={-SL} y2={-SL} /><line className="ln" x1={-SW} x2={SW} y1={SL} y2={SL} />
          <line className="ln" x1={0} x2={0} y1={-SL} y2={SL} /><line className="net" x1={-6.2} x2={6.2} y1={0} y2={0} />
          {pos.map((s) => <circle className="p" key={"p" + s.id} cx={(s.x as number).toFixed(2)} cy={(s.y as number).toFixed(2)} r={0.2} />)}
          {shots.map((s) => <circle className={`p${s.shotIn === false ? " out" : ""}`} key={"b" + s.id} cx={(s.shotX as number).toFixed(2)} cy={(-((s.shotY as number) - HL)).toFixed(2)} r={0.2} />)}
        </svg></div>
      <div className="card"><h3>En la pista</h3>
        <div className="grid2" style={{ marginTop: 8 }}>
          <div className="stat"><b className="num">{fmt((100 * pos.filter((s) => (s.y as number) > HL).length) / Math.max(1, pos.length))} %</b><span>golpea detrás de la línea de fondo</span></div>
          <div className="stat"><b className="num">{fmt((100 * pos.filter((s) => (s.x as number) > 0).length) / Math.max(1, pos.length))} %</b><span>en la mitad de su derecha</span></div>
          <div className="stat"><b className="num">{shots.length}</b><span>golpes con bote visto</span></div>
          <div className="stat"><b className="num">{fmt((100 * shots.filter((s) => s.shotIn === false).length) / Math.max(1, shots.length))} %</b><span>fuera</span></div>
        </div>
        <p className="sub" style={{ marginTop: 10 }}>Abajo, dónde golpea; arriba, dónde bota su golpe (rojo: fuera). Cada punto es un impacto o un bote.</p></div>
    </div>
  );
}

function Tabla({ a }: { a: Golpe[] }) {
  const { abrir } = useApp();
  return (
    <div className="card scroll" style={{ marginTop: 12 }}>
      <table className="t"><tbody>
        <tr><th>Golpe</th><th>Apoyo</th><th>Cómo llega</th><th>Bola</th><th>Resultado</th><th>Captura</th></tr>
        {a.slice(0, 60).map((s) => (
          <tr className="clickable" key={s.id} data-stroke={s.id} onClick={() => abrir(<FichaGolpe s={s} />)}>
            <td>{tituloGolpe(s)}</td><td>{s.stance || "—"}</td><td>{s.movement || "—"}</td><td>{s.bits.join(", ") || "—"}</td>
            <td>{s.detail || s.outcome || "—"}</td><td className="num">{fmt(100 * (s.quality ?? 0))} %</td></tr>
        ))}
      </tbody></table>
      <p className="mock" style={{ marginTop: 8 }}>Los 60 mejor captados de la situación elegida.</p></div>
  );
}

function Fiabilidad({ d }: { d: Datos }) {
  const R = Object.entries((d.reliability as Record<string, AnyRec>) || {});
  const nombre: Record<string, string> = {};
  for (const p of d.phases) for (const c of p.checks) nombre[c.key] = c.label;
  const cls = (v?: string) => (!v ? "mute" : /fiable/.test(v) ? "good" : /ruid|sesgo|no fiable/.test(v) ? "crit" : "warn");
  return (
    <div className="card scroll" style={{ marginTop: 12 }}><h3>Fiabilidad de cada medida</h3>
      <p className="sub">Ruido de medida frente a la dispersión de sus golpes; una diferencia solo se enseña si supera el ruido.</p>
      <table className="t"><tbody><tr><th>Medida</th><th>Golpes</th><th>Ruido</th><th>Dispersión</th><th>Veredicto</th></tr>
        {R.map(([k, v]) => <tr key={k}><td>{nombre[k] || k}</td><td className="num">{v.n ?? "—"}</td><td className="num">{esN(v.noise) ? fmt(v.noise, 2) : "—"}</td>
          <td className="num">{esN(v.spread) ? fmt(v.spread, 2) : "—"}</td><td>{v.verdict ? <span className={`pill ${cls(v.verdict)}`}>{v.verdict}</span> : "—"}</td></tr>)}
      </tbody></table></div>
  );
}

export function Mas({ d, sit, onCelda }: { d: Datos; sit: string; onCelda: (sit: string, apoyo: string) => void }) {
  const [sub, setSub] = useState("comparar");
  const a = d.strokes.filter(SITUACION[sit] || SITUACION.todas).sort((x, y) => (y.quality ?? -1) - (x.quality ?? -1));
  const r: AnyRec = d.run_info || {};
  return (
    <>
      <div className="chips">{MAS.map(([k, t]) => <button className="chip" type="button" key={k} data-sub={k} aria-pressed={k === sub} onClick={() => setSub(k)}>{t}</button>)}</div>
      {sub === "medidas" ? <Explorador d={d} a={a} /> : null}
      {sub === "comparar" ? <Comparar d={d} a={a} /> : null}
      {sub === "conclusiones" ? <Conclusiones d={d} /> : null}
      {sub === "situaciones" ? <Situaciones d={d} onCelda={onCelda} /> : null}
      {sub === "tactica" ? <Tactica a={a} /> : null}
      {sub === "pista" ? <Pista a={a} /> : null}
      {sub === "tabla" ? <Tabla a={a} /> : null}
      {sub === "lateral" ? <div className="card" style={{ marginTop: 12 }}><h3>Vista lateral (entreno)</h3>
        <p className="sub">Apartado aparte y marcado (requisito 6): vídeos de entrenamiento de la propia jugadora filmados de lado, solo para lo que la tele no ve (impacto por delante de la cadera, ángulo del swing). Nunca se mezcla con los datos de partido.</p></div> : null}
      {sub === "fiabilidad" ? <Fiabilidad d={d} /> : null}
      {sub === "datos" ? <div className="grid2" style={{ marginTop: 12 }}>
        <div className="card"><h3>Diferencias conocidas</h3><ul>{d.known.map((t, i) => <li key={i}>{t}</li>)}</ul></div>
        <div className="card"><h3>El análisis</h3><table className="t"><tbody>
          <tr><td>Vídeo analizado</td><td className="num">{fmt(r.video_min)} min</td></tr>
          <tr><td>Tiempo de análisis</td><td className="num">{fmt(r.analysis_min)} min</td></tr>
          <tr><td>Generado</td><td>{d.generated || "—"}</td></tr></tbody></table></div></div> : null}
      {sub === "exportar" ? <div className="card" style={{ marginTop: 12 }}><h3>Exportar</h3>
        <p className="sub">Un PDF corto con lo esencial y los MP4 de los golpes o de una lista de reproducción (#41, #46).</p>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}><button className="btn" type="button">PDF corto</button><button className="btn" type="button">MP4 de esta selección</button></div>
        <p className="mock" style={{ marginTop: 10 }}>La exportación existe en el PC; aquí se conecta con P0.5e.</p></div> : null}
    </>
  );
}
