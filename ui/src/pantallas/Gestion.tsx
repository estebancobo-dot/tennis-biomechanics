// P0.5a (15-11): the management screens (Inicio, Análisis, Partidos, Personas, Cola, Calidad, Almacenamiento, Ajustes)
// and the side panels for a match and for adding matches, from the validated mockup (design/p0/aplicacion.html, #305).
// P0.5d: the actions go to the PC's window (ui/src/api.ts → tennisbio.app.p0_api) and from there to the cloud's queue;
// in a browser they stay disabled and say where they work. What only the PC measures (disk use) waits for P0.5e.
import { useState } from "react";
import { Cabecera, Panel, useApp } from "../App";
import { SOLO_PC, api } from "../api";
import type { FichaAlta, FotoClic, Respuesta } from "../api";
import type { Datos, Partido, Trabajo } from "../contrato";
import { GOLPE_ES, fmt, iniciales } from "../datos";

const etiqueta = (m: Partido) => [m.torneo, m.ronda].filter(Boolean).join(" · ") || "Torneo sin leer del nombre";
const ACCION: Record<string, string> = {
  partido: "Análisis del partido", prueba: "Prueba de 10 min", informe: "Informe", comparar: "Comparación",
  medir: "Prueba de concepto", leer: "Lectura de diagnóstico", investigar: "Vídeos de entrenadores",
};

function nombreTrabajo(d: Datos, j: Trabajo) {
  const m = d.matches.find((x) => x.id === j.partido);
  const quien = m ? `${etiqueta(m)} (${m.personas.join(" – ")})` : "";
  return `${ACCION[j.accion] || j.accion}${quien ? " · " + quien : ""}`;
}

function Fila({ t, s, pill, cls = "est" }: { t: string; s?: string; pill?: string; cls?: string }) {
  return (
    <div className="row">
      <div>
        <div className="t">{t}</div>
        {s ? <div className="s">{s}</div> : null}
      </div>
      {pill ? <span className={`pill ${cls}`}>{pill}</span> : <span />}
    </div>
  );
}

function TarjetaAnalisis() {
  const { d, ir } = useApp();
  const golpe = GOLPE_ES[d.stroke] || d.stroke;
  return (
    <button className="card clickable" type="button" data-open onClick={() => ir("visor")} style={{ textAlign: "left", display: "grid", gap: 8 }}>
      <div className="avatars">
        <div className="avatar">{iniciales(d.player.name)}</div>
        <div>
          <h3>{golpe} de {d.player.name}</h3>
          <span className="sub">{d.n_near} golpes cercanos · {d.n_far} lejanos · {d.matches.filter((m) => m.analysed).length} partidos</span>
        </div>
      </div>
      <div className="chips">
        {d.known.length ? <span className="pill warn">{d.known.length} diferencias conocidas</span> : null}
        <span className="pill good">auditoría {fmt(100 * d.quality.total.score)} %</span>
      </div>
    </button>
  );
}

// P0.5e (21-11, #301): the analysis lives in the cloud; the PC brings its results (only what changed) and shows them
function Resultados() {
  const { d } = useApp();
  const pc = api();
  const [resp, setResp] = useState<Respuesta | null>(null);
  const [trayendo, setTrayendo] = useState(false);
  const traer = async () => {
    if (!pc) return;
    setTrayendo(true);
    try {
      const r = await pc.traer_resultados();
      if (r.recargar) { window.location.reload(); return; }
      setResp(r.ok ? { ok: true, motivo: r.bajados ? `${r.bajados} ficheros nuevos` : "ya tenías los últimos resultados" } : r);
    } catch (e) { setResp({ ok: false, motivo: String(e) }); }
    setTrayendo(false);
  };
  return (
    <div className="card" data-resultados><span className="eyebrow">Resultados</span>
      <p className="sub" style={{ marginTop: 4 }}>Datos de {d.origen || (d.ejemplo ? "ejemplo" : "este PC")}.</p>
      <button className="btn" type="button" data-pc="traer" style={{ marginTop: 8 }} disabled={!pc || trayendo}
        title={pc ? undefined : SOLO_PC} onClick={traer}>{trayendo ? "Trayendo…" : "Traer resultados de la nube"}</button>
      {resp ? <p className={`pill ${resp.ok ? "good" : "crit"}`} role="status" style={{ marginTop: 8 }}>{resp.motivo}</p> : null}
    </div>
  );
}

