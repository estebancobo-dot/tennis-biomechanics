// P0.5b (15-11): «Sus golpes» (the gallery, in the orders of the requirements: best captured, most representative, by
// outcome, least time) and one stroke's analysis, from the validated mockup (#305) plus the design's change 6
// (docs/p0_diseno.md §10): doubtful strokes marked (requirement 5), warnings only where the stroke differs from her usual
// beyond the measuring noise, «Cuenta conmigo» (her strokes in the same game, each with its stance). What needs the
// stroke's video and frame series (the layers, the strobe image, the contact strip) is marked until the player is in.
import { useState } from "react";
import { Panel, useApp } from "../App";
import type { Datos, Golpe } from "../contrato";
import { esN, fmt } from "../datos";
import { SITUACION } from "../situaciones";

type AnyRec = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const sgn = (v: number, d = 0) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);
export const tituloGolpe = (s: Golpe) => `Frente a ${s.rival || "—"}${s.set ? ` · ${s.set}.º set ${s.score || ""}` : ""}`;
const ORDENES: [string, string][] = [["captura", "Mejor captados"], ["representativo", "Más representativos"], ["resultado", "Por resultado"], ["tiempo", "Menos tiempo"]];
const POR: Record<string, (x: Golpe, y: Golpe) => number> = {
  captura: (x, y) => (y.quality ?? -1) - (x.quality ?? -1),
  representativo: (x, y) => (x.repr ?? 9) - (y.repr ?? 9),
  resultado: (x, y) => ["ganador", "error", "sigue"].indexOf(x.outcome || "") - ["ganador", "error", "sigue"].indexOf(y.outcome || ""),
  tiempo: (x, y) => ((x.tAvail as number) ?? 9) - ((y.tAvail as number) ?? 9),
};
const FASES = ["ready", "takeback", "loaded", "acceleration", "impact", "extension", "finish", "recovery"];
const FILAS = ["sh", "xf", "elbow", "contactH", "lat", "baseM", "head", "finishH", "split", "disp", "recov"];

// the analysis' doubts about a stroke, with the report's own words (tennisbio/report_template.html, REVIEW_ES)
const DUDA: Record<string, string> = {
  half_volley_candidate: "media volea candidata", impact_without_audio: "impacto sin audio ni bola",
  racket_not_seen_when_loaded: "raqueta no vista en el armado", elbow_implausible: "codo inverosímil",
  elbow_implausible_at_impact: "codo inverosímil en el impacto (brazos confundidos)",
};
const FASE_ES: Record<string, string> = { ready: "espera", takeback: "preparación", loaded: "armado", acceleration: "aceleración",
  impact: "impacto", extension: "extensión", finish: "terminación", recovery: "recuperación" };
function dudas(s: Golpe): string[] {
  return ((s.review as unknown[]) || []).map((r) => {
    const c = typeof r === "string" ? r : String((r as AnyRec)?.code || (r as AnyRec)?.text || "");
    return c.startsWith("phase:") ? "fase no encontrada o dudosa: " + (FASE_ES[c.slice(6)] || c.slice(6)) : DUDA[c] || c;
  }).filter(Boolean);
}

function Rel({ d, k }: { d: Datos; k: string }) {
  const m = d.metrics[k] || {};
  if (m.est) return <span className="pill est">estimada</span>;
  return (m.rel ?? 0) >= 3 ? <span className="pill good">fiable</span> : m.rel === 2 ? <span className="pill warn">media</span> : <span className="pill crit">baja</span>;
}

export function Galeria({ d, sit, soloApoyo, quitar }: { d: Datos; sit: string; soloApoyo?: string | null; quitar?: () => void }) {
  const { abrir } = useApp();
  const [orden, setOrden] = useState("captura");
  const [vistos, setVistos] = useState(24);
  const [conDudas, setConDudas] = useState(false);
  let a = d.strokes.filter(SITUACION[sit] || SITUACION.todas);
  if (soloApoyo) a = a.filter((s) => s.stance === soloApoyo);
  const nDudas = a.filter((s) => dudas(s).length).length;
  if (conDudas) a = a.filter((s) => dudas(s).length);
  a = [...a].sort(POR[orden]);
  return (
    <>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <b>{a.length} golpes</b>
        {soloApoyo ? <><span className="pill est">apoyo {soloApoyo}</span><button className="btn" type="button" onClick={quitar}>Quitar filtro</button></> : null}
        <button className="chip" type="button" data-dudas aria-pressed={conDudas} onClick={() => { setConDudas(!conDudas); setVistos(24); }}>Con dudas<span className="c num">{nDudas}</span></button>
        <span className="sub" style={{ marginLeft: "auto" }}>Orden:</span>
        <div className="chips">{ORDENES.map(([k, t]) => <button className="chip" type="button" key={k} data-order={k} aria-pressed={k === orden} onClick={() => { setOrden(k); setVistos(24); }}>{t}</button>)}</div>
      </div>
      <div className="vgrid">
        {a.slice(0, vistos).map((s) => (
          <button className="vcard" type="button" key={s.id} data-stroke={s.id} onClick={() => abrir(<FichaGolpe s={s} />)}>
            <div className="frame" style={{ aspectRatio: "16/10" }}><span className="tag">vídeo · captura {fmt(100 * (s.quality ?? 0))} %</span></div>
            <div className="meta"><b>{tituloGolpe(s)}</b>
              <span>{[...s.bits, s.stance && "apoyo " + s.stance, s.outcome === "error" ? "error" : null].filter(Boolean).join(" · ") || "—"}</span>
              {dudas(s).length ? <span className="pill warn">con dudas</span> : null}</div>
          </button>
        ))}
      </div>
      {a.length > vistos ? <button className="btn" type="button" data-more style={{ justifySelf: "center" }} onClick={() => setVistos(vistos + 24)}>Ver más</button> : null}
    </>
  );
}

