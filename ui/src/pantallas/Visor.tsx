// P0.5b (15-11): the viewer of an analysis: the situation chips (they filter the lesson and the gallery), its three tabs
// (Lección, Sus golpes, Más). The lesson is Leccion.tsx; the stroke's full analysis and «Más» come next (P0.5b-c).
import { useState } from "react";
import { Cabecera, useApp } from "../App";
import { GOLPE_ES } from "../datos";
import { Galeria } from "./Golpe";
import { Leccion } from "./Leccion";

const MAS: [string, string][] = [["comparar", "Comparar"], ["conclusiones", "Conclusiones"], ["situaciones", "Situaciones"], ["pista", "Pista"],
  ["tabla", "Tabla"], ["lateral", "Vista lateral (entreno)"], ["fiabilidad", "Fiabilidad"], ["datos", "Datos"], ["exportar", "Exportar"]];

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
  const [sit, setSit] = useState("todas");
  const golpe = GOLPE_ES[d.stroke] || d.stroke;
  const s = d.situations.find((x) => x.id === sit) || d.situations[0];
  return (
    <>
      <Cabecera titulo={`${golpe} de ${d.player.name}`}
        sub={`${s ? s.n : d.n_near} golpes cercanos${sit !== "todas" && s ? ` · ${s.label.toLowerCase()}` : ""} · ${d.matches.filter((m) => m.analysed).length} partidos`}
        acciones={<button className="btn" type="button" onClick={() => ir("analisis")}>‹ Análisis</button>}
        extra={
          <>
            <div className="chips">
              {d.situations.map((x) => (
                <button className="chip" type="button" key={x.id} data-sit={x.id} aria-pressed={x.id === sit} onClick={() => setSit(x.id)}>
                  {x.label}<span className="c num">{x.n}</span>
                </button>
              ))}
            </div>
            <div className="tabs">
              {[["leccion", "Lección"], ["golpes", "Sus golpes"], ["mas", "Más"]].map(([k, t]) => (
                <button className="tab" type="button" key={k} data-tab={k} aria-current={k === tab ? "page" : undefined} onClick={() => setTab(k)}>{t}</button>
              ))}
            </div>
          </>
        } />
      <section className="content">
        {tab === "leccion" ? <Leccion d={d} sit={sit} /> : tab === "golpes" ? <Galeria d={d} sit={sit} /> : <Mas />}
      </section>
    </>
  );
}
