import streamlit as st
import streamlit.components.v1 as components
import json
import math
import requests
import time
import pandas as pd
from deep_translator import GoogleTranslator

# ==========================================
# 0. INICIALIZAÇÃO DA MEMÓRIA (SESSION STATE)
# ==========================================
if 'vento_vel_cb'    not in st.session_state: st.session_state.vento_vel_cb    = 5.0
if 'vento_dir_cb'    not in st.session_state: st.session_state.vento_dir_cb    = 45.0
if 'temp_cb'         not in st.session_state: st.session_state.temp_cb         = 15.0
if 'status_cb'       not in st.session_state: st.session_state.status_cb       = "A aguardar sincronização..."
if 'dados_campanha'  not in st.session_state: st.session_state.dados_campanha  = None
# Clima amanhã
if 'temp_amanha_cb'      not in st.session_state: st.session_state.temp_amanha_cb      = 15.0
if 'vento_vel_amanha_cb' not in st.session_state: st.session_state.vento_vel_amanha_cb = 5.0
if 'vento_dir_amanha_cb' not in st.session_state: st.session_state.vento_dir_amanha_cb = 45.0
# NavLog / FMC
if 'navlog_manual' not in st.session_state:
    st.session_state.navlog_manual = [{"Perna": "Base ➔ Alvo", "Distância (km)": 50.0, "Rumo (TC)": 90.0, "TAS (km/h)": 330, "Altitude (m)": 2000}]
if 'index_perna_ativa'            not in st.session_state: st.session_state.index_perna_ativa            = 0
if 'cronometro_rodando'           not in st.session_state: st.session_state.cronometro_rodando           = False
if 'tempo_inicio_perna'           not in st.session_state: st.session_state.tempo_inicio_perna           = None
if 'tempo_pausado_acumulado'      not in st.session_state: st.session_state.tempo_pausado_acumulado      = 0.0
if 'tempo_inicio_missao_absoluto' not in st.session_state: st.session_state.tempo_inicio_missao_absoluto = None
# Controlo
if 'vel_calc'            not in st.session_state: st.session_state.vel_calc            = 320.0
if 'dist_calc'           not in st.session_state: st.session_state.dist_calc           = 250.0
if 'last_file_hash'      not in st.session_state: st.session_state.last_file_hash      = None
if 'av_nome_selecionado' not in st.session_state: st.session_state.av_nome_selecionado = "He-111 H-16"
if 'mission_end_time'   not in st.session_state: st.session_state.mission_end_time   = ""
if 'mission_start_time' not in st.session_state: st.session_state.mission_start_time = ""
if 'pilots_allied'      not in st.session_state: st.session_state.pilots_allied      = None
if 'pilots_axis'        not in st.session_state: st.session_state.pilots_axis        = None

# ==========================================
# 1. FUNÇÕES DA API E TRADUÇÃO
# ==========================================
@st.cache_data(ttl=3600)
def traduzir_texto(texto):
    if not texto or texto.strip() == "":
        return ""
    try:
        tradutor = GoogleTranslator(source='en', target='pt')
        return tradutor.translate(texto)
    except Exception:
        return texto 

def fetch_combatbox_data():
    try:
        api_url = "https://campaign-data.combatbox.net/rhineland-campaign/rhineland-campaign-latest.json.aspx"
        response = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        
        if response.status_code != 200:
            st.session_state.status_cb = f"❌ Erro HTTP {response.status_code}"
            return
            
        dados_json = response.json()
        st.session_state.dados_campanha = dados_json 
        
        # Tempo de fim da missão — campo confirmado no HAR
        st.session_state.mission_end_time = dados_json.get("EstimatedMissionEnd", "")

        # --- CLIMA HOJE ---
        weather_hoje = dados_json.get("Weather", {})
        wind_hoje = weather_hoje.get("WindAtGroundLevel", {})
        st.session_state.temp_cb = float(weather_hoje.get("Temperature", 15.0))
        st.session_state.vento_vel_cb = float(wind_hoje.get("Speed", 5.0))
        bearing_bruto = float(wind_hoje.get("Bearing", 45.0))
        st.session_state.vento_dir_cb = (bearing_bruto + 180) % 360

        # --- CLIMA AMANHÃ ---
        weather_amanha = dados_json.get("WeatherTomorrow", {})
        wind_amanha = weather_amanha.get("WindAtGroundLevel", {})
        st.session_state.temp_amanha_cb = float(weather_amanha.get("Temperature", 15.0))
        st.session_state.vento_vel_amanha_cb = float(wind_amanha.get("Speed", 5.0))
        bearing_amanha_bruto = float(wind_amanha.get("Bearing", 45.0))
        st.session_state.vento_dir_amanha_cb = (bearing_amanha_bruto + 180) % 360
        
        st.session_state.status_cb = "✅ API Sincronizada!"
            
    except Exception as e:
        st.session_state.status_cb = f"❌ Erro de Ligação: {e}"

