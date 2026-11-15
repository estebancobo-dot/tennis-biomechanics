// P0.5a (15-11): the management screens (Inicio, Análisis, Partidos, Personas, Cola, Calidad, Almacenamiento, Ajustes)
// and the side panels for a match and for adding matches, from the validated mockup (design/p0/aplicacion.html, #305).
// What the PC alone knows (disk use, the photos of the players, the upload) is marked until P0.5d and P0.5e.
import { useState } from "react";
import { Cabecera, Panel, useApp } from "../App";
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
            {tuyo.length ? tuyo.map((j) => <Fila key={j.id} t={nombreTrabajo(d, j)} s={j.nota} pill="espera" cls="warn" />)
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

export function Anadir() {
  const { d } = useApp();
  const [k, setK] = useState(0);
  const ej = d.matches.find((m) => !m.analysed) || d.matches[0];
  const kg = d.queue.kaggle;
  const vistas = [
    <div className="card" key="0"><h2>Elige uno o varios vídeos del PC</h2>
      <p className="sub">Arrastra los ficheros aquí o elígelos. Cada vídeo es un partido; se reconoce por su contenido (renombrarlo no rompe nada).</p>
      <div className="frame" style={{ aspectRatio: "auto", height: 140, marginTop: 12, display: "grid", placeItems: "center", color: "#eaf1f8" }}>Arrastra aquí los vídeos (.mp4, .mkv, .ts)</div></div>,
    <div className="card" key="1"><h2>Propuesta de datos</h2>
      <p className="sub">Del nombre del fichero, la ficha pública y el marcador. Corrige solo si algo está mal.</p>
      {ej ? <table className="t" style={{ marginTop: 8 }}><tbody>
        <tr><th>Dato</th><th>Propuesto</th><th>De dónde sale</th></tr>
        <tr><td>Fichero</td><td>{ej.id}</td><td>—</td></tr>
        <tr><td>Torneo</td><td>{ej.torneo || "—"}</td><td>nombre del fichero</td></tr>
        <tr><td>Ronda</td><td>{ej.ronda || "—"}</td><td>nombre del fichero</td></tr>
        <tr><td>Fecha</td><td>{ej.fecha || "—"}</td><td>nombre del fichero</td></tr>
        <tr><td>Personas</td><td>{ej.personas.join(" – ")}</td><td>nombre del fichero y marcador</td></tr>
      </tbody></table> : null}</div>,
    <div className="card" key="2"><h2>Subiendo a la nube</h2>
      <p className="sub">Por partes: si se corta, sigue donde iba. El vídeo se queda en el PC para verlo.</p>
      <div className="bar" style={{ marginTop: 12 }}><i style={{ width: "0%" }} /></div>
      <p className="mock" style={{ marginTop: 8 }}>La subida al volumen de Modal llega con P0.5e (hoy la hace scripts/subir_nube.py).</p></div>,
    <div className="card" key="3"><h2>¿Cuál es ella?</h2>
      <p className="sub">Un clic en su foto, una vez por partido. Las fotos salen del propio vídeo.</p>
      <div className="grid2" style={{ marginTop: 10 }}>
        {(ej?.personas || []).map((n) => (
          <button className="card clickable" type="button" key={n} style={{ display: "grid", gap: 8, justifyItems: "center" }}>
            <div className="frame" style={{ width: "100%", aspectRatio: "3/4" }}><span className="tag">Fotograma del vídeo</span></div><b>{n}</b>
          </button>
        ))}
      </div></div>,
    <div className="card" key="4"><h2>Aprobar el análisis</h2>
      <p className="sub">Primero una prueba corta de 10 min en la nube; después, con tu visto bueno, el partido entero.</p>
      <div className="grid2" style={{ marginTop: 10 }}>
        <div className="stat"><b>5-6,5 h</b><span>de GPU de Kaggle por partido (medido)</span></div>
        <div className="stat"><b className="num">{kg ? fmt(kg.total - kg.used, 1) + " h" : "—"}</b><span>quedan esta semana</span></div>
      </div>
      <button className="btn primary" type="button" style={{ marginTop: 12 }}>Aprobar</button></div>,
  ];
  return (
    <Panel titulo="Añadir partidos">
      <div className="stepper">{PASOS.map((s, i) => <span className="chip" key={s} aria-current={i === k ? "step" : undefined}>{i + 1}. {s}</span>)}</div>
      {vistas[k]}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn" type="button" data-step="-1" disabled={k === 0} onClick={() => setK(Math.max(0, k - 1))}>Atrás</button>
        <button className="btn primary" type="button" data-step="1" disabled={k === PASOS.length - 1} onClick={() => setK(Math.min(PASOS.length - 1, k + 1))}>Siguiente</button>
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
                  <td>{m.analysed ? <span className="pill good">analizado</span> : <span className="pill warn">en espera</span>}</td>
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
  const q = d.queue, de = (st: string) => q.jobs.filter((j) => j.estado === st);
  const seccion = (t: string, st: string, cls: string) => {
    const js = de(st);
    return js.length ? (
      <div className="card" key={st}><h2>{t} <span className="sub">({js.length})</span></h2>
        <div className="list" style={{ marginTop: 6 }}>{js.map((x) => <Fila key={x.id} t={`${nombreTrabajo(d, x)} · ${x.id}`} s={x.nota || x.partido} pill={x.donde || st} cls={cls} />)}</div></div>
    ) : null;
  };
  return (
    <>
      <Cabecera titulo="Cola de la nube" sub={q.head} acciones={<button className="btn" type="button">Pausar</button>} />
      <section className="content">
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
        <div className="card"><h2>Vídeos en la nube</h2><p className="sub">Cada vídeo se borra del volumen de Modal cuando su partido queda aceptado (T22). Hoy están los {d.matches.length} del catálogo.</p></div>
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
