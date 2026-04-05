"""
app.py — Auditoria Agenda Ole
Streamlit app: carga archivos, tabla dia a dia, informe IA.
"""
import streamlit as st
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

# ── Configuracion de pagina ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Auditoria Agenda Olé",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.row-ok       { background:#1a1a1a; }
.row-aviso    { background:#3d3000; border-left: 3px solid #ffd700; }
.row-error    { background:#3d0000; border-left: 3px solid #ff4444; }
.row-faltante { background:#1a2a1a; border-left: 3px solid #ff6600; font-style:italic; }
.pill-ok       { background:#1e3a1e; color:#4caf50; padding:2px 8px; border-radius:12px; font-size:12px; }
.pill-aviso    { background:#3d3000; color:#ffd700; padding:2px 8px; border-radius:12px; font-size:12px; }
.pill-error    { background:#3d0000; color:#ff6666; padding:2px 8px; border-radius:12px; font-size:12px; }
.pill-faltante { background:#2a1a00; color:#ff9944; padding:2px 8px; border-radius:12px; font-size:12px; }
</style>
""", unsafe_allow_html=True)

# ── Importar engine ────────────────────────────────────────────────────────────
try:
    from engine import (
        ejecutar_auditoria, generar_informe, resumen_por_dia,
        COMPETICIONES_INFORME, URGENTE_KEYWORDS, IMPORTANTE_KEYWORDS,
        TOLERANCIA_HORARIO_MIN,
    )
    ENGINE_OK = True
except ImportError as e:
    st.error(f"Error importando engine.py: {e}")
    ENGINE_OK = False
    st.stop()

import anthropic

TZ_BA = ZoneInfo("America/Argentina/Buenos_Aires")

# ── Session state ──────────────────────────────────────────────────────────────
def _init():
    for k, v in {
        "ole_raw":      None,
        "opta_raw":     None,
        "directv_raw":  None,
        "flow_raw":     None,
        "lnb_raw":      None,
        "resultado":    None,
        "informe":      None,
        "ole_nombre":   "",
        "opta_nombre":  "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuración")

    api_key = st.text_input(
        "🔑 API Key Anthropic",
        type="password",
        placeholder="sk-ant-api03-...",
        help="Necesaria para generar el informe IA",
    )

    st.divider()
    st.markdown("### 📂 Archivos")
    st.caption("Los archivos quedan cargados mientras la pestaña esté abierta.")

    # Agenda Ole
    st.markdown("**Agenda Olé** (obligatorio)")
    metodo_ole = st.radio("Fuente", ["Scrape automático", "Subir archivo", "Pegar texto"],
                          label_visibility="collapsed", key="metodo_ole")

    if metodo_ole == "Scrape automático":
        if st.button("🔄 Scrapear ole.com.ar", use_container_width=True):
            with st.spinner("Conectando..."):
                try:
                    from curl_cffi import requests as _cr
                    from engine import parse_texto_agenda, _next_data, _buscar_evs
                    import re as _re
                    hoy = date.today().isoformat()
                    headers = {
                        "User-Agent": "Mozilla/5.0 Chrome/120",
                        "Accept": "text/html",
                        "Referer": "https://www.google.com/",
                    }
                    r = _cr.get("https://www.ole.com.ar/agenda-deportiva",
                                impersonate="chrome120", headers=headers, timeout=25)
                    if r.status_code == 200:
                        nd = _next_data(r.text)
                        evs = []
                        if nd:
                            raw_evs = _buscar_evs(nd)
                            # normalizar desde next_data
                            for ev in raw_evs:
                                fecha = str(ev.get("date",""))[:10]
                                if not fecha or fecha < hoy: continue
                                home = ev.get("homeTeam") or ev.get("home","")
                                away = ev.get("awayTeam") or ev.get("away","")
                                if isinstance(home,dict): home=home.get("name","")
                                if isinstance(away,dict): away=away.get("name","")
                                name = ev.get("name","") or (f"{home} vs. {away}" if home and away else "")
                                if not name: continue
                                comp = ev.get("competition") or ev.get("tournament","")
                                if isinstance(comp,dict): comp=comp.get("name","")
                                tv = ev.get("tv") or ev.get("canales") or []
                                if isinstance(tv,str):
                                    canales = [c.strip() for c in tv.split(" / ") if c.strip()]
                                elif isinstance(tv,list):
                                    canales = [str(c).strip() for c in tv if c]
                                else:
                                    canales = []
                                hora_raw = ev.get("time") or ev.get("hora")
                                hora = None
                                if hora_raw:
                                    m2 = _re.search(r"(\d{2}:\d{2})", str(hora_raw))
                                    hora = m2.group(1) if m2 else None
                                evs.append({"date":fecha,"time":hora,"name":name,
                                           "competition":str(comp),"canales":canales})
                        if not evs:
                            texto = _re.sub(r"<[^>]+>","\\n",r.text)
                            evs = parse_texto_agenda(texto)
                        if evs:
                            st.session_state.ole_raw = json.dumps({"agenda":evs},
                                                        ensure_ascii=False).encode()
                            st.session_state.ole_nombre = "scrape ole.com.ar"
                            st.success(f"✅ {len(evs)} eventos")
                        else:
                            st.warning("Sin eventos — usá otra opción")
                    else:
                        st.error(f"HTTP {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")

    elif metodo_ole == "Subir archivo":
        f_ole = st.file_uploader("JSON o CSV de la agenda", type=["json","csv"],
                                  key="up_ole")
        if f_ole:
            st.session_state.ole_raw = f_ole.read()
            st.session_state.ole_nombre = f_ole.name
            st.success(f"✅ {f_ole.name}")

    else:  # Pegar texto
        texto_ole = st.text_area("Pegá el texto de ole.com.ar/agenda-deportiva",
                                  height=150, key="ta_ole",
                                  placeholder="Agenda Deportiva del domingo 5 de abril...")
        if st.button("Procesar texto", key="btn_ole_txt"):
            from engine import parse_texto_agenda
            evs = parse_texto_agenda(texto_ole)
            if evs:
                st.session_state.ole_raw = json.dumps({"agenda":evs},
                                            ensure_ascii=False).encode()
                st.session_state.ole_nombre = "texto pegado"
                st.success(f"✅ {len(evs)} eventos")
            else:
                st.error("No se detectaron eventos")

    if st.session_state.ole_raw:
        st.caption(f"📋 Agenda: {st.session_state.ole_nombre}")

    st.divider()

    # Fixtures
    st.markdown("**Fixtures** (fuente de verdad)")
    st.caption("Podés subir varios archivos — se acumulan.")

    f_fix = st.file_uploader("Excel o JSON de fixtures",
                              type=["xlsx","json"], key="up_fix",
                              help="JSON resumido, JSON largo, o Excel con hoja RESUMEN")
    if f_fix:
        from engine import norm_opta
        import io as _io, openpyxl as _xl
        raw = f_fix.read()
        fname = f_fix.name
        try:
            if fname.endswith(".xlsx"):
                from engine import _leer_xlsx_fixtures
                nuevos = _leer_xlsx_fixtures(raw)
            else:
                nuevos = norm_opta(raw)
            # Acumular con los existentes
            existentes = []
            if st.session_state.opta_raw:
                prev = json.loads(st.session_state.opta_raw.decode())
                existentes = prev.get("agenda", [])
            from engine import norm_str
            vistos = {(norm_str(e["name"]), e["date"]) for e in existentes}
            nuevos_dedup = [e for e in nuevos
                           if (norm_str(e["name"]), e["date"]) not in vistos]
            todos = existentes + nuevos_dedup
            st.session_state.opta_raw = json.dumps({"agenda":todos},
                                          ensure_ascii=False).encode()
            st.session_state.opta_nombre = fname
            st.success(f"✅ {fname}: +{len(nuevos_dedup)} eventos ({len(todos)} total)")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.opta_raw:
        tot = len(json.loads(st.session_state.opta_raw.decode()).get("agenda",[]))
        st.caption(f"📊 Fixtures: {tot} eventos")
        if st.button("🗑 Limpiar fixtures", key="btn_limpiar_fix"):
            st.session_state.opta_raw = None
            st.rerun()

    st.divider()

    # DIRECTV / Flow / LNB
    st.markdown("**Grillas de TV** (opcional)")
    f_dtv = st.file_uploader("Excel DIRECTV", type=["xlsx"], key="up_dtv")
    if f_dtv:
        st.session_state.directv_raw = f_dtv.read()
        st.success(f"✅ {f_dtv.name}")

    f_flow = st.file_uploader("Excel Flow", type=["xlsx"], key="up_flow")
    if f_flow:
        st.session_state.flow_raw = f_flow.read()
        st.success(f"✅ {f_flow.name}")

    f_lnb = st.file_uploader("JSON LNB", type=["json"], key="up_lnb")
    if f_lnb:
        st.session_state.lnb_raw = f_lnb.read()
        st.success(f"✅ {f_lnb.name}")

    st.divider()

    # Botón de auditoría
    puede_auditar = bool(st.session_state.ole_raw and
                         (st.session_state.opta_raw or st.session_state.flow_raw or
                          st.session_state.directv_raw or st.session_state.lnb_raw))
    if st.button("▶ Ejecutar auditoría", type="primary",
                  use_container_width=True, disabled=not puede_auditar):
        if not api_key:
            st.error("Ingresá la API Key")
        else:
            with st.spinner("Auditando..."):
                try:
                    cliente = anthropic.Anthropic(api_key=api_key)
                    resultado = ejecutar_auditoria(
                        st.session_state.ole_raw,
                        st.session_state.opta_raw,
                        st.session_state.directv_raw,
                        st.session_state.flow_raw,
                        st.session_state.lnb_raw,
                        cliente,
                    )
                    st.session_state.resultado = resultado
                    st.session_state.informe = None  # resetear informe anterior
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Auditoría Agenda Olé")
tz_now = datetime.now(TZ_BA).strftime("%d/%m/%Y %H:%M")
st.caption(f"Buenos Aires · {tz_now}")

if not st.session_state.resultado:
    st.info("Cargá los archivos en el panel izquierdo y ejecutá la auditoría.")
    st.stop()

resultado = st.session_state.resultado
falt      = resultado["falt"]
horas_err = resultado["horas_error"]
horas_av  = resultado["horas_aviso"]
s_can     = resultado["s_can"]
e_can     = resultado["e_can"]

# ── Métricas resumen ──────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("❌ Faltantes",   len(falt))
c2.metric("⏰ Horarios",    len(horas_err))
c3.metric("⚠️ Avisos hora", len(horas_av))
c4.metric("📺 Canal falta", len(s_can))
c5.metric("🔀 Canal mal",   len(e_can))

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📅 Vista por día", "🤖 Informe IA"])

# ────────────────────────────────────────────────────────────────────────────────
# TAB 1: Vista día a día
# ────────────────────────────────────────────────────────────────────────────────
with tab1:
    dias = resumen_por_dia(resultado)

    if not dias:
        st.info("Sin datos para mostrar.")
    else:
        # Filtros
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            mostrar = st.multiselect(
                "Mostrar",
                ["✅ OK", "⚠️ Avisos", "❌ Errores", "➕ Faltantes"],
                default=["⚠️ Avisos", "❌ Errores", "➕ Faltantes"],
                label_visibility="collapsed",
            )
        with col_f2:
            solo_problemas = st.toggle("Solo días con problemas", value=True)

        estado_map = {
            "✅ OK":        "ok",
            "⚠️ Avisos":   "aviso",
            "❌ Errores":  "error",
            "➕ Faltantes": "faltante",
        }
        estados_visibles = {estado_map[m] for m in mostrar}

        for dia in dias:
            fecha_iso = dia["fecha"]
            filas_visibles = [f for f in dia["filas"] if f["estado"] in estados_visibles]

            if not filas_visibles and solo_problemas:
                continue
            if not filas_visibles:
                filas_visibles = dia["filas"]

            try:
                fecha_lbl = datetime.fromisoformat(fecha_iso).strftime("%A %d/%m").capitalize()
            except Exception:
                fecha_lbl = fecha_iso

            n_ok   = sum(1 for f in dia["filas"] if f["estado"] == "ok")
            n_prob = sum(1 for f in dia["filas"] if f["estado"] != "ok")
            badge  = f"✅ {n_ok} OK" + (f"  ·  ⚠️ {n_prob} con problemas" if n_prob else "")

            with st.expander(f"**{fecha_lbl}** — {badge}", expanded=(n_prob > 0)):

                # Cabecera de columnas
                hdr = st.columns([1, 1, 4, 3, 2, 2, 2])
                for col, txt in zip(hdr, ["Estado","Hora","Partido","Competición",
                                           "Horario ref","Canal Olé","Canal ref"]):
                    col.markdown(f"**{txt}**")
                st.markdown("---")

                for fila in filas_visibles:
                    cols = st.columns([1, 1, 4, 3, 2, 2, 2])

                    # Estado
                    if fila["estado"] == "ok":
                        cols[0].markdown("✅")
                    elif fila["estado"] == "aviso":
                        cols[0].markdown("⚠️")
                    elif fila["estado"] == "error":
                        cols[0].markdown("❌")
                    else:  # faltante
                        cols[0].markdown("➕")

                    # Hora Olé — resaltar si está mal
                    hora_txt = fila["hora_ole"]
                    if fila["hora_ok"] is False:
                        cols[1].markdown(f":red[**{hora_txt}**]")
                    elif fila["hora_ok"] is None:
                        cols[1].markdown(f":orange[{hora_txt}]")
                    else:
                        cols[1].markdown(hora_txt)

                    # Partido — itálica si es faltante
                    nombre = f"*{fila['partido']}*" if not fila["en_ole"] else fila["partido"]
                    cols[2].markdown(nombre)

                    # Competición
                    cols[3].markdown(f"*{fila['competicion']}*")

                    # Horario referencia
                    if fila["hora_ref"] and fila["hora_ref"] != fila["hora_ole"]:
                        if fila["hora_ok"] is False:
                            cols[4].markdown(f":green[**{fila['hora_ref']}**]")
                        else:
                            cols[4].markdown(f":orange[{fila['hora_ref']}]")
                    else:
                        cols[4].markdown("—")

                    # Canal Olé — resaltar si está mal o falta
                    canal_ole = fila["canal_ole"] or "—"
                    if fila["canal_ok"] is False:
                        cols[5].markdown(f":red[{canal_ole}]")
                    elif fila["canal_ok"] is None and not fila["canal_ole"]:
                        cols[5].markdown(":gray[sin canal]")
                    else:
                        cols[5].markdown(canal_ole)

                    # Canal referencia
                    canal_ref = fila["canal_ref"] or ""
                    if canal_ref:
                        if fila["canal_ok"] is False:
                            cols[6].markdown(f":green[**{canal_ref}**]")
                        elif fila["canal_ok"] is None:
                            cols[6].markdown(f":orange[{canal_ref}]")
                        else:
                            cols[6].markdown(canal_ref)
                    else:
                        cols[6].markdown("—")

                    # Notas al pie de la fila si las hay
                    if fila.get("notas"):
                        st.caption(f"↳ {fila['notas']}")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 2: Informe IA
# ────────────────────────────────────────────────────────────────────────────────
with tab2:
    if st.session_state.informe:
        st.markdown(st.session_state.informe)
        st.download_button(
            "⬇️ Descargar informe (.md)",
            data=st.session_state.informe,
            file_name=f"auditoria_ole_{date.today().isoformat()}.md",
            mime="text/markdown",
        )
    else:
        st.info("El informe se genera con IA una vez ejecutada la auditoría.")
        if st.button("🤖 Generar informe", type="primary"):
            if not api_key:
                st.error("Ingresá la API Key en el panel izquierdo.")
            else:
                with st.spinner("Generando informe IA..."):
                    try:
                        cliente = anthropic.Anthropic(api_key=api_key)
                        informe = generar_informe(resultado, cliente)
                        st.session_state.informe = informe
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
