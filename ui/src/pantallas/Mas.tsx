// P0.5c (15-11): «Más», from the validated mockup (#305) plus the design's change 2 (docs/p0_diseno.md §10): Táctica, with
// what the data already give (direction, depth, in or out, under pressure, changes of direction within a game). Every
// figure with its number of strokes; below MIN_N strokes it says so instead of a percentage.
import { useState } from "react";
import { useApp } from "../App";
import type { Datos, Golpe } from "../contrato";
import { SOLO_PC, api, type Respuesta } from "../api";
import { esN, fmt } from "../datos";
import { SITUACION } from "../situaciones";
import { FichaGolpe, tituloGolpe } from "./Golpe";
import { Explorador } from "./Medidas";

type AnyRec = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const MIN_N = 10;
const sgn = (v: number, d = 0) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);
const pct = (n: number, de: number, que = "golpes") => (de >= MIN_N ? `${fmt((100 * n) / de)} %` : `${n} de ${de} (pocos ${que})`);
export const MAS: [string, string][] = [["medidas", "Medidas"], ["comparar", "Comparar"], ["conclusiones", "Conclusiones"], ["situaciones", "Situaciones"], ["tactica", "Táctica"], ["resto", "Resto"],
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

// change 2 (docs/p0_diseno.md §10): her forehands put together by point. A stroke knows its place in the point and her
// hits in it (the cheap pass's hits on her side in the same main-camera shot); strokes of one match with the same total,
// growing places and close in time (≤ 8 s per hit between them) are one point. Only her forehands are analysed: the
// backhands of the point count in its length but have no data here.
interface Punto { match: number; total: number; golpes: Golpe[] }
export function puntos(a: Golpe[]): Punto[] {
  const con = a.filter((s) => esN(s.shotInPoint) && esN(s.shotsInPoint) && esN(s.vt))
    .sort((x, y) => x.match - y.match || (x.vt as number) - (y.vt as number));
  const out: Punto[] = [];
  for (const s of con) {
    const p = out[out.length - 1], last = p?.golpes[p.golpes.length - 1];
    if (p && last && p.match === s.match && p.total === s.shotsInPoint && (s.shotInPoint as number) > (last.shotInPoint as number)
        && (s.vt as number) - (last.vt as number) <= 8 * ((s.shotInPoint as number) - (last.shotInPoint as number))) p.golpes.push(s);
    else out.push({ match: s.match, total: s.shotsInPoint as number, golpes: [s] });
  }
  return out;
}

function MiniPunto({ p }: { p: Punto }) {
  const { abrir } = useApp();
  const HL = 11.885, SW = 4.115, DW = 5.485, SL = 6.4;
  return (
    <div className="grid2" style={{ alignItems: "start" }}>
      <div className="court"><svg viewBox="-6.5 -13.5 13 31" role="img" aria-label="Un punto: sus derechas en orden (abajo, dónde golpea; arriba, dónde bota)" data-minimapa
        style={{ display: "block", margin: "0 auto", maxHeight: 440, width: "100%" }}>
        <rect className="outer" x={-6.5} y={-13.5} width={13} height={31} />
        <rect className="surf" x={-DW} y={-HL} width={2 * DW} height={2 * HL} />
        <rect className="ln" x={-DW} y={-HL} width={2 * DW} height={2 * HL} />
        <line className="ln" x1={-SW} x2={-SW} y1={-HL} y2={HL} /><line className="ln" x1={SW} x2={SW} y1={-HL} y2={HL} />
        <line className="ln" x1={-SW} x2={SW} y1={-SL} y2={-SL} /><line className="ln" x1={-SW} x2={SW} y1={SL} y2={SL} />
        <line className="ln" x1={0} x2={0} y1={-SL} y2={SL} /><line className="net" x1={-6.2} x2={6.2} y1={0} y2={0} />
        {p.golpes.map((s) => {
          const x = s.x as number, y = s.y as number, bx = s.shotX as number, by = -((s.shotY as number) - HL);
          const ok = esN(s.x) && esN(s.y), dest = ok && esN(s.shotX) && esN(s.shotY);
          return ok ? <g key={s.id}>
            {dest ? <line x1={x} y1={y} x2={bx} y2={by} stroke={s.shotIn === false ? "#d83a3a" : "#fff"} strokeWidth={0.08} strokeDasharray="0.3 0.2" /> : null}
            {dest ? <circle cx={bx} cy={by} r={0.22} fill={s.shotIn === false ? "#d83a3a" : "#fff"} /> : null}
            <circle cx={x} cy={y} r={0.62} fill="var(--accent, #2563eb)" stroke="#fff" strokeWidth={0.08} />
            <text x={x} y={y + 0.26} fontSize={0.75} textAnchor="middle" fill="#fff" fontWeight={700}>{s.shotInPoint as number}</text>
          </g> : null;
        })}
      </svg></div>
      <div><p className="sub">Sus {p.total} golpes del punto (los de revés cuentan, pero solo se analizan sus derechas): el número es su golpe en el punto; la línea, adónde fue (rojo: fuera).</p>
        <div className="list" style={{ marginTop: 6 }}>{p.golpes.map((s) => (
          <button className="row clickable" type="button" key={s.id} data-punto-golpe style={{ width: "100%", textAlign: "left" }} onClick={() => abrir(<FichaGolpe s={s} />)}>
            <span><b>{s.shotInPoint as number}.º</b> {[s.shotDir, s.stance, s.outcome && s.outcome !== "sigue" ? s.outcome : null].filter(Boolean).join(" · ") || "—"}</span>
            <span className="sub">ver</span></button>))}</div></div>
    </div>
  );
}

function Peloteo({ a }: { a: Golpe[] }) {
  const ps = puntos(a);
  const largos = ps.filter((p) => p.golpes.length >= 3).sort((x, y) => y.golpes.length - x.golpes.length || y.total - x.total);
  const [i, setI] = useState(0);
  const cubo = (n: number) => (n >= 5 ? "5 o más" : String(n));
  const largo: Record<string, number> = {};
  for (const p of ps) largo[cubo(p.total)] = (largo[cubo(p.total)] || 0) + 1;
  const conK = a.filter((s) => esN(s.shotInPoint));
  const errK: [string, number, number][] = ["1", "2", "3", "4", "5 o más"].map((k) => {
    const xs = conK.filter((s) => cubo(s.shotInPoint as number) === k);
    return [k, xs.filter((s) => s.outcome === "error").length, xs.length];
  });
  const seq: Record<string, number> = {};
  let nseq = 0;
  for (const p of ps) for (let j = 1; j < p.golpes.length; j++) {
    const x = p.golpes[j - 1], y = p.golpes[j];
    if ((y.shotInPoint as number) === (x.shotInPoint as number) + 1 && x.shotDir && y.shotDir) { seq[`${x.shotDir} → ${y.shotDir}`] = (seq[`${x.shotDir} → ${y.shotDir}`] || 0) + 1; nseq++; }
  }
  const p = largos[Math.min(i, Math.max(0, largos.length - 1))];
  return (
    <>
      <div className="grid3" style={{ marginTop: 12 }}>
        <div className="card"><h3>Largo de sus puntos</h3><table className="t"><tbody>
          {["1", "2", "3", "4", "5 o más"].map((k) => <tr key={k}><td>{k} golpe{k === "1" ? "" : "s"} suyos</td><td className="num">{pct(largo[k] || 0, ps.length, "puntos")}</td></tr>)}</tbody></table>
          <p className="sub">{ps.length} puntos vistos desde su principio, con alguna de sus derechas (los puntos, con todos sus golpes, sea cual sea la situación elegida).</p></div>
        <div className="card"><h3>En qué golpe del punto falla</h3><table className="t"><tbody>
          {errK.map(([k, e, n]) => <tr key={k}><td>{k === "5 o más" ? "5.º o más" : `${k}.º`} golpe</td><td className="num">{n ? pct(e, n) : "—"}</td><td className="sub">{e} error{e === 1 ? "" : "es"} de {n}</td></tr>)}</tbody></table>
          <p className="sub">Sus derechas que acaban en error, según su golpe en el punto.</p></div>
        <div className="card"><h3>Dos derechas seguidas</h3>
          {nseq ? <table className="t"><tbody>{Object.entries(seq).sort((x, y) => y[1] - x[1]).slice(0, 6).map(([k, n]) => <tr key={k}><td>{k}</td><td className="num">{pct(n, nseq, "pares")}</td></tr>)}</tbody></table>
            : <p className="sub">Sin pares de derechas seguidas con las dos direcciones medidas.</p>}
          <p className="sub">{nseq} pares (su golpe y el siguiente del mismo punto, los dos de derecha y con dirección medida).</p></div>
      </div>
      <div className="card"><h3>Un punto entero</h3>
        {p ? <>
          <div className="chips" style={{ margin: "6px 0" }}>
            <button className="chip" type="button" data-punto="-1" disabled={i === 0} onClick={() => setI(Math.max(0, i - 1))}>‹ Anterior</button>
            <span className="sub">punto {i + 1} de {largos.length} con 3 o más de sus derechas</span>
            <button className="chip" type="button" data-punto="1" disabled={i >= largos.length - 1} onClick={() => setI(Math.min(largos.length - 1, i + 1))}>Siguiente ›</button>
          </div>
          <MiniPunto p={p} /></> : <p className="sub">Ningún punto con 3 o más de sus derechas en esta situación.</p>}
      </div>
    </>
  );
}

// change 3 (docs/p0_diseno.md §10): the return of serve, as tennisbio.returns finds it and names its variants
const RESTO_COMO = "Un golpe es un resto cuando saca la rival (el icono de saque del marcador) y es su primer golpe del punto "
  + "(los impactos de su lado en el mismo plano). El saque recibido sale de dónde bota en su cuadro (homografía): abierto, al "
  + "cuerpo o a la T, por tercios; el lado, de los puntos jugados en el juego (marcador), comprobado con el bote; primer o "
  + "segundo saque, de si el plano enseña un saque anterior. El tipo de resto se construye con lo que su golpe ya tiene: "
  + "preparación (amplia o compacta), terminación y trayectoria de la mano (cortado: de arriba abajo, no el efecto).";

function mediana(xs: number[]) { const v = [...xs].sort((x, y) => x - y); return v.length ? v[Math.floor(v.length / 2)] : NaN; }

function Resto({ todas }: { todas: Golpe[] }) {
  const { abrir } = useApp();
  const r = todas.filter((s) => s.play === "resto");
  const tabla = (campo: string, que = "restos") => {
    const xs = r.filter((s) => typeof s[campo] === "string" && s[campo]);
    return <><table className="t"><tbody>{reparto(xs, campo).map(([k, n]) => <tr key={k}><td>{k}</td><td className="num">{pct(n, xs.length, que)}</td></tr>)}</tbody></table>
      <p className="sub">{xs.length} de {r.length} restos con este dato.</p></>;
  };
  const lv = (s: Golpe, k: string) => (s.lv as Record<string, unknown> | undefined)?.[k];
  const espera = r.map((s) => lv(s, "stroke.return_ready_depth_m")).filter(esN) as number[];
  const entra = r.map((s) => lv(s, "stroke.return_step_in_m")).filter(esN) as number[];
  const errores = r.filter((s) => s.outcome === "error").length;
  return (
    <>
      <div className="card" style={{ marginTop: 12 }}><h3>Sus restos de derecha</h3>
        <p className="sub">{RESTO_COMO}</p></div>
      <div className="grid4">
        <div className="card stat"><b className="num">{r.length}</b><span>restos de derecha (de {todas.length} derechas)</span></div>
        <div className="card stat"><b className="num">{espera.length >= MIN_N ? `${fmt(mediana(espera), 2)} m` : "pocos"}</b><span>dónde espera el saque (desde la línea de fondo; − es detrás) · {espera.length} restos</span></div>
        <div className="card stat"><b className="num">{entra.length >= MIN_N ? `${fmt(mediana(entra), 2)} m` : "pocos"}</b><span>cuánto entra hacia la bola desde ahí · {entra.length} restos</span></div>
        <div className="card stat"><b className="num">{pct(errores, r.length, "restos")}</b><span>acaban en error</span></div>
      </div>
      <div className="grid3">
        <div className="card"><h3>El saque que recibe</h3>{tabla("serveDir")}</div>
        <div className="card"><h3>Lado</h3>{tabla("returnSide")}<h3 style={{ marginTop: 10 }}>Primer o segundo saque</h3>{tabla("serveNumber")}</div>
        <div className="card"><h3>Tipo de resto</h3>{tabla("returnType")}</div>
      </div>
      <div className="card"><h3>Sus restos, con su vídeo</h3>
        <div className="list">{r.slice(0, 30).map((s) => (
          <button className="row clickable" type="button" key={s.id} data-resto style={{ width: "100%", textAlign: "left" }} onClick={() => abrir(<FichaGolpe s={s} />)}>
            <span>{tituloGolpe(s)}</span>
            <span className="sub">{[s.serveDir ? `saque ${s.serveDir}` : null, s.returnSide, s.returnType].filter(Boolean).join(" · ") || "—"}</span></button>))}</div>
        {r.length > 30 ? <p className="sub">Los 30 primeros de {r.length}; todos están en «Sus golpes».</p> : null}</div>
    </>
  );
}

function Tactica({ a, todas }: { a: Golpe[]; todas: Golpe[] }) {
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
      <Peloteo a={todas} />
      <p className="mock">Lo que falta de la táctica (#14 de Ivanovic, The Tennis Mentor): su punto de recuperación frente a las opciones de la rival (hace falta la posición de la rival en cada golpe) y lo que hace bien o dónde pierde en cada punto.</p>
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
      {sub === "tactica" ? <Tactica a={a} todas={d.strokes} /> : null}
      {sub === "resto" ? <Resto todas={d.strokes} /> : null}
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
      {sub === "exportar" ? <Exportar d={d} /> : null}
    </>
  );
}

// P0.5e (21-11): the export (#41, #46) is made in the cloud with the report (the short PDF with the essentials and a
// montage per conclusion, `tennisbio export`) and brought with the results; each file opens with the PC's own program.
function Exportar({ d }: { d: Datos }) {
  const pc = api();
  const [resp, setResp] = useState<Respuesta | null>(null);
  const ex = d.exportados || [];
  const abrir = async (ruta: string) => {
    if (!pc) return;
    try { const r = await pc.abrir(ruta); setResp(r.ok ? null : r); } catch (e) { setResp({ ok: false, motivo: String(e) }); }
  };
  const boton = (ruta: string, txt = "Abrir") => <button className="btn" type="button" data-abrir={ruta} disabled={!pc}
    title={pc ? undefined : SOLO_PC} onClick={() => abrir(ruta)}>{txt}</button>;
  const pdf = ex.filter((e) => e.tipo === "pdf"), mont = ex.filter((e) => e.tipo === "montaje"), golpes = ex.filter((e) => e.tipo === "golpe");
  const carpeta = (e: { ruta: string }) => e.ruta.split("/").slice(0, -1).join("/");
  return (
    <div className="card" style={{ marginTop: 12 }} data-exportar={ex.length}><h3>Exportar</h3>
      <p className="sub">Un PDF corto con lo esencial y un vídeo por conclusión con sus golpes (#41, #46). Se hacen en la nube con el informe y llegan con los resultados.</p>
      {ex.length ? <table className="t" style={{ marginTop: 10 }}><tbody>
        {pdf.map((e) => <tr key={e.ruta}><td>Resumen en PDF</td><td className="num">{fmt(e.mb, 1)} MB</td><td>{boton(e.ruta)}</td></tr>)}
        {mont.map((e) => <tr key={e.ruta}><td>{e.titulo || ((t) => t.charAt(0).toUpperCase() + t.slice(1))(e.nombre.replace(/^\d+_/, "").replace(/\.mp4$/, "").replace(/[-_]/g, " "))}</td>
          <td className="num">{fmt(e.mb, 1)} MB</td><td>{boton(e.ruta)}</td></tr>)}
        {golpes.length ? <tr><td>Los vídeos de cada golpe de los montajes ({golpes.length})</td><td className="num">{fmt(golpes.reduce((a, e) => a + e.mb, 0), 0)} MB</td>
          <td>{boton(carpeta(golpes[0]), "Abrir la carpeta")}</td></tr> : null}
        {mont.length ? <tr><td>Todos los montajes</td><td></td><td>{boton(carpeta(mont[0]), "Abrir la carpeta")}</td></tr> : null}
      </tbody></table>
        : <p className="sub" style={{ marginTop: 10 }}>{d.ejemplo ? "Con datos de ejemplo no hay nada que exportar." :
          "Aún no hay exportación en el PC: se hace en la nube con el próximo informe y llega con «Traer resultados de la nube» (Inicio)."}</p>}
      {resp ? <p className="pill crit" role="status" style={{ marginTop: 8 }}>{resp.motivo}</p> : null}
    </div>
  );
}
