import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(page_title="Tủ Thuốc Thông Minh", page_icon="💊", layout="wide")

# Chỉ thay đổi màu sắc / kiểu hiển thị, không thay đổi xử lý dữ liệu.
st.markdown("""
<style>
:root { --cabinet-green:#407b73; --cabinet-bg:#f4f8ff; --cabinet-line:#dce4f3; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--cabinet-bg); color:#263044; }
[data-testid="stHeader"] { background:var(--cabinet-bg); }
.block-container { max-width: 1450px; padding-top: 1.4rem; }
h1 { background:var(--cabinet-green); color:white !important; padding:26px 32px; border-radius:18px 18px 0 0; margin-bottom:0 !important; }
h1 + div, h1 + p { color:#526277; }
h2, h3 { color:#263044 !important; }
[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] { background:white; border-radius:18px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:18px !important; border-color:var(--cabinet-line) !important; background:white; }
[data-testid="stForm"] { background:white; border:1px solid var(--cabinet-line); border-radius:18px; padding:16px; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border:1px solid var(--cabinet-line); border-radius:14px; overflow:hidden; }
[data-testid="stExpander"] { background:white; border:1px solid var(--cabinet-line); border-radius:14px; }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button { background:#509a54 !important; border-color:#509a54 !important; color:white !important; border-radius:12px !important; }
.stButton > button, [data-testid="stFormSubmitButton"] button { border-radius:12px; font-weight:600; }
.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover { border-color:#407b73 !important; }
input { border-radius:11px !important; }
hr { border-color:var(--cabinet-line) !important; }
</style>
""", unsafe_allow_html=True)
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def today():
    return datetime.now(TIMEZONE).date()


def connect():
    # Mỗi thao tác ghi có giao dịch riêng; không dùng chung connection giữa các phiên.
    return psycopg2.connect(st.secrets["DATABASE_URL"], connect_timeout=15)


@st.cache_resource(show_spinner=False)
def init_database(database_url):
    # Chỉ tạo/kiểm tra bảng một lần trong mỗi tiến trình Streamlit.
    with psycopg2.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS medicines (
                    id BIGSERIAL PRIMARY KEY,
                    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    daily_dose INTEGER NOT NULL CHECK (daily_dose > 0),
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    in_cabinet BOOLEAN NOT NULL DEFAULT TRUE
                )
            """)
    return True


def read_data():
    # Chỉ mở một kết nối cho việc kiểm tra hạn và đọc cả hai bảng.
    with connect() as conn:
        with conn.cursor() as cur:
            # Thuốc đã lấy ra không được tự động đưa trở lại kho.
            cur.execute("""
                UPDATE medicines SET in_cabinet = FALSE
                WHERE in_cabinet = TRUE AND end_date < %s
            """, (today(),))
            cur.execute("SELECT id, name FROM people ORDER BY id")
            people = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
            cur.execute("""
                SELECT id, person_id, name, quantity, daily_dose,
                       start_date, end_date, in_cabinet
                FROM medicines ORDER BY id
            """)
            keys = ("id", "person_id", "name", "quantity", "daily_dose",
                    "start_date", "end_date", "in_cabinet")
            medicines = [dict(zip(keys, row)) for row in cur.fetchall()]
    return people, medicines


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
            cur.execute("""
                INSERT INTO medicines(person_id, name, quantity, daily_dose,
                                      start_date, end_date, in_cabinet)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (person_id, name, quantity, daily_dose, start_date,
                  end_date, end_date >= today()))


def save_edits(person_id, edited, original_medicines):
    original = {m["id"]: m for m in original_medicines}
    updates, deletes, errors = [], [], []
    for _, row in edited.iterrows():
        medicine_id = int(row["ID"])
        if medicine_id not in original:
            continue
        if bool(row["Xóa"]):
            deletes.append(medicine_id)
            continue
        try:
            name = str(row["Tên thuốc"]).strip()
            quantity = int(row["Số lượng"])
            daily_dose = int(row["Liều/ngày"])
            start_date = row["Ngày bắt đầu"]
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            elif isinstance(start_date, (pd.Timestamp, datetime)):
                start_date = start_date.date()
            if not name or quantity < 1 or daily_dose < 1 or not isinstance(start_date, date):
                raise ValueError()
            end_date = calculate_end_date(start_date, quantity, daily_dose)
            previous = original[medicine_id]
            # Chỉ cập nhật các dòng thực sự đã sửa; không ghi đè mọi dòng.
            if (name, quantity, daily_dose, start_date) != (
                previous["name"], previous["quantity"],
                previous["daily_dose"], previous["start_date"]
            ):
                updates.append((name, quantity, daily_dose, start_date, end_date,
                                end_date >= today(), medicine_id, person_id))
        except (ValueError, TypeError, OverflowError):
            errors.append(f"Thuốc ID {medicine_id} có dữ liệu không hợp lệ.")
    if errors:
        return errors
    if not updates and not deletes:
        return []
    with connect() as conn:
        with conn.cursor() as cur:
            for medicine_id in deletes:
                cur.execute("DELETE FROM medicines WHERE id = %s AND person_id = %s",
                            (medicine_id, person_id))
            for values in updates:
                cur.execute("""
                    UPDATE medicines SET name = %s, quantity = %s, daily_dose = %s,
                        start_date = %s, end_date = %s,
                        in_cabinet = CASE WHEN in_cabinet = FALSE THEN FALSE ELSE %s END
                    WHERE id = %s AND person_id = %s
                """, values)
    return []