def fetch_pilots_online():
    """Busca pilotos online do endpoint dedicado — coalition 1=Allied, 2=Axis."""
    try:
        r = requests.get("https://il2statsapi.combatbox.net/api/onlineplayers",
                         headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            players = r.json()
            st.session_state.pilots_allied = sum(1 for p in players if p.get('coalition') == 1)
            st.session_state.pilots_axis   = sum(1 for p in players if p.get('coalition') == 2)
    except Exception:
        pass
        
        # --- AJUSTE DE CONVENÇÃO: HOJE ---
        weather_hoje = dados_json.get("Weather", {})
        wind_hoje = weather_hoje.get("WindAtGroundLevel", {})
        st.session_state.temp_cb = float(weather_hoje.get("Temperature", 15.0))
        st.session_state.vento_vel_cb = float(wind_hoje.get("Speed", 5.0))
        
        # Inversão de 180 graus para converter "Para Onde" em "De Onde"
        bearing_bruto = float(wind_hoje.get("Bearing", 45.0))
        st.session_state.vento_dir_cb = (bearing_bruto + 180) % 360

        # --- AJUSTE DE CONVENÇÃO: AMANHÃ ---
        weather_amanha = dados_json.get("WeatherTomorrow", {})
        wind_amanha = weather_amanha.get("WindAtGroundLevel", {})
        st.session_state.temp_amanha_cb = float(weather_amanha.get("Temperature", 15.0))
        st.session_state.vento_vel_amanha_cb = float(wind_amanha.get("Speed", 5.0))
        
        bearing_amanha_bruto = float(wind_amanha.get("Bearing", 45.0))
        st.session_state.vento_dir_amanha_cb = (bearing_amanha_bruto + 180) % 360
        
        st.session_state.status_cb = "✅ API Sincronizada!"
            
    except Exception as e:
        st.session_state.status_cb = f"❌ Erro de Ligação: {e}"

def calcular_rumo_e_distancia(p1, p2):
    # No IL-2 Mission Planner (Rheinland):
    # lat cresce para NORTE (menos negativo = mais norte), lng cresce para LESTE.
    # Rumo correto: atan2(dlng, dlat) — Norte = dlat+, Leste = dlng+
    # Escala: 3.872 km/grau (calibrado contra Plan Summary do Mission Planner)
    dlng = p2['lng'] - p1['lng']
    dlat = p2['lat'] - p1['lat']
    rumo_final   = (math.degrees(math.atan2(dlng, dlat)) + 360) % 360
    distancia_km = math.sqrt(dlng**2 + dlat**2) * 3.872
    return rumo_final, distancia_km

# ==========================================
# 2.1 BASE DE DADOS DEFINITIVA (ALTITUDES)
# ==========================================
db_altitudes_tecnico = {
    "Aachen": 190, "Achmer": 54, "Bad Lippspringe": 140, "Breitscheid": 558,
    "Chievres": 59, "Coesfeld-Lette": 80, "Deelen": 48, "Deurne": 12,
    "Diest": 27, "Dortmund": 129, "Eudenbach": 360, "Florennes": 285,
    "Gilze-Rijen": 15, "Greven": 48, "Guetersloh": 80, "Kirchhellen": 67,
    "Liege": 201, "Limburg": 31, "Melsbroek": 56, "Nivelles": 103,
    "Petit Brogel": 61, "Plantluenne": 35, "Quackenbrueck": 24, "Schiphol": 0,
    "Sint-Denijs-Westrem": 8, "Soesterberg": 20, "Stoermede": 90,
    "Strassfeld": 161, "Twente": 35, "Venlo": 30, "Volkel": 14, "Woensdrecht": 19
}

# ==========================================
# 2. BASE DE DADOS COMPLETA: AERONAVES (C4ISR)
# ==========================================
db_avioes = {
    "He-111 H-16": {
        "peso_base_sem_combustivel": 9300, 
        "peso_max": 14000, 
        "consumo_l_min": 10.2, 
        "vel_cruzeiro_padrao": 330, 
        "tanque_max_l": 3450,
        "climb_rate_default": 2.5, 
        "descent_rate_default": 4.0,
        "armamento_fixo": "4x 7.92mm MG-81J | 1x 20mm MG-FF | 1x 13mm MG-131",
        "modificacoes": {
            "Padrão": 0,
            "Remover Blindagem": -115,
            "Tanque Adicional": 150
        },
        "presets_bombas": {
            "Vazio": 0, 
            "1x SC 2500 (Max)": 2400, 
            "2x SC 1800 (Satan)": 3560, 
            "2x SC 1000 (Hermann)": 2180, 
            "8x SC 250": 2000, 
            "32x SC 50": 1600
        }
    },
    "He-111 H-6": {
        "peso_base_sem_combustivel": 9500, 
        "peso_max": 14000, 
        "consumo_l_min": 10.5, 
        "vel_cruzeiro_padrao": 320, 
        "tanque_max_l": 3450,
        "climb_rate_default": 2.5, 
        "descent_rate_default": 4.0,
        "armamento_fixo": "6x 7.92mm MG-15",
        "modificacoes": {
            "Padrão": 0, 
            "Torre Frontal (20mm)": 46, 
            "Torre Ventral": 147, 
            "Kit Anti-Navio": 193
        },
        "presets_bombas": {
            "Vazio": 0, 
            "2x SC 1000": 2180, 
            "1x SC 1800": 1780, 
            "4x SC 250": 1000, 
            "16x SC 50": 800
        }
    },
    "Ju-52/3M": {
        "peso_base_sem_combustivel": 7500, 
        "peso_max": 11000, 
        "consumo_l_min": 12.0, 
        "vel_cruzeiro_padrao": 240, 
        "tanque_max_l": 2450,   
        "climb_rate_default": 2.0, 
        "descent_rate_default": 3.0,
        "armamento_fixo": "1x 13mm MG-131 (Dorsal)",
        "modificacoes": {
            "Padrão": 0, 
            "Paraquedistas (12 homens)": 1200, 
            "Carga Interna Tática": 2300, 
            "Rodas de Inverno": 45
        },
        "presets_bombas": {
            "Vazio": 0, 
            "10x MAB 250 (Containers)": 2550,
            "12x SC 50": 600
        }
    },
    "Ju-88 A-4": {
        "peso_base_sem_combustivel": 8600, 
        "peso_max": 14000, 
        "consumo_l_min": 10.0, 
        "vel_cruzeiro_padrao": 370, 
        "tanque_max_l": 1680,   
        "climb_rate_default": 3.5, 
        "descent_rate_default": 5.0,
        "armamento_fixo": "1x 13mm MG-131 | 3x 7.92mm MG-81J",
        "modificacoes": {
            "Padrão": 0, 
            "Sem Dive Brakes": -60, 
            "Sem Gôndola Inferior": -123,
            "Câmera de Reconhecimento": 25
        },
        "presets_bombas": {
            "Vazio": 0, 
            "4x SC 500": 2000, 
            "10x SC 50 (Interno)": 500, 
            "28x SC 50 (Full Load)": 1400,
            "2x SC 1000": 2180
        }
    }
}

# ==========================================
# 3. INTERFACE E BARRA LATERAL
# ==========================================
st.set_page_config(page_title="Painel Tático - Combat Box", layout="wide")
st.markdown("""<style>.stApp { background-color: #0E1117; color: #FAFAFA; }</style>""", unsafe_allow_html=True)

with st.sidebar:
    # Remove padding excessivo do Streamlit na sidebar
    st.markdown("""
        <style>
        section[data-testid="stSidebar"] > div { padding-top: 0.8rem !important; }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }
        </style>
    """, unsafe_allow_html=True)

    # ── BLOCO 1 (60s): Status, campanha e meteorologia ─────────────────
    @st.fragment(run_every="60s")
    def painel_telemetria_ativo():
        fetch_combatbox_data()
        fetch_pilots_online()
        _dados = st.session_state.dados_campanha
        ok  = "🟢" if "Sincronizada" in st.session_state.status_cb else "🔴"
        dia_txt, win_txt, rem_txt = "—", "—", "—"
        if _dados:
            _dia    = _dados.get("Day", {})
            dia_txt = f"Dia {_dia.get('DayInCampaign','?')} &nbsp;·&nbsp; {_dia.get('Day','?')}/{_dia.get('Month','?')}/{_dia.get('Year','?')}"
            win_txt = _dados.get('WinningCoalition','—')
            rem_txt = str(_dados.get('DaysRemaining','?'))
        v1 = st.session_state.vento_vel_cb
        d1 = st.session_state.vento_dir_cb
        t1 = st.session_state.temp_cb
        v2 = st.session_state.vento_vel_amanha_cb
        d2 = st.session_state.vento_dir_amanha_cb
        t2 = st.session_state.temp_amanha_cb

        st.markdown(
            f'<div style="font-family:sans-serif;font-size:12px;line-height:1.6;">'
            f'<div style="color:#666;margin-bottom:6px;">{ok} API sincronizada</div>'
            f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;margin-bottom:8px;">'
            f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:3px;">📅 CAMPANHA</div>'
            f'<div style="color:#eee;font-weight:bold;">{dia_txt}</div>'
            f'<div style="color:#aaa;font-size:11px;margin-top:2px;">'
            f'🏆 {win_txt} &nbsp;|&nbsp; ⏳ {rem_txt} dias restantes</div></div>'
            f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;">'
            f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:6px;">🌦️ METEOROLOGIA</div>'
            f'<div style="background:#0d1117;border-radius:5px;padding:5px 8px;margin-bottom:5px;">'
            f'<div style="color:#f5a623;font-size:10px;font-weight:bold;margin-bottom:3px;">☀️ HOJE</div>'
            f'<div style="display:flex;gap:12px;color:#eee;">'
            f'<span>💨 {v1} m/s</span><span>🧭 {d1:.0f}°</span><span>🌡️ {t1} °C</span>'
            f'</div></div>'
            f'<div style="background:#0d1117;border-radius:5px;padding:5px 8px;">'
            f'<div style="color:#7ec8e3;font-size:10px;font-weight:bold;margin-bottom:3px;">🌙 AMANHÃ</div>'
            f'<div style="display:flex;gap:12px;color:#eee;">'
            f'<span>💨 {v2} m/s</span><span>🧭 {d2:.0f}°</span><span>🌡️ {t2} °C</span>'
            f'</div></div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    painel_telemetria_ativo()

    # ── BLOCO 2 (1s): Pilotos + Countdown ─────────────────────────────
    @st.fragment(run_every="1s")
    def sidebar_countdown():
        pa = st.session_state.pilots_allied
        px = st.session_state.pilots_axis

        pilots_html = ""
        if pa is not None and px is not None:
            total = max(pa + px, 1)
            pct_a = int(pa / total * 100)
            pct_x = 100 - pct_a
            pilots_html = (
                f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;margin-bottom:8px;">'
                f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:5px;">✈️ PILOTS ON STATION</div>'
                f'<div style="display:flex;justify-content:space-around;margin-bottom:5px;">'
                f'<div style="text-align:center;">'
                f'<div style="color:#dd4444;font-size:28px;font-weight:900;line-height:1;">{pa}</div>'
                f'<div style="color:#888;font-size:10px;">ALLIES</div>'
                f'</div>'
                f'<div style="text-align:center;">'
                f'<div style="color:#4488cc;font-size:28px;font-weight:900;line-height:1;">{px}</div>'
                f'<div style="color:#888;font-size:10px;">AXIS</div>'
                f'</div></div>'
                f'<div style="display:flex;height:12px;border-radius:3px;overflow:hidden;">'
                f'<div style="width:{pct_a}%;background:#aa2222;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:bold;color:#fff;">{pct_a}%</div>'
                f'<div style="width:{pct_x}%;background:#2255aa;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:bold;color:#fff;">{pct_x}%</div>'
                f'</div>'
                f'<div style="text-align:center;font-size:9px;color:#555;margin-top:2px;">COALITION BALANCE</div>'
                f'</div>'
            )

        countdown_html = ""
        end_str = st.session_state.mission_end_time
        if end_str:
            try:
                from datetime import datetime, timezone
                import re as _re
                end_clean = _re.sub(r'(\.\d{6})\d*Z?$', r'\1', end_str.rstrip('Z'))
                end_dt    = datetime.strptime(end_clean, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
                restante  = (end_dt - datetime.now(timezone.utc)).total_seconds()
                if restante > 0:
                    hh  = int(restante // 3600)
                    mm  = int((restante % 3600) // 60)
                    ss  = int(restante % 60)
                    cor = "#ffcc00" if restante > 1800 else ("#ff8800" if restante > 600 else "#ff3333")
                    countdown_html = (
                        f'<div style="background:#0d1117;border:1px solid #333;border-radius:6px;padding:8px 6px;text-align:center;">'
                        f'<div style="color:#aaa;font-size:10px;letter-spacing:1.5px;font-weight:bold;margin-bottom:4px;">⏰ MISSION COUNTDOWN</div>'
                        f'<div style="font-size:34px;font-weight:900;font-family:monospace;color:{cor};letter-spacing:2px;line-height:1.1;">'
                        f'{hh:02d}:{mm:02d}:{ss:02d}</div></div>'
                    )
                else:
                    countdown_html = '<div style="color:#ff4444;text-align:center;padding:8px;">🔄 Servidor a reiniciar...</div>'
            except Exception:
                pass

        if pilots_html or countdown_html:
            st.markdown(
                f'<div style="font-family:sans-serif;">{pilots_html}{countdown_html}</div>',
                unsafe_allow_html=True
            )

    sidebar_countdown()

st.title("🛩️ Painel Tático C4ISR")

# ── PLAYER FMC STICKY — aparece logo abaixo do título em todas as abas ──
if st.session_state.get('cronometro_rodando') and st.session_state.get('navlog_manual'):

    # Calcula pernas a partir do session_state
    _w_dir   = float(st.session_state.get('vento_dir_cb', 45.0))
    _w_spd   = float(st.session_state.get('vento_vel_cb', 5.0) * 3.6)
    _nav_tas = float(st.session_state.get('vel_calc', 320))
    _pernas_top = []
    for _i, _ln in enumerate(st.session_state.navlog_manual):
        try:
            _d   = float(_ln.get("Distância (km)", 0.0))
            _tc  = float(_ln.get("Rumo (TC)", 0.0))
            _wa  = math.radians(_w_dir - _tc)
            _swca = max(-1.0, min(1.0, (_w_spd * math.sin(_wa)) / _nav_tas))
            _wca  = math.degrees(math.asin(_swca))
            _th   = (_tc + _wca + 360) % 360
            _gs   = max(1.0, (_nav_tas * math.cos(math.radians(_wca))) - (_w_spd * math.cos(_wa)))
            _pernas_top.append({"nome": _ln.get("Perna", f"WP{_i}"), "proa": _th,
                                "tempo": (_d / _gs) * 3600})
        except: continue

    # CSS: barra com borda colorida, compacta, sem scroll
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlock"]:has(> div > div[data-testid="stHorizontalBlock"].fmc-bar) {
            position: sticky; top: 0; z-index: 999;
        }
        </style>
    """, unsafe_allow_html=True)

    @st.fragment(run_every="1s")
    def fmc_top_bar():
        _idx = st.session_state.index_perna_ativa
        total_pernas = len(_pernas_top)

        if _idx < total_pernas:
            _p = _pernas_top[_idx]

            # Calcula tempo restante
            _restante_str = "--:--"
            _prog = 0.0
            if st.session_state.tempo_inicio_perna:
                _passado  = time.time() - st.session_state.tempo_inicio_perna
                _restante = max(0.0, _p['tempo'] - _passado)
                _m, _s    = divmod(int(_restante), 60)
                _restante_str = f"{_m:02d}:{_s:02d}"
                _prog = min(1.0, _passado / max(_p['tempo'], 1))

            # Layout da barra: proa grande | nome+timer | botões
            st.markdown(f"""
                <div style="
                    background: linear-gradient(90deg, #1a2a1a 0%, #0e1117 100%);
                    border: 1px solid #2a5a2a;
                    border-left: 4px solid #44cc44;
                    border-radius: 8px;
                    padding: 10px 16px;
                    margin-bottom: 8px;
                    display: flex;
                    align-items: center;
                    gap: 24px;
                ">
                    <div style="font-size:13px; color:#888; min-width:80px;">🚀 FMC ATIVO</div>
                    <div style="font-size:36px; font-weight:900; color:#44ff44; min-width:90px; line-height:1;">
                        {_p['proa']:.0f}°
                    </div>
                    <div>
                        <div style="font-size:13px; color:#aaa;">📍 {_p['nome']}</div>
                        <div style="font-size:22px; font-weight:bold; color:#fff; font-family:monospace;">⏱️ {_restante_str}</div>
                    </div>
                    <div style="font-size:12px; color:#666; margin-left:auto;">
                        Perna {_idx+1}/{total_pernas}
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Barra de progresso da perna
            st.progress(_prog)

            # Botões em linha
            b1, b2, b3, _spacer = st.columns([1, 1, 1, 5])
            with b1:
                if st.button("⏭️ NEXT", use_container_width=True, key="top_next"):
                    st.session_state.index_perna_ativa += 1
                    st.session_state.tempo_inicio_perna = time.time()
                    st.rerun()
            with b2:
                if st.button("⏹️ STOP", use_container_width=True, key="top_stop"):
                    st.session_state.cronometro_rodando           = False
                    st.session_state.index_perna_ativa            = 0
                    st.session_state.tempo_inicio_missao_absoluto = None
                    st.rerun()
            with b3:
                # Mostra perna seguinte como dica
                if _idx + 1 < total_pernas:
                    _prox = _pernas_top[_idx + 1]
                    st.caption(f"Próx: {_prox['proa']:.0f}°")
        else:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.success("🏁 **Missão Concluída!** Objetivo Atingido.")
            with c2:
                if st.button("🔄 Reset", use_container_width=True, key="top_reset"):
                    st.session_state.cronometro_rodando           = False
                    st.session_state.index_perna_ativa            = 0
                    st.session_state.tempo_inicio_missao_absoluto = None
                    st.rerun()

    fmc_top_bar()
    st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Hangar", "🎯 Lotfe 7", "🧮 NavLog & E6B", "🚀 FMC (Ativo)", "🌐 Inteligência", "🗺️ Mapa"])

# ==========================================
# ABA 1: HANGAR (LOGÍSTICA E PREPARAÇÃO)
# ==========================================
with tab1:
    st.header("🛠️ Configuração de Carga e Rota")
    
    # --- Seção de Importação ---
    col_f, col_clear = st.columns([3, 1])
    with col_f: 
        arquivo_plano = st.file_uploader("📥 Importar Plano de Voo (.json)", type=["json"])
        
        if arquivo_plano is not None:
            file_content = arquivo_plano.getvalue()
            current_hash = hash(file_content)
            
            if st.session_state.get('last_file_hash') != current_hash:
                st.session_state.last_file_hash = current_hash
                try:
                    dados_plano = json.loads(file_content)
                    if "routes" in dados_plano:
                        # Usa isFlightPlan=true (não routes[0] que pode ser linha de frente)
                        plano = next((r for r in dados_plano["routes"] if r.get("isFlightPlan")), None)
                        if plano is None:
                            st.error("❌ Nenhuma rota de plano de voo encontrada. Marque uma rota como 'Flight Plan' no Mission Planner.")
                        else:
                            coords    = plano["latLngs"]
                            speeds    = plano.get("speeds", [])
                            altitudes = plano.get("altitudes", [])

                            # Detecta unidades do plano (imperial = mph/ft, metric = km/h/m)
                            is_imperial = dados_plano.get("units", "metric").lower() == "imperial"
                            dist_factor = 2.4796 if is_imperial else 3.872

                            navlog_temp = []
                            dist_total  = 0.0
                            for i in range(len(coords) - 1):
                                dlng = coords[i+1]['lng'] - coords[i]['lng']
                                dlat = coords[i+1]['lat'] - coords[i]['lat']
                                rumo = (math.degrees(math.atan2(dlng, dlat)) + 360) % 360
                                dist = math.sqrt(dlng**2 + dlat**2) * dist_factor  # sempre km

                                dist_total += dist

                                # Velocidade: converte mph→km/h se imperial
                                vel_raw = int(speeds[i]) if i < len(speeds) else int(plano.get("speed", 330))
                                vel_p   = round(vel_raw * 1.60934) if is_imperial else vel_raw

                                # Altitude: converte ft→m se imperial
                                alt_raw = int(altitudes[i+1]) if i+1 < len(altitudes) else int(plano.get("altitude", 2000))
                                alt_p   = round(alt_raw * 0.3048) if is_imperial else alt_raw

                                navlog_temp.append({
                                    "Perna":          f"WP{i}➔WP{i+1}",
                                    "Distância (km)": round(dist, 1),
                                    "Rumo (TC)":      round(rumo, 0),
                                    "TAS (km/h)":     vel_p,
                                    "Altitude (m)":   alt_p
                                })
                            st.session_state.navlog_manual = navlog_temp
                            st.session_state.dist_calc     = dist_total
                            if navlog_temp:
                                st.session_state.vel_calc = float(navlog_temp[0]["TAS (km/h)"])
                            unidade_txt = "imperial (mph/ft→km/h/m)" if is_imperial else "metric"
                            st.success(f"✅ {len(navlog_temp)} pernas de '{plano.get('name','Rota')}' [{unidade_txt}] → NavLog atualizado!")
                    else:
                        st.session_state.navlog_manual = dados_plano
                        st.session_state.dist_calc = sum(item.get("Distância (km)", 0) for item in dados_plano)
                        st.success("✅ Rota carregada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo JSON: {e}")
            
    with col_clear:
        if st.button("🗑️ Reset Rota", use_container_width=True): 
            st.session_state.navlog_manual = []
            st.session_state.dist_calc = 100.0
            st.rerun()

    st.divider()
    
    # --- Seleção de Avião e Pesos ---
    c1, c2 = st.columns(2)
    with c1:
        av_nome = st.selectbox("Selecione a Aeronave", list(db_avioes.keys()))
        st.session_state.av_nome_selecionado = av_nome  # salva para o FMC
        av = db_avioes[av_nome]
        
        missao_dist = st.number_input("Distância da Missão (km)", value=float(st.session_state.get('dist_calc', 100.0)))
        missao_vel = st.number_input("Velocidade de Cruzeiro (km/h)", value=float(av['vel_cruzeiro_padrao']))
        margem_seg = st.slider("Reserva de Combustível (%)", 0, 100, 30)
    
    with c2:
        mod_sel = st.selectbox("Modificações", list(av['modificacoes'].keys()))
        bomb_sel = st.selectbox("Carga de Bombas", list(av['presets_bombas'].keys()))
        st.caption(f"🛡️ Armamento Fixo: {av.get('armamento_fixo', 'Não listado')}")
        
    # --- Cálculos Logísticos ---
    if missao_vel > 0:
        tempo_estimado = (missao_dist / missao_vel) * 60
        comb_l = tempo_estimado * av['consumo_l_min'] * (1 + (margem_seg / 100))
        peso_total = av['peso_base_sem_combustivel'] + av['modificacoes'][mod_sel] + av['presets_bombas'][bomb_sel] + (comb_l * 0.72)
        
        st.divider()
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            if peso_total <= av['peso_max']:
                st.success(f"⚖️ Peso Total: **{peso_total:.0f} kg** / {av['peso_max']} kg")
            else:
                st.error(f"⚠️ SOBRECARGA: **{peso_total:.0f} kg** / {av['peso_max']} kg")
        with col_res2:
            if comb_l > av['tanque_max_l']:
                st.error(f"⛽ Combustível: **{comb_l:.0f} L** ⚠️ EXCEDE TANQUE ({av['tanque_max_l']} L)")
            else:
                st.info(f"⛽ Combustível: **{comb_l:.0f} L** / {av['tanque_max_l']} L")
        with col_res3:
            st.info(f"⏱️ Tempo estimado: **{tempo_estimado:.0f} min** ({tempo_estimado/60:.1f}h)")
        
# ==========================================
# ABA 2: CONFIGURAÇÃO DA MIRA (LOFTE 7)
# ==========================================
with tab2:
    st.markdown("""
        <style>
            .stSlider [data-baseweb="slider"] { height: 45px; }
            .stSlider [data-baseweb="thumb"] { height: 40px; width: 40px; background-color: #FF4B4B; }
            .stMetric { background-color: #1e2124; padding: 15px; border-radius: 10px; border: 1px solid #444; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🎯 Ajuste de Vento da Mira (Lofte 7)")
    st.caption("Calcule os parâmetros de entrada do Lofte 7 a partir da proa e vento.")

    usar_api_vento = False
    if st.session_state.dados_campanha:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            usar_api_vento = st.button("🌬️ Usar Vento da API")
        with col_info:
            st.caption(f"API atual: {st.session_state.vento_vel_cb} m/s de {st.session_state.vento_dir_cb:.0f}°")

    phead  = st.slider("🧭 PLANE HEADING (°)",      0, 359,
                       value=0, step=1, key="phdg_lofte")
    whead_def  = int(st.session_state.vento_dir_cb) if usar_api_vento else 0
    wspd_def   = int(st.session_state.vento_vel_cb) if usar_api_vento else 0
    whead  = st.slider("🌬️ WIND DIRECTION (FROM °)", 0, 359,
                       value=whead_def, step=1, key="whdg_lofte")
    wspeed = st.slider("💨 WIND SPEED (m/s)",         0, 30,
                       value=wspd_def,  step=1, key="wspeed_lofte")

    # Fórmula signed -179/+180 (igual ao site spiff.ddns.net/il2bcalc/)
    raw_hdg        = (whead - phead) % 360
    sight_wind_hdg = raw_hdg if raw_hdg <= 180 else raw_hdg - 360
    sight_wind_speed = wspeed

    st.divider()
    res1, res2 = st.columns(2)
    with res1:
        st.metric(label="× Sight Wind Hdg",   value=f"{sight_wind_hdg:+d}°")
        st.caption("Gire o seletor de direção na mira para este valor.")
    with res2:
        st.metric(label="× Sight Wind Speed", value=f"{sight_wind_speed} m/s")
        st.caption("Ajuste a força do vento na engrenagem da mira.")

    if sight_wind_speed > 0:
        direcao_txt = "DIREITA ➡️" if sight_wind_hdg > 0 else ("ESQUERDA ⬅️" if sight_wind_hdg < 0 else "FRONTAL ⬆️")
        st.info(f"💡 Configure sua mira com **{sight_wind_hdg:+d}°** ({direcao_txt}) e **{sight_wind_speed} m/s** antes do bomb run.")
# ==========================================
# ABA 3: E6B & NAVLOG HÍBRIDO (ATUALIZADA)
# ==========================================
with tab3:
    st.header("🗺️ Centro de Navegação")
    st.caption("📥 Importe o plano de voo na **Aba 1 (Hangar)** para preencher o NavLog automaticamente.")

    st.divider()

    # --- INPUTS DO VENTO ---
    c_tas, c_dir, c_vel = st.columns(3)
    with c_tas:
        # Pega a velocidade da primeira perna se existir
        def_tas = float(st.session_state.navlog_manual[0].get("TAS (km/h)", st.session_state.vel_calc)) if st.session_state.navlog_manual else float(st.session_state.vel_calc)
        nav_tas = st.number_input("Sua TAS esperada (km/h)", value=def_tas, step=10.0)
    with c_dir:
        nav_w_dir = st.number_input("Vento vindo DE (°)", value=float(st.session_state.vento_dir_cb), key="nav_dir_e6b")
    with c_vel:
        nav_w_spd = st.number_input("Vel. Vento (km/h)", value=float(st.session_state.vento_vel_cb * 3.6), step=5.0, key="nav_spd_e6b")

    # --- NAVLOG EDITÁVEL ---
    st.subheader("📝 Navigation Log (Diário de Rota)")
    navlog_editado = st.data_editor(
        st.session_state.navlog_manual, 
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Perna": st.column_config.TextColumn("Nome da Perna"),
            "Distância (km)": st.column_config.NumberColumn("Distância (km)", format="%.1f"),
            "Rumo (TC)": st.column_config.NumberColumn("Rumo Mapa (TC °)", format="%.0f"),
            "TAS (km/h)": st.column_config.NumberColumn("TAS (km/h)"),
            "Altitude (m)": st.column_config.NumberColumn("Altitude (m)")
        }
    )
    st.session_state.navlog_manual = navlog_editado
    
    if len(navlog_editado) > 0:
        resultados_finais = []
        for linha in navlog_editado:
            try:
                dist = float(linha.get("Distância (km)", 0.0))
                tc_deg = float(linha.get("Rumo (TC)", 0.0))
            except:
                dist, tc_deg = 0.0, 0.0
                
            nome_perna = linha.get("Perna", "N/D")
            
            if dist > 0:
                wa_rad = math.radians(nav_w_dir - tc_deg)
                try:
                    sin_wca = max(-1.0, min(1.0, (nav_w_spd * math.sin(wa_rad)) / nav_tas))
                    wca_deg = math.degrees(math.asin(sin_wca))
                except: wca_deg = 0.0

                th_deg = (tc_deg + wca_deg + 360) % 360
                gs_leg = (nav_tas * math.cos(math.radians(wca_deg))) - (nav_w_spd * math.cos(wa_rad))
                gs_leg = max(1.0, gs_leg)
                
                tempo_min = (dist / gs_leg) * 60
                
                resultados_finais.append({
                    "📍 Perna": nome_perna,
                    "🗺️ Rumo Mapa": f"{tc_deg:.0f}°",
                    "🧭 Voar PROA (TH)": f"{th_deg:.0f}°",
                    "💨 Vel. Solo (GS)": f"{gs_leg:.0f} km/h",
                    "⏱️ Tempo Voo": f"{tempo_min:.1f} min"
                })
        
        if resultados_finais:
            st.table(resultados_finais)

    st.divider()

    # --- A FERRAMENTA (E6B) ---
    st.subheader("🧮 Computador E6B (Cálculos de Bordo)")
    col_tsd, col_conv = st.columns(2)
    
    with col_tsd:
        st.markdown("**⏱️ Tempo, Velocidade, Distância (TSD)**")
        modo_tsd = st.radio("Calcular:", ["Tempo", "Distância", "Velocidade (GS)"], horizontal=True)
        if modo_tsd == "Tempo":
            d_in = st.number_input("Distância (km)", value=50.0, key="d_t")
            v_in = st.number_input("Velocidade (km/h)", value=300.0, key="v_t")
            if v_in > 0: st.info(f"**Resultado:** {(d_in/v_in)*60:.1f} minutos")
        elif modo_tsd == "Distância":
            t_in = st.number_input("Tempo (min)", value=10.0, key="t_d")
            v_in = st.number_input("Velocidade (km/h)", value=300.0, key="v_d")
            st.info(f"**Resultado:** {v_in*(t_in/60):.1f} km")
        else:
            d_in = st.number_input("Distância (km)", value=50.0, key="d_v")
            t_in = st.number_input("Tempo (min)", value=10.0, key="t_v")
            if t_in > 0: st.info(f"**Resultado:** {d_in/(t_in/60):.0f} km/h")
            
    with col_conv:
        st.markdown("**🔄 Conversões Imperiais**")
        cat_conv = st.selectbox("Unidade:", ["Velocidade (km/h ↔ mph)", "Altitude (metros ↔ pés)"])
        val_conv = st.number_input("Valor:", value=1000.0 if "Altitude" in cat_conv else 300.0)
        
        if "Velocidade" in cat_conv:
            st.warning(f"**{val_conv} km/h** = {val_conv / 1.60934:.0f} mph")
            st.warning(f"**{val_conv} mph** = {val_conv * 1.60934:.0f} km/h")
        else:
            st.warning(f"**{val_conv} metros** = {val_conv * 3.28084:.0f} pés")
            st.warning(f"**{val_conv} pés** = {val_conv / 3.28084:.0f} metros")


# ==========================================
# ABA 4: FMC (LISTA DEFINITIVA DO DB)
# ==========================================
with tab4:
    st.header("🚀 Flight Management Computer")
    
    # 1. VALIDAÇÃO DE ROTA
    if not st.session_state.get('navlog_manual'):
        st.info("⚠️ Configure uma rota na Aba 1 ou Aba 3 para ativar o FMC.")
    else:
        # 2. FONTE DE DADOS DEFINITIVA (SEU DB)
        # Ordenamos a lista alfabeticamente para facilitar a busca
        lista_aerodromos_db = sorted(list(db_altitudes_tecnico.keys()))

        # 3. INTERFACE DE SELEÇÃO
        with st.expander("🌍 Configuração de Aeródromos (DB Interno)", expanded=True):
            col_dep, col_arr = st.columns(2)
            
            with col_dep:
                # Agora o menu usa estritamente a sua lista do DB
                base_dep = st.selectbox("Decolagem de:", lista_aerodromos_db, key="fmc_dep_estatico")
                alt_dep = db_altitudes_tecnico[base_dep] # Acesso direto, sem fallback necessário
                st.write(f"**Altitude Base:** {alt_dep}m")
                
            with col_arr:
                base_arr = st.selectbox("Destino Final:", lista_aerodromos_db, key="fmc_arr_estatico")
                alt_arr = db_altitudes_tecnico[base_arr]
                st.write(f"**Altitude Alvo:** {alt_arr}m")

        # 4. PERFORMANCE VERTICAL (VNAV)
        av_nome = st.session_state.get('av_nome_selecionado', "He-111 H-16")
        av = db_avioes.get(av_nome, {})

        with st.expander("📈 Perfil de Voo", expanded=True):
            v1, v2, v3, v4 = st.columns(4)
            with v1: alt_cruzeiro = st.number_input("Cruzeiro (m)", value=4000, step=500)
            with v2: climb_rate = st.number_input("Subida (m/s)", value=float(av.get('climb_rate_default', 2.5)))
            with v3: descent_rate = st.number_input("Descida (m/s)", value=float(av.get('descent_rate_default', 4.0)))
            with v4: alt_pista = st.number_input("Alt. Aeródromo (m)", value=alt_arr)

        # --- CÁLCULO DE ROTA ---
        nav_tas = float(st.session_state.get('vel_calc', 320))
        w_dir = float(st.session_state.get('vento_dir_cb', 45.0))
        w_spd = float(st.session_state.get('vento_vel_cb', 5.0) * 3.6)
        
        pernas_fmc = []
        dist_acum = 0
        for idx, linha in enumerate(st.session_state.navlog_manual):
            try:
                dist = float(linha.get("Distância (km)", 0.0))
                tc = float(linha.get("Rumo (TC)", 0.0))
                wa_rad = math.radians(w_dir - tc)
                sin_wca = max(-1.0, min(1.0, (w_spd * math.sin(wa_rad)) / nav_tas))
                wca = math.degrees(math.asin(sin_wca))
                th = (tc + wca + 360) % 360
                gs = max(1.0, (nav_tas * math.cos(math.radians(wca))) - (w_spd * math.cos(wa_rad)))
                tempo = (dist / gs) * 3600
                dist_acum += dist
                pernas_fmc.append({"id": idx, "nome": linha.get("Perna", f"WP{idx}"), "proa": th, "tempo": tempo, "dist_total": dist_acum})
            except: continue

        # --- GRÁFICO VNAV ---
        total_km     = pernas_fmc[-1]['dist_total'] if pernas_fmc else 0.0
        dist_climb   = 0.0
        dist_descent = 0.0
        if pernas_fmc:
            dist_climb   = ((alt_cruzeiro - alt_dep) / max(climb_rate, 0.1))   * (nav_tas / 3600)
            dist_descent = ((alt_cruzeiro - alt_arr) / max(descent_rate, 0.1)) * (nav_tas / 3600)
            if dist_climb + dist_descent > total_km:
                f = total_km / (dist_climb + dist_descent)
                dist_climb *= f; dist_descent *= f
            df_vnav = pd.DataFrame({
                "Distância (km)": [0, dist_climb, max(dist_climb, total_km - dist_descent), total_km],
                "Altitude (m)":   [alt_dep, alt_cruzeiro, alt_cruzeiro, alt_arr]
            })
            st.area_chart(df_vnav.set_index("Distância (km)"))

        st.divider()

        # HUD de execução — definido UMA VEZ dentro do with tab4
        @st.fragment(run_every="1s")
        def fmc_hud_final():
            idx = st.session_state.index_perna_ativa
            if idx < len(pernas_fmc):
                p = pernas_fmc[idx]
                h1, h2, h3 = st.columns([2, 1, 1])
                with h1:
                    st.subheader(f"📍 Perna: {p['nome']}")
                    st.markdown(f"## 🧭 PROA: {p['proa']:.0f}°")
                with h2:
                    if st.session_state.cronometro_rodando and st.session_state.tempo_inicio_perna:
                        passado  = time.time() - st.session_state.tempo_inicio_perna
                        restante = max(0, p['tempo'] - passado)
                        m, s     = divmod(int(restante), 60)
                        st.metric("⏱️ Tempo WP", f"{m:02d}:{s:02d}")
                    else:
                        st.metric("⏱️ Tempo WP", "--:--")
                # VNAV em tempo real
                if st.session_state.cronometro_rodando and st.session_state.tempo_inicio_missao_absoluto:
                    tempo_seg       = time.time() - st.session_state.tempo_inicio_missao_absoluto
                    dist_percorrida = (tempo_seg / 3600) * nav_tas
                    dist_para_tod   = (total_km - dist_descent) - dist_percorrida
                    st.divider()
                    if 0 < dist_para_tod <= 10:
                        st.warning(f"📉 **PREPARAR DESCIDA:** TOD em {dist_para_tod:.1f} km")
                    elif dist_para_tod <= 0:
                        st.error(f"⬇️ **INICIAR DESCIDA!** Passou {abs(dist_para_tod):.1f} km do TOD")
                    else:
                        st.info(f"📊 Cruzeiro Estável. Descida em {dist_para_tod:.1f} km")
                with h3:
                    if not st.session_state.cronometro_rodando:
                        if st.button("▶️ START", use_container_width=True):
                            st.session_state.cronometro_rodando           = True
                            st.session_state.tempo_inicio_perna           = time.time()
                            st.session_state.tempo_inicio_missao_absoluto = time.time()
                            st.rerun()
                    else:
                        if st.button("⏭️ NEXT", use_container_width=True):
                            st.session_state.index_perna_ativa += 1
                            st.session_state.tempo_inicio_perna = time.time()
                            st.rerun()
            else:
                st.success("🏁 Objetivo Atingido!")
                if st.button("🔄 Reiniciar FMC"):
                    st.session_state.index_perna_ativa            = 0
                    st.session_state.cronometro_rodando           = False
                    st.session_state.tempo_inicio_missao_absoluto = None
                    st.rerun()

        fmc_hud_final()

# ==========================================
# ABA 5: INTELIGÊNCIA TÁTICA (C4ISR)
# ==========================================
with tab5:
    st.header("🌐 Inteligência Tática e Logística (C4ISR)")
    
    if not st.session_state.get('dados_campanha'):
        st.warning("📡 Aguardando sincronização com o servidor do Combat Box...")
    else:
        dados = st.session_state.dados_campanha
        airfields = dados.get('Airfields', [])
        
        # --- 1. BRIEFING DO COMANDO ---
        st.subheader("📜 Relatórios de Operações")
        texto_hoje = dados.get('CurrentDayStateDescription', '')
        if texto_hoje:
            st.info(f"**Briefing do Dia:**\n\n{traduzir_texto(texto_hoje)}")
        
        with st.expander("Ver Resumo das Operações Anteriores"):
            texto_ontem = dados.get('PreviousDaysEventsDescription', '')
            st.write(traduzir_texto(texto_ontem) if texto_ontem else "Sem registros adicionais.")
        
        st.divider()

        # --- 2. FUNÇÕES DE FILTRAGEM (TAG: ActiveToday) ---
        def filtrar_bases_por_atividade(lista, coalizao_alvo):
            resultado = []
            for b in lista:
                # Normalização de Coalizão
                b_coal = str(b.get('Coalition', '')).strip().lower()
                alvos = [c.lower() for c in coalizao_alvo]
                
                if b_coal in alvos:
                    # A TAG MESTRE ENCONTRADA POR VOCÊ:
                    is_active = b.get('ActiveToday')
                    
                    # Verificação robusta (funciona se for booleano ou string do JSON)
                    if str(is_active).lower() in ['true', '1']:
                        resultado.append(b)
            return resultado

        def render_hangar_logic(base):
            hangar = base.get('AvailableAirframes', [])
            if hangar:
                st.caption("Aeronaves em Hangar:")
                for av in hangar:
                    tipo = av.get('Type', 'Aeronave')
                    qtd = int(av.get('NumberAvailable', 0))
                    # REGRA TÉCNICA: -1 significa UNLIMITED
                    txt_qtd = "♾️ ILIMITADO" if qtd == -1 else f"{qtd} unid."
                    st.write(f"- {tipo}: **{txt_qtd}**")
            else:
                st.write("Sem estoque de aeronaves.")

        # --- 3. EXECUÇÃO ---
        aliados_ativos = filtrar_bases_por_atividade(airfields, ['Allies', 'Allied'])
        eixo_ativos = filtrar_bases_por_atividade(airfields, ['Axis'])

        # --- 4. EXIBIÇÃO DE AERÓDROMOS (COLUNAS) ---
        st.subheader(f"🛫 Bases Ativas na Missão: {len(aliados_ativos) + len(eixo_ativos)}")
        
        col_all_b, col_ax_b = st.columns(2)

        with col_all_b:
            st.markdown("### 🔵 Allies Active Bases")
            if not aliados_ativos: st.caption("Nenhuma base aliada ativa hoje.")
            for b in aliados_ativos:
                nome = b.get('Name')
                sup = b.get('SupplyLevel', 0)
                with st.expander(f"📍 {nome} ({sup}/200)"):
                    st.progress(min(1.0, sup / 200.0))
                    st.write(f"**Superfície:** {'🛣️ Concreto' if b.get('RunwayIsConcrete') else '🌱 Grama'}")
                    render_hangar_logic(b)

        with col_ax_b:
            st.markdown("### 🔴 Axis Active Bases")
            if not eixo_ativos: st.error("⚠️ Nenhuma base operacional do Eixo detectada.")
            for b in eixo_ativos:
                nome = b.get('Name')
                sup = b.get('SupplyLevel', 0)
                alerta = "🚨 " if sup < 20 else ""
                with st.expander(f"{alerta}📍 {nome} ({sup}/200)"):
                    st.progress(min(1.0, sup / 200.0))
                    st.write(f"**Superfície:** {'🛣️ Concreto' if b.get('RunwayIsConcrete') else '🌱 Grama'}")
                    render_hangar_logic(b)

        st.divider()

        # --- 5. OBJETIVOS ESTRATÉGICOS (SEPARADOS) ---
        st.subheader("🎯 Objetivos e Alvos Prioritários")
        objetivos = [o for o in dados.get('Objectives', []) if o.get('ActiveToday')]
        
        col_all_obj, col_ax_obj = st.columns(2)

        with col_all_obj:
            st.markdown("### 🔵 Allies Targets")
            allies_o = [o for o in objetivos if str(o.get('Coalition', '')).lower() in ['allies', 'allied']]
            for o in allies_o:
                st.markdown(f":blue[🎯 **{o.get('Name')}**]")
                st.caption(traduzir_texto(o.get('Description', '')))

        with col_ax_obj:
            st.markdown("### 🔴 Axis Targets")
            axis_o = [o for o in objetivos if str(o.get('Coalition', '')).lower() == 'axis']
            for o in axis_o:
                st.markdown(f":red[🎯 **{o.get('Name')}**]")
                st.caption(traduzir_texto(o.get('Description', '')))
# ==========================================
# ABA 6: MAPA TÁTICO (IL-2 MISSION PLANNER)
# ==========================================
with tab6:

    MAP_URL = (
        "https://serverror.github.io/IL2-Mission-Planner/"
        "#json-url=https://campaign-data.combatbox.net/"
        "rhineland-campaign/rhineland-campaign-mission-planner-latest.json.aspx"
    )

    # Botão para abrir em nova aba
    st.markdown(
        f'<div style="margin-bottom:5px;">'
        f'<a href="{MAP_URL}" target="_blank" '
        f'style="display:inline-block;padding:4px 12px;background:#1a3a1a;'
        f'border:1px solid #2a6a2a;border-radius:5px;color:#88ff88;'
        f'text-decoration:none;font-size:12px;">🔗 Abrir em nova aba</a>'
        f'<span style="margin-left:10px;font-size:11px;color:#555;">'
        f'Linha de frente ao vivo · Bases · Objetivos</span></div>',
        unsafe_allow_html=True
    )

    # Apenas remove padding lateral para o mapa ocupar toda a largura
    # NÃO bloqueia overflow globalmente (quebraria scroll das outras abas)
    st.markdown("""
        <style>
        .map-tab-active [data-testid="stMainBlockContainer"] {
            padding-left:  0 !important;
            padding-right: 0 !important;
            padding-bottom: 0 !important;
        }
        iframe[title="components.v1.html"] {
            display: block !important;
            margin: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # components.html executa JavaScript de verdade (st.markdown ignora <script>)
    # O iframe vive dentro deste componente — drag/pan/zoom são eventos internos
    # O JS usa window.parent para travar o scroll da página pai durante o drag
    components.html(
        f"""
        <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        html, body {{ width:100%; height:100%; background:#0e1117; overflow:hidden; }}
        #wrap {{
            position: relative;
            width: 100%;
            height: 100%;
            user-select: none;
        }}
        #mapframe {{
            display: block;
            border: none;
            width: 100%;
            height: 100%;
        }}
        #overlay {{
            display: none;
            position: absolute;
            inset: 0;
            z-index: 99;
            cursor: grabbing;
        }}
        </style>

        <div id="wrap">
            <iframe id="mapframe" src="{MAP_URL}" allow="fullscreen"></iframe>
            <div id="overlay"></div>
        </div>

        <script>
        (function() {{
            var overlay  = document.getElementById('overlay');
            var dragging = false;

            // Remove padding lateral do container pai para o mapa encostar nas bordas
            try {{
                var parentDoc = window.parent.document;
                var container = parentDoc.querySelector('[data-testid="stMainBlockContainer"]');
                if (container) {{
                    container.style.paddingLeft   = '0';
                    container.style.paddingRight  = '0';
                    container.style.paddingBottom = '0';
                }}
            }} catch(e) {{}}

            // Quando o componente for desmontado (troca de aba), restaura scroll e padding
            function restoreParent() {{
                try {{
                    window.parent.document.documentElement.style.overflow = '';
                    window.parent.document.body.style.overflow = '';
                    var container = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]');
                    if (container) {{
                        container.style.paddingLeft   = '';
                        container.style.paddingRight  = '';
                        container.style.paddingBottom = '';
                    }}
                }} catch(e) {{}}
            }}
            window.addEventListener('beforeunload', restoreParent);
            // MutationObserver: detecta remoção do iframe do DOM pai
            try {{
                var myIframe = window.frameElement;
                if (myIframe) {{
                    new MutationObserver(function() {{
                        if (!window.parent.document.contains(myIframe)) {{
                            restoreParent();
                        }}
                    }}).observe(window.parent.document.body, {{childList: true, subtree: true}});
                }}
            }} catch(e) {{}}

            function lockScroll() {{
                try {{
                    window.parent.document.documentElement.style.overflow = 'hidden';
                    window.parent.document.body.style.overflow = 'hidden';
                    window.parent.scrollTo(0, 0);
                }} catch(e) {{}}
            }}

            function unlockScroll() {{
                try {{
                    window.parent.document.documentElement.style.overflow = 'hidden';
                    window.parent.document.body.style.overflow = 'hidden';
                }} catch(e) {{}}
            }}

            document.getElementById('wrap').addEventListener('mousedown', function() {{
                dragging = true;
                overlay.style.display = 'block';
                lockScroll();
            }});

            window.addEventListener('mouseup', function() {{
                if (dragging) {{
                    dragging = false;
                    overlay.style.display = 'none';
                    unlockScroll();
                }}
            }});

            // Durante drag: se mouse sair do componente, mantém o lock
            window.parent.addEventListener('scroll', function() {{
                if (dragging) window.parent.scrollTo(0, 0);
            }}, true);

            // Bloqueia scroll inicial ao carregar o mapa
            lockScroll();
        }})();
        </script>
        """,
        height=860,
        scrolling=False
    )
