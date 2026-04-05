import streamlit as st
import streamlit.components.v1 as components
import json, math, re, time
import requests, pandas as pd
from bs4 import BeautifulSoup

# ==========================================
# 0. SESSION STATE
# ==========================================
if 'taw_status'       not in st.session_state: st.session_state.taw_status       = "A aguardar sincronização..."
if 'taw_dados'        not in st.session_state: st.session_state.taw_dados         = {}
if 'taw_vento_vel'    not in st.session_state: st.session_state.taw_vento_vel     = 1.0   # m/s superfície
if 'taw_vento_dir'    not in st.session_state: st.session_state.taw_vento_dir     = 0.0
if 'taw_temp'         not in st.session_state: st.session_state.taw_temp          = 15.0
if 'taw_pilots_allied' not in st.session_state: st.session_state.taw_pilots_allied = None
if 'taw_pilots_axis'   not in st.session_state: st.session_state.taw_pilots_axis   = None
if 'taw_elapsed_min'   not in st.session_state: st.session_state.taw_elapsed_min   = 0
if 'navlog_manual'    not in st.session_state:
    st.session_state.navlog_manual = [{"Perna": "Base ➔ Alvo", "Distância (km)": 50.0,
                                       "Rumo (TC)": 90.0, "TAS (km/h)": 450, "Altitude (m)": 3000}]
if 'index_perna_ativa'            not in st.session_state: st.session_state.index_perna_ativa            = 0
if 'cronometro_rodando'           not in st.session_state: st.session_state.cronometro_rodando           = False
if 'tempo_inicio_perna'           not in st.session_state: st.session_state.tempo_inicio_perna           = None
if 'tempo_inicio_missao_absoluto' not in st.session_state: st.session_state.tempo_inicio_missao_absoluto = None
if 'vel_calc'            not in st.session_state: st.session_state.vel_calc            = 450.0
if 'dist_calc'           not in st.session_state: st.session_state.dist_calc           = 100.0
if 'last_file_hash'      not in st.session_state: st.session_state.last_file_hash      = None
if 'av_nome_selecionado' not in st.session_state: st.session_state.av_nome_selecionado = "Bf 109 G-6"

HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

TRADUCOES = {
    'Stratocumulus Castellanus': 'Estratocumulo Castellanus',
    'Stratocumulus Cumuliformis': 'Estratocumulo Cumuliformis',
    'Stratocumulus': 'Estratocumulo',
    'Altostratus': 'Altostrato',
    'Altocumulus': 'Altocumulo',
    'Cumulonimbus': 'Cumulonimbo',
    'Cumulus': 'Cumulo',
    'Cirrostratus': 'Cirrostrato',
    'Nimbostratus': 'Nimbostrato',
    'Cirrus': 'Cirro',
    'Stratus': 'Estrato',
    'and': 'e',
    'Good Visibility': 'Boa visibilidade',
    'Good visibility': 'Boa visibilidade',
    'Moderate Visibility': 'Visibilidade moderada',
    'Moderate visibility': 'Visibilidade moderada',
    'Poor Visibility': 'Visibilidade fraca',
    'Poor visibility': 'Visibilidade fraca',
    'Low Visibility': 'Visibilidade baixa',
    'Low visibility': 'Visibilidade baixa',
    'Hazy': 'Nevoa seca',
    'Foggy': 'Nevoeiro',
    'Fog': 'Nevoeiro',
    'Mist': 'Neblina',
    'Clear': 'Limpo',
    'Smooth': 'Ar calmo',
    'Light Turbulence': 'Turbulencia leve',
    'Moderate Turbulence': 'Turbulencia moderada',
    'Severe Turbulence': 'Turbulencia severa',
    'No Precipitation': 'Sem precipitacao',
    'Light Rain': 'Chuva fraca',
    'Heavy Rain': 'Chuva forte',
    'Rain': 'Chuva',
    'Snow': 'Neve',
    'Drizzle': 'Garoa',
    'Hail': 'Granizo',
    'Road Condition: Dry': 'Pista: Seca',
    'Road Condition: Wet': 'Pista: Molhada',
    'Road Condition: Icy': 'Pista: Gelada',
    'Road Condition: Snowy': 'Pista: Nevada',
    'Dry': 'Seca',
    'Wet': 'Molhada',
    'Icy': 'Gelada',
    'Good': 'Boa',
    'Poor': 'Fraca',
    'Average': 'Média',
    'Excellent': 'Excelente',
}

def traduzir_meteo(texto):
    if not texto: return texto
    result = texto
    for en, pt in TRADUCOES.items():
        result = result.replace(en, pt)
    return result

