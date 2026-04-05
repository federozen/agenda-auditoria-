# Auditoría Agenda Olé

App para auditar la agenda deportiva de Olé comparando contra SofaScore y grillas de TV.

## Deploy en Streamlit Cloud

1. Hacer fork de este repo en GitHub
2. Ir a [share.streamlit.io](https://share.streamlit.io)
3. Conectar el repo y seleccionar `app.py`
4. En **Secrets** agregar: `ANTHROPIC_API_KEY = "sk-ant-..."`  
   *(opcional — también se puede ingresar en la sidebar)*

## Archivos esperados

| Paso | Archivo | Formato |
|------|---------|---------|
| Agenda Olé | `agenda_deportiva_ole.json` o `.csv` | Scrapeado de ole.com.ar |
| Fixtures | `agenda_resumida_*.json` o `.xlsx` | SofaScore exportado |
| DIRECTV | Excel semanal | Hoja `Deportes_Argentina` |
| Flow | Excel semanal | Hoja `Argentina` |
| LNB | `basquet.json` | Lista de partidos |

## Uso

1. Ingresar API Key de Anthropic en el panel izquierdo
2. Cargar la agenda Olé (scrape automático o subir archivo)
3. Cargar fixtures (podés subir varios para acumular)
4. Opcionalmente subir DIRECTV, Flow o LNB
5. Clic en **Ejecutar auditoría**
6. Ver tabla día a día en el Tab 1
7. Generar informe IA en el Tab 2
