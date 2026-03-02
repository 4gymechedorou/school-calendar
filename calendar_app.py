import streamlit as st
from streamlit_calendar import calendar
import pandas as pd
from datetime import datetime
from icalendar import Calendar
import re
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

# Ρυθμίσεις Εφαρμογής
st.set_page_config(page_title="Σχολικό Ημερολόγιο Web", layout="wide")

DEPARTMENTS = ["Α1", "Α2", "Α3", "Α4", "Β1", "Β2", "Β3", "Γ1", "Γ2", "Γ3"]
HOURS = [str(i) for i in range(1, 8)]
LESSONS = ["ΤΕΧΝΟΛΟΓΙΑ", "ΠΛΗΡΟΦΟΡΙΚΗ", "ΟΙΚ. ΟΙΚΟΝ.", "ΒΙΟΛΟΓΙΑ", "ΦΥΣΙΚΗ", "ΧΗΜΕΙΑ", "ΜΑΘΗΜΑΤΙΚΑ", "ΓΛΩΣΣΑ", "ΑΡΧΑΙΑ", "ΘΡΗΣΚΕΥΤΙΚΑ", "ΛΟΓΟΤΕΧΝΙΑ", "ΕΡΓΑΣΤΗΡΙΟ ΔΕΞΙΟΤΗΤΩΝ", "ΜΟΥΣΙΚΗ", "ΙΣΤΟΡΙΑ", "ΜΕΤΑΦΡΑΣΗ", "ΚΑΛΛΙΤΕΧΝΙΚΑ", "ΓΕΩΓΡΑΦΙΑ", "ΑΓΓΛΙΚΑ", "ΓΕΡΜΑΝΙΚΑ", "ΓΑΛΛΙΚΑ", "ΓΥΜΝΑΣΤΙΚΗ", "Κ.Π.Α.", "ΟΙΚΟΝΟΜΙΚΑ"]

conn = st.connection("gsheets", type=GSheetsConnection)

# --- ΗΧΟΣ ΑΠΟΡΡΙΨΗΣ ---
def play_error_sound():
    components.html(
        """
        <script>
        var context = new (window.AudioContext || window.webkitAudioContext)();
        var osc = context.createOscillator();
        var gain = context.createGain();
        osc.connect(gain);
        gain.connect(context.destination);
        osc.type = 'sawtooth';
        osc.frequency.value = 150;
        gain.gain.setValueAtTime(0.1, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.00001, context.currentTime + 0.6);
        osc.start();
        osc.stop(context.currentTime + 0.6);
        </script>
        """,
        height=0, width=0
    )

# --- ΛΕΙΤΟΥΡΓΙΕΣ GOOGLE SHEETS ---
def load_data():
    try:
        df = conn.read(ttl=0).dropna(how="all")
        df['id'] = df.index.astype(str)
        return df.fillna("")
    except:
        return pd.DataFrame(columns=['id', 'title', 'start', 'type', 'dept', 'teacher', 'lesson', 'hours', 'created_at', 'notes', 'color'])

def save_data(df_to_save):
    if 'id' in df_to_save.columns:
        df_to_save = df_to_save.drop(columns=['id'])
    conn.update(data=df_to_save)

def get_saved_teachers():
    base_list = ["ΚΕΝΟ"]
    try:
        df_t = conn.read(worksheet="teachers", ttl=0).dropna(how="all")
        saved = df_t['name'].dropna().astype(str).tolist()
        return base_list + saved
    except:
        return base_list

