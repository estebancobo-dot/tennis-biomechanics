// P0.5a (15-11): the application's shell. A left column (Ver, Gestionar, Sistema) and the screen on the right; a side
// panel (drawer) for a match, adding matches or one stroke. Screens are named in the address (#inicio, #partidos, …),
// with the mockup's names and data-* hooks, so its walk and its validation (design/p0) run on the real application.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Datos } from "./contrato";
import { ICONOS } from "./iconos";
import { Ajustes, Almacen, Analisis, Calidad, ColaPantalla, Inicio, Partidos, Personas } from "./pantallas/Gestion";
import { Visor } from "./pantallas/Visor";

const GRUPOS: [string, [string, string][]][] = [
  ["Ver", [["inicio", "Inicio"], ["analisis", "Análisis"]]],
  ["Gestionar", [["partidos", "Partidos"], ["personas", "Personas"]]],
  ["Sistema", [["cola", "Cola de la nube"], ["calidad", "Calidad"], ["almacen", "Almacenamiento"], ["ajustes", "Ajustes"]]],
];

interface Ctx {
  d: Datos;
  ir: (pantalla: string) => void;
  abrir: (contenido: ReactNode) => void;
  cerrar: () => void;
}
const Contexto = createContext<Ctx | null>(null);
export const useApp = () => {
  const c = useContext(Contexto);
  if (!c) throw new Error("fuera de la aplicación");
  return c;
};

export function Cabecera({ titulo, sub, acciones, extra }: { titulo: ReactNode; sub?: ReactNode; acciones?: ReactNode; extra?: ReactNode }) {
  return (
    <header className="top">
      <div className="top-row">
        <div className="grow">
          <h1>{titulo}</h1>
          {sub ? <p className="sub">{sub}</p> : null}
        </div>
        {acciones}
      </div>
      {extra}
    </header>
  );
}

export function Panel({ titulo, sub, children }: { titulo: ReactNode; sub?: ReactNode; children: ReactNode }) {
  const { cerrar } = useApp();
  return (
    <>
      <div className="drawer-h">
        <div>
          <h2>{titulo}</h2>
          {sub ? <p className="sub">{sub}</p> : null}
        </div>
        <button className="btn" type="button" data-close onClick={cerrar}>Cerrar</button>
      </div>
      {children}
    </>
  );
}

const PANTALLAS: Record<string, () => JSX.Element> = {
  inicio: Inicio, analisis: Analisis, partidos: Partidos, personas: Personas, cola: ColaPantalla, calidad: Calidad,
  almacen: Almacen, ajustes: Ajustes, visor: Visor,
};

export default function App({ d }: { d: Datos }) {
  const leer = () => (location.hash.slice(1) in PANTALLAS ? location.hash.slice(1) : "inicio");
  const [pantalla, setPantalla] = useState(leer);
  const [panel, setPanel] = useState<ReactNode>(null);
  // P0.5e: the PC's window gives its API a moment after the page loads (pywebviewready): drawn again then, so the
  // management buttons of the screen already open come alive
  const [, setVentana] = useState(0);
  useEffect(() => {
    const lista = () => setVentana((n) => n + 1);
    window.addEventListener("pywebviewready", lista);
    return () => window.removeEventListener("pywebviewready", lista);
  }, []);
  const cerrar = useCallback(() => setPanel(null), []);
  const ir = useCallback((p: string) => {
    if (location.hash !== "#" + p) location.hash = p;
    else setPantalla(p);
  }, []);
  useEffect(() => {
    const cambio = () => {
      setPanel(null);
      setPantalla(leer());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", cambio);
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setPanel(null);
    window.addEventListener("keydown", tecla);
    return () => {
      window.removeEventListener("hashchange", cambio);
      window.removeEventListener("keydown", tecla);
    };
  }, []);
  const enMarcha = d.queue.jobs.filter((j) => j.estado === "en_marcha").length;
  const Pantalla = PANTALLAS[pantalla] || Inicio;
  const actual = pantalla === "visor" ? "analisis" : pantalla;
  return (
    <Contexto.Provider value={{ d, ir, abrir: setPanel, cerrar }}>
      <div className="shell">
        <nav className="side" aria-label="Secciones">
          <div className="brand">Tennis<span>Bio</span></div>
          {GRUPOS.map(([grupo, items]) => (
            <div className="group" key={grupo}>
              <span className="eyebrow">{grupo}</span>
              <div>
                {items.map(([k, t]) => (
                  <button className="nav" type="button" key={k} data-go={k} aria-current={k === actual ? "page" : undefined} onClick={() => ir(k)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: ICONOS[k] }} />
                    {t}
                    {k === "cola" ? <span className="count num">{enMarcha}</span> : null}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {d.ejemplo ? <p className="side-note">Datos de ejemplo: nada de esta pantalla es de una jugadora real.</p> : null}
        </nav>
        <main>
          <Pantalla />
        </main>
      </div>
      <div className="drawer" hidden={!panel} onClick={(e) => e.target === e.currentTarget && cerrar()}>
        <div role="dialog" aria-modal="true">{panel}</div>
      </div>
    </Contexto.Provider>
  );
}