export function Inicio() {
  const { d, abrir } = useApp();
  const q = d.queue, k = q.kaggle;
  const enMarcha = q.jobs.filter((j) => j.estado === "en_marcha");
  const tuyo = q.jobs.filter((j) => j.estado !== "hecho" && /aprobación|clic/i.test(j.nota));
  return (
    <>
      <Cabecera titulo="Inicio" sub="Lo que pasa ahora, lo que necesita algo de ti y lo último terminado."
        acciones={<button className="btn primary" type="button" data-add onClick={() => abrir(<Anadir />)}>Añadir partidos</button>} />
      <section className="content">
        <div className="grid3">
          <div className="card"><span className="eyebrow">Ahora en la nube</span>
            {enMarcha.length ? enMarcha.map((j) => <Fila key={j.id} t={nombreTrabajo(d, j)} s={`${j.id}${j.nota ? " · " + j.nota : ""}`} pill={j.donde} />)
              : <p className="sub">Nada en marcha.</p>}
          </div>
          <div className="card"><span className="eyebrow">Necesita algo de ti</span>
            {Object.entries(q.app?.esperas || {}).map(([m, why]) => {          // P0.5d: the queue's answer, match by match
              const pm = d.matches.find((x) => x.id === m);
              return <Fila key={m} t={pm ? `${etiqueta(pm)} (${pm.personas.join(" – ")})` : m} s={why} pill="espera" cls="warn" />;
            })}
            {tuyo.length ? tuyo.map((j) => <Fila key={j.id} t={nombreTrabajo(d, j)} s={j.nota} pill="espera" cls="warn" />)
              : Object.keys(q.app?.esperas || {}).length ? null
              : <Fila t="Nada" s="Ningún clic de identidad ni aprobación esperan." pill="al día" cls="good" />}
          </div>
          <div className="card"><span className="eyebrow">Cuota</span>
            {k ? (
              <>
                <div className="stat"><b className="num">{fmt(k.total - k.used, 1)} h</b><span>de GPU en Kaggle esta semana ({fmt(k.used, 1)} de {fmt(k.total, 0)} usadas)</span></div>
                <div className={`bar ${k.used / k.total > 0.8 ? "warn" : ""}`} style={{ marginTop: 8 }}><i style={{ width: `${(100 * k.used) / k.total}%` }} /></div>
              </>
            ) : <p className="sub">Sin dato de Kaggle.</p>}
            {q.modal ? <p className="sub" style={{ marginTop: 10 }}>Modal: quedan {fmt(q.modal.left, 2)} $ de {fmt(q.modal.total, 0)} $ este mes.</p> : null}
          </div>
        </div>
        <Resultados />
        <div>
          <h2>Tus análisis</h2>
          <div className="grid3" style={{ marginTop: 10 }}><TarjetaAnalisis /></div>
        </div>
        <div className="card"><span className="eyebrow">Lo último terminado</span>
          {q.jobs.filter((j) => j.estado === "hecho").slice(-6).reverse().map((j) => (
            <Fila key={j.id} t={nombreTrabajo(d, j)} s={`${j.id}${j.nota ? " · " + j.nota : ""}`} pill="hecho" cls="good" />
          ))}
        </div>
      </section>
    </>
  );
}

