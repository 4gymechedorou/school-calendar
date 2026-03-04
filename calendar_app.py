import streamlit as st
from streamlit_calendar import calendar
import pandas as pd
from datetime import datetime, timedelta
from icalendar import Calendar
import re
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

# --- ΡΥΘΜΙΣΕΙΣ ΕΦΑΡΜΟΓΗΣ ---
st.set_page_config(page_title="Σχολικό Ημερολόγιο Web", layout="wide")

# Σταθερές
DEPARTMENTS = ["Α1", "Α2", "Α3", "Α4", "Β1", "Β2", "Β3", "Γ1", "Γ2", "Γ3"]
HOURS = [str(i) for i in range(1, 8)]
LESSONS = ["ΤΕΧΝΟΛΟΓΙΑ", "ΠΛΗΡΟΦΟΡΙΚΗ", "ΟΙΚ. ΟΙΚΟΝ.", "ΒΙΟΛΟΓΙΑ", "ΦΥΣΙΚΗ", "ΧΗΜΕΙΑ", "ΜΑΘΗΜΑΤΙΚΑ", "ΓΛΩΣΣΑ", "ΑΡΧΑΙΑ", "ΘΡΗΣΚΕΥΤΙΚΑ", "ΛΟΓΟΤΕΧΝΙΑ", "ΕΡΓΑΣΤΗΡΙΟ ΔΕΞΙΟΤΗΤΩΝ", "ΜΟΥΣΙΚΗ", "ΙΣΤΟΡΙΑ", "ΜΕΤΑΦΡΑΣΗ", "ΚΑΛΛΙΤΕΧΝΙΚΑ", "ΓΕΩΓΡΑΦΙΑ", "ΑΓΓΛΙΚΑ", "ΓΕΡΜΑΝΙΚΑ", "ΓΑΛΛΙΚΑ", "ΓΥΜΝΑΣΤΙΚΗ", "Κ.Π.Α.", "ΟΙΚΟΝΟΜΙΚΑ"]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ENw07twtEbduCWifb4tt0_sQo2iT8SiAoB9QlXnMeY0/edit?usp=sharing"

# Σύνδεση
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ΗΧΟΣ ΑΠΟΡΡΙΨΗΣ ---
def play_error_sound():
    components.html(
        """<script>
        var context = new (window.AudioContext || window.webkitAudioContext)();
        var osc = context.createOscillator();
        var gain = context.createGain();
        osc.connect(gain); gain.connect(context.destination);
        osc.type = 'sawtooth'; osc.frequency.value = 150;
        gain.gain.setValueAtTime(0.1, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.00001, context.currentTime + 0.6);
        osc.start(); osc.stop(context.currentTime + 0.6);
        </script>""", height=0, width=0
    )

# --- ΛΕΙΤΟΥΡΓΙΕΣ ΔΕΔΟΜΕΝΩΝ ---
def load_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0).dropna(how="all")
        df['id'] = df.index.astype(str)
        return df.fillna("")
    except:
        return pd.DataFrame(columns=['id', 'title', 'start', 'type', 'dept', 'teacher', 'lesson', 'hours', 'created_at', 'notes', 'color'])

def save_data(df_to_save):
    if 'id' in df_to_save.columns:
        df_to_save = df_to_save.drop(columns=['id'])
    conn.update(spreadsheet=SHEET_URL, data=df_to_save)

def get_saved_teachers():
    try:
        df_t = conn.read(spreadsheet=SHEET_URL, worksheet="teachers", ttl=0).dropna(how="all")
        return ["ΚΕΝΟ"] + sorted(df_t['name'].dropna().astype(str).tolist())
    except:
        return ["ΚΕΝΟ"]

# --- ΕΛΕΓΧΟΣ ΠΕΡΙΟΡΙΣΜΩΝ ---
def check_constraints(df, date_str, dept, entry_type, exclude_idx=None):
    if dept == "ΣΧΟΛΕΙΟ" or entry_type in ["Τεστ", "Δράση"]: return True, ""
    
    target_date = pd.to_datetime(date_str).date()
    
    # Έλεγχος ίδιας μέρας
    day_events = df[(df['start'].astype(str) == str(date_str)) & (df['dept'] == dept) & (df['type'] == "Διαγώνισμα")]
    if exclude_idx is not None: day_events = day_events.drop(index=int(exclude_idx), errors='ignore')
    if not day_events.empty:
        return False, f"🚨 ΑΠΑΓΟΡΕΥΕΤΑΙ: Το τμήμα {dept} έχει ΗΔΗ διαγώνισμα στις {date_str}!"

    # Έλεγχος εβδομάδας (Max 3)
    dt_obj = pd.to_datetime(target_date)
    start_week = dt_obj - timedelta(days=dt_obj.weekday())
    end_week = start_week + timedelta(days=6)
    
    dept_exams = df[(df['dept'] == dept) & (df['type'] == "Διαγώνισμα")]
    if exclude_idx is not None: dept_exams = dept_exams.drop(index=int(exclude_idx), errors='ignore')
    
    weekly_count = 0
    for d in dept_exams['start']:
        ev_d = pd.to_datetime(d)
        if start_week <= ev_d <= end_week: weekly_count += 1
            
    if weekly_count >= 3:
        return False, f"🚨 ΑΠΑΓΟΡΕΥΕΤΑΙ: Το τμήμα {dept} έχει ήδη 3 διαγωνίσματα αυτή την εβδομάδα!"

    return True, ""