export function FichaGolpe({ s }: { s: Golpe }) {
  const { d, abrir } = useApp();
  const ph: AnyRec = (s.phases as AnyRec) || {}, b: AnyRec = (s.body as AnyRec) || {}, f: AnyRec = (s.feet as AnyRec) || {};
  const todas = d.situations.find((x) => x.id === "todas");
  const mismo = d.strokes.filter((x) => x.match === s.match && x.set === s.set && x.game === s.game && x.id !== s.id);
  const filas = FILAS.filter((k) => d.metrics[k] && esN(s.m[k])).map((k) => {
    const v = s.m[k] as number, all = todas?.m[k], met = d.metrics[k];
    const dv = all && esN(all.med) ? v - all.med : null;
    return { k, v, all, met, dv, fuera: dv !== null && Math.abs(dv) > (met.noise || 0) };
  });
  const avisos = filas.filter((r) => r.fuera);
  const dd = dudas(s);
  return (
    <Panel titulo={tituloGolpe(s)} sub={[...s.bits, s.stance && "apoyo " + s.stance, s.movement, s.finish && "terminación " + s.finish].filter(Boolean).join(" · ")}>
      {dd.length ? <div className="card"><span className="pill warn">golpe con dudas</span><p className="sub" style={{ marginTop: 6 }}>{dd.join(" · ")}</p>
        <p className="mock" style={{ marginTop: 6 }}>Marcado, nunca pedido: nadie tiene que revisarlo (requisito 5).</p></div> : null}
      <div>
        <div className="frame"><span className="tag">Vídeo real del golpe con capas · captura {fmt(100 * (s.quality ?? 0))} %</span></div>
        <div className="controls">
          {["Velocidad real", "½", "¼", "⅛", "Fotograma a fotograma", "Pantalla completa"].map((t, i) => <button className="chip" type="button" key={t} aria-pressed={i === 0}>{t}</button>)}
          <span className="sub" style={{ marginLeft: 8 }}>Capas:</span>
          {["Cuerpo", "Raqueta", "Bola", "Medidas"].map((t, i) => <button className="chip" type="button" key={t} aria-pressed={i === 0}>{t}</button>)}
        </div>
      </div>
      <div className="card"><h3>Sus 8 fases</h3>
        <div className="chips" style={{ marginTop: 8 }}>
          {FASES.map((k) => <span className="chip" key={k}>{d.phases.find((p) => p.id === k)?.title || k}{esN(ph[k]) ? <span className="c num"> {ph[k] === 0 ? "impacto" : sgn(ph[k], 2) + " s"}</span> : null}</span>)}
        </div></div>
      {avisos.length ? (
        <div className="card"><h3>Avisos: distinto de lo habitual en ella</h3>
          <div className="list">{avisos.map((r) => <div className="row" key={r.k}><div><div className="t">{r.met.name}</div>
            <div className="s">{fmt(r.v, r.met.dec ?? 0)} {r.met.unit} frente a {fmt(r.all?.med, r.met.dec ?? 0)} {r.met.unit} habitual: {sgn(r.dv!, r.met.dec ?? 0)} {r.met.unit}, más que su error de medida</div></div><Rel d={d} k={r.k} /></div>)}</div></div>
      ) : null}
      {((s.ball as AnyRec[]) || []).length ? (
        <div className="card"><h3>La bola y ella</h3>
          <div className="moments" style={{ marginTop: 8 }}>{(s.ball as AnyRec[]).map((m, i) => (
            <div className="moment" key={i}><div className="frame"><span className="tag">{m.t === 0 ? "impacto" : sgn(m.t, 2) + " s"}</span></div><b>{m.title}</b><span>{m.text}</span></div>))}</div></div>
      ) : null}
      <div className="grid2">
        <div className="card"><h3>Bajar y subir</h3>
          {esN(b.drop) ? <>
            <div className="hbar" style={{ marginTop: 8 }}><span>Baja (espera → más bajo)</span><div className="track"><i style={{ left: 0, width: `${Math.min(100, 2.5 * b.drop)}%` }} /></div><span className="num">{fmt(b.drop)} cm</span></div>
            <div className="hbar" style={{ marginTop: 6 }}><span>Sube (más bajo → más alto)</span><div className="track"><i className="up" style={{ left: 0, width: `${Math.min(100, 2.5 * (b.rise || 0))}%` }} /></div><span className="num">{fmt(b.rise)} cm</span></div>
          </> : <p className="sub">Sin medida en este golpe.</p>}
          <h3 style={{ marginTop: 14 }}>Base (m entre los pies)</h3>
          {b.base ? Object.entries(b.base as Record<string, number>).map(([k, v]) => (
            <div className="hbar" style={{ marginTop: 6 }} key={k}><span>{({ loaded: "Armado", impact: "Impacto", finish: "Terminación" } as Record<string, string>)[k] || k}</span>
              <div className="track"><i style={{ left: 0, width: `${Math.min(100, 60 * v)}%` }} /></div><span className="num">{fmt(v, 2)} m</span></div>)) : <p className="sub">Sin medida.</p>}
          <p className="sub" style={{ marginTop: 10 }}>Tronco al terminar: <b>{b.trunk || "—"}</b></p></div>
        <div className="card"><h3>Sus pies</h3>
          <table className="t"><tbody>{([
            ["Recorrido hasta la bola", esN(f.path_m) ? fmt(f.path_m, 1) + " m" : "—"], ["Velocidad máxima", esN(f.peak_speed_mps) ? fmt(f.peak_speed_mps, 1) + " m/s" : "—"],
            ["Cambios de dirección", esN(f.direction_changes) ? fmt(f.direction_changes) : "—"], ["Hacia dónde", f.move_direction || "—"],
            ["Talón de atrás arriba", f.back_heel_lift ? `sí, ${fmt(f.back_heel_lift_s, 2)} s tras el impacto` : "—"],
            ["Vuelve hacia el centro", esN(f.recovery_to_centre_m) ? fmt(f.recovery_to_centre_m, 1) + " m en 1 s" : "—"], ["Papel del apoyo", f.stance_role || "—"],
          ] as [string, string][]).map(([a, v]) => <tr key={a}><td>{a}</td><td><b>{v}</b></td></tr>)}</tbody></table></div>
      </div>
      <div className="grid2">
        <div className="card"><h3>Imagen estroboscópica</h3><p className="sub">Sus esqueletos superpuestos a lo largo del golpe y la trayectoria de la muñeca.</p>
          <p className="mock" style={{ marginTop: 8 }}>Se dibuja con la serie fotograma a fotograma del golpe, que llega con el reproductor (P0.5e).</p></div>
        <div className="card"><h3>Tira de contactos</h3><p className="sub">Todos sus impactos en esta situación, uno junto a otro, y superpuestos en un fotograma.</p>
          <p className="mock" style={{ marginTop: 8 }}>Con los fotogramas de cada impacto, que llegan con el reproductor (P0.5e).</p></div>
      </div>
      <div className="card scroll"><h3>Frente a lo habitual en ella</h3>
        <table className="t"><tbody><tr><th>Medida</th><th>Este golpe</th><th>Lo habitual</th><th>Diferencia</th><th>Fiabilidad</th></tr>
          {filas.map((r) => <tr key={r.k}><td>{r.met.name}</td><td className="num">{fmt(r.v, r.met.dec ?? 0)} {r.met.unit}</td>
            <td className="num">{r.all && esN(r.all.med) ? fmt(r.all.med, r.met.dec ?? 0) : "—"}</td>
            <td>{r.dv === null ? "—" : r.fuera ? <b style={{ color: "var(--court)" }}>{sgn(r.dv, r.met.dec ?? 0)}</b> : <span className="sub">dentro del error</span>}</td><td><Rel d={d} k={r.k} /></td></tr>)}
        </tbody></table></div>
      <div className="card"><h3>Cuenta conmigo: el juego entero</h3>
        <p className="sub">{mismo.length ? `Sus otros golpes del mismo juego (${s.set}.º set), cada uno con su apoyo:` : "Ningún otro golpe suyo en este juego."}</p>
        <div className="chips" style={{ marginTop: 6 }}>{mismo.slice(0, 12).map((x) => <button className="chip" type="button" key={x.id} onClick={() => abrir(<FichaGolpe s={x} />)}>{x.score || "—"}{x.stance ? " · " + x.stance : ""}</button>)}</div></div>
    </Panel>
  );
}
