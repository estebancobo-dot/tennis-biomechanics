// 21-11 (#310, the user: «ni siquiera sé si la app de Windows funciona bien»): the window checks itself once it has the
// cloud's results, without asking anything: a few strokes' videos open in this PC's browser engine (WebView2) and their
// frame series load. Its numbers go to the PC (tennisbio.app.p0_api.ApiVentana.autocomprobacion), which keeps them on the
// cloud's volume, so Claude reads whether the application works on this PC.
import { api } from "./api";
import type { Datos } from "./contrato";
import { cargarSerie } from "./pantallas/Reproductor";

let hecha = false;

function abre(src: string, ms = 15000): Promise<{ ok: boolean; ancho: number; error?: string }> {
  return new Promise((res) => {
    const v = document.createElement("video");
    const fin = (r: { ok: boolean; ancho: number; error?: string }) => { clearTimeout(t); v.removeAttribute("src"); v.load(); res(r); };
    const t = setTimeout(() => fin({ ok: false, ancho: 0, error: "no cargó en 15 s" }), ms);
    v.muted = true; v.preload = "auto";
    v.addEventListener("loadeddata", () => fin({ ok: v.videoWidth > 0, ancho: v.videoWidth }), { once: true });
    v.addEventListener("error", () => fin({ ok: false, ancho: 0, error: `código ${v.error?.code ?? "?"}` }), { once: true });
    v.src = src;
  });
}

export async function autocomprobar(d: Datos, n = 3): Promise<Record<string, unknown> | null> {
  const pc = api();
  if (hecha || !pc || !d.medios || d.ejemplo) return null;
  hecha = true;
  const t0 = performance.now();
  const golpes = d.strokes.filter((s) => s.video && s.series).slice(0, n);
  const filas = [];
  for (const s of golpes) {
    const v = await abre(d.medios + (s.video as string));
    const ser = await cargarSerie(s.id, d.medios + (s.series as string));
    filas.push({ id: s.id, video: v.ok, ancho: v.ancho, error: v.error, serie: !!(ser && ser.kp && ser.kp.length) });
  }
  const r = {
    origen: d.origen, golpes_con_video: d.strokes.filter((s) => s.video).length, probados: filas.length,
    videos_ok: filas.filter((f) => f.video).length, series_ok: filas.filter((f) => f.serie).length,
    ms: Math.round(performance.now() - t0), filas, navegador: navigator.userAgent,
  };
  try { await pc.autocomprobacion(r); } catch { /* the window without the method: nothing more to do */ }
  return r;
}
