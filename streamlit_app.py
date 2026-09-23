import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


# ==========================================================
# CẤU HÌNH
# ==========================================================

st.set_page_config(
    page_title="Tủ Thuốc Thông Minh",
    page_icon="💊",
    layout="wide",
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def today():
    return datetime.now(TIMEZONE).date()


# ==========================================================
# DỮ LIỆU TEST
# Không có database bên ngoài.
# Dữ liệu chỉ tồn tại trong phiên chạy hiện tại.
# ==========================================================

if "people" not in st.session_state:
    st.session_state.people = []

if "medicines" not in st.session_state:
    st.session_state.medicines = []

if "next_person_id" not in st.session_state:
    st.session_state.next_person_id = 1

if "next_medicine_id" not in st.session_state:
    st.session_state.next_medicine_id = 1


# ==========================================================
# HÀM XỬ LÝ
# ==========================================================

def calculate_end_date(start_date, quantity, daily_dose):
    days = math.ceil(quantity / daily_dose)
    return start_date + timedelta(days=days)


def check_expired():
    """Đưa thuốc quá ngày kết thúc ra khỏi kho phần mềm."""

    for medicine in st.session_state.medicines:
        if (
            medicine["in_cabinet"]
            and medicine["end_date"] < today()
        ):
            medicine["in_cabinet"] = False


def get_inventory():
    """Tính kho từ các thuốc còn được đánh dấu trong tủ."""

    inventory = {}

    for medicine in st.session_state.medicines:
        if medicine["in_cabinet"]:
            name = medicine["name"]
            inventory[name] = (
                inventory.get(name, 0)
                + medicine["quantity"]
            )

    return inventory


def add_person(name):
    person = {
        "id": st.session_state.next_person_id,
        "name": name,
    }

    st.session_state.people.append(person)
    st.session_state.next_person_id += 1


def delete_person(person_id):
    st.session_state.people = [
        person
        for person in st.session_state.people
        if person["id"] != person_id
    ]

    st.session_state.medicines = [
        medicine
        for medicine in st.session_state.medicines
        if medicine["person_id"] != person_id
    ]


def add_medicine(
    person_id,
    name,
    quantity,
    daily_dose,
    start_date,
):
    end_date = calculate_end_date(
        start_date,
        quantity,
        daily_dose,
    )

    medicine = {
        "id": st.session_state.next_medicine_id,
        "person_id": person_id,
        "name": name,
        "quantity": quantity,
        "daily_dose": daily_dose,
        "start_date": start_date,
        "end_date": end_date,
        "in_cabinet": end_date >= today(),
    }

    st.session_state.medicines.append(medicine)
    st.session_state.next_medicine_id += 1


def get_person_medicines(person_id):
    return [
        medicine
        for medicine in st.session_state.medicines
        if medicine["person_id"] == person_id
    ]


# ==========================================================
# GIAO DIỆN
# ==========================================================

check_expired()

st.title("💊 Tủ Thuốc Thông Minh")

st.caption(
    "Bản test Streamlit không dùng Neon hoặc database bên ngoài."
)

st.warning(
    "Dữ liệu chỉ được giữ trong phiên sử dụng hiện tại. "
    "Khi phiên kết thúc hoặc ứng dụng khởi động lại, "
    "người dùng và đơn thuốc có thể bị mất."
)


# ==========================================================
# THÊM NGƯỜI DÙNG
# ==========================================================

st.header("👤 Người dùng")

with st.form("add_person_form", clear_on_submit=True):
    person_name = st.text_input(
        "Tên người dùng",
        placeholder="Nhập tên người dùng...",
    )

    submitted = st.form_submit_button(
        "+ Thêm người dùng"
    )

    if submitted:
        if not person_name.strip():
            st.error("Vui lòng nhập tên người dùng.")
        else:
            add_person(person_name.strip())
            st.rerun()


# ==========================================================
# KHO THUỐC
# ==========================================================

st.divider()

st.header("📦 Kho thuốc")

inventory = get_inventory()

if not inventory:
    st.info("Kho đang trống.")
else:
    inventory_rows = [
        {
            "Tên thuốc": name,
            "Số lượng trong kho": quantity,
        }
        for name, quantity in inventory.items()
    ]

    st.dataframe(
        pd.DataFrame(inventory_rows),
        use_container_width=True,
        hide_index=True,
    )


# ==========================================================
# ĐƠN THUỐC THEO NGƯỜI DÙNG
# ==========================================================

st.divider()

st.header("📋 Đơn thuốc")

if not st.session_state.people:
    st.info(
        "Chưa có người dùng. "
        "Hãy thêm người dùng để bắt đầu."
    )


for person in st.session_state.people:
    person_id = person["id"]

    with st.container(border=True):
        left, right = st.columns([5, 1])

        with left:
            st.subheader(f'👤 {person["name"]}')

        with right:
            if st.button(
                "Xóa người",
                key=f"delete_person_{person_id}",
            ):
                delete_person(person_id)
                st.rerun()

        # --------------------------------------------------
        # FORM THÊM THUỐC
        # --------------------------------------------------

        with st.expander("➕ Nhập thuốc vào đơn"):
            with st.form(
                f"add_medicine_{person_id}",
                clear_on_submit=True,
            ):
                name = st.text_input(
                    "Tên thuốc",
                    key=f"name_{person_id}",
                )

                quantity = st.number_input(
                    "Số lượng (viên)",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"quantity_{person_id}",
                )

                daily_dose = st.number_input(
                    "Liều/ngày",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"dose_{person_id}",
                )

                start_date = st.date_input(
                    "Ngày bắt đầu",
                    value=today(),
                    key=f"start_{person_id}",
                )

                save_new = st.form_submit_button(
                    "Thêm thuốc"
                )

                if save_new:
                    if not name.strip():
                        st.error("Vui lòng nhập tên thuốc.")
                    else:
                        add_medicine(
                            person_id,
                            name.strip(),
                            int(quantity),
                            int(daily_dose),
                            start_date,
                        )

                        st.rerun()

        # --------------------------------------------------
        # BẢNG THUỐC
        # --------------------------------------------------

        medicines = get_person_medicines(person_id)

        if not medicines:
            st.caption("Người này chưa có thuốc trong đơn.")
            continue

        rows = []

        for medicine in medicines:
            rows.append(
                {
                    "ID": medicine["id"],
                    "Tên thuốc": medicine["name"],
                    "Số lượng": medicine["quantity"],
                    "Liều/ngày": medicine["daily_dose"],
                    "Ngày bắt đầu": medicine["start_date"],
                    "Ngày kết thúc": medicine["end_date"],
                    "Trong kho": medicine["in_cabinet"],
                    "Xóa": False,
                }
            )

        st.write(
            "Bấm trực tiếp vào ô để sửa, "
            "sau đó bấm **Lưu thay đổi**."
        )

        edited = st.data_editor(
            pd.DataFrame(rows),
            key=f"editor_{person_id}",
            use_container_width=True,
            hide_index=True,
            disabled=[
                "ID",
                "Ngày kết thúc",
                "Trong kho",
            ],
            column_config={
                "Số lượng": st.column_config.NumberColumn(
                    min_value=1,
                    step=1,
                ),
                "Liều/ngày": st.column_config.NumberColumn(
                    min_value=1,
                    step=1,
                ),
                "Ngày bắt đầu": st.column_config.DateColumn(
                    format="DD/MM/YYYY",
                ),
                "Xóa": st.column_config.CheckboxColumn(
                    "Xóa thuốc",
                    default=False,
                ),
            },
        )

        if st.button(
            "💾 Lưu thay đổi",
            key=f"save_{person_id}",
        ):
            errors = []

            for _, row in edited.iterrows():
                medicine_id = int(row["ID"])

                medicine = next(
                    (
                        item
                        for item in st.session_state.medicines
                        if item["id"] == medicine_id
                        and item["person_id"] == person_id
                    ),
                    None,
                )

                if medicine is None:
                    continue

                if bool(row["Xóa"]):
                    st.session_state.medicines.remove(
                        medicine
                    )
                    continue

                name = str(row["Tên thuốc"]).strip()

                try:
                    quantity = int(row["Số lượng"])
                    daily_dose = int(row["Liều/ngày"])

                    start_date = row["Ngày bắt đầu"]

                    if isinstance(start_date, str):
                        start_date = date.fromisoformat(
                            start_date
                        )

                    if hasattr(start_date, "date"):
                        start_date = start_date.date()

                    if (
                        not name
                        or quantity < 1
                        or daily_dose < 1
                        or not isinstance(start_date, date)
                    ):
                        raise ValueError()

                    end_date = calculate_end_date(
                        start_date,
                        quantity,
                        daily_dose,
                    )

                except (ValueError, TypeError, OverflowError):
                    errors.append(
                        f"Thuốc ID {medicine_id} có dữ liệu không hợp lệ."
                    )
                    continue

                medicine.update(
                    {
                        "name": name,
                        "quantity": quantity,
                        "daily_dose": daily_dose,
                        "start_date": start_date,
                        "end_date": end_date,
                        "in_cabinet": end_date >= today(),
                    }
                )

            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.success(
                    "Đã lưu đơn thuốc và cập nhật kho."
                )
                st.rerun()

        # --------------------------------------------------
        # ĐƯA THUỐC RA NGOÀI
        # --------------------------------------------------

        with st.expander("📤 Đưa thuốc ra ngoài"):
            for medicine in medicines:
                if not medicine["in_cabinet"]:
                    continue

                if st.button(
                    f'Đưa ra ngoài: {medicine["name"]}',
                    key=f"remove_{medicine['id']}",
                ):
                    medicine["in_cabinet"] = False
                    st.rerun()