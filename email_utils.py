
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("EMAIL_SENDER", "")
SENDER_PASS  = os.getenv("EMAIL_PASSWORD", "")


def send_otp_email(to_email: str, regno: str, otp: str) -> tuple[bool, str]:
    if not SENDER_EMAIL or not SENDER_PASS:
        return False, "Email not configured (see .env)"

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1a56db;padding:20px;border-radius:10px 10px 0 0;">
        <h2 style="color:white;margin:0;">🎓 BCA Student Portal</h2>
        <p style="color:#c7d7f8;margin:4px 0 0;">Password Reset Request</p>
      </div>
      <div style="border:1px solid #e0e0e0;border-top:none;padding:28px;border-radius:0 0 10px 10px;">
        <p>Hello <strong>{regno}</strong>,</p>
        <p>Use this OTP to reset your password:</p>
        <div style="background:#f0f5ff;border:2px dashed #1a56db;border-radius:10px;
                    text-align:center;padding:24px;margin:20px 0;">
          <span style="font-size:40px;font-weight:900;letter-spacing:10px;color:#1a56db;">
            {otp}
          </span>
        </div>
        <p style="color:#555;">Valid for <strong>10 minutes</strong>. Do not share with anyone.</p>
        <p style="color:#c00;font-size:13px;">If you did not request this, ignore this email.</p>
      </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BCA Portal – OTP for {regno}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True, f"OTP sent to {to_email}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail auth failed – check EMAIL_PASSWORD in .env (use App Password)"
    except Exception as e:
        return False, f"Email error: {e}"
