// P0.5a (15-11): the viewer of an analysis, first version: its three tabs (Lección, Sus golpes, Más), the lesson's phase
// strip with each phase's focus and its checks, the gallery of strokes and the sections of «Más». P0.5b brings the rest
// of the validated mockup (video with its layers, drawing per check, the stroke's full analysis) and P0.5c «Más».
import { useState } from "react";
import { Cabecera, Panel, useApp } from "../App";
import type { Datos, Golpe } from "../contrato";
import { GOLPE_ES, fmt } from "../datos";

const MAS: [string, string][] = [["comparar", "Comparar"], ["conclusiones", "Conclusiones"], ["situaciones", "Situaciones"], ["pista", "Pista"],
  ["tabla", "Tabla"], ["lateral", "Vista lateral (entreno)"], ["fiabilidad", "Fiabilidad"], ["datos", "Datos"], ["exportar", "Exportar"]];

const titulo = (s: Golpe) => `Frente a ${s.rival || "—"}${s.set ? ` · ${s.set}.º set ${s.score || ""}` : ""}`;

function Leccion({ d }: { d: Datos }) {
  const [ph, setPh] = useState(0);
  const f = d.phases[ph];
  return (
    <>
      <div className="strip" role="tablist">
        {d.phases.map((p, i) => (
          <button className="ph" type="button" key={p.id} data-ph={i} aria-current={i === ph ? "page" : undefined} onClick={() => setPh(i)}>
            <div className="nm">{i + 1} · {p.title}</div>
          </button>
        ))}
      </div>
      {f ? (
        <div className="card" style={{ display: "grid", gap: 10 }}>
          <span className="eyebrow">Foco</span>
          <h2>{f.focus || f.title}</h2>
          {f.when ? <p className="sub">{f.when}</p> : null}
          <div className="list">
            {f.checks.map((c) => (
              <div className="row" key={c.key}>
                <div>
                  <div className="t">{c.label}</div>
                  {c.cue ? <div className="s">{c.cue}</div> : null}
                  {c.mistake ? <div className="s">Si te pasa: {c.mistake}</div> : null}
                </div>
                <span className="pill mute">{c.unit || ""}</span>
              </div>
            ))}
          </div>
        </div>
      ) : <p className="sub">Sin fases en este análisis.</p>}
    </>
  );
}

function FichaGolpe({ s }: { s: Golpe }) {
  return (
    <Panel titulo={titulo(s)} sub={[...s.bits, s.stance && "apoyo " + s.stance, s.movement].filter(Boolean).join(" · ")}>
      <div className="card"><h3>Medidas de este golpe</h3>
        <table className="t"><tbody>
          {Object.entries(s.m).filter(([, v]) => v != null).map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{fmt(v, 1)}</td></tr>)}
        </tbody></table>
      </div>
    </Panel>
  );
}

function SusGolpes({ d }: { d: Datos }) {
  const { abrir } = useApp();
  const orden = [...d.strokes].sort((a, b) => (b.quality ?? 0) - (a.quality ?? 0)).slice(0, 24);
  return (
    <div className="vgrid">
      {orden.map((s) => (
        <button className="vcard" type="button" key={s.id} data-stroke={s.id} onClick={() => abrir(<FichaGolpe s={s} />)}>
          <div className="frame" style={{ aspectRatio: "16/10" }}><span className="tag">vídeo</span></div>
          <div className="sub">{titulo(s)}</div>
          <div className="sub">{s.bits.join(" · ")}</div>
        </button>
      ))}
    </div>
  );
}

function Mas() {
  const [sub, setSub] = useState("comparar");
  return (
    <>
      <div className="chips">
        {MAS.map(([k, t]) => <button className="chip" type="button" key={k} data-sub={k} aria-pressed={k === sub} onClick={() => setSub(k)}>{t}</button>)}
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>{MAS.find(([k]) => k === sub)?.[1]}</h3>
        <p className="mock" style={{ marginTop: 8 }}>En construcción (P0.5c).</p>
      </div>
    </>
  );
}

export function Visor() {
  const { d, ir } = useApp();
  const [tab, setTab] = useState("leccion");
  const golpe = GOLPE_ES[d.stroke] || d.stroke;
  return (
    <>
      <Cabecera titulo={`${golpe} de ${d.player.name}`} sub={`${d.n_near} golpes cercanos · ${d.matches.filter((m) => m.analysed).length} partidos`}
        acciones={<button className="btn" type="button" onClick={() => ir("analisis")}>‹ Análisis</button>}
        extra={
          <div className="tabs">
            {[["leccion", "Lección"], ["golpes", "Sus golpes"], ["mas", "Más"]].map(([k, t]) => (
              <button className="tab" type="button" key={k} data-tab={k} aria-current={k === tab ? "page" : undefined} onClick={() => setTab(k)}>{t}</button>
            ))}
          </div>
        } />
      <section className="content">
        {tab === "leccion" ? <Leccion d={d} /> : tab === "golpes" ? <SusGolpes d={d} /> : <Mas />}
      </section>
    </>
  );
}