export function Analisis() {
  const { d } = useApp();
  const golpe = GOLPE_ES[d.stroke] || d.stroke;
  const otros: [string, string][] = [];
  for (const p of d.players) for (const g of ["Derecha", "Revés", "Saque"]) if (!(p.name === d.player.name && g === golpe)) otros.push([p.name, g]);
  return (
    <>
      <Cabecera titulo="Análisis" sub="Uno por persona y golpe, con todos sus partidos." />
      <section className="content">
        <div className="grid3"><TarjetaAnalisis /></div>
        <div className="card"><h2>Se puede analizar</h2>
          <p className="sub">Otro golpe de una persona ya analizada sale en minutos: la pasada barata ya registró todos sus impactos. Otra persona de un partido subido, unas horas.</p>
          <div className="list" style={{ marginTop: 8 }}>
            {otros.map(([n, g]) => (
              <div className="row" key={n + g}>
                <div className="avatars"><div className="avatar">{iniciales(n)}</div><div className="t">{g} de {n}</div></div>
                <button className="btn" type="button" data-also>Analizar</button>
              </div>
            ))}
          </div>
          <p className="mock" style={{ marginTop: 10 }}>Volea, remate y cortado aparecen cuando tengan casos suficientes, con su número; no se esconden.</p>
        </div>
      </section>
    </>
  );
}

function FichaPartido({ m }: { m: Partido }) {
  const { d, ir } = useApp();
  return (
    <Panel titulo={etiqueta(m)} sub={m.id}>
      <div className="grid2">
        {m.personas.map((n) => (
          <div className="card avatars" key={n}>
            <div className="avatar">{iniciales(n)}</div>
            <div style={{ flex: 1 }}><b>{n}</b><div className="sub">{n === d.player.name ? `${m.near} golpes cerca · ${m.far} lejos` : "sin analizar"}</div></div>
            {n === d.player.name ? <button className="btn" type="button" data-open onClick={() => ir("visor")}>Ver</button> : <button className="btn" type="button" data-also>Analizar a…</button>}
          </div>
        ))}
      </div>
      <div className="card"><h2>Datos</h2>
        <table className="t"><tbody>
          <tr><td>Torneo</td><td>{m.torneo || "—"}</td><td className="sub">nombre del fichero</td></tr>
          <tr><td>Ronda</td><td>{m.ronda || "—"}</td><td className="sub">nombre del fichero</td></tr>
          <tr><td>Fecha</td><td>{m.fecha || "—"}</td><td className="sub">nombre del fichero</td></tr>
          <tr><td>Superficie</td><td>{m.surf && m.surf !== "—" ? m.surf : "—"}</td><td className="sub">catálogo</td></tr>
        </tbody></table>
      </div>
      <div className="card"><h2>Estado</h2>
        <p className="sub">{m.analysed ? "Analizado en la nube. Las etapas, una por una, y sus fallos por niveles (#265)." : "Sin analizar: primero una prueba de 10 min y después, con tu aprobación, el partido entero."}</p>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button className="btn" type="button">Reanalizar con la versión nueva</button>
          <button className="btn" type="button">Cambiar el clic de identidad</button>
          <button className="btn" type="button">Archivar</button>
        </div>
      </div>
    </Panel>
  );
}

const PASOS = ["Elegir vídeos", "Datos del partido", "Subida", "¿Quién es ella?", "Aprobar"];
const CAMPOS: [keyof FichaAlta, string][] = [["jugadora", "Jugadora"], ["rival", "Rival"], ["torneo", "Torneo"],
  ["ronda", "Ronda"], ["fecha", "Fecha"], ["superficie", "Superficie"]];
// P0.5d (docs/p0_plan.md §3 ter): only what was measured: the 10-minute test 0,45 h of GPU (v26, Gauff), a whole match
// 5-6,5 h (the final and Gauff); the pass up to the click is part of the match's hours (kept, never run twice) and its
// own share is not measured apart yet: no number is shown for it
const PRUEBA_H = 0.45, PARTIDO_H = "5-6,5";

// P0.5d: the PC's answer, said as it is (never «hecho» when the PC said no)
function Resultado({ r }: { r: Respuesta | null }) {
  if (!r) return null;
  return <p className={`pill ${r.ok ? "good" : "crit"}`} role="status" style={{ marginTop: 8 }}>
    {r.ok ? `Pedido a la cola (${r.cuando || "ahora"}): la nube lo hace en su vuelta siguiente (cada 30 min).` : r.motivo}</p>;
}