# ==========================================
# 1. FUNÇÕES DE FETCH
# ==========================================
def fetch_taw_data():
    """Scraping completo da página principal do TAW — equivalente ao fetch_combatbox_data()."""
    try:
        r = requests.get("https://tacticalairwar.com/", headers=HDR, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        d = {}

        # Mapa e fase
        for h in soup.find_all('h2'):
            t = h.get_text(strip=True)
            if '#' in t and 'Top' not in t and 'Online' not in t:
                d['map_name'] = t
            elif any(x in t.lower() for x in ['offensive', 'defensive', 'neutral']):
                d['phase'] = t

        # Data, hora, meteorologia geral
        for tbl in soup.find_all('table'):
            txt = tbl.get_text()
            if 'Date:' in txt and 'Time:' in txt:
                for th in tbl.find_all('th'):
                    tv = th.get_text(strip=True)
                    if tv.startswith('Date:'): d['mission_date'] = tv.replace('Date:', '').strip()
                    if tv.startswith('Time:'): d['mission_time'] = tv.replace('Time:', '').strip()
                # Percorre cada linha da tabela meteorológica
                for tr in tbl.find_all('tr'):
                    tds = [td.get_text(strip=True) for td in tr.find_all('td')]
                    if not tds: continue
                    # Linha com 1 td — tipo de nuvem
                    if len(tds) == 1:
                        if not d.get('weather_desc') and tds[0]: d['weather_desc'] = tds[0]
                    # Linha com 2 tds — pode ser tipo de nuvem (sem ':') ou campo label
                    if len(tds) >= 2:
                        # Tipo de nuvem: primeiro td não vazio e sem ':' e sem keywords de campo
                        campo_keywords = ('Coverage','Cloud Base','Temp','QNH','Road',
                                          'Hazy','Good','Poor','Moderate','Low','Fog','Mist','Clear',
                                          'Smooth','Turbulence')
                        primeiro = tds[0]
                        if (not d.get('weather_desc') and primeiro
                                and ':' not in primeiro
                                and not any(k.lower() in primeiro.lower() for k in campo_keywords)):
                            d['weather_desc'] = primeiro
                        for td in tds:
                            if 'Temp:' in td:           d['temp']          = td.replace('Temp:', '').strip()
                            if 'QNH:' in td:            d['qnh']           = td.replace('QNH:', '').strip()
                            if 'Coverage:' in td:       d['cloud_cover']   = td.replace('Coverage:', '').strip()
                            if 'Cloud Base:' in td:     d['cloud_base']    = td.replace('Cloud Base:', '').strip()
                            if 'Road Condition:' in td: d['road']          = td.replace('Road Condition:', '').strip()
                            # Precipitação — captura qualquer td que contenha "Precipitation" ou "Rain" ou "Snow"
                            td_l = td.lower()
                            if any(x in td_l for x in ['precipitation', 'rain', 'snow', 'drizzle', 'hail']):
                                d['precipitation'] = td.strip()
                            if any(x in td_l for x in ['hazy','good visibility','poor visibility','moderate visibility','low visibility','fog','mist','clear']):
                                d['visibility'] = td.strip()
                            if any(x in td_l for x in ['smooth','light turbulence','moderate turbulence','severe turbulence']):
                                d['turbulence'] = td.strip()

            # Vento por altitude (8 níveis)
            if 'Wind Data' in txt:
                wind_rows = []
                for tr in tbl.find_all('tr')[1:]:
                    tds = [td.get_text(strip=True) for td in tr.find_all('td')]
                    if len(tds) >= 3:
                        dir_clean = re.sub(r'[^\d°]', '', tds[1]).strip()
                        wind_rows.append({"Alt": tds[0], "Dir": dir_clean, "Vel": tds[2]})
                if wind_rows:
                    d['wind_data'] = wind_rows
                    try:
                        dir_num = float(re.sub(r'[^\d]', '', wind_rows[0]['Dir']) or '0')
                        vel_num = float(wind_rows[0]['Vel'].replace('m/s', '').strip())
                        st.session_state.taw_vento_dir = dir_num
                        st.session_state.taw_vento_vel = vel_num
                    except: pass

            # Previsão 6 dias — thead com datas, tbody row1 = ícones img, row2 = temperaturas
            ths = tbl.find_all('th')
            th_texts = [th.get_text(strip=True) for th in ths]
            if sum(1 for t in th_texts if re.match(r'\d{2}\.\d{2}\.\d{4}', t)) >= 3:
                tbody = tbl.find('tbody')
                if tbody:
                    all_trs = tbody.find_all('tr')
                    # row 0: ícones (img src com nome do ficheiro)
                    # row 1: temperaturas
                    icon_row = all_trs[0].find_all('td') if len(all_trs) > 0 else []
                    temp_row = all_trs[1].find_all('td') if len(all_trs) > 1 else []
                    # mapa nome_ficheiro → emoji + descrição
                    CLOUD_MAP = {
                        'clouds_clear':              ('☀️', 'Céu limpo'),
                        'clouds_few':                ('🌤️', 'Poucas nuvens'),
                        'clouds_scattered':          ('⛅', 'Nuvens dispersas'),
                        'clouds_broken':             ('🌥️', 'Nublado'),
                        'clouds_overcast':           ('☁️', 'Encoberto'),
                        'clouds_few_rain':           ('🌦️', 'Pancadas isoladas'),
                        'clouds_scattered_rain':     ('🌧️', 'Chuva'),
                        'clouds_broken_rain':        ('🌧️', 'Chuva moderada'),
                        'clouds_overcast_rain':      ('🌧️', 'Chuva forte'),
                        'clouds_broken_rain_noFly':  ('⛈️', 'Tempestade — NÃO VOAR'),
                        'clouds_few_rain_noFly':     ('⛈️', 'Tempestade — NÃO VOAR'),
                        'clouds_scattered_rain_noFly': ('⛈️', 'Tempestade — NÃO VOAR'),
                        'clouds_snow':               ('🌨️', 'Neve'),
                        'fog':                       ('🌫️', 'Nevoeiro'),
                    }
                    forecast = []
                    for i, dt_str in enumerate(th_texts):
                        temp = temp_row[i].get_text(strip=True) if i < len(temp_row) else '—'
                        emoji, desc = '❓', ''
                        if i < len(icon_row):
                            img = icon_row[i].find('img')
                            if img:
                                src = img.get('src', '')
                                fname = src.split('/')[-1].replace('.png','').replace('.jpg','')
                                for key, val in CLOUD_MAP.items():
                                    if key in fname:
                                        emoji, desc = val
                                        break
                        forecast.append({'date': dt_str, 'temp': temp, 'emoji': emoji, 'desc': desc})
                    if forecast:
                        d['forecast'] = forecast

        # Seções HTML → dicts
        SECTIONS = {
            'Allied frontline airfields': 'allied_airfields',
            'Axis frontline airfields':   'axis_airfields',
            'Allied frontline cities':    'allied_cities',
            'Axis frontline cities':      'axis_cities',
            'Allied depots':              'allied_depots',
            'Axis depots':                'axis_depots',
            'Allied Losses':              'allied_losses',
            'Axis Losses':                'axis_losses',
        }
        for label, key in SECTIONS.items():
            tag = soup.find(lambda t: t.name in ['h2', 'h3'] and label in t.get_text())
            if tag:
                tbl = tag.find_next('table')
                if tbl:
                    headers = [th.get_text(strip=True) for th in tbl.find_all('th')]
                    rows = []
                    # Salta a primeira linha só se existirem headers (linha de cabeçalho)
                    # Sem headers (como nas tabelas de Losses), começa do índice 0
                    start = 1 if headers else 0
                    for tr in tbl.find_all('tr')[start:]:
                        tds = [td.get_text(strip=True) for td in tr.find_all('td')]
                        if tds:
                            rows.append(dict(zip(headers, tds)) if headers else tds)
                    d[key] = rows

        # Top pilotos e esquadrões
        tops = {}
        for h in soup.find_all(['h2', 'h3']):
            txt = h.get_text(strip=True)
            if 'Top 3' in txt:
                tbl = h.find_next('table')
                if tbl:
                    rows = []
                    for tr in tbl.find_all('tr')[1:]:
                        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                        if any(cells): rows.append(cells)
                    if rows: tops[txt] = rows
        d['top_stats'] = tops

        # Pilotos online com coalizão (ícone usaf-star = Allied, balkenkreuz = Axis)
        section = soup.find(lambda t: t.name in ['h2', 'h3'] and 'Online Players' in t.get_text())
        if section:
            tbl = section.find_next('table')
            if tbl:
                players = []
                for tr in tbl.find_all('tr')[1:]:
                    tds = tr.find_all('td')
                    if len(tds) >= 3:
                        name = tds[2].get_text(strip=True)
                        img  = tds[1].find('img')
                        side = 'axis' if img and 'balkenkreuz' in str(img) else 'allied'
                        players.append({'name': name, 'side': side})
                d['online_players'] = players

        st.session_state.taw_dados  = d
        st.session_state.taw_status = "✅ TAW Sincronizado"
        try: st.session_state.taw_temp = float(re.sub(r'[^-\d.]', '', d.get('temp', '15')))
        except: pass

    except Exception as e:
        st.session_state.taw_status = f"❌ Erro: {e}"


def fetch_taw_time():
    """time.php → elapsed + pilotos Allied/Axis — equivalente ao fetch_pilots_online()."""
    try:
        ts = int(time.time() * 1000)
        r  = requests.get(f"https://tacticalairwar.com/time.php?_={ts}", headers=HDR, timeout=5)
        r.raise_for_status()
        m = re.search(r'Elapsed:\s*(\d+)h\s*(\d+)m', r.text)
        if m:
            st.session_state.taw_elapsed_min = int(m.group(1)) * 60 + int(m.group(2))
        nums = re.findall(r'<tbody>\s*(\d+)', r.text)
        if len(nums) >= 2:
            st.session_state.taw_pilots_allied = int(nums[0])
            st.session_state.taw_pilots_axis   = int(nums[1])
    except: pass


def calcular_rumo_e_distancia(p1, p2):
    dlng = p2['lng'] - p1['lng']
    dlat = p2['lat'] - p1['lat']
    rumo = (math.degrees(math.atan2(dlng, dlat)) + 360) % 360
    dist = math.sqrt(dlng**2 + dlat**2) * 3.872
    return rumo, dist


# ==========================================
# 2. BASE DE DADOS
# ==========================================
# Aeródromos TAW — Normandy (altitudes em metros)
db_altitudes_tecnico = {
    # Allied
    "A-19 La Vielle": 20,  "B-10 Plumetot": 15,  "B-17 Carpiquet": 40,
    "Tangmere": 27,         "Ford": 9,             "Needs Oar Point": 35,
    "Hurn": 10,             "Warmwell": 90,         "Exeter": 30,
    "Thruxton": 100,        "Funtington": 30,       "Chailey": 50,
    # Axis
    "Beaumont le Roger": 170, "Lonrai": 200,  "Triqueville": 90,
    "Evreux": 130,            "Dreux": 90,    "Chartres": 155,
    "Le Mans": 50,            "Alencon": 145, "Caen": 30,
    "Lisieux": 70,            "Falaise": 150,
}

# Aeronaves TAW — mesma estrutura do FUEL.py
db_avioes = {
    # ── EIXO ──────────────────────────────────────────────────────────
    "Bf 109 G-6": {
        "peso_base_sem_combustivel": 2673, "peso_max": 3400,
        "consumo_l_min": 4.2, "vel_cruzeiro_padrao": 480, "tanque_max_l": 400,
        "climb_rate_default": 13.0, "descent_rate_default": 15.0,
        "armamento_fixo": "1x 20mm MG151/20 centro | 2x 7.92mm MG17",
        "modificacoes": {"Padrão": 0, "2x Gondola 20mm MG151/20": 120, "Sem Rádio FuG 16ZY": -20, "Tanque Auxiliar 300L": 240},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500}
    },
    "Bf 109 G-14": {
        "peso_base_sem_combustivel": 2800, "peso_max": 3550,
        "consumo_l_min": 4.5, "vel_cruzeiro_padrao": 500, "tanque_max_l": 400,
        "climb_rate_default": 13.5, "descent_rate_default": 15.0,
        "armamento_fixo": "1x 20mm MG151/20 centro | 2x 13mm MG131",
        "modificacoes": {"Padrão": 0, "2x Gondola 20mm MG151/20": 120, "Sem Rádio": -20},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500}
    },
    "Bf 109 K-4": {
        "peso_base_sem_combustivel": 2800, "peso_max": 3700,
        "consumo_l_min": 5.0, "vel_cruzeiro_padrao": 530, "tanque_max_l": 400,
        "climb_rate_default": 16.0, "descent_rate_default": 16.0,
        "armamento_fixo": "1x 30mm MK108 centro | 2x 15mm MG151/15",
        "modificacoes": {"Padrão": 0, "MK108 → MK103 30mm": 20, "Sem Rádio": -20},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500}
    },
    "Fw 190 A-6": {
        "peso_base_sem_combustivel": 3205, "peso_max": 4900,
        "consumo_l_min": 6.0, "vel_cruzeiro_padrao": 510, "tanque_max_l": 524,
        "climb_rate_default": 10.0, "descent_rate_default": 13.0,
        "armamento_fixo": "4x 20mm MG151/20 (asa+raiz) | 2x 13mm MG131",
        "modificacoes": {"Padrão": 0, "ETC 501 (bomba)": 30, "Sem blindagem piloto": -50},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500}
    },
    "Fw 190 A-8": {
        "peso_base_sem_combustivel": 3470, "peso_max": 4900,
        "consumo_l_min": 6.5, "vel_cruzeiro_padrao": 530, "tanque_max_l": 524,
        "climb_rate_default": 10.0, "descent_rate_default": 13.0,
        "armamento_fixo": "4x 20mm MG151/20 | 2x 13mm MG131",
        "modificacoes": {"Padrão": 0, "Sturmbock (2x 30mm MK108)": 320, "ETC 501": 30, "Tanque Auxiliar": 240},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500, "1x SC 1000": 1000}
    },
    "Fw 190 D-9": {
        "peso_base_sem_combustivel": 3490, "peso_max": 4840,
        "consumo_l_min": 6.8, "vel_cruzeiro_padrao": 580, "tanque_max_l": 524,
        "climb_rate_default": 11.0, "descent_rate_default": 14.0,
        "armamento_fixo": "2x 20mm MG151/20 (asa) | 2x 13mm MG131",
        "modificacoes": {"Padrão": 0, "ETC 504 (bomba)": 30, "Sem Rádio": -20},
        "presets_bombas": {"Vazio": 0, "1x SC 250": 250, "1x SC 500": 500}
    },
    "Ju 88 A-4": {
        "peso_base_sem_combustivel": 8600, "peso_max": 14000,
        "consumo_l_min": 10.0, "vel_cruzeiro_padrao": 370, "tanque_max_l": 1680,
        "climb_rate_default": 3.5, "descent_rate_default": 5.0,
        "armamento_fixo": "1x 13mm MG131 frontal | 3x 7.92mm MG81J",
        "modificacoes": {"Padrão": 0, "Sem Dive Brakes": -60, "Sem Gôndola Ventral": -123, "Câmera Recon Rb 50/30": 25},
        "presets_bombas": {"Vazio": 0,
                           "4x SC 250 (1000kg)": 1000,
                           "2x SC 500 (1000kg)": 1000,
                           "4x SC 500 (2000kg)": 2000,
                           "2x SC 1000 Hermann (2180kg)": 2180,
                           "10x SC 50 interno (500kg)": 500,
                           "28x SC 50 full load (1400kg)": 1400}
    },
    "Me 262 A-1a": {
        "peso_base_sem_combustivel": 4000, "peso_max": 7130,
        "consumo_l_min": 18.0, "vel_cruzeiro_padrao": 750, "tanque_max_l": 1900,
        "climb_rate_default": 15.0, "descent_rate_default": 18.0,
        "armamento_fixo": "4x 30mm MK108",
        "modificacoes": {"Padrão": 0, "24x R4M Rockets": 120},
        "presets_bombas": {"Vazio": 0, "2x SC 250": 500}
    },
    "Me 262 A-2a": {
        "peso_base_sem_combustivel": 4000, "peso_max": 7130,
        "consumo_l_min": 18.0, "vel_cruzeiro_padrao": 700, "tanque_max_l": 1900,
        "climb_rate_default": 13.0, "descent_rate_default": 16.0,
        "armamento_fixo": "2x 30mm MK108 (sem canhões dianteiros)",
        "modificacoes": {"Padrão": 0},
        "presets_bombas": {"Vazio": 0, "2x SC 250 (500kg)": 500, "2x SC 500 (1000kg)": 1000}
    },
    # ── ALIADOS ───────────────────────────────────────────────────────
    "Spitfire Mk.IXe": {
        "peso_base_sem_combustivel": 2950, "peso_max": 3900,
        "consumo_l_min": 4.8, "vel_cruzeiro_padrao": 480, "tanque_max_l": 386,
        "climb_rate_default": 12.0, "descent_rate_default": 15.0,
        "armamento_fixo": "2x 20mm Hispano Mk.II | 4x .303 Browning",
        "modificacoes": {"Padrão": 0, "Tanque Ferry 170L": 136, "Mirror + Landing Lights": 5},
        "presets_bombas": {"Vazio": 0, "1x 500lb GP": 227, "2x 250lb GP": 227}
    },
    "Spitfire Mk.XIVe": {
        "peso_base_sem_combustivel": 3100, "peso_max": 4200,
        "consumo_l_min": 5.5, "vel_cruzeiro_padrao": 540, "tanque_max_l": 386,
        "climb_rate_default": 14.0, "descent_rate_default": 16.0,
        "armamento_fixo": "2x 20mm Hispano Mk.II | 4x .303 Browning",
        "modificacoes": {"Padrão": 0, "Tanque Ferry": 136},
        "presets_bombas": {"Vazio": 0, "1x 500lb GP": 227}
    },
    "P-47D-28": {
        "peso_base_sem_combustivel": 5490, "peso_max": 7260,
        "consumo_l_min": 10.5, "vel_cruzeiro_padrao": 560, "tanque_max_l": 1060,
        "climb_rate_default": 8.5, "descent_rate_default": 12.0,
        "armamento_fixo": "8x .50 cal M2 Browning",
        "modificacoes": {"Padrão": 0, "Tanque Ventral 200gal": 560, "Sem Tanque Ventral": 0},
        "presets_bombas": {"Vazio": 0, "2x 500lb": 454, "2x 1000lb": 907,
                           "1x 500lb + 2x 250lb": 340, "10x HVAR": 600, "3x 500lb": 680}
    },
    "P-51D-15": {
        "peso_base_sem_combustivel": 3465, "peso_max": 5490,
        "consumo_l_min": 6.2, "vel_cruzeiro_padrao": 590, "tanque_max_l": 696,
        "climb_rate_default": 10.0, "descent_rate_default": 14.0,
        "armamento_fixo": "6x .50 cal M2 Browning",
        "modificacoes": {"Padrão": 0, "2x Tanques Externos 75gal": 363},
        "presets_bombas": {"Vazio": 0, "2x 500lb": 454, "2x 1000lb": 907}
    },
    "Typhoon Mk.Ib": {
        "peso_base_sem_combustivel": 4445, "peso_max": 6010,
        "consumo_l_min": 9.0, "vel_cruzeiro_padrao": 520, "tanque_max_l": 496,
        "climb_rate_default": 9.0, "descent_rate_default": 13.0,
        "armamento_fixo": "4x 20mm Hispano Mk.II",
        "modificacoes": {"Padrão": 0, "Tanque de Fuselagem": 204},
        "presets_bombas": {"Vazio": 0, "2x 500lb GP": 454, "2x 1000lb GP": 907,
                           "8x RP-3 60lb": 432, "4x RP-3 + 2x 500lb": 681}
    },
    "Tempest Mk.V ser.2": {
        "peso_base_sem_combustivel": 4354, "peso_max": 5940,
        "consumo_l_min": 9.5, "vel_cruzeiro_padrao": 570, "tanque_max_l": 682,
        "climb_rate_default": 11.0, "descent_rate_default": 14.0,
        "armamento_fixo": "4x 20mm Hispano Mk.V",
        "modificacoes": {"Padrão": 0, "Tanque Ferry": 182},
        "presets_bombas": {"Vazio": 0, "2x 500lb GP": 454, "2x 1000lb GP": 907}
    },
    "B-25D Mitchell": {
        "peso_base_sem_combustivel": 8836, "peso_max": 14062,
        "consumo_l_min": 15.0, "vel_cruzeiro_padrao": 370, "tanque_max_l": 3028,
        "climb_rate_default": 4.0, "descent_rate_default": 6.0,
        "armamento_fixo": "4x .50 cal frontal | 2x .50 cal dorsal | 2x .50 cal waist | 1x .50 cal ventral",
        "modificacoes": {"Padrão": 0},
        "presets_bombas": {"Vazio": 0,
                           "12x 250lb (1361kg)": 1361,
                           "8x 500lb (1814kg)": 1814,
                           "4x 500lb + 4x 250lb": 1361,
                           "6x 500lb (2722kg)": 1361}
    },
    "A-20G Havoc": {
        "peso_base_sem_combustivel": 7700, "peso_max": 11000,
        "consumo_l_min": 12.0, "vel_cruzeiro_padrao": 420, "tanque_max_l": 2196,
        "climb_rate_default": 5.5, "descent_rate_default": 8.0,
        "armamento_fixo": "4x .50 cal M2 frontal | 2x .50 cal dorsal | 1x .50 cal ventral",
        "modificacoes": {"Padrão": 0},
        "presets_bombas": {"Vazio": 0,
                           "8x 250lb (907kg)": 907,
                           "4x 500lb (907kg)": 907,
                           "2x 500lb + 4x 250lb": 680}
    },
    # ── BOMBARDEIROS PESADOS (Combat Box / Rhineland) ─────────────────
    "He-111 H-16": {
        "peso_base_sem_combustivel": 9300, "peso_max": 14000,
        "consumo_l_min": 10.2, "vel_cruzeiro_padrao": 330, "tanque_max_l": 3450,
        "climb_rate_default": 2.5, "descent_rate_default": 4.0,
        "armamento_fixo": "4x 7.92mm MG-81J | 1x 20mm MG-FF | 1x 13mm MG-131",
        "modificacoes": {
            "Padrão": 0,
            "Remover Blindagem": -115,
            "Tanque Adicional": 150
        },
        "presets_bombas": {
            "Vazio": 0,
            "1x SC 2500 (2400kg)": 2400,
            "2x SC 1800 Satan (3560kg)": 3560,
            "2x SC 1000 Hermann (2180kg)": 2180,
            "8x SC 250 (2000kg)": 2000,
            "32x SC 50 (1600kg)": 1600
        }
    },
    "He-111 H-6": {
        "peso_base_sem_combustivel": 9500, "peso_max": 14000,
        "consumo_l_min": 10.5, "vel_cruzeiro_padrao": 320, "tanque_max_l": 3450,
        "climb_rate_default": 2.5, "descent_rate_default": 4.0,
        "armamento_fixo": "6x 7.92mm MG-15",
        "modificacoes": {
            "Padrão": 0,
            "Torre Frontal 20mm MG-FF": 46,
            "Torre Ventral": 147,
            "Kit Anti-Navio": 193
        },
        "presets_bombas": {
            "Vazio": 0,
            "2x SC 1000 (2180kg)": 2180,
            "1x SC 1800 (1780kg)": 1780,
            "4x SC 250 (1000kg)": 1000,
            "16x SC 50 (800kg)": 800
        }
    },
    "Ju-52/3M": {
        "peso_base_sem_combustivel": 7500, "peso_max": 11000,
        "consumo_l_min": 12.0, "vel_cruzeiro_padrao": 240, "tanque_max_l": 2450,
        "climb_rate_default": 2.0, "descent_rate_default": 3.0,
        "armamento_fixo": "1x 13mm MG-131 (Dorsal)",
        "modificacoes": {
            "Padrão": 0,
            "Paraquedistas (12 homens)": 1200,
            "Carga Interna Tática": 2300,
            "Rodas de Inverno": 45
        },
        "presets_bombas": {
            "Vazio": 0,
            "10x MAB 250 Containers (2550kg)": 2550,
            "12x SC 50 (600kg)": 600
        }
    },
}

