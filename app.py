"""
app.py  –  BCA Student Portal + Admin Panel
Run:  streamlit run app.py
"""
import time
import pandas as pd
import streamlit as st
from database import (
    init_db, get_student, verify_password, is_first_login,
    change_password, get_all_students, search_students,
    update_student_profile, delete_student, upsert_student,
    get_email_by_regno, generate_otp, save_otp, verify_otp,
    auth_exists, create_auth, admin_reset_password,
    verify_admin, change_admin_password, get_stats,
    get_credentials_for_export, default_password,
)
from email_utils import send_otp_email

# ════════════════════════════════════════════════════════════
#  MUST BE THE VERY FIRST STREAMLIT COMMAND IN THE SCRIPT
# ════════════════════════════════════════════════════════════
st.set_page_config(page_title="BCA Student Portal", page_icon="🎓",
                   layout="wide", initial_sidebar_state="collapsed")

init_db()

# ════════════════════════════════════════════════════════════
#  SPLASH / LOADING SCREEN (runs once per session)
# ════════════════════════════════════════════════════════════
if "loaded" not in st.session_state:
    st.session_state.loaded = False

if not st.session_state.loaded:

    # Hide the sidebar only while the splash screen is showing
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    placeholder = st.empty()

    with placeholder.container():

        # Center Logo
        col1, col2, col3, col4 = st.columns([2, 2, 1, 4])

        with col3:
            st.image(
                "images/img.png",
                width=250
            )

        # SPAAMS Title
        st.markdown(
            "<h1 style='text-align:center;'>🎓 SPAAMS</h1>",
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <h4 style='text-align:center;'>
            Student Performance Analytics and Attendance Monitoring System
            </h4>
            """,
            unsafe_allow_html=True
        )

        st.write("")

        # Progress bar
        progress = st.progress(0)
        status = st.empty()

        steps = [
            "Initializing System...",
            "Connecting to Database...",
            "Loading Student Records...",
            "Loading Attendance Module...",
            "Loading Analytics...",
            "Preparing Dashboard...",
            "Starting Application..."
        ]

        for i in range(101):

            progress.progress(i)

            if i < 15:
                status.info(steps[0])
            elif i < 30:
                status.info(steps[1])
            elif i < 45:
                status.info(steps[2])
            elif i < 60:
                status.info(steps[3])
            elif i < 75:
                status.info(steps[4])
            elif i < 90:
                status.info(steps[5])
            else:
                status.info(steps[6])

            time.sleep(0.03)

    placeholder.empty()

    st.session_state.loaded = True
    st.rerun()

# ════════════════════════════════════════════════════════════
#  GLOBAL STYLES
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#f0f4f8; }

.portal-hero { text-align:center; padding:24px 0 8px; }
.portal-hero h1 { font-size:2rem; font-weight:800; color:#1a56db; margin:0; }
.portal-hero p  { color:#6b7280; margin:4px 0 0; font-size:.95rem; }

.info-table { width:100%; border-collapse:collapse; }
.info-table td { padding:9px 14px; border-bottom:1px solid #f3f4f6; font-size:.93rem; }
.info-table td:first-child { color:#6b7280; font-weight:600; width:38%; }
.info-table td:last-child  { color:#111827; font-weight:500; }

.stat-box { background:white; border-radius:12px; padding:20px 24px;
            box-shadow:0 2px 12px rgba(0,0,0,.06); text-align:center; }
.stat-box .num { font-size:2.2rem; font-weight:800; color:#1a56db; }
.stat-box .lbl { font-size:.85rem; color:#6b7280; margin-top:4px; }

.pill { display:inline-block; padding:2px 10px; border-radius:20px;
        font-size:.8rem; font-weight:600; }
.blue  { background:#dbeafe; color:#1e40af; }
.green { background:#d1fae5; color:#065f46; }
.red   { background:#fee2e2; color:#991b1b; }

.stButton>button { border-radius:8px; font-weight:600; transition:.2s; }
.stButton>button:hover { transform:translateY(-1px); }
</style>
""", unsafe_allow_html=True)