# --- UI STYLE ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f1f5f9; border-right: 2px solid #1E3A8A; }
    .legend-item { display: inline-block; margin-right: 20px; font-weight: bold; padding: 5px 12px; border-radius: 4px; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- ΚΥΡΙΩΣ ΠΡΟΓΡΑΜΜΑ ---
df = load_data()
curr_teachers = get_saved_teachers()

with st.sidebar:
    st.title("🛠️ Διαχείριση")
    with st.expander("📝 Νέα Καταχώρηση", expanded=True):
        t_name = st.selectbox("👤 Εκπαιδευτικός", curr_teachers)
        t_date = st.date_input("📅 Ημερομηνία", datetime.now())
        t_depts = st.multiselect("👥 Τμήμα(τα)", ["ΣΧΟΛΕΙΟ"] + DEPARTMENTS)
        t_hours = st.multiselect("⏳ Ώρα", HOURS)
        t_type = st.radio("🏷️ Τύπος", ["Διαγώνισμα", "Τεστ", "Δράση"], horizontal=True)
        t_lesson = st.selectbox("📖 Μάθημα", LESSONS) if t_type != "Δράση" else st.text_input("🎯 Τίτλος Δράσης")
        
        if st.button("✅ ΚΑΤΑΧΩΡΗΣΗ"):
            error_found = False
            for d in t_depts:
                ok, msg = check_constraints(df, t_date, d, t_type)
                if not ok:
                    st.error(msg); play_error_sound(); error_found = True; break
            
            if not error_found and t_depts:
                h_s = ", ".join(sorted(t_hours))
                for d in t_depts:
                    color = "#B91C1C" if t_type == "Διαγώνισμα" else ("#D97706" if t_type == "Τεστ" else "#1D4ED8")
                    title = f"{d}_Ω:{h_s}_{t_lesson}_{t_name}" if t_type != "Δράση" else f"{t_lesson}_{d}"
                    new_row = {'title': title, 'start': str(t_date), 'type': t_type, 'dept': d, 'teacher': t_name, 'lesson': t_lesson, 'hours': h_s, 'created_at': datetime.now().strftime("%d/%m/%Y %H:%M"), 'color': color}
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df); st.rerun()

    with st.expander("📂 Εισαγωγή Αρχείων"):
        up_xlsx = st.file_uploader("Καθηγητές (Excel)", type=['xlsx'])
        if up_xlsx and st.button("🚀 Update Teachers"):
            df_k = pd.read_excel(up_xlsx, usecols=[1], skiprows=4, header=None)
            t_list = pd.DataFrame({'name': sorted(df_k[1].dropna().unique())})
            conn.update(spreadsheet=SHEET_URL, worksheet="teachers", data=t_list); st.success("OK!"); st.rerun()

st.title("🏫 Σχολικό Ημερολόγιο Web")
st.markdown("""
    <div style="margin-bottom:20px">
        <span class="legend-item" style="background:#B91C1C">🔴 ΔΙΑΓΩΝΙΣΜΑ</span>
        <span class="legend-item" style="background:#D97706">🟠 ΤΕΣΤ</span>
        <span class="legend-item" style="background:#1D4ED8">🔵 ΔΡΑΣΗ</span>
    </div>
    """, unsafe_allow_html=True)

# Φίλτρα
f1, f2 = st.columns(2)
sel_dept = f1.multiselect("🔍 Τμήμα", DEPARTMENTS, default=None)
sel_type = f2.multiselect("🔍 Τύπος", ["Διαγώνισμα", "Τεστ", "Δράση"], default=None)

df_view = df.copy()
if sel_dept: df_view = df_view[df_view['dept'].isin(sel_dept)]
if sel_type: df_view = df_view[df_view['type'].isin(sel_type)]

# Ημερολόγιο
cal_options = {
    "locale": "el",
    "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listWeek"},
    "initialView": "dayGridMonth",
}
state = calendar(events=df_view.to_dict(orient='records'), options=cal_options)

# Διαγραφή/Επεξεργασία
if state.get("eventClick"):
    ev_id = state["eventClick"]["event"]["id"]
    if st.button(f"🗑️ Διαγραφή Εγγραφής {ev_id}"):
        df = df.drop(index=int(ev_id))
        save_data(df); st.rerun()

st.write("---")
st.dataframe(df_view[['start', 'dept', 'teacher', 'lesson', 'type']].sort_values('start'), use_container_width=True)