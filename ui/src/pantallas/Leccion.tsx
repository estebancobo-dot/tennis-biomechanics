// P0.5b (15-11): the lesson, ported from the validated mockup (#305): per phase its drawing (from its measure, one at a
// time, as the coaches' shorts), its focus, its three key measures in the chosen situation (value, half of her strokes,
// whether it changes with the ball beyond the measuring noise, reliability), the strings, practice with its criterion;
// under it, the lesson's sections. Nothing invented: a measure without data says so.
import { useState } from "react";
import type { Datos, PuntoDeControl } from "../contrato";
import { esN, fmt } from "../datos";

type AnyRec = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const sgn = (v: number, d = 0) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);

const G = "var(--draw)", R2 = "var(--draw-2)";
const BASE = '<g fill="none" stroke="#f3f7fb" stroke-opacity=".45" stroke-width=".4"><path d="M28 18 L72 18 L94 70 L6 70 Z"/><path d="M34 18 L24 70 M66 18 L76 70 M31 34 L69 34 M50 34 L50 70"/><path d="M25 40 L75 40" stroke-width=".9" stroke-opacity=".7"/></g>';
const FIG = '<g stroke="#fff" stroke-width="1.6" stroke-linecap="round" fill="none" opacity=".92"><circle cx="50" cy="46" r="2.6" fill="#fff"/><path d="M50 49 L50 58 M45 51 L55 51 M50 58 L46 66 M50 58 L55 66"/></g>';
const DIBUJOS: Record<string, string> = {
  ready: `<circle cx="50" cy="22" r="1.8" fill="${G}"/><text x="53" y="23" fill="#fff" font-size="3">golpea la rival</text><path d="M44 66 L47 63 M56 66 L53 63" stroke="${G}" stroke-width="1.4"/>`,
  takeback: `<path d="M41 50 Q50 43 60 49" stroke="${G}" stroke-width="1.4" fill="none" marker-end="url(#ar)"/>`,
  loaded: `<line x1="50" y1="38" x2="50" y2="69" stroke="#fff" stroke-width=".7" stroke-dasharray="1.5 1"/><path d="M42 47 Q50 40 58 47" stroke="${G}" stroke-width="1.4" fill="none" marker-end="url(#ar)"/>`,
  acceleration: `<path d="M60 44 Q66 60 56 62 Q46 62 44 50" stroke="#fff" stroke-width="1" fill="none"/><circle cx="56" cy="62" r="1.6" fill="${R2}"/>`,
  impact: `<path d="M50 51 L58 52 L64 48" stroke="${G}" stroke-width="1.4" fill="none"/><circle cx="58" cy="52" r="2" stroke="${G}" fill="none"/><rect x="62" y="44" width="8" height="7" stroke="${G}" fill="none" stroke-width=".8"/>`,
  extension: `<path d="M56 50 L70 44" stroke="${G}" stroke-width="1.4" marker-end="url(#ar)"/>`,
  finish: `<line x1="38" y1="47" x2="64" y2="47" stroke="${G}" stroke-width="1"/><circle cx="44" cy="43" r="1.6" fill="${G}"/>`,
  recovery: `<path d="M56 66 Q50 60 44 64" stroke="${G}" stroke-width="1.4" fill="none" marker-end="url(#ar)"/>`,
  feet: `<g fill="${G}" font-size="3"><circle cx="40" cy="64" r="1.6"/><circle cx="47" cy="62" r="1.6"/><circle cx="54" cy="64" r="1.6"/><text x="39" y="61" fill="#fff">1</text><text x="46" y="59" fill="#fff">2</text><text x="53" y="61" fill="#fff">3</text></g>`,
};

function Dibujo({ fase }: { fase: string }) {
  const html = `<defs><marker id="ar" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0 6 3 0 6z" fill="${G}"/></marker></defs>${BASE}${FIG}${DIBUJOS[fase] || ""}`;
  return <svg viewBox="0 0 100 75" preserveAspectRatio="none" aria-hidden="true" dangerouslySetInnerHTML={{ __html: html }} />;
}

function Fiabilidad({ d, k }: { d: Datos; k: string }) {
  const m = d.metrics[k] || {};
  if (m.est) return <span className="pill est">estimada</span>;
  return (m.rel ?? 0) >= 3 ? <span className="pill good">fiable</span> : m.rel === 2 ? <span className="pill warn">media</span> : <span className="pill crit">baja</span>;
}

