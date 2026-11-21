// P0.5d (15-11, docs/p0_plan.md §3 ter): what the management screens ask the PC's window to do (pywebview's js_api,
// tennisbio.app.p0_api.Gestion behind it). Each action is a request on the volume that the one cloud queue turns into
// jobs; the answer comes back with the queue's state. In a browser (no window) there is no API: the buttons stay
// disabled and say where they work, never pretend to have done something.
export interface Respuesta { ok: boolean; motivo?: string; peticion?: string; cuando?: string; partido?: string }
export interface FichaAlta { jugadora: string; rival: string; torneo?: string; ronda?: string; fecha?: string; superficie?: string }
export interface FotoClic { src: string; t: number; by?: string | null }

export interface ApiPC {
  elegir_video(): Promise<string | null>;
  proponer(ruta: string): Promise<FichaAlta>;
  alta(ruta: string, ficha: FichaAlta, preparar: boolean): Promise<Respuesta>;
  fotos(partido: string): Promise<FotoClic[]>;
  clic(partido: string, t: number, near_is_her: boolean, by?: string | null): Promise<Respuesta>;
  aprobar(partido: string, previsto: Record<string, number | string>): Promise<Respuesta>;
  pausar(): Promise<Respuesta>;
  reanudar(): Promise<Respuesta>;
  cancelar(trabajo: string): Promise<Respuesta>;
  borrar_video(partido: string): Promise<Respuesta>;
  // P0.5e (21-11): the cloud's latest results to the PC (tennisbio.app.p0_nube); «recargar»: the page was made again
  traer_resultados(): Promise<Respuesta & { bajados?: number; mb?: number; generado?: string; recargar?: boolean }>;
  // 21-11 (#310): the window's own check of its videos and series on this PC (ui/src/autocomprobacion.ts)
  autocomprobacion(r: Record<string, unknown>): Promise<Respuesta>;
  // 21-11 (P0.5e): a result brought from the cloud (the export's PDF, a montage, its folder) with the PC's own program
  abrir(ruta: string): Promise<Respuesta>;
}

export const SOLO_PC = "Se hace en la aplicación del PC (aquí, solo para mirar)";

export function api(): ApiPC | null {
  const w = window as unknown as { pywebview?: { api?: ApiPC } };
  return w.pywebview?.api ?? null;
}