# --- ΕΛΕΓΧΟΣ ΠΕΡΙΟΡΙΣΜΩΝ ---
def check_constraints(df, date_str, dept, entry_type, exclude_idx=None):
    if dept == "ΣΧΟΛΕΙΟ": return True, ""
    
    if entry_type in ["Τεστ", "Δράση"]:
        return True, ""
    
    target_date = datetime.strptime(str(date_str), '%Y-%m-%d').date()
    target_year, target_week, _ = target_date.isocalendar()
    
    day_events = df[df['start'].astype(str) == str(date_str)]
    day_events = day_events[day_events['dept'] == dept]
    
    if exclude_idx is not None:
        day_events = day_events.drop(index=int(exclude_idx), errors='ignore')

    existing_exams_day = day_events[day_events['type'] == "Διαγώνισμα"]

    if len(existing_exams_day) >= 1:
        return False, f"🚨 ΑΠΑΓΟΡΕΥΕΤΑΙ: Το τμήμα {dept} έχει ΗΔΗ 1 ΔΙΑΓΩΝΙΣΜΑ στις {date_str}!"

    dept_exams = df[(df['dept'] == dept) & (df['type'] == "Διαγώνισμα")]
    if exclude_idx is not None:
        dept_exams = dept_exams.drop(index=int(exclude_idx), errors='ignore')
        
    weekly_exams_count = 0
    for ev_date_str in dept_exams['start']:
        try:
            ev_date = datetime.strptime(str(ev_date_str), '%Y-%m-%d').date()
            ev_year, ev_week, _ = ev_date.isocalendar()
            if ev_year == target_year and ev_week == target_week:
                weekly_exams_count += 1
        except:
            pass
            
    if weekly_exams_count >= 3:
        return False, f"🚨 ΑΠΑΓΟΡΕΥΕΤΑΙ: Το τμήμα {dept} έχει ΗΔΗ 3 ΔΙΑΓΩΝΙΣΜΑΤΑ αυτήν την εβδομάδα!"

    return True, ""