def remove_from_cabinet(medicine_id, person_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE medicines SET in_cabinet = FALSE
                WHERE id = %s AND person_id = %s
            """, (medicine_id, person_id))


try:
    init_database(st.secrets["DATABASE_URL"])
    people, medicines = read_data()
except (psycopg2.Error, KeyError):
    st.error("Không kết nối được Neon. Kiểm tra DATABASE_URL trong Streamlit Secrets và requirements.txt.")
    st.stop()

st.title("💊 Tủ Thuốc Thông Minh")
st.caption("Dữ liệu người dùng, đơn thuốc và kho thuốc được lưu trên Neon PostgreSQL.")
st.info("Ngày kết thúc = ngày bắt đầu + số ngày dùng. Kho hiển thị tổng số viên đã nhập của các thuốc còn được đánh dấu trong tủ, không phải số viên còn lại thực tế.")

st.header("👤 Người dùng")
with st.form("add_person_form", clear_on_submit=True):
    person_name = st.text_input("Tên người dùng", placeholder="Nhập tên người dùng...")
    submitted = st.form_submit_button("+ Thêm người dùng")
    if submitted:
        if not person_name.strip():
            st.error("Vui lòng nhập tên người dùng.")
        else:
            try:
                add_person(person_name.strip())
                st.rerun()
            except psycopg2.Error:
                st.error("Không thể lưu người dùng vào Neon. Vui lòng thử lại.")

st.divider()
st.header("📦 Kho thuốc")
inventory = {}
for medicine in medicines:
    if medicine["in_cabinet"]:
        inventory[medicine["name"]] = inventory.get(medicine["name"], 0) + medicine["quantity"]
if not inventory:
    st.info("Kho đang trống.")
else:
    st.dataframe(pd.DataFrame([
        {"Tên thuốc": name, "Số lượng trong kho": quantity}
        for name, quantity in inventory.items()
    ]), use_container_width=True, hide_index=True)

st.divider()
st.header("📋 Đơn thuốc")
if not people:
    st.info("Chưa có người dùng. Hãy thêm người dùng để bắt đầu.")


@st.fragment
# Sửa ô trong bảng chỉ chạy lại thẻ người dùng này, KHÔNG kết nối Neon mỗi lần gõ.
def person_card(person, person_medicines):
    person_id = person["id"]
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left:
            st.subheader(f'👤 {person["name"]}')
        with right:
            if st.button("Xóa người", key=f"delete_person_{person_id}"):
                try:
                    delete_person(person_id)
                    st.rerun(scope="app")
                except psycopg2.Error:
                    st.error("Không thể xóa người dùng. Vui lòng thử lại.")

        with st.expander("➕ Nhập thuốc vào đơn"):
            with st.form(f"add_medicine_{person_id}", clear_on_submit=True):
                name = st.text_input("Tên thuốc", key=f"name_{person_id}")
                quantity = st.number_input("Số lượng (viên)", min_value=1, value=1,
                                           step=1, key=f"quantity_{person_id}")
                daily_dose = st.number_input("Liều/ngày", min_value=1, value=1,
                                             step=1, key=f"dose_{person_id}")
                start_date = st.date_input("Ngày bắt đầu", value=today(),
                                           key=f"start_{person_id}")
                if st.form_submit_button("Thêm thuốc"):
                    if not name.strip():
                        st.error("Vui lòng nhập tên thuốc.")
                    else:
                        try:
                            add_medicine(person_id, name.strip(), int(quantity),
                                         int(daily_dose), start_date)
                            st.rerun(scope="app")
                        except psycopg2.Error:
                            st.error("Không thể lưu thuốc vào Neon. Vui lòng thử lại.")

        if not person_medicines:
            st.caption("Người này chưa có thuốc trong đơn.")
            return

        rows = [{"ID": m["id"], "Tên thuốc": m["name"], "Số lượng": m["quantity"],
                 "Liều/ngày": m["daily_dose"], "Ngày bắt đầu": m["start_date"],
                 "Ngày kết thúc": m["end_date"], "Trong kho": m["in_cabinet"],
                 "Xóa": False} for m in person_medicines]
        st.write("Bấm trực tiếp vào ô để sửa, sau đó bấm **Lưu thay đổi**.")
        edited = st.data_editor(
            pd.DataFrame(rows), key=f"editor_{person_id}",
            use_container_width=True, hide_index=True,
            disabled=["ID", "Ngày kết thúc", "Trong kho"],
            column_config={
                "Số lượng": st.column_config.NumberColumn(min_value=1, step=1),
                "Liều/ngày": st.column_config.NumberColumn(min_value=1, step=1),
                "Ngày bắt đầu": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Xóa": st.column_config.CheckboxColumn("Xóa thuốc", default=False),
            },
        )
        if st.button("💾 Lưu thay đổi", key=f"save_{person_id}"):
            try:
                errors = save_edits(person_id, edited, person_medicines)
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    st.rerun(scope="app")
            except psycopg2.Error:
                st.error("Không thể lưu thay đổi vào Neon. Vui lòng thử lại.")

        with st.expander("📤 Đưa thuốc ra ngoài"):
            for medicine in person_medicines:
                if not medicine["in_cabinet"]:
                    continue
                if st.button(f'Đưa ra ngoài: {medicine["name"]}',
                             key=f'remove_{medicine["id"]}'):
                    try:
                        remove_from_cabinet(medicine["id"], person_id)
                        st.rerun(scope="app")
                    except psycopg2.Error:
                        st.error("Không thể cập nhật kho trên Neon. Vui lòng thử lại.")


for person in people:
    person_card(person, [m for m in medicines if m["person_id"] == person["id"]])
