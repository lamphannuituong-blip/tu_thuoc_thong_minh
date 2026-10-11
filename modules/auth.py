import streamlit as st
import psycopg2
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_auth_database(database_url):
    try:
        with psycopg2.connect(database_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS system_users (
                        id BIGSERIAL PRIMARY KEY,
                        fullname TEXT NOT NULL,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'user',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    INSERT INTO system_users (fullname, username, password_hash, role)
                    VALUES ('Quản Trị Viên', 'admin', %s, 'admin')
                    ON CONFLICT (username) DO NOTHING;
                """, (hash_password("123456"),))
                conn.commit()
    except Exception:
        pass

def inject_auth_css():
    try:
        with open("assets/auth.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Không tìm thấy file assets/auth.css")

def render_auth(database_url):
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    if "social_provider" not in st.session_state:
        st.session_state.social_provider = None

    # --- KHI ĐÃ ĐĂNG NHẬP: TẠO GIAO DIỆN DASHBOARD MÀU SẮC DỄ NHÌN, HIỆN ĐẠI ---
    if st.session_state.logged_in:
        st.markdown("""
            <style>
                /* Nền gradient xanh dương đậm chuyên nghiệp cho dashboard */
                .stApp {
                    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f2a4a 100%) !important;
                    background-attachment: fixed;
                }
                
                /* Tối ưu bố cục rộng rãi, thoáng đãng */
                [data-testid="block-container"] {
                    max-width: 1300px !important;
                    padding: 2.5rem 2rem !important;
                }

                /* Làm đẹp các khung chứa bảng dữ liệu (DataFrames/Containers) */
                div[data-testid="stVerticalBlock"] > div {
                    color: #f8fafc !important;
                }
            </style>
        """, unsafe_allow_html=True)
        return True

    init_auth_database(database_url)
    inject_auth_css()

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("""
            <div class="auth-left-content">
                <h2>Smart Medicine Cabinet</h2>
                <p>
                    Join the smart healthcare platform to manage medications, automated dispensing, and prescriptions securely.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.auth_mode == "login":
            if st.button("Switch to Create Account"):
                st.session_state.auth_mode = "signup"
                st.session_state.social_provider = None
                st.rerun()
        else:
            if st.button("Switch to Sign In"):
                st.session_state.auth_mode = "login"
                st.session_state.social_provider = None
                st.rerun()

    with col2:
        with st.container(border=True):
            if st.session_state.social_provider:
                provider_name = "Google" if st.session_state.social_provider == "google" else "Facebook"
                st.markdown(f"<h1>{provider_name.upper()} LOGIN</h1>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; color: rgba(255,255,255,0.7); font-size: 0.9rem;'>Nhập email {provider_name} của bạn</p>", unsafe_allow_html=True)
                
                social_email = st.text_input("Email", placeholder=f"Nhập email {provider_name}...", label_visibility="collapsed")
                social_name = st.text_input("Full Name", placeholder="Họ và tên...", label_visibility="collapsed")
                
                if st.button(f"Xác nhận {provider_name}"):
                    if not social_email or not social_name:
                        st.error("Vui lòng điền đầy đủ thông tin.")
                    else:
                        with st.spinner(f"Đang kết nối {provider_name}..."):
                            try:
                                with psycopg2.connect(database_url, connect_timeout=10) as conn:
                                    with conn.cursor() as cur:
                                        cur.execute("SELECT fullname, role, password_hash FROM system_users WHERE username = %s", (social_email,))
                                        user_data = cur.fetchone()
                                        
                                        if not user_data:
                                            dummy_pass = hash_password(social_email + "_social")
                                            cur.execute(
                                                "INSERT INTO system_users (fullname, username, password_hash, role) VALUES (%s, %s, %s, 'user')",
                                                (social_name, social_email, dummy_pass)
                                            )
                                            conn.commit()
                                            user_data = (social_name, 'user', dummy_pass)
                                        
                                        st.session_state.logged_in = True
                                        st.session_state.username = social_email
                                        st.session_state.fullname = user_data[0]
                                        st.session_state.role = user_data[1]
                                        st.session_state.social_provider = None
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Lỗi: {e}")
                
                if st.button("Quay lại"):
                    st.session_state.social_provider = None
                    st.rerun()

            elif st.session_state.auth_mode == "signup":
                st.markdown("<h1>CREATE NEW ACCOUNT</h1>", unsafe_allow_html=True)
                
                reg_name = st.text_input("Full Name", placeholder="Type full name...", label_visibility="collapsed")
                reg_user = st.text_input("Username", placeholder="Type username or email...", label_visibility="collapsed")
                reg_pass = st.text_input("Password", type="password", placeholder="Type password...", label_visibility="collapsed")
                
                if st.button("Create Account"):
                    if not reg_name or not reg_user or not reg_pass:
                        st.error("Vui lòng điền đủ thông tin.")
                    else:
                        with st.spinner("Đang tạo tài khoản..."):
                            try:
                                with psycopg2.connect(database_url, connect_timeout=10) as conn:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            "INSERT INTO system_users (fullname, username, password_hash) VALUES (%s, %s, %s)",
                                            (reg_name, reg_user, hash_password(reg_pass))
                                        )
                                st.success("Đăng ký thành công! Hãy đăng nhập.")
                                st.session_state.auth_mode = "login"
                                st.rerun()
                            except psycopg2.IntegrityError:
                                st.error("Tài khoản này đã tồn tại.")
                            except Exception as e:
                                st.error(f"Lỗi cơ sở dữ liệu: {e}")

                if st.button("Already a member? Log in"):
                    st.session_state.auth_mode = "login"
                    st.rerun()

            else:
                st.markdown("<h1>SYSTEM LOGIN</h1>", unsafe_allow_html=True)
                
                log_user = st.text_input("Username", placeholder="Type username...", label_visibility="collapsed")
                log_pass = st.text_input("Password", type="password", placeholder="Type password...", label_visibility="collapsed")
                
                if st.button("Login"):
                    if not log_user or not log_pass:
                        st.error("Vui lòng điền đủ thông tin.")
                    else:
                        with st.spinner("Đang xác thực..."):
                            try:
                                with psycopg2.connect(database_url, connect_timeout=10) as conn:
                                    with conn.cursor() as cur:
                                        cur.execute("SELECT fullname, role, password_hash FROM system_users WHERE username = %s", (log_user,))
                                        user_data = cur.fetchone()
                                        
                                if user_data and user_data[2] == hash_password(log_pass):
                                    st.session_state.logged_in = True
                                    st.session_state.username = log_user
                                    st.session_state.fullname = user_data[0]
                                    st.session_state.role = user_data[1]
                                    st.rerun()
                                else:
                                    st.error("Tên đăng nhập hoặc mật khẩu không đúng!")
                            except Exception as e:
                                st.error(f"Lỗi cơ sở dữ liệu: {e}")
                
                if st.button("Don't have an account? Sign up"):
                    st.session_state.auth_mode = "signup"
                    st.rerun()

                st.markdown("""
                    <div style="text-align: center; margin: 15px 0 5px 0; font-size: 11px; color: rgba(255,255,255,0.7); letter-spacing: 0.5px;">
                        <span>OR LOGIN WITH</span>
                    </div>
                """, unsafe_allow_html=True)
                
                col_g, col_f = st.columns(2)
                with col_g:
                    if st.button("🌐 Google"):
                        st.session_state.social_provider = "google"
                        st.rerun()
                with col_f:
                    if st.button("f Facebook"):
                        st.session_state.social_provider = "facebook"
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    return False