function Veredicto({ v }: { v?: string }) {
  if (!v) return null;
  const cls = /fiable/.test(v) ? "good" : /ruid|sesgo|no fiable/.test(v) ? "crit" : "warn";
  return <span className={`pill ${cls}`}>{v}</span>;
}

function Clave({ d, c, sit }: { d: Datos; c: PuntoDeControl; sit: string }) {
  const s = d.situations.find((x) => x.id === sit), todas = d.situations.find((x) => x.id === "todas");
  const met = c.m ? d.metrics[c.m] : undefined;
  const st = c.m && s ? s.m[c.m] : null, all = c.m && todas ? todas.m[c.m] : null;
  const dec = met?.dec ?? 0, unit = met?.unit || "";
  const rel = (d.reliability as AnyRec | undefined)?.[c.key];
  let valor: JSX.Element | null = null, n = rel?.n ?? null, extra: JSX.Element | null = null, rango = "valor de su serie fotograma a fotograma";
  if (met && st && esN(st.med)) {
    valor = <span className="v num">{fmt(st.med, dec)}<small>{unit}</small></span>;
    n = st.n;
    rango = `la mitad de sus golpes entre ${fmt(st.p25, dec)} y ${fmt(st.p75, dec)} ${unit}`;
    if (sit !== "todas" && all && esN(all.med)) {
      const dv = st.med - all.med;
      extra = Math.abs(dv) > (met.noise || 0) ? <span className="pill est">cambia con la bola: {sgn(dv, dec)} {unit}</span> : <span className="pill mute">igual que siempre</span>;
    }
  }
  return (
    <div className="key">
      <div className="key-h"><div><b>{c.label}</b>{n ? <span className="sub"> · {n} golpes</span> : null}</div>{valor}</div>
      {c.cue ? <p className="how">{c.cue}</p> : null}
      {c.mistake ? <p className="pb"><b>Si te pasa:</b> {c.mistake}</p> : null}
      {c.read ? <p className="sub">Cómo se mide: {c.read}</p> : null}
      <div className="chips">{met ? <Fiabilidad d={d} k={c.m!} /> : <Veredicto v={rel?.verdict} />}{extra}<span className="sub">{rango}</span></div>
    </div>
  );
}

const CARA: Record<string, string> = { loaded: "rFaceArm", impact: "rFaceImp", finish: "rFaceFin" };

function leerHechas(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem("tb-done") || "{}"); } catch { return {}; }
}