# --- UI STYLE ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f1f5f9; border-right: 2px solid #1E3A8A; }
    .fc-event { cursor: pointer; border: none !important; width: 100% !important; }
    .fc-event-main { padding: 4px !important; font-weight: 500 !important; white-space: normal !important; }
    .legend-container { margin-bottom: 20px; padding: 10px; background-color: white; border-radius: 8px; border: 1px solid #e2e8f0; }
    .legend-item { display: inline-block; margin-right: 20px; font-weight: bold; padding: 5px 12px; border-radius: 4px; color: white; font-size: 14px; }
    .blue-bg { background-color: #1D4ED8; }
    .red-bg { background-color: #B91C1C; }
    .orange-bg { background-color: #D97706; }
    .sidebar-header { color: #1e3a8a; font-size: 20px; font-weight: bold; text-align: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown('<p class="sidebar-header">🛠️ Διαχείριση</p>', unsafe_allow_html=True)
    st.subheader("📝 Νέα Καταχώρηση")
    
    curr_teachers = get_saved_teachers()
    t_name = st.selectbox("👤 Εκπαιδευτικός", curr_teachers, key="sidebar_teach")
    t_date = st.date_input("📅 Ημερομηνία", datetime.now(), key="sidebar_date")
    t_depts = st.multiselect("👥 Τμήμα(τα)", ["ΣΧΟΛΕΙΟ"] + DEPARTMENTS, key="sidebar_depts")
    t_hours = st.multiselect("⏳ Ώρα", HOURS, key="sidebar_hours")
    t_type = st.radio("🏷️ Τύπος", ["Διαγώνισμα", "Τεστ", "Δράση"], horizontal=True, key="sidebar_type")
    
    t_notes = ""
    if t_type == "Δράση":
        t_lesson = st.text_input("🎯 Τίτλος Δράσης", key="sidebar_act")
        t_notes = st.text_area("📝 Σχόλια/Περιγραφή Δράσης", key="sidebar_notes_act")
    else:
        t_lesson = st.selectbox("📖 Μάθημα", LESSONS, key="sidebar_les")
    
    if st.button("✅ ΚΑΤΑΧΩΡΗΣΗ"):
        if not t_depts or (not t_hours and t_type != "Δράση") or not t_lesson:
            st.error("Συμπληρώστε τα απαραίτητα πεδία!")
        else:
            df_global = load_data()
            error_found = False
            for d in t_depts:
                ok, msg = check_constraints(df_global, t_date, d, t_type)
                if not ok:
                    st.error(f"**{msg}**", icon="🛑")
                    play_error_sound()
                    error_found = True
                    break
            
            if not error_found:
                h_s = ", ".join(sorted(t_hours))
                for d in t_depts:
                    title = f"{d}_Ω:{h_s}_{t_lesson}_{t_name}" if t_type != "Δράση" else f"{t_lesson}_{d}"
                    color = "#B91C1C" if t_type == "Διαγώνισμα" else ("#D97706" if t_type == "Τεστ" else "#1D4ED8")
                    new_row = {'title': title, 'start': str(t_date), 'type': t_type, 'dept': d, 'teacher': t_name, 'lesson': t_lesson, 'hours': h_s, 'created_at': datetime.now().strftime("%d/%m/%Y %H:%M"), 'notes': t_notes, 'color': color}
                    df_global = pd.concat([df_global, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df_global); st.rerun()

    st.write("---")
    st.subheader("📂 Εισαγωγή Αρχείων")
    
    up_xlsx = st.file_uploader("Εισαγωγή Καθηγητών (Excel)", type=['xlsx'])
    if up_xlsx:
        try:
            df_k = pd.read_excel(up_xlsx, usecols=[1], skiprows=4, header=None)
            t_list = sorted(df_k[1].dropna().astype(str).str.strip().unique().tolist())
            df_to_save = pd.DataFrame({'name': t_list})
            conn.update(worksheet="teachers", data=df_to_save)
            st.success("Η λίστα εκπαιδευτικών ενημερώθηκε!")
            st.rerun()
        except: st.error("Σφάλμα. Βεβαιωθείτε ότι υπάρχει η καρτέλα 'teachers' στο Sheet.")

    up_ics = st.file_uploader("Εισαγωγή .ics (Google Calendar)", type=['ics'])
    if up_ics and st.button("🚀 IMPORT ICS"):
        try:
            gcal = Calendar.from_ical(up_ics.read())
            df_ics = load_data()
            count = 0
            for component in gcal.walk():
                if component.name == "VEVENT":
                    summary = str(component.get('summary'))
                    dt = component.get('dtstart').dt
                    date_s = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)
                    c_cat = "Διαγώνισμα" if any(w in summary.upper() for w in ["Δ_", "ΔΙΑΓ", "ΤΕΣΤ", "Δ."]) else "Δράση"
                    c_dept = next((d for d in DEPARTMENTS if d in summary.upper()), "ΣΧΟΛΕΙΟ")
                    clean = summary.replace(c_dept, "").replace("Δ_", "").replace("ΔΙΑΓ.", "").replace("ΤΕΣΤ", "").strip(" _-")
                    parts = re.split(r'[-_]', clean)
                    l_p = parts[0].strip()
                    t_p = parts[1].strip() if len(parts) > 1 else "GCal"
                    title_ics = f"{c_dept}_Ω:1_{l_p}_{t_p}" if c_cat != "Δράση" else f"{l_p}_{c_dept}"
                    new_row = {'title': title_ics, 'start': date_s, 'type': c_cat, 'dept': c_dept, 'teacher': t_p, 'lesson': l_p, 'hours': "1", 'created_at': datetime.now().strftime("%d/%m/%Y %H:%M"), 'notes': "Imported from ICS", 'color': "#B91C1C" if c_cat=="Διαγώνισμα" else "#1D4ED8"}
                    df_ics = pd.concat([df_ics, pd.DataFrame([new_row])], ignore_index=True)
                    count += 1
            save_data(df_ics); st.success(f"Εισήχθησαν {count} εγγραφές!"); st.rerun()
        except: st.error("Σφάλμα στην ανάγνωση του αρχείου ICS.")

# --- ΚΥΡΙΩΣ ΟΘΟΝΗ ---
col_t1, col_t2 = st.columns([5, 1])
with col_t1:
    st.title("🏫 Σχολικό Ημερολόγιο Web")
with col_t2:
    st.write("") 
    if st.button("🔄 ΑΝΑΝΕΩΣΗ ΔΕΔΟΜΕΝΩΝ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("""
    <div class="legend-container">
        <span class="legend-item red-bg">🔴 ΔΙΑΓΩΝΙΣΜΑ</span>
        <span class="legend-item orange-bg">🟠 ΤΕΣΤ</span>
        <span class="legend-item blue-bg">🔵 ΔΡΑΣΗ</span>
    </div>
    """, unsafe_allow_html=True)

df = load_data()

if "clipboard" in st.session_state:
    with st.container(border=True):
        st.info(f"📋 Έτοιμο για επικόλληση: {st.session_state.clipboard['title']}")
        cp1, cp2 = st.columns([2, 1])
        p_date = cp1.date_input("Νέα Ημερομηνία για Επικόλληση:", datetime.now(), key="paste_date")
        if cp2.button("📥 ΕΠΙΚΟΛΛΗΣΗ ΕΔΩ"):
            ok, msg = check_constraints(df, p_date, st.session_state.clipboard['dept'], st.session_state.clipboard['type'])
            if ok:
                new_e = st.session_state.clipboard.copy()
                new_e['start'] = str(p_date)
                new_e['created_at'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                df = pd.concat([df, pd.DataFrame([new_e])], ignore_index=True); save_data(df)
                del st.session_state.clipboard; st.rerun()
            else:
                st.error(f"**{msg}**", icon="🛑")
                play_error_sound()

f1, f2, f3 = st.columns(3)
f_dept = f1.multiselect("🔍 Τμήμα", ["ΟΛΑ"] + DEPARTMENTS, default="ΟΛΑ", key="filter_dept")
f_teach = f2.multiselect("🔍 Καθηγητής", ["ΟΛΟΙ"] + curr_teachers, default="ΟΛΟΙ", key="filter_teach")
f_type = f3.multiselect("🔍 Τύπος", ["ΟΛΟΙ", "Διαγώνισμα", "Τεστ", "Δράση"], default="ΟΛΟΙ", key="filter_type")

df_view = df.copy()
if not df_view.empty:
    if "ΟΛΑ" not in f_dept: df_view = df_view[df_view['dept'].isin(f_dept)]
    if "ΟΛΟΙ" not in f_teach: df_view = df_view[df_view['teacher'].isin(f_teach)]
    if "ΟΛΟΙ" not in f_type: df_view = df_view[df_view['type'].isin(f_type)]

cal_options = {
    "locale": "el",
    "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek,timeGridDay,listWeek"},
    "initialView": "dayGridMonth",
    "buttonText": {"listWeek": "Λίστα"}
}
state = calendar(events=df_view.to_dict(orient='records'), options=cal_options)

if state.get("eventClick"):
    @st.dialog("⚙️ Διαχείριση Εγγραφής")
    def edit_modal(ev_id):
        df_ed = load_data()
        idx = int(ev_id)
        row = df_ed.loc[idx]
        
        c1, c2 = st.columns(2)
        n_dept = c1.selectbox("Τμήμα", ["ΣΧΟΛΕΙΟ"] + DEPARTMENTS, index=(["ΣΧΟΛΕΙΟ"] + DEPARTMENTS).index(row['dept']) if row['dept'] in (["ΣΧΟΛΕΙΟ"] + DEPARTMENTS) else 0, key=f"mod_dept_{ev_id}")
        n_type = c1.radio("Τύπος", ["Διαγώνισμα", "Τεστ", "Δράση"], index=["Διαγώνισμα", "Τεστ", "Δράση"].index(row['type']) if row['type'] in ["Διαγώνισμα", "Τεστ", "Δράση"] else 0, key=f"mod_type_{ev_id}")
        
        n_date = c2.date_input("Ημερομηνία", datetime.strptime(str(row['start']), '%Y-%m-%d'), key=f"mod_date_{ev_id}")
        n_teacher = c2.selectbox("👤 Εκπαιδευτικός", curr_teachers, index=curr_teachers.index(str(row['teacher'])) if str(row['teacher']) in curr_teachers else 0, key=f"mod_teach_{ev_id}")
        n_hours = st.text_input("Ώρες", value=str(row['hours']), key=f"mod_hours_{ev_id}")
        
        if n_type == "Δράση":
            n_lesson = st.text_input("🎯 Τίτλος Δράσης", value=str(row['lesson']), key=f"mod_act_{ev_id}")
        else:
            def_l = row['lesson'] if row['lesson'] in LESSONS else LESSONS[0]
            n_lesson = st.selectbox("📖 Μάθημα", LESSONS, index=LESSONS.index(def_l), key=f"mod_les_{ev_id}")
            
        n_notes = st.text_area("Σχόλια/Περιγραφή", value=str(row['notes']), key=f"mod_notes_{ev_id}")
        
        st.write("---")
        b1, b2, b3, b4 = st.columns(4)
        
        if b1.button("💾 ΑΠΟΘΗΚΕΥΣΗ", key=f"btn_save_{ev_id}"):
            ok, msg = check_constraints(df_ed, n_date, n_dept, n_type, exclude_idx=idx)
            if ok:
                title_up = f"{n_dept}_Ω:{n_hours}_{n_lesson}_{n_teacher}" if n_type in ["Διαγώνισμα", "Τεστ"] else f"{n_lesson}_{n_dept}"
                color_up = "#B91C1C" if n_type=="Διαγώνισμα" else ("#D97706" if n_type=="Τεστ" else "#1D4ED8")
                
                df_ed.at[idx, 'dept'] = n_dept
                df_ed.at[idx, 'type'] = n_type
                df_ed.at[idx, 'start'] = str(n_date)
                df_ed.at[idx, 'teacher'] = n_teacher
                df_ed.at[idx, 'lesson'] = n_lesson
                df_ed.at[idx, 'hours'] = n_hours
                df_ed.at[idx, 'title'] = title_up
                df_ed.at[idx, 'color'] = color_up
                df_ed.at[idx, 'notes'] = n_notes
                save_data(df_ed); st.rerun()
            else:
                st.error(f"**{msg}**", icon="🛑")
                play_error_sound()
                
        if b2.button("✂️ ΑΝΤΙΓΡΑΦΗ", key=f"btn_copy_{ev_id}"):
            temp_dict = row.to_dict()
            temp_dict['dept'] = n_dept
            temp_dict['type'] = n_type
            temp_dict['teacher'] = n_teacher
            temp_dict['lesson'] = n_lesson
            temp_dict['hours'] = n_hours
            temp_dict['notes'] = n_notes
            temp_dict['title'] = f"{n_dept}_Ω:{n_hours}_{n_lesson}_{n_teacher}" if n_type in ["Διαγώνισμα", "Τεστ"] else f"{n_lesson}_{n_dept}"
            st.session_state.clipboard = temp_dict
            st.rerun()
            
        if b3.button("❌ ΔΙΑΓΡΑΦΗ", type="primary", key=f"btn_del_{ev_id}"):
            df_ed = df_ed.drop(idx); save_data(df_ed); st.rerun()
            
        if b4.button("🔙 ΑΚΥΡΟ", key=f"btn_cancel_{ev_id}"):
            st.rerun()

    edit_modal(state["eventClick"]["event"]["id"])

st.write("---")
st.subheader("📋 Ιστορικό Εγγραφών")

if not df_view.empty:
    columns_to_show = ['created_at', 'start', 'dept', 'teacher', 'lesson', 'hours', 'type', 'notes']
    st.dataframe(
        df_view[columns_to_show].sort_values(by='start', ascending=False),
        use_container_width=True,
        column_config={
            "created_at": "Ημ/νία Καταχώρησης", "start": "Ημ/νία Διεξαγωγής", "dept": "Τμήμα",
            "teacher": "Καθηγητής", "lesson": "Μάθημα/Δράση", "hours": "Ώρες", "type": "Τύπος", "notes": "Σχόλια"
        }
    )