# ==========================================
# 3. INTERFACE
# ==========================================
st.set_page_config(page_title="Painel Tático — TAW", layout="wide")
st.markdown("<style>.stApp{background-color:#0E1117;color:#FAFAFA;}</style>", unsafe_allow_html=True)

TAW_MAP_URL = (
    "https://serverror.github.io/IL2-Mission-Planner/"
    "#json-url=https://tacticalairwar.com/map/taw_map.json"
)

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("""
        <style>
        section[data-testid="stSidebar"] > div {
            padding-top: 0.8rem !important;
            overflow: visible !important;
            height: auto !important;
        }
        section[data-testid="stSidebar"] {
            overflow-y: auto !important;
            height: 100vh !important;
        }
        section[data-testid="stSidebar"]::-webkit-scrollbar { display: none !important; }
        section[data-testid="stSidebar"] { scrollbar-width: none !important; }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }
        </style>
    """, unsafe_allow_html=True)

    # BLOCO 1 (60s): status + campanha + meteorologia
    @st.fragment(run_every="60s")
    def painel_telemetria_ativo():
        fetch_taw_data()
        d    = st.session_state.taw_dados
        ok   = "🟢" if "✅" in st.session_state.taw_status else "🔴"
        mn   = d.get('map_name', '—')
        ph   = d.get('phase', '—')
        dt   = d.get('mission_date', '—')
        tm   = d.get('mission_time', '—')
        tmp  = d.get('temp', f"{st.session_state.taw_temp:.0f} °C")
        qnh  = d.get('qnh', '—')
        cov  = d.get('cloud_cover', '—')
        cb   = d.get('cloud_base', '—')
        wd   = d.get('weather_desc', '—')
        vis  = d.get('visibility', '')
        turb = d.get('turbulence', '')
        prec = d.get('precipitation', '—')
        rd   = d.get('road', '—')
        winds = d.get('wind_data', [])
        w0 = winds[0] if winds else {}
        w_dir = w0.get('Dir', f"{st.session_state.taw_vento_dir:.0f}°")
        w_spd = w0.get('Vel', f"{st.session_state.taw_vento_vel} m/s")

        # Linha extra de condições
        wd_pt   = traduzir_meteo(wd)
        vis_pt  = traduzir_meteo(vis)
        turb_pt = traduzir_meteo(turb)
        prec_pt = traduzir_meteo(prec)
        rd_pt   = traduzir_meteo(rd)
        cond_items = []
        if vis_pt  and vis_pt  != '—': cond_items.append(f"👁️ {vis_pt}")
        if turb_pt and turb_pt != '—': cond_items.append(f"〰️ {turb_pt}")
        if prec_pt and prec_pt != '—': cond_items.append(f"🌧️ {prec_pt}")
        if rd_pt   and rd_pt   != '—': cond_items.append(f"🛣️ {rd_pt}")
        cond_html = "".join(
            f'<div style="color:#ccc;font-size:11px;">{item}</div>' for item in cond_items
        )

        st.markdown(
            f'<div style="font-family:sans-serif;font-size:12px;line-height:1.6;">'
            f'<div style="color:#666;margin-bottom:6px;">{ok} TAW sincronizado</div>'
            f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;margin-bottom:8px;">'
            f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:3px;">🗺️ CAMPANHA</div>'
            f'<div style="color:#f5a623;font-weight:bold;">{mn}</div>'
            f'<div style="color:#eee;">{ph}</div>'
            f'<div style="color:#aaa;font-size:11px;margin-top:2px;">📅 {dt} &nbsp;·&nbsp; ⏰ {tm}</div>'
            f'</div>'
            f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;">'
            f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:4px;">🌦️ METEOROLOGIA</div>'
            f'<div style="background:#0d1117;border-radius:5px;padding:5px 8px;margin-bottom:5px;">'
            f'<div style="color:#f5a623;font-size:10px;font-weight:bold;margin-bottom:2px;">⛅ AGORA</div>'
            f'<div style="color:#eee;">{wd_pt}</div>'
            f'<div style="color:#eee;">☁️ {cov} &nbsp;|&nbsp; Base: {cb}</div>'
            f'<div style="color:#eee;">🌡️ {tmp} &nbsp;|&nbsp; QNH: {qnh}</div>'
            + cond_html
            + f'</div>'
            f'<div style="background:#0d1117;border-radius:5px;padding:5px 8px;">'
            f'<div style="color:#7ec8e3;font-size:10px;font-weight:bold;margin-bottom:3px;">💨 VENTO POR ALTITUDE</div>'
            + "".join(
                f'<div style="display:flex;justify-content:space-between;color:#eee;font-size:11px;'
                f'border-bottom:1px solid #1e2a1e;padding:1px 0;">'
                f'<span style="color:#888;width:55px;">{w["Alt"]}</span>'
                f'<span>{w["Dir"]}</span>'
                f'<span style="color:#7ec8e3;">{w["Vel"]}</span></div>'
                for w in winds[:8]
            )
            + f'</div></div></div>',
            unsafe_allow_html=True
        )

    painel_telemetria_ativo()

    # BLOCO 2 (15s): pilotos + countdown
    @st.fragment(run_every="15s")
    def sidebar_countdown():
        fetch_taw_time()
        pa = st.session_state.taw_pilots_allied
        px = st.session_state.taw_pilots_axis
        el = st.session_state.taw_elapsed_min

        pilots_html = ""
        if pa is not None and px is not None:
            total = max(pa + px, 1)
            pct_a = int(pa / total * 100)
            pct_x = 100 - pct_a
            pilots_html = (
                f'<div style="background:#161b22;border-radius:6px;padding:7px 10px;margin-top:8px;margin-bottom:8px;">'
                f'<div style="color:#aaa;font-size:11px;letter-spacing:.5px;margin-bottom:5px;">✈️ PILOTS ON STATION</div>'
                f'<div style="display:flex;justify-content:space-around;margin-bottom:5px;">'
                f'<div style="text-align:center;">'
                f'<div style="color:#4488cc;font-size:28px;font-weight:900;line-height:1;">{pa}</div>'
                f'<div style="color:#888;font-size:10px;">ALLIED</div>'
                f'</div>'
                f'<div style="text-align:center;">'
                f'<div style="color:#dd4444;font-size:28px;font-weight:900;line-height:1;">{px}</div>'
                f'<div style="color:#888;font-size:10px;">AXIS</div>'
                f'</div></div>'
                f'<div style="display:flex;height:12px;border-radius:3px;overflow:hidden;">'
                f'<div style="width:{pct_a}%;background:#2255aa;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:bold;color:#fff;">{pct_a}%</div>'
                f'<div style="width:{pct_x}%;background:#aa2222;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:bold;color:#fff;">{pct_x}%</div>'
                f'</div>'
                f'<div style="text-align:center;font-size:9px;color:#555;margin-top:2px;">COALITION BALANCE</div>'
                f'</div>'
            )

        restante_min = max(0, 120 - el)
        cor = "#ffcc00" if restante_min > 30 else ("#ff8800" if restante_min > 10 else "#ff3333")
        countdown_html = (
            f'<div style="background:#0d1117;border:1px solid #333;border-radius:6px;padding:8px 6px;text-align:center;">'
            f'<div style="color:#aaa;font-size:10px;letter-spacing:1.5px;font-weight:bold;margin-bottom:4px;">⏰ MISSION COUNTDOWN</div>'
            f'<div style="font-size:34px;font-weight:900;font-family:monospace;color:{cor};letter-spacing:2px;line-height:1.1;">'
            f'{restante_min:02d}:{0:02d} min</div>'
            f'<div style="color:#555;font-size:9px;margin-top:2px;">Elapsed: {el//60:02d}h {el%60:02d}m · ±5min</div>'
            f'</div>'
        )
        st.markdown(
            f'<div style="font-family:sans-serif;">{pilots_html}{countdown_html}</div>',
            unsafe_allow_html=True
        )

    sidebar_countdown()