export function Leccion({ d, sit }: { d: Datos; sit: string }) {
  const [ph, setPh] = useState(0);
  const [hechas, setHechas] = useState(leerHechas);
  const fases = d.phases, p = fases[ph], i0 = ph;
  if (!p) return <p className="sub">Sin fases en este análisis.</p>;
  const plan = new Set(((d.plan as AnyRec[]) || []).slice(0, 3).map((x) => x.key));
  const ritmo: AnyRec = (d.rhythm as AnyRec) || {};
  const rh = (ritmo.events || []).find((e: AnyRec) => e.k === p.id);
  const claves = p.checks.filter((c) => c.m && d.metrics[c.m]).concat(p.checks.filter((c) => !(c.m && d.metrics[c.m]))).slice(0, 3);
  const cita = (p.focus || "").match(/«([^»]+)»/);
  const foco = p.focus || p.when || "";
  const cara = CARA[p.id];
  const fs = cara ? d.situations.find((x) => x.id === sit)?.m[cara] : null;
  const ejercicio = p.checks.find((c) => c.drill)?.drill;
  const marcar = () => {
    const h = { ...hechas, [p.id]: !hechas[p.id] };
    setHechas(h);
    try { localStorage.setItem("tb-done", JSON.stringify(h)); } catch { /* sin almacenamiento: solo esta vez */ }
  };
  return (
    <>
      <div className="strip" role="tablist">
        {fases.map((x, i) => (
          <button className="ph" type="button" key={x.id} data-ph={i} aria-current={i === ph ? "page" : undefined} onClick={() => setPh(i)}>
            <div className="mini" style={{ position: "relative" }}><Dibujo fase={x.id} /></div>
            <div className="nm">{i + 1} · {x.title}</div>
            {x.checks.some((c) => plan.has(c.key)) ? <span className="start">empieza aquí</span> : null}
            {hechas[x.id] ? <span className="start" style={{ left: 6, right: "auto", background: "var(--good)", color: "#fff" }}>✓</span> : null}
          </button>
        ))}
      </div>
      <div className="lesson">
        <div>
          <div className="frame">
            <Dibujo fase={p.id} />
            <span className="tag">Su golpe más representativo en esta situación · fotograma real en la aplicación</span>
            <span className="cap">{(p.title.split("·")[1] || p.title).trim()}{rh && esN(rh.median) ? <> · <em>{rh.median === 0 ? "impacto" : sgn(rh.median, 2) + " s"}</em></> : null}</span>
          </div>
          <div className="controls">
            <button className="chip" type="button" aria-pressed="true">Velocidad real</button>
            <button className="chip" type="button">¼</button>
            <button className="chip" type="button">Otro golpe suyo</button>
            <button className="chip" type="button">El golpe entero</button>
          </div>
          <p className="mock" style={{ marginTop: 10 }}>El dibujo sale de la medida de la fase (como en los shorts de los entrenadores): uno solo cada vez. El vídeo real y sus capas llegan con el reproductor.</p>
        </div>
        <div style={{ display: "grid", gap: 14 }}>
          <div><span className="eyebrow">Foco</span>
            <div className="focus">{cita ? <>{foco.slice(0, foco.indexOf(cita[0]))}<em>{cita[0]}</em>{foco.slice(foco.indexOf(cita[0]) + cita[0].length)}</> : foco}</div></div>
          {claves.map((c) => <Clave d={d} c={c} sit={sit} key={c.key} />)}
          {p.checks.length > claves.length ? (
            <details className="fold"><summary>Todas las claves de esta fase ({p.checks.length})</summary>
              <div style={{ display: "grid", gap: 10, paddingBottom: 12 }}>
                {p.checks.filter((c) => !claves.includes(c)).map((c) => <Clave d={d} c={c} sit={sit} key={c.key} />)}
              </div></details>
          ) : null}
          {i0 === 0 ? (
            <div className="key"><b>Empuñadura</b>
              <p className="how">{d.grip || "El tipo exacto no se ve desde la tele: la mano mide 20-40 px. Solo se dice si sus golpes son compatibles con una familia (por la altura del contacto y la cara en el armado)."}</p>
              <div className="chips"><span className="pill mute">{d.grip && /compatible con/.test(d.grip) ? "estimación por indicios" : "no medible desde la tele"}</span></div></div>
          ) : null}
          <div className="key"><b>Cuerdas en esta fase</b>
            <p className="how">{fs && esN(fs.med) ? `Cara ${fs.med >= 0 ? "cerrada" : "abierta"} ${fmt(Math.abs(fs.med))}° (mediana de ${fs.n} golpes con la mano en 3D)`
              : cara ? "Pocos golpes con la mano en 3D para decirlo en esta situación." : "No medible desde la tele en esta fase (sin la mano en 3D)."} {cara ? <Fiabilidad d={d} k={cara} /> : null}</p></div>
          <div className="practice"><b>Practica</b><span>{ejercicio || "—"}</span><span className="sub">Criterio: 8 de 10 bien = conseguido.</span>
            <div><button className={`btn ${hechas[p.id] ? "" : "primary"}`} type="button" data-done={p.id} onClick={marcar}>{hechas[p.id] ? "Conseguido ✓" : "Conseguido"}</button></div></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <button className="btn" type="button" onClick={() => setPh(Math.max(0, ph - 1))}>‹ Fase anterior</button>
            <button className="btn" type="button" onClick={() => setPh(Math.min(fases.length - 1, ph + 1))}>Fase siguiente ›</button>
          </div>
        </div>
      </div>
      <Secciones d={d} sit={sit} />
    </>
  );
}