export function Anadir() {
  const { d } = useApp();
  const pc = api();
  const [k, setK] = useState(0);
  const [ruta, setRuta] = useState<string | null>(null);
  const [ficha, setFicha] = useState<FichaAlta>({ jugadora: d.player.name, rival: "" });
  const [preparar, setPreparar] = useState(false);
  const [partido, setPartido] = useState<string | null>(null);
  const [resp, setResp] = useState<Respuesta | null>(null);
  const [fotos, setFotos] = useState<FotoClic[] | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const ej = d.matches.find((m) => !m.analysed) || d.matches[0];
  const kg = d.queue.kaggle;
  const espera = partido ? d.queue.app?.esperas?.[partido] : undefined;
  const hacer = async (f: () => Promise<Respuesta>) => {
    setOcupado(true);
    try { setResp(await f()); } catch (e) { setResp({ ok: false, motivo: String(e) }); } finally { setOcupado(false); }
  };
  const elegir = async () => {
    if (!pc) return;
    const r = await pc.elegir_video();
    if (r) { setRuta(r); setFicha({ ...ficha, ...(await pc.proponer(r)) }); setK(1); }
  };
  const soloPC = pc ? undefined : SOLO_PC;
  const vistas = [
    <div className="card" key="0"><h2>Elige el vídeo del partido en el PC</h2>
      <p className="sub">Un vídeo es un partido; se reconoce por su contenido (renombrarlo no rompe nada).</p>
      <button className="btn primary" type="button" data-pc="elegir" disabled={!pc} title={soloPC} onClick={elegir} style={{ marginTop: 12 }}>Elegir vídeo…</button>
      {ruta ? <p className="sub" style={{ marginTop: 8 }}>{ruta}</p> : null}
      {!pc ? <p className="mock" style={{ marginTop: 8 }}>{SOLO_PC}.</p> : null}</div>,
    <div className="card" key="1"><h2>Datos del partido</h2>
      <p className="sub">Propuestos del nombre del fichero; corrige solo si algo está mal.</p>
      {pc ? <div className="grid2" style={{ marginTop: 8 }}>
        {CAMPOS.map(([c, t]) => (
          <label key={c} className="sub" style={{ display: "grid", gap: 4 }}>{t}
            <input value={ficha[c] || ""} onChange={(e) => setFicha({ ...ficha, [c]: e.target.value })}
              style={{ padding: "6px 10px", border: "1px solid var(--line)", borderRadius: 8 }} /></label>
        ))}</div>
        : ej ? <table className="t" style={{ marginTop: 8 }}><tbody>
          <tr><th>Dato</th><th>Propuesto</th><th>De dónde sale</th></tr>
          <tr><td>Fichero</td><td>{ej.id}</td><td>—</td></tr>
          <tr><td>Torneo</td><td>{ej.torneo || "—"}</td><td>nombre del fichero</td></tr>
          <tr><td>Ronda</td><td>{ej.ronda || "—"}</td><td>nombre del fichero</td></tr>
          <tr><td>Fecha</td><td>{ej.fecha || "—"}</td><td>nombre del fichero</td></tr>
          <tr><td>Personas</td><td>{ej.personas.join(" – ")}</td><td>nombre del fichero y marcador</td></tr>
        </tbody></table> : null}</div>,
    <div className="card" key="2"><h2>Subir y preparar</h2>
      <p className="sub">El vídeo va al volumen de Modal (se borra de allí cuando sus resultados estén en el PC) y se prepara: una prueba de 10 min y la pasada hasta las fotos de «¿Cuál es ella?». El análisis entero espera a tu aprobación.</p>
      <div className="grid2" style={{ marginTop: 10 }}>
        <div className="stat"><b className="num">{fmt(PRUEBA_H, 2)} h</b><span>de GPU la prueba de 10 min (medido); la pasada hasta el clic es parte de las {PARTIDO_H} h del partido</span></div>
        <div className="stat"><b className="num">{kg ? fmt(kg.total - kg.used, 1) + " h" : "—"}</b><span>quedan esta semana · 0 €</span></div>
      </div>
      <label className="sub" style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <input type="checkbox" checked={preparar} disabled={!pc} onChange={(e) => setPreparar(e.target.checked)} /> Sí, prepáralo (lo de arriba)</label>
      <button className="btn primary" type="button" data-pc="alta" disabled={!pc || !ruta || !preparar || ocupado} title={soloPC} style={{ marginTop: 10 }}
        onClick={() => pc && ruta && hacer(async () => { const r = await pc.alta(ruta, ficha, preparar); if (r.ok && r.partido) setPartido(r.partido); return r; })}>
        {ocupado ? "Subiendo…" : "Subir y preparar"}</button>
      <Resultado r={resp} /></div>,
    <div className="card" key="3"><h2>¿Cuál es ella?</h2>
      <p className="sub">Un clic en su foto, una vez por partido. Las fotos salen del propio vídeo cuando la nube termina la preparación.</p>
      {espera ? <p className="pill warn" style={{ marginTop: 8 }}>{espera}</p> : null}
      <button className="btn" type="button" data-pc="fotos" disabled={!pc || !partido} title={soloPC} style={{ marginTop: 8 }}
        onClick={async () => { if (pc && partido) setFotos(await pc.fotos(partido)); }}>Mirar si están las fotos</button>
      <div className="grid2" style={{ marginTop: 10 }}>
        {fotos && fotos.length ? fotos.map((f, i) => (
          <button className="card clickable" type="button" key={f.src} data-pc="clic" style={{ display: "grid", gap: 8, justifyItems: "center" }}
            onClick={() => pc && partido && hacer(() => pc.clic(partido, f.t, true, f.by))}>
            <img src={f.src} alt={`Persona ${i + 1}`} style={{ width: "100%", borderRadius: 8 }} /><b>Es ella</b>
          </button>
        )) : (fotos ? <p className="sub">Aún no están: la cola avisa cuando la preparación termine.</p> : (ej?.personas || []).map((n) => (
          <div className="card" key={n} style={{ display: "grid", gap: 8, justifyItems: "center" }}>
            <div className="frame" style={{ width: "100%", aspectRatio: "3/4" }}><span className="tag">Fotograma del vídeo</span></div><b>{n}</b>
          </div>)))}
      </div>
      <Resultado r={resp} /></div>,
    <div className="card" key="4"><h2>Aprobar el análisis</h2>
      <p className="sub">Con tu visto bueno, el partido entero (lo ya preparado no se repite).</p>
      <div className="grid2" style={{ marginTop: 10 }}>
        <div className="stat"><b>{PARTIDO_H} h</b><span>de GPU de Kaggle por partido (medido)</span></div>
        <div className="stat"><b className="num">{kg ? fmt(kg.total - kg.used, 1) + " h" : "—"}</b><span>quedan esta semana · 0 €</span></div>
      </div>
      <button className="btn primary" type="button" data-pc="aprobar" disabled={!pc || !partido || ocupado} title={soloPC} style={{ marginTop: 12 }}
        onClick={() => pc && partido && hacer(() => pc.aprobar(partido, { horas_gpu: PARTIDO_H, coste_eur: 0 }))}>Aprobar</button>
      <Resultado r={resp} /></div>,
  ];
  return (
    <Panel titulo="Añadir partidos">
      <div className="stepper">{PASOS.map((s, i) => <span className="chip" key={s} aria-current={i === k ? "step" : undefined}>{i + 1}. {s}</span>)}</div>
      {vistas[k]}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn" type="button" data-step="-1" disabled={k === 0} onClick={() => { setResp(null); setK(Math.max(0, k - 1)); }}>Atrás</button>
        <button className="btn primary" type="button" data-step="1" disabled={k === PASOS.length - 1} onClick={() => { setResp(null); setK(Math.min(PASOS.length - 1, k + 1)); }}>Siguiente</button>
      </div>
    </Panel>
  );
}