# ==========================================
# TÍTULO + PLAYER FMC GLOBAL (topo das tabs)
# ==========================================
st.title("✈️ Painel Tático C4ISR — Tactical Air War")

if st.session_state.get('cronometro_rodando') and st.session_state.get('navlog_manual'):
    _w_dir   = float(st.session_state.taw_vento_dir)
    _w_spd   = float(st.session_state.taw_vento_vel * 3.6)
    _nav_tas = float(st.session_state.get('vel_calc', 450))
    _pernas_top = []
    for _i, _ln in enumerate(st.session_state.navlog_manual):
        try:
            _d  = float(_ln.get("Distância (km)", 0.0))
            _tc = float(_ln.get("Rumo (TC)", 0.0))
            _wa = math.radians(_w_dir - _tc)
            _swca = max(-1.0, min(1.0, (_w_spd * math.sin(_wa)) / max(_nav_tas, 1)))
            _wca  = math.degrees(math.asin(_swca))
            _th   = (_tc + _wca + 360) % 360
            _gs   = max(1.0, (_nav_tas * math.cos(math.radians(_wca))) - (_w_spd * math.cos(_wa)))
            _pernas_top.append({"nome": _ln.get("Perna", f"WP{_i}"), "proa": _th,
                                "tempo": (_d / _gs) * 3600})
        except: continue

    @st.fragment(run_every="1s")
    def fmc_top_bar():
        _idx   = st.session_state.index_perna_ativa
        _total = len(_pernas_top)
        if _idx < _total:
            p = _pernas_top[_idx]
            _restante_str = "--:--"
            _prog = 0.0
            if st.session_state.tempo_inicio_perna:
                _passado  = time.time() - st.session_state.tempo_inicio_perna
                _restante = max(0.0, p['tempo'] - _passado)
                _m, _s    = divmod(int(_restante), 60)
                _restante_str = f"{_m:02d}:{_s:02d}"
                _prog = min(1.0, _passado / max(p['tempo'], 1))
            st.markdown(
                f'<div style="background:linear-gradient(90deg,#1a2a1a,#0e1117);border:1px solid #2a5a2a;'
                f'border-left:4px solid #44cc44;border-radius:8px;padding:10px 16px;margin-bottom:8px;'
                f'display:flex;align-items:center;gap:24px;">'
                f'<div style="font-size:13px;color:#888;min-width:80px;">🚀 FMC ATIVO</div>'
                f'<div style="font-size:36px;font-weight:900;color:#44ff44;min-width:90px;line-height:1;">{p["proa"]:.0f}°</div>'
                f'<div><div style="font-size:13px;color:#aaa;">📍 {p["nome"]}</div>'
                f'<div style="font-size:22px;font-weight:bold;color:#fff;font-family:monospace;">⏱️ {_restante_str}</div></div>'
                f'<div style="font-size:12px;color:#666;margin-left:auto;">Perna {_idx+1}/{_total}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.progress(_prog)
            b1, b2, b3, _ = st.columns([1, 1, 1, 5])
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
            if _idx + 1 < _total:
                with b3: st.caption(f"Próx: {_pernas_top[_idx+1]['proa']:.0f}°")
        else:
            c1, c2 = st.columns([4, 1])
            with c1: st.success("🏁 Missão Concluída!")
            with c2:
                if st.button("🔄 Reset", key="top_reset"):
                    st.session_state.cronometro_rodando           = False
                    st.session_state.index_perna_ativa            = 0
                    st.session_state.tempo_inicio_missao_absoluto = None
                    st.rerun()
    fmc_top_bar()
    st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Hangar", "🎯 Mira / Bomba", "🧮 NavLog & E6B",
    "🚀 FMC (Ativo)", "🌐 Inteligência", "🗺️ Mapa"
])

