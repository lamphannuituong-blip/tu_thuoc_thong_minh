
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
    st.dataframe(pd.DataFrame([{"Tên thuốc": name, "Số lượng trong kho": quantity}
                               for name, quantity in inventory.items()]),
                 use_container_width=True, hide_index=True)

st.divider()
st.header("📋 Đơn thuốc")
if not people:
    st.info("Chưa có người dùng. Hãy thêm người dùng để bắt đầu.")

for person in people:
    person_id = person["id"]
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left:
            st.subheader(f'👤 {person["name"]}')
        with right:
            if st.button("Xóa người", key=f"delete_person_{person_id}"):
                try:
                    delete_person(person_id)
                    st.rerun()
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
                            st.rerun()
                        except psycopg2.Error:
                            st.error("Không thể lưu thuốc vào Neon. Vui lòng thử lại.")

        person_medicines = [m for m in medicines if m["person_id"] == person_id]
        if not person_medicines:
            st.caption("Người này chưa có thuốc trong đơn.")
            continue
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
                errors = save_edits(person_id, edited, {m["id"] for m in person_medicines})
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    st.rerun()
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
                        st.rerun()
                    except psycopg2.Error:
                        st.error("Không thể cập nhật kho trên Neon. Vui lòng thử lại.")
