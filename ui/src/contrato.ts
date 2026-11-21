// P0.5a (15-11): the data the application shows, as tennisbio.app.p0 gives them (from the analysis, the audit, the cloud
// queue and the catalogue). One contract for the PC's window and for the tests; nothing of a player is fixed here.

export interface Persona {
  id: string;
  name: string;
  hand?: "right" | "left" | null;
  backhand?: "one_handed" | "two_handed" | null;
  height_m?: number | null;
  ficha: boolean;
}

export interface Partido {
  id: string;
  rival?: string | null;
  personas: string[]; // the two players, from the catalogue (never guessed from the file name in the interface)
  analysed: boolean;
  surf?: string | null;
  torneo?: string;
  ronda?: string;
  fecha?: string;
  near: number;
  far: number;
}

export interface Trabajo {
  id: string;
  accion: string;
  partido: string;
  estado: "en_marcha" | "pendiente" | "hecho" | "error" | "revisar" | string;
  donde: string;
  nota: string;
}

// P0.5d: the queue's answer to what the user did in the application (cola/app.json, tennisbio.infra.peticiones)
export interface RespuestaApp {
  esperas: Record<string, string>;
  errores: [string, string][];
  pausa: { en_pausa: boolean; cuando: string } | null;
  borrados: string[];
  hora?: string;
}

export interface Cola {
  head: string;
  jobs: Trabajo[];
  kaggle: { used: number; total: number } | null;
  modal: { left: number; total: number } | null;
  app?: RespuestaApp | null;
}

export interface Casilla {
  d: string; c: string; l: string; score: number | null; n: number; ok: number; unmeasured: boolean;
  accepted: boolean; fail: string[]; how?: string | null;
}

export interface Calidad {
  total: { score: number; ok: number; n: number; accepted: number; cells: number; unmeasured: number };
  threshold: number;
  cells: Casilla[];
  counts: Record<string, number>;
  fails: { name: string; detail: string; area?: string }[];
  domains: Record<string, { score: number | null }>;
}

export interface Medida {
  name: string; sub?: string; unit?: string; dec?: number; noise?: number | null; rel?: number; est?: boolean;
}

export interface Estadistica { n: number; med?: number; p25?: number; p75?: number }

export interface Situacion { id: string; label: string; n: number; m: Record<string, Estadistica | null> }

export interface PuntoDeControl {
  key: string; label: string; unit?: string; dec?: number; read?: string; cue?: string; mistake?: string;
  drill?: string; m?: string | null;
}

export interface Fase { id: string; title: string; focus?: string; when?: string; checks: PuntoDeControl[] }

export interface Golpe {
  id: string; match: number; rival?: string; set?: number; score?: string; bits: string[];
  outcome?: string; detail?: string; stance?: string; movement?: string; finish?: string;
  quality?: number; repr?: number; height?: string; intent?: string; pressure?: boolean;
  fast?: boolean; wide?: boolean; short?: boolean;
  m: Record<string, number | null>;
  lv?: Record<string, number | boolean | string | null>;   // change 1: the lesson's checkpoints, stroke by stroke
  // P0.5e (21-11): the report's own video and frame series of the stroke (relative to the report page, Datos.medios)
  video?: string | null; series?: string | null; vImpact?: number | null; thumb?: string | null;
  [extra: string]: unknown;
}

export interface Datos {
  generated?: string;
  player: { id?: string; name: string; [k: string]: unknown };
  stroke: string;
  known: string[];
  conclusions: unknown[];
  findings: unknown[];
  metrics: Record<string, Medida>;
  situations: Situacion[];
  phases: Fase[];
  plan: unknown[];
  symptoms: unknown[];
  not_tv: [string, string][] | string[];
  glossary: unknown[];
  strokes: Golpe[];
  why?: Record<string, [string, string]>;   // each checkpoint: why it matters and its source (ITF, Elliott, Landlinger…)
  n_near: number;
  n_far: number;
  players: Persona[];
  matches: Partido[];
  queue: Cola;
  quality: Calidad;
  run_info?: Record<string, unknown>;
  ejemplo?: boolean; // made-up data (tests and the repository's preview), said on screen
  origen?: string; // P0.5e (21-11): where the data come from (the cloud's results brought to the PC, or the PC's report)
  medios?: string | null; // P0.5e: the report page's folder from the application's page (its videos and series)
  grip?: string | null; // what the TV allows to say of her grip (tennisbio.explain.grip_compatible)
  [k: string]: unknown;
}
