# 🎓 BCA Student Portal – MySQL Edition

Streamlit portal for Tribhuvan University BCA students with auto-generated credentials, bcrypt-hashed passwords, forced first-login password change, and email OTP forgot-password.

---

## 📁 Files

```
bca_student_portal/
├── app.py                  ← Main Streamlit app  (streamlit run app.py)
├── database.py             ← MySQL connection + all queries
├── import_students.py      ← Import Excel → MySQL (run from terminal)
├── email_utils.py          ← Gmail SMTP OTP sender
├── requirements.txt
├── .env.example            ← Copy to .env and fill in
└── README.md
```

---

## 🚀 Setup (5 steps)

### 1 – Install dependencies
```bash
pip install -r requirements.txt
```

### 2 – Create MySQL database
```sql
CREATE DATABASE bca_portal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3 – Configure .env
```bash
cp .env.example .env
```
Edit `.env`:
```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=bca_portal
DB_USER=root
DB_PASSWORD=your_mysql_password

EMAIL_SENDER=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password   # Gmail App Password

ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@1234
```
> For Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords

### 4 – Import students from Excel
```bash
python import_students.py --file BCA_Semester_1_to_8_Student_Table_csv.xlsx
```
This prints a table of all students with their **username** and **default password**.

### 5 – Run the app
```bash
streamlit run app.py
```
Open **http://localhost:8501**

---

## 🔐 Credential Rules

| Field | Rule | Example |
|-------|------|---------|
| Username | = Registration Number | `BCA-2081-001` |
| Default Password | RegNo + DOB as DDMMYYYY | `BCA-2081-00124032006` |
| After 1st login | Student must set new password | (they choose) |

All passwords stored as **bcrypt hashes** — admin can never see actual passwords.

---

## 🛡️ Admin Panel Features

| Feature | Description |
|---------|-------------|
| Dashboard | Stats: total students, accounts created, pending 1st login, by semester |
| All Students | Search/filter, view full details, create accounts, reset passwords, delete |
| Add Student | Add one student manually — credentials auto-generated |
| Import Excel | Upload any BCA Excel sheet (all semesters) — bulk upsert |
| Credentials Sheet | Export all usernames + default passwords as CSV |
| Settings | Change admin password |

---

## 👨‍🎓 Student Portal Features

| Feature | Description |
|---------|-------------|
| Login | Username + password |
| First login | Forced password change before any access |
| Dashboard | Full student details |
| Change Password | Any time from dashboard |
| Edit Profile | Update email, phone, address |
| Forgot Password | Enter RegNo → OTP email → verify → reset |

---

## 📊 Adding More Students (300+)

Just add rows to your Excel file (same columns) and re-run:
```bash
python import_students.py --file updated_students.xlsx
```
Already-imported students are **updated, not duplicated**.

Or use the **Admin Panel → Import Excel** upload in the browser — no terminal needed.

---

## 🗄️ MySQL Table Structure

```sql
students     – all student details
auth         – username, bcrypt hash, is_first_login flag
otp_tokens   – OTP codes with expiry
admins       – admin credentials
```

Tables are created automatically on first run.