DEFAULTS = dict(
    mode="select",          # select | student | admin
    page="login",           # student pages
    admin_page="dashboard", # admin pages
    logged_in=False,
    regno=None,
    admin_logged_in=False,
    admin_user=None,
    otp_regno=None,
    otp_verified=False,
)
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _go(page):         st.session_state.page = page;        st.rerun()
def _ago(page):        st.session_state.admin_page = page;  st.rerun()
def _student_logout():
    for k in ("logged_in", "regno", "otp_regno", "otp_verified"):
        st.session_state[k] = False if k == "logged_in" else None
    st.session_state.page = "login"
    st.session_state.mode = "select"
    st.rerun()
def _admin_logout():
    st.session_state.admin_logged_in = False
    st.session_state.admin_user = None
    st.session_state.admin_page = "dashboard"
    st.session_state.mode = "select"
    st.rerun()

def _hero(sub=""):
    st.markdown(f"""
    <div class="portal-hero">
      <h1>🎓 BCA Student Portal</h1>
      <p>{sub}</p>
    </div>""", unsafe_allow_html=True)

def _validate_pw(pw, confirm):
    if len(pw) < 8:       return False, "Minimum 8 characters."
    if pw != confirm:     return False, "Passwords do not match."
    if pw.isdigit():      return False, "Include at least one letter."
    return True, ""

def _fmt_date(d):
    try:
        if hasattr(d, "strftime"):
            return d.strftime("%d %B %Y")
        return pd.to_datetime(str(d)).strftime("%d %B %Y")
    except Exception:
        return str(d) if d else "—"


def page_mode_select():
    _hero("Tribhuvan University – BCA Programme")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        st.markdown('<div class="card" style="text-align:center;">', unsafe_allow_html=True)
        st.markdown("### Who are you?")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("👨‍🎓  Student Login", use_container_width=True, type="primary"):
                st.session_state.mode = "student"
                st.rerun()
        with col_b:
            if st.button("🛡️  Admin Panel", use_container_width=True):
                st.session_state.mode = "admin"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def page_student_login():
    _hero("Sign in with your Registration Number")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        username = st.text_input("🪪 Username (Registration No.)", placeholder="BCA-2081-001")
        password = st.text_input("🔒 Password", type="password")

        if st.button("Sign In", use_container_width=True, type="primary"):
            u = username.strip().upper()
            regno = verify_password(u, password)
            if not regno:
                st.error("Invalid username or password.")
            else:
                st.session_state.logged_in = True
                st.session_state.regno     = regno
                _go("first_change" if is_first_login(regno) else "dashboard")

        st.markdown("---")
        co1, co2 = st.columns(2)
        with co1:
            if st.button("Forgot Password?", use_container_width=True): _go("forgot")
        with co2:
            if st.button("← Back",           use_container_width=True):
                st.session_state.mode = "select"; st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
    st.info("**Username** = Registration Number (e.g. BCA-2081-001)  \n"
            "**Default password** = RegNo + DOB in DDMMYYYY  \n"
            "e.g. `BCA-2081-001` + `24032006` → `BCA-2081-00124032006`")


def page_first_change():
    _hero("Set Your Permanent Password")
    regno = st.session_state.regno
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.warning(f"👋 Welcome **{regno}**!  \n"
                   "You must set a new password before you can access the portal.", icon="⚠️")
        new_pw  = st.text_input("New Password",    type="password", placeholder="Min 8 characters")
        confirm = st.text_input("Confirm Password", type="password")
        if st.button("Set Password & Enter Portal", use_container_width=True, type="primary"):
            ok, msg = _validate_pw(new_pw, confirm)
            if not ok:
                st.error(msg)
            else:
                change_password(regno, new_pw)
                st.success("✅ Password set! Loading dashboard…")
                st.balloons()
                time.sleep(1.2)
                _go("dashboard")
        st.markdown("</div>", unsafe_allow_html=True)