export function Partidos() {
  const { d, abrir } = useApp();
  return (
    <>
      <Cabecera titulo="Partidos" sub={`${d.matches.length} partidos en el catálogo · ${d.matches.filter((m) => m.analysed).length} analizados`}
        acciones={<button className="btn primary" type="button" data-add onClick={() => abrir(<Anadir />)}>Añadir partidos</button>} />
      <section className="content">
        <div className="card scroll">
          <table className="t">
            <thead><tr><th>Partido</th><th>Personas</th><th>Fecha</th><th>Superficie</th><th>Golpes de ella</th><th>Estado</th></tr></thead>
            <tbody>
              {d.matches.map((m, i) => (
                <tr className="clickable" key={m.id} data-match={i} onClick={() => abrir(<FichaPartido m={m} />)}>
                  <td><b>{etiqueta(m)}</b><div className="sub">{m.id}</div></td>
                  <td><div className="avatars">{m.personas.map((n) => <div className="avatar" title={n} key={n}>{iniciales(n)}</div>)}<span className="sub">{m.personas.join(" – ")}</span></div></td>
                  <td className="num">{m.fecha || "—"}</td>
                  <td>{m.surf && m.surf !== "—" ? m.surf : "—"}</td>
                  <td className="num">{m.analysed ? `${m.near} cerca · ${m.far} lejos` : "—"}</td>
                  <td>{m.analysed ? <span className="pill good">analizado</span> : <span className="pill warn" title={d.queue.app?.esperas?.[m.id]}>{d.queue.app?.esperas?.[m.id] || "en espera"}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mock" style={{ marginTop: 10 }}>Torneo, ronda y fecha salen del nombre del fichero hasta tener la ficha pública (#258).</p>
        </div>
      </section>
    </>
  );
}

export function Personas() {
  const { d } = useApp();
  const golpe = GOLPE_ES[d.stroke] || d.stroke;
  const conFicha = new Set(d.players.map((p) => p.name));
  const sinFicha = [...new Set(d.matches.flatMap((m) => m.personas))].filter((n) => n && !conFicha.has(n));
  return (
    <>
      <Cabecera titulo="Personas" sub="Fichas creadas desde el partido; hombres y mujeres igual." />
      <section className="content">
        <div className="grid3">
          {d.players.map((p) => (
            <div className="card" key={p.id}>
              <div className="avatars"><div className="avatar">{iniciales(p.name)}</div>
                <div><h3>{p.name}</h3><span className="sub">{p.hand === "left" ? "zurdo/a" : "diestro/a"} · revés a {p.backhand === "one_handed" ? "una mano" : "dos manos"} · {fmt(p.height_m, 2)} m</span></div></div>
              <p className="sub" style={{ marginTop: 8 }}>{p.name === d.player.name ? `Analizado: ${golpe.toLowerCase()} (${d.n_near} golpes cercanos).` : "Sin análisis todavía."}</p>
            </div>
          ))}
        </div>
        <div className="card"><h2>En los partidos, sin ficha todavía</h2>
          <p className="sub">Se crean solas al analizarlas (nombre del marcador y ficha pública); la altura, si falta, se marca como supuesta.</p>
          <div className="list" style={{ marginTop: 6 }}>
            {sinFicha.map((n) => (
              <div className="row" key={n}><div className="avatars"><div className="avatar">{iniciales(n)}</div><div className="t">{n}</div></div>
                <button className="btn" type="button" data-also>Analizar a {n.split(" ")[0]}</button></div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

export function ColaPantalla() {
  const { d } = useApp();
  const pc = api();
  const [resp, setResp] = useState<Respuesta | null>(null);
  const q = d.queue, de = (st: string) => q.jobs.filter((j) => j.estado === st);
  const pausa = q.app?.pausa?.en_pausa ? q.app.pausa : null;
  const pide = async (f: () => Promise<Respuesta>) => { try { setResp(await f()); } catch (e) { setResp({ ok: false, motivo: String(e) }); } };
  const cancelar = (x: Trabajo) => pc && window.confirm(`¿Cancelar «${nombreTrabajo(d, x)}»? Lo hecho se guarda.`) && pide(() => pc.cancelar(x.id));
  const seccion = (t: string, st: string, cls: string) => {
    const js = de(st);
    return js.length ? (
      <div className="card" key={st}><h2>{t} <span className="sub">({js.length})</span></h2>
        <div className="list" style={{ marginTop: 6 }}>{js.map((x) => (
          <div key={x.id} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
            <Fila t={`${nombreTrabajo(d, x)} · ${x.id}`} s={x.nota || x.partido} pill={x.donde || st} cls={cls} />
            {st === "en_marcha" || st === "pendiente" ? <button className="btn" type="button" data-pc="cancelar" disabled={!pc}
              title={pc ? undefined : SOLO_PC} onClick={() => cancelar(x)}>Cancelar</button> : <span />}
          </div>))}</div></div>
    ) : null;
  };
  const boton = pausa
    ? <button className="btn primary" type="button" data-pc="reanudar" disabled={!pc} title={pc ? undefined : SOLO_PC} onClick={() => pc && pide(() => pc.reanudar())}>Reanudar</button>
    : <button className="btn" type="button" data-pc="pausar" disabled={!pc} title={pc ? undefined : SOLO_PC} onClick={() => pc && pide(() => pc.pausar())}>Pausar</button>;
  return (
    <>
      <Cabecera titulo="Cola de la nube" sub={q.head} acciones={boton} />
      <section className="content">
        {pausa ? <div className="card"><span className="pill warn">En pausa desde la aplicación ({pausa.cuando})</span>
          <p className="sub" style={{ marginTop: 6 }}>No se lanza nada nuevo; lo que está en marcha termina.</p></div> : null}
        <Resultado r={resp} />
        {q.app?.errores?.length ? <div className="card"><h2>Lo que la cola no pudo hacer</h2>
          <div className="list" style={{ marginTop: 6 }}>{q.app.errores.map(([n, why]) => <Fila key={n} t={why} s={n} pill="rechazada" cls="crit" />)}</div></div> : null}
        {seccion("En marcha", "en_marcha", "est")}{seccion("Pendientes", "pendiente", "warn")}{seccion("Para mirar", "revisar", "warn")}{seccion("Con error", "error", "crit")}
        <details className="fold"><summary>Hechos ({de("hecho").length})</summary>
          <div className="list">{de("hecho").map((x) => <Fila key={x.id} t={x.id} s={x.nota || x.partido} pill={x.donde} cls="good" />)}</div></details>
      </section>
    </>
  );
}

export function Calidad() {
  const { d } = useApp();
  const Q = d.quality, t = Q.total;
  const doms = Object.entries(Q.domains).sort((a, b) => (a[1].score ?? 0) - (b[1].score ?? 0));
  return (
    <>
      <Cabecera titulo="Calidad" sub={`Modelo de calidad (#256) sobre la auditoría: ${t.ok} de ${t.n} comprobaciones cumplidas.`} />
      <section className="content">
        <div className="grid4">
          <div className="card stat"><b className="num">{fmt(100 * t.score)} %</b><span>comprobaciones cumplidas</span></div>
          <div className="card stat"><b className="num">{t.accepted} / {t.cells}</b><span>casillas aceptadas (≥ {fmt(100 * Q.threshold)} %)</span></div>
          <div className="card stat"><b className="num">{t.unmeasured}</b><span>casillas sin medir</span></div>
          <div className="card stat"><b className="num">{Q.counts.falta || 0}</b><span>que fallan (de {Object.values(Q.counts).reduce((a, b) => a + b, 0)})</span></div>
        </div>
        <div className="grid2">
          <div className="card"><h2>Por dominio</h2>
            {doms.map(([n, v]) => (
              <div className="hbar" style={{ marginTop: 8 }} key={n}><span>{n}</span>
                <div className="track"><i style={{ left: 0, width: `${100 * (v.score ?? 0)}%` }} /></div>
                <span className="num">{v.score == null ? "sin medir" : fmt(100 * v.score) + " %"}</span></div>
            ))}
          </div>
          <div className="card"><h2>Lo que falta medir y cómo se medirá</h2>
            {Q.cells.filter((c) => c.unmeasured).map((c) => <Fila key={c.d + c.c + c.l} t={`${c.d} · ${c.c}`} s={c.how || "métrica sin escribir todavía"} pill={c.l} cls="mute" />)}
          </div>
        </div>
        <div className="card"><h2>Lo que falla</h2>
          <div className="list">{Q.fails.map((f) => <Fila key={f.name} t={f.name} s={f.detail} pill={f.area} cls="crit" />)}</div></div>
      </section>
    </>
  );
}

export function Almacen() {
  const { d } = useApp();
  const pc = api();
  const [resp, setResp] = useState<Respuesta | null>(null);
  const borrados = new Set(d.queue.app?.borrados || []);
  const borrar = async (m: Partido) => {
    if (!pc || !window.confirm(`¿Borrar de la nube el vídeo de ${etiqueta(m)}? Solo se borra si sus resultados ya están en el PC; el vídeo del PC se queda.`)) return;
    try { setResp(await pc.borrar_video(m.id)); } catch (e) { setResp({ ok: false, motivo: String(e) }); }
  };
  return (
    <>
      <Cabecera titulo="Almacenamiento" sub="Espacio en el PC y en la nube." />
      <section className="content">
        <div className="grid3">
          {[["Imprescindible", "fichas, clics de identidad, resultados por golpe", "good"], ["Regenerable", "recortes de vídeo y cachés: se rehacen solos", "warn"], ["Temporal", "lo que se borra al terminar un trabajo", "mute"]].map(([t, s, c]) => (
            <div className="card" key={t}><span className={`pill ${c}`}>{t}</span><p className="sub" style={{ marginTop: 8 }}>{s}</p>
              <p className="mock" style={{ marginTop: 8 }}>Lo mide la aplicación en el PC (P0.5e).</p></div>
          ))}
        </div>
        <div className="card"><h2>Vídeos en la nube</h2><p className="sub">Un vídeo se borra del volumen de Modal cuando su partido está analizado y sus resultados están en el PC (la cola lo comprueba; si no, lo dice y no borra nada).</p>
          <div className="list" style={{ marginTop: 6 }}>{d.matches.map((m) => (
            <div key={m.id} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
              <Fila t={etiqueta(m)} s={m.personas.join(" – ")} pill={borrados.has(m.id) ? "borrado de la nube" : m.analysed ? "analizado" : "en análisis"} cls={borrados.has(m.id) ? "mute" : m.analysed ? "good" : "warn"} />
              <button className="btn" type="button" data-pc="borrar_video" disabled={!pc || !m.analysed || borrados.has(m.id)} title={pc ? undefined : SOLO_PC} onClick={() => borrar(m)}>Borrar de la nube</button>
            </div>))}</div>
          <Resultado r={resp} /></div>
      </section>
    </>
  );
}

export function Ajustes() {
  const [altura, setAltura] = useState(() => {
    try { return Number(localStorage.getItem("tb-h") || 1.78); } catch { return 1.78; }
  });
  return (
    <>
      <Cabecera titulo="Ajustes" sub="Casi todo es automático; aquí solo lo que es tuyo." />
      <section className="content">
        <div className="grid2">
          <div className="card"><h2>Tu altura</h2><p className="sub">Para traducir sus medidas a tus centímetros en la lección.</p>
            <input id="mi-altura" type="number" step="0.01" min="1.2" max="2.2" value={altura}
              onChange={(e) => { setAltura(+e.target.value); try { localStorage.setItem("tb-h", e.target.value); } catch { /* sin almacenamiento: solo esta vez */ } }}
              style={{ marginTop: 8, padding: "6px 10px", border: "1px solid var(--line)", borderRadius: 8, width: 120 }} /> m</div>
          <div className="card"><h2>Avisos de Windows</h2><p className="sub">Al terminar un análisis, al fallar algo o con poco disco.</p></div>
          <div className="card"><h2>Carpetas</h2><p className="sub">Vídeos y resultados en el PC (config/local.yaml).</p></div>
          <div className="card"><h2>Claves</h2><p className="sub">Modal y GitHub, guardadas en el PC. Aquí solo se ve si están puestas, nunca su valor.</p></div>
        </div>
      </section>
    </>
  );
}
