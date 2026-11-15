// Where the application's data come from: put into the page when it opens (tennisbio.app.p0.pagina), or, in the PC's
// window, asked to its Python API (pywebview). Nothing is fetched from the internet.
import type { Datos } from "./contrato";

declare global {
  interface Window {
    __TENNISBIO__?: Datos | null;
    pywebview?: { api?: { datos?: () => Promise<Datos> } };
  }
}

export async function cargar(): Promise<Datos> {
  if (window.__TENNISBIO__) return window.__TENNISBIO__;
  const api = window.pywebview?.api;
  if (api?.datos) return api.datos();
  throw new Error("La aplicación se abrió sin datos: ábrela desde TennisBio (o con tennisbio.app.p0).");
}

export const esN = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
export const fmt = (v: unknown, d = 0) =>
  esN(v) ? v.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—";
export const iniciales = (n?: string | null) =>
  String(n || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
export const GOLPE_ES: Record<string, string> = { forehand: "Derecha", backhand: "Revés", serve: "Saque", overhead: "Saque" };