function Ritmo({ d }: { d: Datos }) {
  const r: AnyRec = (d.rhythm as AnyRec) || {};
  const ev: AnyRec[] = (r.events || []).concat((r.chain || []).map((c: AnyRec) => ({ ...c, label: "Pico: " + c.label })));
  if (!ev.length) return <p className="sub">Sin datos de ritmo.</p>;
  const W = 900, L = 200, R = 20, row = 26, top = 20, H = top + row * ev.length + 26, lo = -1.6, hi = 0.7;
  const X = (t: number) => L + ((t - lo) / (hi - lo)) * (W - L - R);
  const ticks = [-1.5, -1, -0.5, 0, 0.5];
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Su ritmo: cuándo pasa cada momento respecto al impacto">
      {ticks.map((t) => <g key={t}><line className="grid" x1={X(t)} x2={X(t)} y1={top - 6} y2={H - 22} /><text x={X(t)} y={H - 6} textAnchor="middle">{t === 0 ? "impacto" : sgn(t, 1) + " s"}</text></g>)}
      {ev.map((e, i) => {
        const y = top + i * row + row / 2;
        return (
          <g key={i}>
            <text className="lab" x={L - 10} y={y + 4} textAnchor="end">{e.label}</text>
            {esN(e.p25) && esN(e.p75) && e.p75 > e.p25 ? <rect className="bar" x={X(e.p25)} y={y - 6} width={X(e.p75) - X(e.p25)} height={12} rx={6} /> : null}
            {esN(e.median) ? (e.k === "impact" ? <circle className="imp" cx={X(0)} cy={y} r={6} /> : <circle className="dot" cx={X(e.median)} cy={y} r={5} />) : null}
          </g>
        );
      })}
    </svg>
  );
}

function Secciones({ d, sit }: { d: Datos; sit: string }) {
  const s = d.situations.find((x) => x.id === sit);
  const conf = (c: string) => (/fiable|real/.test(c) ? "good" : /estimada|baja/.test(c) ? "est" : "warn");
  const conc = (d.conclusions as AnyRec[]) || [], hall = (d.findings as AnyRec[]) || [], plan = (d.plan as AnyRec[]) || [];
  const sint = (d.symptoms as AnyRec[]) || [], glos = (d.glossary as [string, string][]) || [];
  const notv = (d.not_tv as [string, string][]) || [];
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <details className="fold"><summary>Lo esencial: conclusiones medidas ({conc.length})</summary>
        <div className="list">{conc.map((c, i) => <div className="row" key={i}><div>{c.text}</div><span className={`pill ${conf(c.conf || "")}`}>{c.conf}</span></div>)}</div></details>
      <details className="fold"><summary>Su ritmo y su cadena cinética</summary><div><Ritmo d={d} /></div></details>
      <details className="fold"><summary>Qué cambia según la bola (con ajuste por la bola y el partido)</summary>
        <div className="list">{hall.map((f, i) => (
          <div className="row" key={i}><div><div className="t">{f.t}</div><div className="s">{f.c}</div></div>
            <span className={`pill ${(f.v || [])[0] === "good" ? "good" : /ruido/i.test((f.v || [])[1] || "") ? "warn" : "crit"}`}>{(f.v || [])[1] || ""}</span></div>))}</div></details>
      <details className="fold"><summary>Tu plan completo</summary><ol className="steps">{plan.map((p, i) => <li key={i}><div><b>{p.title}</b><div className="sub">{p.why}</div></div></li>)}</ol></details>
      <details className="fold"><summary>Si te pasa…</summary>
        <div className="list">{sint.map((x, i) => <div className="row" key={i}><div><div className="t">{x.s}</div><div className="s">{x.why}</div></div></div>)}</div></details>
      <details className="fold"><summary>Lo que la tele no mide</summary>
        <div className="list">{notv.map(([a, b], i) => <div className="row" key={i}><div><div className="t">{a}</div><div className="s">{b}</div></div><span className="pill mute">no medible desde la tele</span></div>)}</div></details>
      <details className="fold"><summary>Todas las medidas</summary>
        <div className="scroll"><table className="t"><tbody>
          <tr><th>Medida</th><th>Mediana</th><th>Mitad central</th><th>Golpes</th><th>Fiabilidad</th></tr>
          {Object.entries(d.metrics).map(([k, m]) => {
            const st = s?.m[k];
            return (
              <tr key={k}><td>{m.name}<div className="sub">{m.sub || ""}</div></td>
                <td className="num">{st && esN(st.med) ? `${fmt(st.med, m.dec ?? 0)} ${m.unit || ""}` : "—"}</td>
                <td className="num">{st && esN(st.med) ? `${fmt(st.p25, m.dec ?? 0)} – ${fmt(st.p75, m.dec ?? 0)}` : "—"}</td>
                <td className="num">{st ? st.n : 0}</td><td><Fiabilidad d={d} k={k} /></td></tr>
            );
          })}
        </tbody></table></div></details>
      <details className="fold"><summary>Glosario ({glos.length} términos)</summary>
        <div className="list">{glos.map(([a, b], i) => <div className="row" key={i}><div><div className="t">{a}</div><div className="s">{b}</div></div></div>)}</div></details>
    </div>
  );
}