def page_dashboard():
    regno   = st.session_state.regno
    student = get_student(regno)
    if not student:
        _student_logout()
        return

    # Top bar
    c1, c2 = st.columns([7, 1])
    with c1: st.markdown(f"### 🎓 Welcome, {student['name']}")
    with c2:
        if st.button("Logout 🚪"): _student_logout()

    # Student card
    sem_pill  = f'<span class="pill blue">Semester {student["semester"]}</span>'
    strm_pill = f'<span class="pill green">{student["stream"]}</span>'

    st.markdown(f"""
    <div class="card">
      <h3 style="margin-top:0;color:#1a56db;">📋 Student Details</h3>
      <table class="info-table">
        <tr><td>Registration No.</td><td><strong>{student['regno']}</strong></td></tr>
        <tr><td>Username</td><td>{student['regno']}</td></tr>
        <tr><td>Full Name</td><td>{student['name']}</td></tr>
        <tr><td>Email</td><td>{student.get('email') or '—'}</td></tr>
        <tr><td>Date of Birth</td><td>{_fmt_date(student.get('dob'))}</td></tr>
        <tr><td>Stream</td><td>{strm_pill}</td></tr>
        <tr><td>Semester</td><td>{sem_pill}</td></tr>
        <tr><td>Phone</td><td>{student.get('phone') or '—'}</td></tr>
        <tr><td>Address</td><td>{student.get('address') or '—'}</td></tr>
        <tr><td>University</td><td>{student.get('university') or '—'}</td></tr>
        <tr><td>Guardian</td><td>{student.get('guardian_name') or '—'}
            {(' – ' + student['guardian_phone']) if student.get('guardian_phone') else ''}</td></tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Change Password",  use_container_width=True): _go("change_pw")
    with col2:
        if st.button("✏️ Edit My Profile",   use_container_width=True): _go("edit_profile")


def page_change_password():
    _hero("Change Password")
    regno = st.session_state.regno
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        cur_pw  = st.text_input("Current Password",     type="password")
        new_pw  = st.text_input("New Password",         type="password")
        confirm = st.text_input("Confirm New Password", type="password")
        ca, cb  = st.columns(2)
        with ca:
            if st.button("Update", type="primary", use_container_width=True):
                if not verify_password(regno, cur_pw):
                    st.error("Current password is incorrect.")
                elif verify_password(regno, new_pw):
                    st.warning("New password must differ from current.")
                else:
                    ok, msg = _validate_pw(new_pw, confirm)
                    if not ok: st.error(msg)
                    else:
                        change_password(regno, new_pw)
                        st.success("✅ Password updated!")
                        time.sleep(1.2); _go("dashboard")
        with cb:
            if st.button("← Back", use_container_width=True): _go("dashboard")
        st.markdown("</div>", unsafe_allow_html=True)


def page_edit_profile():
    _hero("Edit Profile")
    regno   = st.session_state.regno
    student = get_student(regno)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        name    = st.text_input("Full Name", value=student["name"])
        email   = st.text_input("Email",     value=student.get("email", ""))
        phone   = st.text_input("Phone",     value=student.get("phone", ""))
        address = st.text_area("Address",    value=student.get("address", ""))
        ca, cb = st.columns(2)
        with ca:
            if st.button("Save", type="primary", use_container_width=True):
                if not name: st.error("Name is required.")
                else:
                    update_student_profile(regno, name, email, phone, address)
                    st.success("✅ Profile updated!")
                    time.sleep(1); _go("dashboard")
        with cb:
            if st.button("← Back", use_container_width=True): _go("dashboard")
        st.markdown("</div>", unsafe_allow_html=True)


def page_forgot():
    _hero("Forgot Password")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.info("Enter your Registration Number. An OTP will be sent to your registered email.")
        regno = st.text_input("Registration Number", placeholder="BCA-2081-001")
        ca, cb = st.columns(2)
        with ca:
            if st.button("Send OTP", type="primary", use_container_width=True):
                r = regno.strip().upper()
                email = get_email_by_regno(r)
                if not email:
                    st.error("Registration number not found.")
                else:
                    otp = generate_otp()
                    save_otp(r, email, otp)
                    ok, msg = send_otp_email(email, r, otp)
                    if ok:
                        st.success(f"OTP sent to **{email}**")
                    else:
                        st.warning(f"⚠️ {msg}  \n**DEV – OTP: `{otp}`** (remove in production)")
                    st.session_state.otp_regno = r
                    time.sleep(1.5); _go("otp")
        with cb:
            if st.button("← Back to Login", use_container_width=True): _go("login")
        st.markdown("</div>", unsafe_allow_html=True)


def page_otp():
    _hero("Verify OTP")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.info(f"Enter the 6-digit OTP sent for **{st.session_state.otp_regno}**")
        otp_in = st.text_input("OTP", max_chars=6, placeholder="______")
        ca, cb = st.columns(2)
        with ca:
            if st.button("Verify", type="primary", use_container_width=True):
                if len(otp_in.strip()) != 6:
                    st.error("Enter a 6-digit OTP.")
                elif verify_otp(st.session_state.otp_regno, otp_in.strip()):
                    st.session_state.otp_verified = True
                    st.success("✅ OTP verified!")
                    time.sleep(1); _go("reset")
                else:
                    st.error("Invalid or expired OTP.")
        with cb:
            if st.button("← Back", use_container_width=True): _go("forgot")
        st.markdown("</div>", unsafe_allow_html=True)


def page_reset():
    if not st.session_state.otp_verified:
        _go("forgot"); return
    _hero("Reset Password")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        new_pw  = st.text_input("New Password",     type="password")
        confirm = st.text_input("Confirm Password", type="password")
        if st.button("Reset Password", type="primary", use_container_width=True):
            ok, msg = _validate_pw(new_pw, confirm)
            if not ok: st.error(msg)
            else:
                change_password(st.session_state.otp_regno, new_pw)
                st.success("✅ Password reset! Redirecting to login…")
                st.session_state.otp_verified = False
                st.session_state.otp_regno    = None
                time.sleep(1.8); _go("login")
        st.markdown("</div>", unsafe_allow_html=True)


def page_admin_login():
    _hero("Admin Panel")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        user = st.text_input("Admin Username")
        pw   = st.text_input("Password", type="password")
        ca, cb = st.columns(2)
        with ca:
            if st.button("Login", type="primary", use_container_width=True):
                if verify_admin(user.strip(), pw):
                    st.session_state.admin_logged_in = True
                    st.session_state.admin_user      = user.strip()
                    st.session_state.admin_page      = "dashboard"
                    st.rerun()
                else:
                    st.error("Invalid admin credentials.")
        with cb:
            if st.button("← Back", use_container_width=True):
                st.session_state.mode = "select"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def admin_sidebar():
    with st.sidebar:
        st.markdown(f"### 🛡️ Admin Panel\n**{st.session_state.admin_user}**")
        st.markdown("---")
        pages = {
            "📊 Dashboard":          "dashboard",
            "👥 All Students":       "students",
            "➕ Add Student":        "add_student",
            "📤 Import Excel":       "import",
            "🔑 Credentials Sheet":  "credentials",
            "⚙️ Admin Settings":     "settings",
        }
        for label, key in pages.items():
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.admin_page == key else "secondary"):
                _ago(key)
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True): _admin_logout()


def page_admin_dashboard():
    st.markdown("## 📊 Dashboard")
    stats = get_stats()

    c1, c2, c3, c4 = st.columns(4)
    boxes = [
        (c1, stats["total"],       "Total Students"),
        (c2, stats["with_auth"],   "Accounts Created"),
        (c3, stats["pw_changed"],  "Passwords Changed"),
        (c4, stats["total"] - stats["pw_changed"], "Pending 1st Login"),
    ]
    for col, num, lbl in boxes:
        with col:
            st.markdown(f"""
            <div class="stat-box">
              <div class="num">{num}</div>
              <div class="lbl">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Semester breakdown
    if stats["by_semester"]:
        st.markdown("### Students by Semester")
        sem_df = pd.DataFrame(
            list(stats["by_semester"].items()),
            columns=["Semester", "Count"]
        ).sort_values("Semester")
        st.bar_chart(sem_df.set_index("Semester"))


def page_admin_students():
    st.markdown("## 👥 All Students")

    # Search + filter
    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("🔍 Search by name, RegNo, email or semester", placeholder="Type to search…")
    with col2:
        sem_filter = st.selectbox("Semester", ["All", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"])

    students = search_students(q) if q else get_all_students()
    if sem_filter != "All":
        students = [s for s in students if str(s.get("semester", "")).strip() == sem_filter]

    st.markdown(f"**{len(students)} student(s) found**")

    if not students:
        st.info("No students found."); return

    for s in students:
        status = ("🟢 Active" if not s.get("is_first_login") else "🟡 Awaiting 1st login") if s.get("username") else "🔴 No account"
        with st.expander(f"{s['regno']}  –  {s['name']}  [{s.get('semester','?')} Sem]  {status}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"""
                <table class="info-table">
                  <tr><td>RegNo</td><td>{s['regno']}</td></tr>
                  <tr><td>Username</td><td>{s.get('username') or '—'}</td></tr>
                  <tr><td>Email</td><td>{s.get('email') or '—'}</td></tr>
                  <tr><td>DOB</td><td>{_fmt_date(s.get('dob'))}</td></tr>
                  <tr><td>Phone</td><td>{s.get('phone') or '—'}</td></tr>
                  <tr><td>Address</td><td>{s.get('address') or '—'}</td></tr>
                  <tr><td>Guardian</td><td>{s.get('guardian_name') or '—'}
                    {' – '+s['guardian_phone'] if s.get('guardian_phone') else ''}</td></tr>
                </table>""", unsafe_allow_html=True)
            with c2:
                if not s.get("username"):
                    if st.button("Create Account", key=f"ca_{s['regno']}"):
                        dob = s.get("dob")
                        dpw = create_auth(s["regno"], dob)
                        st.success(f"Account created!\nDefault PW: `{dpw}`")
                        time.sleep(1); st.rerun()
                else:
                    if st.button("🔄 Reset Password", key=f"rp_{s['regno']}"):
                        dpw = admin_reset_password(s["regno"])
                        st.success(f"Reset!\nNew default: `{dpw}`")
                if st.button("🗑️ Delete", key=f"del_{s['regno']}", type="secondary"):
                    delete_student(s["regno"])
                    st.warning(f"Deleted {s['regno']}")
                    time.sleep(0.8); st.rerun()


def page_admin_add_student():
    st.markdown("## ➕ Add New Student")
    with st.form("add_student_form"):
        c1, c2 = st.columns(2)
        with c1:
            regno    = st.text_input("Registration No.*", placeholder="BCA-2081-036")
            name     = st.text_input("Full Name*")
            email    = st.text_input("Email")
            dob      = st.date_input("Date of Birth", value=None)
            phone    = st.text_input("Phone")
        with c2:
            address  = st.text_area("Address")
            semester = st.selectbox("Semester", ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"])
            stream   = st.text_input("Stream", value="BCA")
            univ     = st.text_input("University", value="Tribhuvan")
            g_name   = st.text_input("Guardian Name")
            g_phone  = st.text_input("Guardian Phone")

        submitted = st.form_submit_button("Add Student & Generate Credentials", type="primary")
        if submitted:
            if not regno or not name:
                st.error("RegNo and Name are required.")
            else:
                dob_str = dob.strftime("%Y-%m-%d") if dob else None
                upsert_student(regno.strip().upper(), name, address, dob_str,
                               phone, univ, email, stream, semester, g_name, g_phone)
                dpw = create_auth(regno.strip().upper(), dob_str)
                st.success(f"""
                ✅ Student added!
                - **Username:** `{regno.strip().upper()}`
                - **Default Password:** `{dpw}`

                Student must change password on first login.
                """)


def page_admin_import():
    st.markdown("## 📤 Import Students from Excel")
    st.info("Upload your Excel file – all semesters are supported. Existing records are updated (no duplicates).")
    uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    if uploaded:
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            from import_students import load_excel, normalise, _parse_dob
            df = load_excel(tmp_path)
            df = normalise(df)
            df = df[df["regno"].notna() & (df["regno"].str.strip() != "") & (df["regno"] != "nan")]
            df = df[df["regno"].str.startswith("BCA")]

            st.markdown(f"**{len(df)} students found in file.**")
            if st.button("Import All", type="primary"):
                results = []
                for _, row in df.iterrows():
                    regno   = str(row.get("regno", "")).strip()
                    name    = str(row.get("name", "")).strip()
                    address = str(row.get("address", "")).strip()
                    dob     = _parse_dob(row.get("dob"))
                    phone   = str(row.get("phone", "")).strip()
                    univ    = str(row.get("university", "Tribhuvan")).strip()
                    email   = str(row.get("email", "")).strip()
                    stream  = str(row.get("stream", "BCA")).strip()
                    sem     = str(row.get("semester", "I")).strip()
                    g_name  = str(row.get("guardian_name", "")).strip()
                    g_phone = str(row.get("guardian_phone", "")).strip()
                    if not regno or not name: continue
                    try:
                        upsert_student(regno, name, address, dob, phone, univ,
                                       email, stream, sem, g_name, g_phone)
                        dpw = create_auth(regno, dob)
                        results.append({"RegNo": regno, "Name": name, "Semester": sem,
                                        "Username": regno, "Default Password": dpw, "Status": "✅"})
                    except Exception as e:
                        results.append({"RegNo": regno, "Name": name, "Semester": sem,
                                        "Username": "—", "Default Password": "—", "Status": f"❌ {e}"})
                st.success(f"Import complete: {len(results)} processed.")
                rdf = pd.DataFrame(results)
                st.dataframe(rdf, use_container_width=True, hide_index=True)
                # Download
                csv = rdf.to_csv(index=False).encode()
                st.download_button("⬇️ Download results CSV", csv,
                                   "import_results.csv", "text/csv")
        finally:
            os.unlink(tmp_path)


def page_admin_credentials():
    st.markdown("## 🔑 Credentials Sheet")
    st.info("This sheet shows every student's username and **what their default password would be** (actual stored password is hashed and cannot be shown). Students who have already changed their password are marked.")

    creds = get_credentials_for_export()
    if not creds:
        st.warning("No students yet."); return

    df = pd.DataFrame(creds)[[
        "regno", "name", "semester", "email",
        "username", "is_first_login", "default_password"
    ]]
    df.columns = ["RegNo", "Name", "Semester", "Email",
                  "Username", "Pending 1st Login", "Default Password"]
    df["Pending 1st Login"] = df["Pending 1st Login"].map({1: "🟡 Yes", 0: "🟢 Changed"})

    sem_filter = st.selectbox("Filter by Semester",
                              ["All", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"])
    if sem_filter != "All":
        df = df[df["Semester"] == sem_filter]

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode()
    st.download_button("⬇️ Download as CSV", csv, "credentials.csv", "text/csv")
    st.warning("⚠️ Keep this file secure. Do not share it publicly.")


def page_admin_settings():
    st.markdown("## ⚙️ Admin Settings")
    with st.expander("🔑 Change Admin Password"):
        with st.form("chg_admin_pw"):
            cur  = st.text_input("Current Password", type="password")
            nw   = st.text_input("New Password",     type="password")
            conf = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Update", type="primary"):
                if not verify_admin(st.session_state.admin_user, cur):
                    st.error("Current password incorrect.")
                else:
                    ok, msg = _validate_pw(nw, conf)
                    if not ok: st.error(msg)
                    else:
                        change_admin_password(st.session_state.admin_user, nw)
                        st.success("✅ Admin password updated!")


# ════════════════════════════════════════════════════════════
#  ROUTER
# ════════════════════════════════════════════════════════════
STUDENT_PAGES = {
    "login":        page_student_login,
    "first_change": page_first_change,
    "dashboard":    page_dashboard,
    "change_pw":    page_change_password,
    "edit_profile": page_edit_profile,
    "forgot":       page_forgot,
    "otp":          page_otp,
    "reset":        page_reset,
}
PUBLIC_PAGES = {"login", "forgot", "otp", "reset"}

ADMIN_PAGES = {
    "dashboard":   page_admin_dashboard,
    "students":    page_admin_students,
    "add_student": page_admin_add_student,
    "import":      page_admin_import,
    "credentials": page_admin_credentials,
    "settings":    page_admin_settings,
}

mode = st.session_state.mode

if mode == "select":
    page_mode_select()

elif mode == "student":
    page = st.session_state.page
    if page not in PUBLIC_PAGES and not st.session_state.logged_in:
        st.session_state.page = "login"; page = "login"
    STUDENT_PAGES.get(page, page_student_login)()

elif mode == "admin":
    if not st.session_state.admin_logged_in:
        page_admin_login()
    else:
        admin_sidebar()
        ADMIN_PAGES.get(st.session_state.admin_page, page_admin_dashboard)()