import psycopg2
import streamlit as st

def log_audit(database_url, user_id, action, details):
    with psycopg2.connect(database_url, connect_timeout=15, sslmode='require') as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs (user_id, action, details) 
                VALUES (%s, %s, %s)
            """, (user_id, action, details))

def render_schedule_admin(st_module, database_url: str):
    st_module.subheader('Lịch cấp thuốc cho thiết bị')
    
    is_doctor = st.session_state.get("role") == "doctor"
    if not is_doctor:
        st_module.warning("⚠️ Cảnh báo: Chỉ tài khoản Bác sĩ mới có thẩm quyền phê duyệt lịch cấp thuốc.")
    
    with psycopg2.connect(database_url, connect_timeout=15, sslmode='require') as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name FROM people ORDER BY id')
            people = cur.fetchall()
            cur.execute('SELECT id, person_id, name, quantity, daily_dose FROM medicines ORDER BY id')
            meds = cur.fetchall()
            
    if not people or not meds:
        st_module.info('Hãy thêm bệnh nhân và thuốc trước.')
        return
        
    person_map = {f'{name} (ID {pid})': pid for pid, name in people}
    selected_person_label = st_module.selectbox('Bệnh nhân', list(person_map))
    person_id = person_map[selected_person_label]
    med_rows = [m for m in meds if m[1] == person_id]
    
    if not med_rows:
        st_module.info('Bệnh nhân này chưa có thuốc.')
    else:
        med_map = {f'{m[2]} — thuốc ID {m[0]}': m for m in med_rows}
        label = st_module.selectbox('Thuốc', list(med_map))
        med = med_map[label]
        
        with st_module.form('schedule_form'):
            times = st_module.text_input('Giờ uống (HH:MM, ngăn cách dấu phẩy)', '08:00,20:00')
            units = st_module.number_input('Số đơn vị mỗi lần', min_value=1, max_value=100, value=1)
            approve = st_module.checkbox('Tôi đã xác minh chỉ định và phê duyệt lịch này', value=False, disabled=not is_doctor)
            submitted = st_module.form_submit_button('Lưu lịch và Phê duyệt', disabled=not is_doctor)
            
        if submitted:
            import re
            parsed = [x.strip() for x in times.split(',') if x.strip()]
            if not approve:
                st_module.error('Cần xác nhận phê duyệt y khoa trước khi lưu.')
            elif not parsed or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', x) for x in parsed):
                st_module.error('Giờ không hợp lệ. Dùng định dạng HH:MM.')
            else:
                doctor_name = st.session_state["fullname"]
                with psycopg2.connect(database_url, connect_timeout=15, sslmode='require') as conn:
                    with conn.cursor() as cur:
                        cur.execute('''INSERT INTO medication_schedules
                            (medicine_id,times_local,units_per_dose,approved,approved_by,approved_at,updated_at)
                            VALUES (%s,%s,%s,TRUE,%s,NOW(),NOW())
                            ON CONFLICT (medicine_id) DO UPDATE SET times_local=EXCLUDED.times_local,
                            units_per_dose=EXCLUDED.units_per_dose, approved=TRUE,
                            approved_by=EXCLUDED.approved_by, approved_at=NOW(), updated_at=NOW()''',
                            (med[0], parsed, int(units), doctor_name))
                log_audit(database_url, doctor_name, "APPROVE_SCHEDULE", f"Phê duyệt lịch cho thuốc ID {med[0]}, bệnh nhân ID {person_id}")
                st_module.success(f'Đã lưu lịch! Ký duyệt bởi: **{doctor_name}**.')