# ==========================================
# ABA 1: HANGAR
# ==========================================
with tab1:
    st.header("🛠️ Configuração de Carga e Rota")

    col_f, col_clear = st.columns([3, 1])
    with col_f:
        arquivo_plano = st.file_uploader("📥 Importar Plano de Voo (.json)", type=["json"])
        if arquivo_plano is not None:
            fc = arquivo_plano.getvalue()
            fh = hash(fc)
            if st.session_state.get('last_file_hash') != fh:
                st.session_state.last_file_hash = fh
                try:
                    dados_plano = json.loads(fc)
                    if "routes" in dados_plano:
                        plano = next((r for r in dados_plano["routes"] if r.get("isFlightPlan")), None)
                        if plano is None:
                            st.error("❌ Nenhuma rota marcada como Flight Plan.")
                        else:
                            coords    = plano["latLngs"]
                            speeds    = plano.get("speeds", [])
                            altitudes = plano.get("altitudes", [])
                            nl, dt = [], 0.0
                            for i in range(len(coords) - 1):
                                rumo, dist = calcular_rumo_e_distancia(coords[i], coords[i+1])
                                dt += dist
                                vel_p = int(speeds[i])      if i < len(speeds)       else int(plano.get("speed", 450))
                                alt_p = int(altitudes[i+1]) if i+1 < len(altitudes) else int(plano.get("altitude", 3000))
                                nl.append({"Perna": f"WP{i}➔WP{i+1}", "Distância (km)": round(dist, 1),
                                           "Rumo (TC)": round(rumo, 0), "TAS (km/h)": vel_p, "Altitude (m)": alt_p})
                            st.session_state.navlog_manual = nl
                            st.session_state.dist_calc     = dt
                            if nl: st.session_state.vel_calc = float(nl[0]["TAS (km/h)"])
                            st.success(f"✅ {len(nl)} pernas de '{plano.get('name','Rota')}' → NavLog atualizado!")
                except Exception as e:
                    st.error(f"Erro: {e}")
    with col_clear:
        if st.button("🗑️ Reset Rota", use_container_width=True):
            st.session_state.navlog_manual = []
            st.session_state.dist_calc = 100.0
            st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        av_nome = st.selectbox("Selecione a Aeronave", list(db_avioes.keys()))
        st.session_state.av_nome_selecionado = av_nome
        av = db_avioes[av_nome]
        missao_dist = st.number_input("Distância da Missão (km)", value=float(st.session_state.get('dist_calc', 100.0)))
        missao_vel  = st.number_input("Velocidade de Cruzeiro (km/h)", value=float(av['vel_cruzeiro_padrao']))
        margem_seg  = st.slider("Reserva de Combustível (%)", 0, 100, 25)
    with c2:
        mod_sel  = st.selectbox("Modificações",    list(av['modificacoes'].keys()))
        bomb_sel = st.selectbox("Carga de Bombas", list(av['presets_bombas'].keys()))
        st.caption(f"🛡️ Armamento Fixo: {av.get('armamento_fixo', 'Não listado')}")

    if missao_vel > 0:
        tempo_estimado = (missao_dist / missao_vel) * 60
        comb_l     = tempo_estimado * av['consumo_l_min'] * (1 + margem_seg / 100)
        peso_total = (av['peso_base_sem_combustivel']
                      + av['modificacoes'][mod_sel]
                      + av['presets_bombas'][bomb_sel]
                      + (comb_l * 0.72))
        st.divider()
        cr1, cr2, cr3 = st.columns(3)
        with cr1:
            if peso_total <= av['peso_max']:
                st.success(f"⚖️ Peso Total: **{peso_total:.0f} kg** / {av['peso_max']} kg")
            else:
                st.error(f"⚠️ SOBRECARGA: **{peso_total:.0f} kg** / {av['peso_max']} kg")
        with cr2:
            if comb_l > av['tanque_max_l']:
                st.error(f"⛽ Combustível: **{comb_l:.0f} L** ⚠️ EXCEDE ({av['tanque_max_l']} L)")
            else:
                st.info(f"⛽ Combustível: **{comb_l:.0f} L** / {av['tanque_max_l']} L")
        with cr3:
            st.info(f"⏱️ Tempo estimado: **{tempo_estimado:.0f} min** ({tempo_estimado/60:.1f}h)")

