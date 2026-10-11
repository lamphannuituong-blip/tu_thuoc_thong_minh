import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import psycopg2
import streamlit as st

# --- IMPORT MODULES ---
from modules.auth import render_auth
from modules.schedule_admin_prototype import render_schedule_admin

st.set_page_config(page_title="Tủ Thuốc Thông Minh", page_icon="💊", layout="wide")

# ==========================================
# 1. HỆ THỐNG ĐĂNG NHẬP (Chạy đầu tiên)
# ==========================================
is_authenticated = render_auth(st.secrets["DATABASE_URL"])

if not is_authenticated:
    st.stop()

# ==========================================
# 2. GIAO DIỆN CHÍNH & LOGIC DATABASE 
# ==========================================
try:
    with open("assets/main.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.error("Không tìm thấy file assets/main.css")

# Banner Header tinh tế, gọn gàng (Không bị lỗi tràn viền)
st.markdown(f"""
    <div class="header-banner">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1>💊 Tủ Thuốc Thông Minh</h1>
                <p>Quản lý thuốc và đơn thuốc riêng cho từng người trong gia đình</p>
            </div>
            <div style="text-align: right;">
                <span style="font-size: 0.95rem; color: #f1f5f9;">Xin chào, <b>{st.session_state.fullname}</b></span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Nút đăng xuất nhỏ gọn phía trên
col_space, col_logout = [st.columns([9, 1])[0], st.columns([9, 1])[1]]
with col_logout:
    if st.button("Đăng xuất", key="logout_top", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
def today(): return datetime.now(TIMEZONE).date()
def connect(): return psycopg2.connect(st.secrets["DATABASE_URL"], connect_timeout=15)

@st.cache_resource(show_spinner=False)
def init_database(database_url):
    with psycopg2.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS people (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL)")
            cur.execute("""CREATE TABLE IF NOT EXISTS medicines (
                id BIGSERIAL PRIMARY KEY, person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK (quantity > 0),
                daily_dose INTEGER NOT NULL CHECK (daily_dose > 0), start_date DATE NOT NULL,
                end_date DATE NOT NULL, in_cabinet BOOLEAN NOT NULL DEFAULT TRUE)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS medication_schedules (
                medicine_id BIGINT PRIMARY KEY REFERENCES medicines(id) ON DELETE CASCADE,
                times_local TEXT[] NOT NULL, units_per_dose INTEGER NOT NULL,
                approved BOOLEAN DEFAULT FALSE, approved_by TEXT, approved_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())""")
            cur.execute("""CREATE TABLE IF NOT EXISTS device_patient_links (
                device_id TEXT NOT NULL, person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                enabled BOOLEAN DEFAULT TRUE, PRIMARY KEY (device_id, person_id))""")
            cur.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL,
                details TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())""")
    return True

def read_data():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE medicines SET in_cabinet = FALSE WHERE in_cabinet = TRUE AND end_date < %s", (today(),))
            cur.execute("SELECT id, name FROM people ORDER BY id")
            people_data = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
            cur.execute("SELECT id, person_id, name, quantity, daily_dose, start_date, end_date, in_cabinet FROM medicines ORDER BY id")
            keys = ("id", "person_id", "name", "quantity", "daily_dose", "start_date", "end_date", "in_cabinet")
            medicines_data = [dict(zip(keys, row)) for row in cur.fetchall()]
    return people_data, medicines_data

def calculate_end_date(start_date, quantity, daily_dose):
    return start_date + timedelta(days=math.ceil(quantity / daily_dose))

def add_person(name):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO people(name) VALUES (%s)", (name,))

def delete_person(person_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM people WHERE id = %s", (person_id,))

def add_medicine(person_id, name, quantity, daily_dose, start_date):
    end_date = calculate_end_date(start_date, quantity, daily_dose)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO medicines(person_id, name, quantity, daily_dose, start_date, end_date, in_cabinet)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                            (person_id, name, quantity, daily_dose, start_date, end_date, end_date >= today()))

def save_edits(person_id, edited, original_medicines):
    original = {m["id"]: m for m in original_medicines}
    updates, deletes, errors = [], [], []
    for _, row in edited.iterrows():
        medicine_id = int(row["ID"])
        if medicine_id not in original: continue
        if bool(row["Xóa"]):
            deletes.append(medicine_id)
            continue
        try:
            name = str(row["Tên thuốc"]).strip()
            quantity, daily_dose = int(row["Số lượng"]), int(row["Liều/ngày"])
            start_date = row["Ngày bắt đầu"]
            if isinstance(start_date, str): start_date = date.fromisoformat(start_date)
            elif isinstance(start_date, (pd.Timestamp, datetime)): start_date = start_date.date()
            if not name or quantity < 1 or daily_dose < 1 or not isinstance(start_date, date): raise ValueError()
            end_date = calculate_end_date(start_date, quantity, daily_dose)
            previous = original[medicine_id]
            if (name, quantity, daily_dose, start_date) != (previous["name"], previous["quantity"], previous["daily_dose"], previous["start_date"]):
                updates.append((name, quantity, daily_dose, start_date, end_date, end_date >= today(), medicine_id, person_id))
        except (ValueError, TypeError, OverflowError):
            errors.append(f"Thuốc ID {medicine_id} có dữ liệu không hợp lệ.")
            
    if errors: return errors
    if not updates and not deletes: return []
    with connect() as conn:
        with conn.cursor() as cur:
            for m_id in deletes:
                cur.execute("DELETE FROM medicines WHERE id = %s AND person_id = %s", (m_id, person_id))
            for values in updates:
                cur.execute("""UPDATE medicines SET name = %s, quantity = %s, daily_dose = %s, start_date = %s, end_date = %s,
                                in_cabinet = CASE WHEN in_cabinet = FALSE THEN FALSE ELSE %s END WHERE id = %s AND person_id = %s""", values)
    return []

def remove_from_cabinet(medicine_id, person_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE medicines SET in_cabinet = FALSE WHERE id = %s AND person_id = %s", (medicine_id, person_id))

try:
    init_database(st.secrets["DATABASE_URL"])
    people, medicines = read_data()
except (psycopg2.Error, KeyError):
    st.error("Không kết nối được Neon DB. Kiểm tra cấu hình DATABASE_URL.")
    st.stop()

# --- 1. QUẢN LÝ NGƯỜI SỬ DỤNG ---
with st.container():
    st.markdown("### 👥 Quản lý người sử dụng")
    with st.form("add_person_form", clear_on_submit=True):
        col_inp, col_btn = st.columns([4, 1])
        with col_inp:
            person_name = st.text_input("Tên người dùng", placeholder="Nhập tên người dùng...", label_visibility="collapsed")
        with col_btn:
            submitted = st.form_submit_button("+ Thêm người", use_container_width=True)
        
        if submitted:
            if not person_name.strip(): 
                st.error("Vui lòng nhập tên người dùng.")
            else:
                add_person(person_name.strip())
                st.rerun()

# --- 2. KHO THUỐC (HIỂN THỊ DẠNG CARD LƯỚI GỌN GÀNG) ---
with st.container():
    st.markdown("### 📦 Kho thuốc")
    
    inventory = {}
    for medicine in medicines:
        if medicine["in_cabinet"]:
            inventory[medicine["name"]] = inventory.get(medicine["name"], 0) + medicine["quantity"]
            
    if not inventory:
        st.info("Kho đang trống.")
    else:
        medicines_list = list(inventory.items())
        cols_per_row = 4
        for i in range(0, len(medicines_list), cols_per_row):
            row_items = medicines_list[i:i + cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, (med_name, qty) in enumerate(row_items):
                with cols[idx]:
                    st.markdown(f"""
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                            <div style="font-weight: 600; color: #1e293b; font-size: 14px; margin-bottom: 4px;">{med_name}</div>
                            <div style="font-size: 20px; font-weight: 700; color: #0f766e;">{qty}</div>
                            <div style="font-size: 11px; color: #64748b;">viên</div>
                        </div>
                    """, unsafe_allow_html=True)

# --- 3. ĐƠN THUỐC & NGƯỜI DÙNG CHI TIẾT ---
st.markdown("### 📋 Đơn thuốc")
if not people: st.info("Chưa có người dùng. Hãy thêm người dùng để bắt đầu.")

@st.fragment
def person_card(person, person_medicines):
    person_id = person["id"]
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left: st.subheader(f'👤 {person["name"]}')
        with right:
            if st.button("Xóa người", key=f"delete_person_{person_id}"):
                delete_person(person_id)
                st.rerun(scope="app")

        with st.expander("➕ Nhập thuốc vào đơn"):
            with st.form(f"add_medicine_{person_id}", clear_on_submit=True):
                name = st.text_input("Tên thuốc", key=f"name_{person_id}")
                quantity = st.number_input("Số lượng (viên)", min_value=1, value=1, step=1, key=f"quantity_{person_id}")
                daily_dose = st.number_input("Liều/ngày", min_value=1, value=1, step=1, key=f"dose_{person_id}")
                start_date = st.date_input("Ngày bắt đầu", value=today(), key=f"start_{person_id}")
                if st.form_submit_button("Thêm thuốc"):
                    if not name.strip(): st.error("Vui lòng nhập tên thuốc.")
                    else:
                        add_medicine(person_id, name.strip(), int(quantity), int(daily_dose), start_date)
                        st.rerun(scope="app")

        if not person_medicines: return st.caption("Người này chưa có thuốc trong đơn.")

        rows = [{"ID": m["id"], "Tên thuốc": m["name"], "Số lượng": m["quantity"], "Liều/ngày": m["daily_dose"],
                 "Ngày bắt đầu": m["start_date"], "Ngày kết thúc": m["end_date"], "Trong kho": m["in_cabinet"], "Xóa": False} for m in person_medicines]
        st.write("Bấm trực tiếp vào ô để sửa, sau đó bấm **Lưu thay đổi**.")
        edited = st.data_editor(
            pd.DataFrame(rows), key=f"editor_{person_id}", use_container_width=True, hide_index=True,
            disabled=["ID", "Ngày kết thúc", "Trong kho"],
            column_config={
                "Số lượng": st.column_config.NumberColumn(min_value=1, step=1),
                "Liều/ngày": st.column_config.NumberColumn(min_value=1, step=1),
                "Ngày bắt đầu": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Xóa": st.column_config.CheckboxColumn("Xóa thuốc", default=False),
            }
        )
        if st.button("💾 Lưu thay đổi", key=f"save_{person_id}"):
            errors = save_edits(person_id, edited, person_medicines)
            if errors:
                for error in errors: st.error(error)
            else: st.rerun(scope="app")

        with st.expander("📤 Đưa thuốc ra ngoài"):
            for medicine in person_medicines:
                if medicine["in_cabinet"]:
                    if st.button(f'Đưa ra ngoài: {medicine["name"]}', key=f'remove_{medicine["id"]}'):
                        remove_from_cabinet(medicine["id"], person_id)
                        st.rerun(scope="app")

for person in people:
    person_card(person, [m for m in medicines if m["person_id"] == person["id"]])

# ==========================================
# 4. GỌI MODULE LỊCH CẤP THUỐC CUỐI TRANG
# ==========================================
st.divider()
render_schedule_admin(st, st.secrets["DATABASE_URL"])