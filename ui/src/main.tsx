import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { autocomprobar } from "./autocomprobacion";
import { cargar } from "./datos";
import "./estilo.css";

const raiz = createRoot(document.getElementById("raiz")!);
cargar()
  .then((d) => {
    raiz.render(<StrictMode><App d={d} /></StrictMode>);
    // 21-11 (#310): in the PC's window, once its API is there, the window checks its videos and series by itself
    const comprobar = () => { autocomprobar(d).catch(() => undefined); };
    if ((window as unknown as { pywebview?: { api?: unknown } }).pywebview?.api) comprobar();
    else window.addEventListener("pywebviewready", comprobar, { once: true });
  })
  .catch((e: Error) => raiz.render(<p style={{ padding: 24 }}>{e.message}</p>));