# ==========================================
# ABA 2: MIRA / BOMBA (equivale ao Lotfe 7)
# ==========================================
with tab2:
    st.markdown("""
        <style>
        .stSlider [data-baseweb="slider"] { height: 45px; }
        .stSlider [data-baseweb="thumb"]  { height: 40px; width: 40px; background-color: #FF4B4B; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🎯 Calculadora de Vento da Mira")
    st.caption("Calcule os parâmetros de vento para miras de bombardeiro (Norris, Norden, etc.).")

    # Inicializa session_state dos sliders da mira
    if "mira_wdir" not in st.session_state: st.session_state.mira_wdir = 0
    if "mira_wspd" not in st.session_state: st.session_state.mira_wspd = 0

    if st.session_state.taw_dados:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("🌬️ Usar Vento da API"):
                # Atualiza os session_state → os sliders usarão os novos valores
                st.session_state.mira_wdir = int(st.session_state.taw_vento_dir)
                st.session_state.mira_wspd = int(st.session_state.taw_vento_vel)
                st.rerun()
        with col_info:
            st.caption(f"API: {st.session_state.taw_vento_vel} m/s de {st.session_state.taw_vento_dir:.0f}°")

    phead  = st.slider("🧭 PLANE HEADING (°)", 0, 359, value=0, step=1, key="phdg_taw")
    whead  = st.slider("🌬️ WIND DIRECTION (FROM °)", 0, 359, step=1, key="mira_wdir")
    wspeed = st.slider("💨 WIND SPEED (m/s)", 0, 30, step=1, key="mira_wspd")

    raw_hdg        = (whead - phead) % 360
    sight_wind_hdg = raw_hdg if raw_hdg <= 180 else raw_hdg - 360

    st.divider()
    res1, res2 = st.columns(2)
    with res1:
        st.metric("× Sight Wind Hdg",   f"{sight_wind_hdg:+d}°")
        st.caption("Gire o seletor de direção na mira para este valor.")
    with res2:
        st.metric("× Sight Wind Speed", f"{wspeed} m/s")
        st.caption("Ajuste a velocidade do vento na mira.")

    if wspeed > 0:
        direcao_txt = "DIREITA ➡️" if sight_wind_hdg > 0 else ("ESQUERDA ⬅️" if sight_wind_hdg < 0 else "FRONTAL ⬆️")
        st.info(f"💡 Configure sua mira com **{sight_wind_hdg:+d}°** ({direcao_txt}) e **{wspeed} m/s**.")

# ==========================================
# ABA 3: NAVLOG & E6B
# ==========================================
with tab3:
    st.header("🗺️ Centro de Navegação")
    st.caption("📥 Importe o plano de voo na **Aba 1 (Hangar)** para preencher o NavLog automaticamente.")
    st.divider()

    c_tas, c_dir, c_vel = st.columns(3)
    with c_tas:
        def_tas = float(st.session_state.navlog_manual[0].get("TAS (km/h)", st.session_state.vel_calc)) \
                  if st.session_state.navlog_manual else float(st.session_state.vel_calc)
        nav_tas = st.number_input("Sua TAS esperada (km/h)", value=def_tas, step=10.0)
    with c_dir:
        nav_w_dir = st.number_input("Vento vindo DE (°)", value=float(st.session_state.taw_vento_dir), key="nav_dir_taw")
    with c_vel:
        nav_w_spd = st.number_input("Vel. Vento (km/h)", value=float(st.session_state.taw_vento_vel * 3.6), step=5.0, key="nav_spd_taw")
        st.caption(f"API: {st.session_state.taw_vento_vel} m/s = {st.session_state.taw_vento_vel*3.6:.1f} km/h")

    st.subheader("📝 Navigation Log (Diário de Rota)")
    navlog_editado = st.data_editor(
        st.session_state.navlog_manual,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Perna":          st.column_config.TextColumn("Nome da Perna"),
            "Distância (km)": st.column_config.NumberColumn("Distância (km)", format="%.1f"),
            "Rumo (TC)":      st.column_config.NumberColumn("Rumo Mapa (TC °)", format="%.0f"),
            "TAS (km/h)":     st.column_config.NumberColumn("TAS (km/h)"),
            "Altitude (m)":   st.column_config.NumberColumn("Altitude (m)")
        }
    )
    st.session_state.navlog_manual = navlog_editado

    if len(navlog_editado) > 0:
        resultados_finais = []
        for linha in navlog_editado:
            try:
                dist   = float(linha.get("Distância (km)", 0.0))
                tc_deg = float(linha.get("Rumo (TC)", 0.0))
            except: dist, tc_deg = 0.0, 0.0
            if dist > 0:
                wa_rad = math.radians(nav_w_dir - tc_deg)
                try:
                    sin_wca = max(-1.0, min(1.0, (nav_w_spd * math.sin(wa_rad)) / nav_tas))
                    wca_deg = math.degrees(math.asin(sin_wca))
                except: wca_deg = 0.0
                th_deg = (tc_deg + wca_deg + 360) % 360
                gs_leg = max(1.0, (nav_tas * math.cos(math.radians(wca_deg))) - (nav_w_spd * math.cos(wa_rad)))
                tempo_min = (dist / gs_leg) * 60
                resultados_finais.append({
                    "📍 Perna":          linha.get("Perna", "N/D"),
                    "🗺️ Rumo Mapa":      f"{tc_deg:.0f}°",
                    "🧭 Voar PROA (TH)": f"{th_deg:.0f}°",
                    "💨 Vel. Solo (GS)": f"{gs_leg:.0f} km/h",
                    "⏱️ Tempo Voo":      f"{tempo_min:.1f} min"
                })
        if resultados_finais:
            st.table(resultados_finais)

    st.divider()
    st.subheader("🧮 Computador E6B")
    col_tsd, col_conv = st.columns(2)
    with col_tsd:
        st.markdown("**⏱️ Tempo, Velocidade, Distância (TSD)**")
        modo_tsd = st.radio("Calcular:", ["Tempo", "Distância", "Velocidade (GS)"], horizontal=True)
        if modo_tsd == "Tempo":
            d_in = st.number_input("Distância (km)", value=50.0, key="d_t")
            v_in = st.number_input("Velocidade (km/h)", value=450.0, key="v_t")
            if v_in > 0: st.info(f"**Resultado:** {(d_in/v_in)*60:.1f} minutos")
        elif modo_tsd == "Distância":
            t_in = st.number_input("Tempo (min)", value=10.0, key="t_d")
            v_in = st.number_input("Velocidade (km/h)", value=450.0, key="v_d")
            st.info(f"**Resultado:** {v_in*(t_in/60):.1f} km")
        else:
            d_in = st.number_input("Distância (km)", value=50.0, key="d_v")
            t_in = st.number_input("Tempo (min)", value=10.0, key="t_v")
            if t_in > 0: st.info(f"**Resultado:** {d_in/(t_in/60):.0f} km/h")
    with col_conv:
        st.markdown("**🔄 Conversões**")
        cat_conv = st.selectbox("Unidade:", ["Velocidade (km/h ↔ mph)", "Altitude (metros ↔ pés)"])
        val_conv = st.number_input("Valor:", value=1000.0 if "Altitude" in cat_conv else 450.0)
        if "Velocidade" in cat_conv:
            st.warning(f"**{val_conv} km/h** = {val_conv/1.60934:.0f} mph")
            st.warning(f"**{val_conv} mph** = {val_conv*1.60934:.0f} km/h")
        else:
            st.warning(f"**{val_conv} metros** = {val_conv*3.28084:.0f} pés")
            st.warning(f"**{val_conv} pés** = {val_conv/3.28084:.0f} metros")

# ==========================================
# ABA 4: FMC
# ==========================================
with tab4:
    st.header("🚀 Flight Management Computer")

    if not st.session_state.get('navlog_manual'):
        st.info("⚠️ Configure uma rota na Aba 1 ou Aba 3 para ativar o FMC.")
    else:
        lista_aerodromos_db = sorted(list(db_altitudes_tecnico.keys()))

        with st.expander("🌍 Configuração de Aeródromos (DB Interno)", expanded=True):
            col_dep, col_arr = st.columns(2)
            with col_dep:
                base_dep = st.selectbox("Decolagem de:", lista_aerodromos_db, key="fmc_dep")
                alt_dep  = db_altitudes_tecnico[base_dep]
                st.write(f"**Altitude Base:** {alt_dep}m")
            with col_arr:
                base_arr = st.selectbox("Destino Final:", lista_aerodromos_db, key="fmc_arr")
                alt_arr  = db_altitudes_tecnico[base_arr]
                st.write(f"**Altitude Alvo:** {alt_arr}m")

        av_nome_fmc = st.session_state.get('av_nome_selecionado', "Bf 109 G-6")
        av_fmc      = db_avioes.get(av_nome_fmc, {})

        with st.expander("📈 Perfil de Voo (VNAV)", expanded=True):
            v1, v2, v3, v4 = st.columns(4)
            with v1: alt_cruzeiro = st.number_input("Cruzeiro (m)", value=4000, step=500)
            with v2: climb_rate   = st.number_input("Subida (m/s)",  value=float(av_fmc.get('climb_rate_default', 8.0)))
            with v3: descent_rate = st.number_input("Descida (m/s)", value=float(av_fmc.get('descent_rate_default', 12.0)))
            with v4: st.number_input("Alt. Destino (m)", value=alt_arr, disabled=True)

        nav_tas = float(st.session_state.get('vel_calc', 450))
        w_dir   = float(st.session_state.taw_vento_dir)
        w_spd   = float(st.session_state.taw_vento_vel * 3.6)

        pernas_fmc = []
        dist_acum  = 0.0
        for idx, linha in enumerate(st.session_state.navlog_manual):
            try:
                dist = float(linha.get("Distância (km)", 0.0))
                tc   = float(linha.get("Rumo (TC)", 0.0))
                wa_rad  = math.radians(w_dir - tc)
                sin_wca = max(-1.0, min(1.0, (w_spd * math.sin(wa_rad)) / max(nav_tas, 1)))
                wca     = math.degrees(math.asin(sin_wca))
                th      = (tc + wca + 360) % 360
                gs      = max(1.0, (nav_tas * math.cos(math.radians(wca))) - (w_spd * math.cos(wa_rad)))
                tempo   = (dist / gs) * 3600
                dist_acum += dist
                pernas_fmc.append({"id": idx, "nome": linha.get("Perna", f"WP{idx}"),
                                   "proa": th, "tempo": tempo, "dist_total": dist_acum})
            except: continue

        # Gráfico VNAV
        total_km = pernas_fmc[-1]['dist_total'] if pernas_fmc else 0.0
        dist_climb = dist_descent = 0.0
        if pernas_fmc:
            dist_climb   = ((alt_cruzeiro - alt_dep)  / max(climb_rate,   0.1)) * (nav_tas / 3600)
            dist_descent = ((alt_cruzeiro - alt_arr)  / max(descent_rate, 0.1)) * (nav_tas / 3600)
            if dist_climb + dist_descent > total_km:
                f = total_km / (dist_climb + dist_descent)
                dist_climb *= f; dist_descent *= f
            df_vnav = pd.DataFrame({
                "Distância (km)": [0, dist_climb, max(dist_climb, total_km - dist_descent), total_km],
                "Altitude (m)":   [alt_dep, alt_cruzeiro, alt_cruzeiro, alt_arr]
            })
            st.area_chart(df_vnav.set_index("Distância (km)"))

        st.divider()

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
    st.markdown("""
        <style>
        /* Destrava scroll vertical em toda a cadeia de containers do Streamlit */
        html, body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"],
        [data-testid="stVerticalBlock"],
        [data-testid="stVerticalBlockBorderWrapper"],
        .main, .block-container {
            overflow-y: auto !important;
            overflow-x: hidden !important;
            height: auto !important;
            max-height: none !important;
            min-height: 0 !important;
        }
        /* Garante que o body e html podem crescer */
        html, body { height: 100% !important; min-height: 100vh !important; }
        /* Margem lateral de 20px */
        [data-testid="stMainBlockContainer"] {
            padding-left:  20px !important;
            padding-right: 20px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.header("🌐 Inteligência Tática e Logística (C4ISR)")

    d = st.session_state.taw_dados
    # Se dados existem mas campos meteo estão em falta (sessão antiga antes do fix), força re-fetch
    if d and 'precipitation' not in d:
        fetch_taw_data()
        d = st.session_state.taw_dados
    if not d:
        st.warning("📡 Aguardando sincronização com o servidor TAW...")
        if st.button("🔄 Sincronizar agora"):
            fetch_taw_data()
            st.rerun()
    else:
        mn   = d.get("map_name", "—")
        ph   = d.get("phase", "—")
        dt   = d.get("mission_date", "—")
        tm   = d.get("mission_time", "—")

        # ── SITUAÇÃO GERAL ────────────────────────────────────────────
        st.subheader("📜 Situação da Missão")
        st.info(f"**{mn}** — {ph} &nbsp;|&nbsp; 📅 {dt} &nbsp;|&nbsp; ⏰ {tm}")

        st.divider()

        # ── METEOROLOGIA COMPLETA ─────────────────────────────────────
        st.subheader("🌦️ Meteorologia Detalhada")

        wd   = d.get("weather_desc", "—")
        tmp  = d.get("temp", "—")
        qnh  = d.get("qnh", "—")
        cov  = d.get("cloud_cover", "—")
        cb   = d.get("cloud_base", "—")
        vis  = d.get("visibility", "—")
        turb = d.get("turbulence", "—")
        prec = d.get("precipitation", "—")
        rd   = d.get("road", "—")

        wd_pt   = traduzir_meteo(wd)
        vis_pt  = traduzir_meteo(vis)
        turb_pt = traduzir_meteo(turb)
        prec_pt = traduzir_meteo(prec)
        rd_pt   = traduzir_meteo(rd)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("⛅ Condição",  wd_pt or "—")
            st.metric("☁️ Cobertura", cov)
        with m2:
            st.metric("📏 Base Nuvens", cb)
            st.metric("🌡️ Temperatura", tmp)
        with m3:
            st.metric("📊 QNH", qnh)
            st.metric("👁️ Visibilidade", vis_pt if vis_pt and vis_pt != "—" else "—")
        with m4:
            st.metric("🌧️ Precipitação", prec_pt if prec_pt and prec_pt != "—" else "—")
            st.metric("🛣️ Pista", rd_pt if rd_pt and rd_pt != "—" else "—")

        if turb and turb != "—":
            turb_l = turb.lower()
            if "smooth" in turb_l:
                st.success(f"✈️ **{turb_pt}**")
            elif "moderate" in turb_l:
                st.warning(f"⚠️ Turbulência: **{turb_pt}**")
            elif "severe" in turb_l:
                st.error(f"🚨 Turbulência severa: **{turb_pt}**")

        # Vento por altitude — todas as 8 camadas
        winds = d.get("wind_data", [])
        if winds:
            st.markdown("**💨 Vento por Altitude**")
            df_w = pd.DataFrame(winds)
            df_w.columns = ["Altitude", "Direção", "Velocidade"]
            st.dataframe(df_w, use_container_width=True, hide_index=True)

        # Previsão dos próximos dias
        forecast = d.get("forecast", [])
        if forecast:
            st.markdown("**📅 Previsão dos Próximos Dias**")
            # Usa HTML com flex-wrap para evitar corte lateral quando há 6+ dias
            cards_html = ""
            for fc in forecast:
                is_no_fly  = 'NÃO VOAR' in fc.get('desc', '') or 'noFly' in fc.get('desc', '')
                border_col = '#aa2222' if is_no_fly else '#1e3a1e'
                temp_col   = '#ff4444' if is_no_fly else '#f5a623'
                extra      = "<div style='color:#ff6666;font-size:9px;margin-top:2px;'>⚠️ PERIGO</div>" if is_no_fly else ""
                cards_html += (
                    f"<div style='flex:1;min-width:90px;max-width:160px;text-align:center;"
                    f"background:#161b22;border:1px solid {border_col};border-radius:6px;"
                    f"padding:8px 4px;margin:3px;'>"
                    f"<div style='color:#aaa;font-size:10px;margin-bottom:3px;'>{fc['date']}</div>"
                    f"<div style='font-size:24px;line-height:1;margin-bottom:3px;'>{fc.get('emoji','❓')}</div>"
                    f"<div style='color:{temp_col};font-size:15px;font-weight:bold;'>{fc['temp']}</div>"
                    f"{extra}</div>"
                )
            st.markdown(
                f"<div style='display:flex;flex-wrap:wrap;gap:0;width:100%;'>{cards_html}</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

        st.divider()

        # ── AERÓDROMOS DA LINHA DE FRENTE ─────────────────────────────
        allied_airfields = d.get("allied_airfields", [])
        axis_airfields   = d.get("axis_airfields", [])
        st.subheader(f"🛫 Aeródromos Frontline: {len(allied_airfields) + len(axis_airfields)}")

        col_all_b, col_ax_b = st.columns(2)

        def render_airfield(row):
            vals   = list(row.values()) if isinstance(row, dict) else row
            nome   = vals[0] if len(vals) > 0 else "—"
            dano   = vals[1] if len(vals) > 1 else "—"
            supply = vals[2] if len(vals) > 2 else "—"
            aberto = vals[3] if len(vals) > 3 else "—"
            icon   = "🟢" if str(aberto).lower() in ["yes", "sim", "true"] else "🔴"
            try:
                sup_num  = float(str(supply).replace(",", "."))
                dano_num = float(re.sub(r"[^\d.]", "", str(dano)) or "0")
            except:
                sup_num = dano_num = 0.0
            alerta = "🚨 " if sup_num < 20 or dano_num >= 50 else ""
            with st.expander(f"{alerta}{icon} **{nome}**"):
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Supply")
                    st.progress(min(1.0, sup_num / 100.0))
                    st.write(f"**{supply}** / 100")
                with c2:
                    st.caption("Dano")
                    dano_pct = dano_num / 100.0
                    if dano_num == 0:
                        st.success(f"✅ {dano}")
                    elif dano_num < 30:
                        st.warning(f"⚠️ {dano}")
                    else:
                        st.error(f"🔴 {dano}")
                st.write(f"**Aberto:** {aberto}")

        with col_all_b:
            st.markdown("### 🔵 Allied Airfields")
            if not allied_airfields:
                st.caption("Sem dados.")
            for row in allied_airfields:
                render_airfield(row)

        with col_ax_b:
            st.markdown("### 🔴 Axis Airfields")
            if not axis_airfields:
                st.caption("Sem dados.")
            for row in axis_airfields:
                render_airfield(row)

        st.divider()

        # ── CIDADES DA LINHA DE FRENTE ────────────────────────────────
        allied_cities = d.get("allied_cities", [])
        axis_cities   = d.get("axis_cities", [])
        st.subheader("🏙️ Cidades da Linha de Frente")

        col_ca, col_cx = st.columns(2)

        def render_city_full(row, lado):
            vals   = list(row.values()) if isinstance(row, dict) else row
            nome   = vals[0] if len(vals) > 0 else "—"
            ataque = vals[1] if len(vals) > 1 else ""
            defesa = vals[2] if len(vals) > 2 else "—"
            supply = vals[3] if len(vals) > 3 else "—"
            atk_ico = "🚨 " if ataque else ""
            cor_defesa = {"poor": "🔴", "average": "🟡", "good": "🟢", "excellent": "💚"}
            def_icon = cor_defesa.get(str(defesa).lower(), "⬜")
            try:   sup_num = float(str(supply).replace(",", "."))
            except: sup_num = 0.0
            with st.expander(f"{atk_ico}🏙️ **{nome}**"):
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Supply")
                    st.progress(min(1.0, sup_num / 100.0))
                    st.write(f"**{supply}** / 100")
                with c2:
                    st.write(f"**Defesa:** {def_icon} {defesa}")
                    if ataque:
                        st.error("⚔️ **SOB ATAQUE!**")

        with col_ca:
            st.markdown("### 🔵 Allied Cities")
            for row in allied_cities: render_city_full(row, "allied")
            if not allied_cities: st.caption("Sem dados.")
        with col_cx:
            st.markdown("### 🔴 Axis Cities")
            for row in axis_cities: render_city_full(row, "axis")
            if not axis_cities: st.caption("Sem dados.")

        st.divider()

        # ── DEPOTS ────────────────────────────────────────────────────
        st.subheader("🏭 Depósitos de Abastecimento")
        col_dep_a, col_dep_x = st.columns(2)

        def render_depot_full(row):
            vals = list(row.values()) if isinstance(row, dict) else row
            nome = vals[0] if len(vals) > 0 else "—"
            dano = vals[1] if len(vals) > 1 else "—"
            prod = vals[2] if len(vals) > 2 else "—"
            try:   dano_num = float(re.sub(r"[^\d.]", "", str(dano)) or "0")
            except: dano_num = 0.0
            # Barra de saúde invertida (100% = sem dano)
            saude = max(0.0, 1.0 - dano_num / 100.0)
            with st.expander(f"{'⚠️ ' if dano_num >= 20 else '✅ '}**{nome}** — Dano: {dano}"):
                st.progress(saude)
                c1, c2 = st.columns(2)
                with c1: st.write(f"**Dano:** {dano}")
                with c2: st.write(f"**Produção:** {prod}/missão")

        with col_dep_a:
            st.markdown("### 🔵 Allied Depots")
            for row in d.get("allied_depots", []): render_depot_full(row)
            if not d.get("allied_depots"): st.caption("Sem dados.")
        with col_dep_x:
            st.markdown("### 🔴 Axis Depots")
            for row in d.get("axis_depots", []): render_depot_full(row)
            if not d.get("axis_depots"): st.caption("Sem dados.")

        st.divider()

        # ── PERDAS ────────────────────────────────────────────────────
        st.subheader("💀 Balanço de Perdas")

        def parse_loss(val_str):
            """Extrai atual e total de strings como '192 / 980'."""
            parts = str(val_str).split("/")
            try:
                atual = int(parts[0].strip())
                total = int(parts[1].strip()) if len(parts) > 1 else None
                return atual, total
            except:
                return None, None

        col_la, col_lx = st.columns(2)
        for col, key, label in [(col_la, "allied_losses", "🔵 Allied"), (col_lx, "axis_losses", "🔴 Axis")]:
            with col:
                st.markdown(f"**{label}**")
                for row in d.get(key, []):
                    vals = list(row.values()) if isinstance(row, dict) else row
                    if len(vals) >= 2:
                        cat = vals[0]
                        val = vals[1]
                        atual, total = parse_loss(val)
                        if total:
                            pct = min(1.0, atual / total)
                            cor = "🔴" if pct > 0.5 else ("🟡" if pct > 0.25 else "🟢")
                            st.write(f"{cor} **{cat}:** {val}")
                            st.progress(pct)
                        else:
                            st.write(f"**{cat}:** {val}")

# ABA 6: MAPA (IL-2 MISSION PLANNER — TAW)
# ==========================================
with tab6:
    st.markdown(
        f'<div style="margin-bottom:5px;">'
        f'<a href="{TAW_MAP_URL}" target="_blank" '
        f'style="display:inline-block;padding:4px 12px;background:#1a1a3a;'
        f'border:1px solid #2a2a6a;border-radius:5px;color:#8888ff;'
        f'text-decoration:none;font-size:12px;">🔗 Abrir em nova aba</a>'
        f'<span style="margin-left:10px;font-size:11px;color:#555;">'
        f'Linha de frente ao vivo · Aeródromos · Objetivos</span></div>',
        unsafe_allow_html=True
    )

    st.markdown("""
        <style>
        iframe[title="components.v1.html"] { display: block !important; margin: 0 !important; }
        </style>
    """, unsafe_allow_html=True)

    components.html(
        f"""
        <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        html, body {{ width:100%; height:100%; background:#0e1117; overflow:hidden; }}
        #wrap {{ position:relative; width:100%; height:100%; user-select:none; }}
        #mapframe {{ display:block; border:none; width:100%; height:100%; }}
        #overlay {{ display:none; position:absolute; inset:0; z-index:99; cursor:grabbing; }}
        </style>
        <div id="wrap">
            <iframe id="mapframe" src="{TAW_MAP_URL}" allow="fullscreen"></iframe>
            <div id="overlay"></div>
        </div>
        <script>
        (function() {{
            var overlay = document.getElementById('overlay');
            var dragging = false;
            try {{
                var c = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]');
                if (c) {{ c.style.paddingLeft='0'; c.style.paddingRight='0'; c.style.paddingBottom='0'; }}
            }} catch(e) {{}}
            function restoreParent() {{
                try {{
                    window.parent.document.documentElement.style.overflow = '';
                    window.parent.document.body.style.overflow = '';
                    var c = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]');
                    if (c) {{ c.style.paddingLeft=''; c.style.paddingRight=''; c.style.paddingBottom=''; }}
                }} catch(e) {{}}
            }}
            window.addEventListener('beforeunload', restoreParent);
            try {{
                var myIframe = window.frameElement;
                if (myIframe) {{
                    new MutationObserver(function() {{
                        if (!window.parent.document.contains(myIframe)) restoreParent();
                    }}).observe(window.parent.document.body, {{childList:true, subtree:true}});
                }}
            }} catch(e) {{}}
            function lockScroll() {{
                try {{
                    window.parent.document.documentElement.style.overflow = 'hidden';
                    window.parent.document.body.style.overflow = 'hidden';
                    window.parent.scrollTo(0, 0);
                }} catch(e) {{}}
            }}
            document.getElementById('wrap').addEventListener('mousedown', function() {{
                dragging = true; overlay.style.display = 'block'; lockScroll();
            }});
            window.addEventListener('mouseup', function() {{
                if (dragging) {{ dragging = false; overlay.style.display = 'none'; restoreParent(); }}
            }});
            window.parent.addEventListener('scroll', function() {{
                if (dragging) window.parent.scrollTo(0, 0);
            }}, true);
            // NÃO chama lockScroll() no load — só bloqueia durante drag
        }})();
        </script>
        """,
        height=860,
        scrolling=False
    )
