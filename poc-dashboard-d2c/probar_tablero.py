"""Pruebas del tablero en el navegador (Playwright): cada grafico filtra todo, las fichas de filtros se pueden quitar, el listado emergente funciona.
Levanta su propio servidor de ejemplo. Uso:  python probar_tablero.py   (requiere: pip install playwright y un Chromium)"""
import os
import subprocess
import sys
import time
import urllib.request

os.environ["DEMO"] = "1"
from playwright.sync_api import sync_playwright  # noqa: E402

PUERTO = 8791
URL = f"http://127.0.0.1:{PUERTO}/"
CROMO = next((p for p in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome") if os.path.exists(p)), None)
fallos = []


def prueba(nombre, ok, detalle=""):
    print(("  [OK]    " if ok else "  [FALLA] ") + nombre + (f"  ->  {detalle}" if not ok and detalle else ""))
    if not ok:
        fallos.append(nombre)


srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PUERTO)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(URL + "api/salud", timeout=1)
            break
        except Exception:  # noqa: BLE001
            time.sleep(.5)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CROMO, args=["--no-sandbox"]) if CROMO else p.chromium.launch(args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        def ir(vista):
            ctx.add_init_script(f"localStorage.setItem('d2c.vista','{vista}');localStorage.setItem('d2c.tema','light')")
            pg.goto(URL)
            pg.wait_for_selector(".screen", timeout=20000)
            pg.wait_for_timeout(1200)

        def esperar(js, t=8000):
            fin = time.time() + t / 1000
            while time.time() < fin:
                if pg.evaluate(js):
                    return True
                pg.wait_for_timeout(100)
            return False

        def clic_grafico(id_, idx, mod=None):
            xy = pg.evaluate("""([id,i])=>{const c=charts[id],p=c.getDatasetMeta(0).data[i],r=c.canvas.getBoundingClientRect();
              return [r.left+(p.x!==undefined?p.x:0)+(c.config.options.indexAxis==='y'?-12:0),r.top+(c.config.options.indexAxis==='y'?p.y:Math.min(p.y+8,c.chartArea.bottom-4))]}""", [id_, idx])
            pg.mouse.click(xy[0], xy[1])

        def n():
            return pg.evaluate("S.data.n_filtrado")

        print("Pedidos VTEX: gráfico de entrega estimada")
        ir("pedidos")
        n0 = n()
        m = pg.evaluate("S.data.matriz_entrega")
        prueba("la matriz usa los tres estados nuevos", m["estados"] == ["Integrado · En proceso (On time)", "Integrado · Atrasado (Out time)", "No integrado · Pendiente"], m["estados"])
        prueba("la leyenda del gráfico muestra los tres estados", pg.locator(".lg2").count() == 3)
        prueba("la tabla de detalle está en pantalla y tiene filas", pg.locator("table.t2 tbody tr").count() >= 3)
        i = 3
        clic_grafico("cEnt", i)
        ok = esperar(f"S.filtros.entrega.length===1&&S.data&&S.data.n_filtrado===S.data.matriz_entrega.totales[{i}]&&S.req>0")
        k = pg.evaluate("S.filtros.entrega[0]")
        tot = pg.evaluate(f"S.data.matriz_entrega.totales[{i}]")
        prueba("clic en una columna del gráfico filtra por ese día de entrega", ok and n() == tot, (k, n(), tot))
        prueba("aparece la ficha del filtro", pg.locator(".chip", has_text="Entrega").count() == 1)
        prueba("los demás gráficos se ajustan (SLA suma lo mismo que los pedidos filtrados)", pg.evaluate("S.data.g_sla.valores.reduce((a,b)=>a+b,0)") == n())
        prueba("la columna elegida queda resaltada y las otras atenuadas", pg.evaluate("charts.cEnt.data.activa&&charts.cEnt.data.activa.filter(Boolean).length===1"))
        clic_grafico("cEnt", i)
        prueba("segundo clic en la misma columna quita el filtro", esperar(f"S.filtros.entrega.length===0&&S.data.n_filtrado=={n0}"))
        pg.click("[data-ent='vencido']:not(.kt)")
        prueba("botón «Vencidos» filtra los pedidos con entrega vencida", esperar("S.filtros.entrega[0]==='vencido'&&S.data.n_filtrado===S.data.vencidos.n"), (n(), pg.evaluate("S.data.vencidos.n")))
        pg.click(".chip .x")
        prueba("la ✕ de la ficha quita el filtro", esperar(f"S.filtros.entrega.length===0&&S.data.n_filtrado=={n0}"))
        pg.click(".trow[data-ent='vencido']")
        prueba("el indicador «Entrega vencida» también filtra", esperar("S.filtros.entrega[0]==='vencido'"))
        pg.click("[data-limpiar-todo]")
        prueba("«Limpiar todo» quita las fichas", esperar(f"S.filtros.entrega.length===0&&S.data.n_filtrado=={n0}") and pg.locator(".chip").count() == 0)
        est = pg.evaluate("S.data.matriz_entrega.estados[1]")
        cuenta = pg.evaluate("S.data.matriz_entrega.filas[1].reduce((a,b)=>a+b,0)")
        pg.click(f".lg2[data-festado='{est}']")
        prueba("clic en un estado de la leyenda filtra por él", esperar(f"S.filtros.estado_ent.length===1&&S.data.n_filtrado=={cuenta}"), (n(), cuenta))
        pg.click("[data-limpiar-todo]")
        esperar(f"S.filtros.estado_ent.length===0&&S.data.n_filtrado=={n0}")

        print("Todos los gráficos se filtran entre sí")
        etq = pg.evaluate("charts.cCli.data.labels[1]")
        clic_grafico("cCli", 1)
        prueba("clic en un cliente filtra", esperar(f"S.filtros.cliente[0]==='{etq}'"))
        prueba("el gráfico de entrega se recalcula con ese cliente", esperar("S.data.matriz_entrega.total<=" + str(m["total"])))
        pg.click("[data-limpiar-todo]")
        esperar(f"S.filtros.cliente.length===0&&S.data.n_filtrado=={n0}")
        cl = pg.evaluate("charts.cClas?charts.cClas.data.labels[0]:null")
        if cl is None:
            esperar("charts.cClas")
            cl = pg.evaluate("charts.cClas.data.labels[0]")
        clic_grafico("cClas", 0)
        prueba("clic en una clasificación filtra todo el tablero", esperar(f"S.filtros.clasif2[0]==='{cl}'&&S.data.n_filtrado<{n0}"), (cl, n()))
        nclas = n()
        from app import servicio
        dim, hoy, _ = servicio._snapshot()
        indep = servicio._aplicar_filtros(dim, {"alcance": "abiertos", "bodega": ["EC01", "POST_Fechado"], "clasif2": [cl],
                                                 "fecha_ini": pg.evaluate("S.filtros.fecha_ini"), "fecha_fin": pg.evaluate("S.filtros.fecha_fin")})
        prueba("la cantidad coincide con el cálculo directo", nclas == len(indep), (nclas, len(indep)))
        prueba("el gráfico de entrega solo cuenta pedidos con esa clasificación", pg.evaluate("S.data.matriz_entrega.total")<=nclas)
        pg.click("[data-quitar='clasif2']")
        prueba("quitar la ficha de clasificación vuelve al total", esperar(f"S.filtros.clasif2.length===0&&S.data.n_filtrado=={n0}"))
        pg.click("[data-causa]")
        prueba("clic en una causa de pendiente filtra", esperar("S.filtros.causa.length===1&&S.data.n_filtrado<" + str(n0)))
        pg.click("[data-limpiar-todo]")
        esperar(f"S.filtros.causa.length===0&&S.data.n_filtrado=={n0}")

        print("Listado emergente y detalle de un pedido")
        pg.click("[data-ver-lista='det']")
        prueba("«Ver pedidos» abre el listado con filas", esperar("document.querySelectorAll('#lista .lst-d table.t tbody tr').length>20"))
        pg.keyboard.press("Escape")
        prueba("Esc cierra el listado", esperar("document.querySelectorAll('#lista .lst-d').length===0"))
        pg.click("table.t2 tbody tr")
        prueba("una fila de la tabla de detalle abre el detalle del pedido", esperar("document.querySelector('.dr:not([hidden])')!==null&&S.dr!==null"))
        pg.keyboard.press("Escape")

        print("Resumen ejecutivo")
        pg.click("[data-go='resumen']")
        esperar("S.view==='resumen'&&document.getElementById('cComp')&&charts.cClas")
        pg.wait_for_timeout(800)
        r0 = n()
        clic_grafico("cClas", 1)
        prueba("en Resumen, una clasificación filtra KPI, meses y canal", esperar(f"S.filtros.clasif2.length===1&&S.data.n_filtrado<{r0}"))
        prueba("los meses suman los pedidos filtrados", pg.evaluate("S.data.composicion.filas.flat().reduce((a,b)=>a+b,0)")==n())
        clic_grafico("cCanal", 0)
        prueba("clic en un canal del gráfico de riesgo filtra", esperar("S.filtros.canal.length===1"))
        pg.click("[data-limpiar-todo]")
        prueba("«Limpiar todo» deja el resumen como estaba", esperar(f"S.filtros.canal.length===0&&S.filtros.clasif2.length===0&&S.data.n_filtrado=={r0}"))

        print("Diagnóstico")
        pg.click("[data-go='diagnostico']")
        esperar("S.view==='diagnostico'&&charts.cDiaEst")
        pg.wait_for_timeout(600)
        d0 = n()
        clic_grafico("cDiaEst", 5)
        prueba("clic en un día filtra todo con los pedidos de ese día", esperar(f"S.filtros.fecha_ini&&S.filtros.fecha_ini===S.filtros.fecha_fin&&S.data.n_filtrado<{d0}"))
        prueba("la ficha dice el día", pg.locator(".chip", has_text="Creados el").count() == 1)
        pg.click("[data-limpiar-todo]")
        esperar(f"S.data.n_filtrado=={d0}")

        prueba("sin errores en la consola", not errs, errs[:3])
        b.close()
finally:
    srv.terminate()
print()
if fallos:
    print(f"RESULTADO: {len(fallos)} falla(s): " + "; ".join(fallos))
    sys.exit(1)
print("RESULTADO: todo en orden")
