// P0.5b-c (15-11): the viewer of an analysis: the situation chips (they filter the lesson, the gallery and «Más»), its
// three tabs (Lección, Sus golpes, Más). A cell of «Más › Situaciones» opens the gallery of that situation and stance.
import { useState } from "react";
import { Cabecera, useApp } from "../App";
import { GOLPE_ES } from "../datos";
import { Galeria } from "./Golpe";
import { Leccion } from "./Leccion";
import { Mas } from "./Mas";

export function Visor() {
  const { d, ir } = useApp();
  const [tab, setTab] = useState("leccion");
  const [sit, setSit] = useState("todas");
  const [apoyo, setApoyo] = useState<string | null>(null);
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
                <button className="tab" type="button" key={k} data-tab={k} aria-current={k === tab ? "page" : undefined} onClick={() => { setTab(k); setApoyo(null); }}>{t}</button>
              ))}
            </div>
          </>
        } />
      <section className="content">
        {tab === "leccion" ? <Leccion d={d} sit={sit} />
          : tab === "golpes" ? <Galeria d={d} sit={sit} soloApoyo={apoyo} quitar={() => setApoyo(null)} />
          : <Mas d={d} sit={sit} onCelda={(si, ap) => { setSit(si); setApoyo(ap); setTab("golpes"); }} />}
      </section>
    </>
  );
}
