
import argparse
import sys
import pandas as pd
from datetime import datetime
from database import init_db, upsert_student, create_auth, get_conn

# ── Roman numeral semester map ───────────────────────────────────────────────
ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4,
    "V": 5, "VI": 6, "VII": 7, "VIII": 8,
}

# ── Excel serial date → Python date ─────────────────────────────────────────
_EXCEL_EPOCH = pd.Timestamp("1899-12-30")

def _parse_dob(val) -> str | None:
    """Return YYYY-MM-DD string or None."""
    if pd.isna(val):
        return None
    # Already a Timestamp
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%Y-%m-%d")
    # Excel serial number stored as float/int
    try:
        serial = int(float(str(val)))
        if serial > 20000:          # plausible Excel serial (post-1950)
            return (_EXCEL_EPOCH + pd.Timedelta(days=serial)).strftime("%Y-%m-%d")
    except ValueError:
        pass
    # String formats
    val = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def load_excel(path: str) -> pd.DataFrame:
    """
    The Excel file can have one or multiple sheets.
    Each sheet may have a title row like 'I Semester Student Table'
    followed by actual headers on the next row.
    We detect this pattern and skip the title rows automatically.
    """
    xl = pd.ExcelFile(path)
    frames = []

    for sheet in xl.sheet_names:
        raw = xl.parse(sheet, header=None, dtype=str)

        # Find the row that contains 'Reg-no.' or 'regno' (case-insensitive)
        header_row = None
        for i, row in raw.iterrows():
            if any("reg" in str(c).lower() for c in row.values):
                header_row = i
                break

        if header_row is None:
            print(f"  ⚠  Sheet '{sheet}': no header row found – skipping.")
            continue

        df = xl.parse(sheet, header=header_row, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        # Detect semester from a title row above the header
        semester_label = "I"
        if header_row > 0:
            for i in range(header_row - 1, -1, -1):
                cell = str(raw.iloc[i, 0]).strip()
                for roman in ROMAN:
                    if cell.upper().startswith(roman + " SEM"):
                        semester_label = roman
                        break
                if semester_label != "I":
                    break

        df["_sheet_semester"] = semester_label
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to standard names regardless of capitalisation/spacing."""
    col_map = {}
    for c in df.columns:
        cl = c.lower().replace("-", "").replace(".", "").replace(" ", "").replace("_", "")
        if "regno" in cl or "rollno" in cl:      col_map[c] = "regno"
        elif "name" == cl:                        col_map[c] = "name"
        elif "address" in cl:                     col_map[c] = "address"
        elif "dob" in cl or "birth" in cl:        col_map[c] = "dob"
        elif "phoneno" in cl or "mobile" in cl:   col_map[c] = "phone"
        elif "university" in cl:                  col_map[c] = "university"
        elif "email" in cl:                       col_map[c] = "email"
        elif "stream" in cl:                      col_map[c] = "stream"
        elif "semester" in cl and c != "_sheet_semester": col_map[c] = "semester"
        elif "guardianname" in cl:                col_map[c] = "guardian_name"
        elif "guardiancontact" in cl or "guardianphone" in cl: col_map[c] = "guardian_phone"
    df = df.rename(columns=col_map)
    # Fill semester from sheet title if column missing or empty
    if "semester" not in df.columns:
        df["semester"] = df["_sheet_semester"]
    else:
        df["semester"] = df["semester"].fillna(df["_sheet_semester"])
    return df


def import_file(path: str):
    print(f"\n📂  Reading: {path}")
    init_db()

    df = load_excel(path)
    if df.empty:
        print("❌  No data found."); sys.exit(1)

    df = normalise(df)

    # Drop rows with no regno
    df = df[df["regno"].notna() & (df["regno"].str.strip() != "") & (df["regno"] != "nan")]
    df = df[df["regno"].str.startswith("BCA")]   # keep only student rows

    total = len(df)
    print(f"✅  Found {total} students across all semesters.\n")
    print(f"{'#':<5} {'RegNo':<16} {'Name':<22} {'Semester':<10} {'Username':<16} {'Default Password'}")
    print("-" * 90)

    success = 0
    errors  = []

    for _, row in df.iterrows():
        regno   = str(row.get("regno", "")).strip()
        name    = str(row.get("name", "")).strip()
        address = str(row.get("address", "")).strip()
        dob_raw = row.get("dob")
        dob     = _parse_dob(dob_raw)
        phone   = str(row.get("phone", "")).strip()
        univ    = str(row.get("university", "Tribhuvan")).strip()
        email   = str(row.get("email", "")).strip()
        stream  = str(row.get("stream",  "BCA")).strip()
        sem     = str(row.get("semester", "I")).strip()
        g_name  = str(row.get("guardian_name",  "")).strip()
        g_phone = str(row.get("guardian_phone", "")).strip()

        if not regno or not name:
            continue

        try:
            upsert_student(regno, name, address, dob, phone, univ,
                           email, stream, sem, g_name, g_phone)
            default_pw = create_auth(regno, dob)
            success += 1
            print(f"{success:<5} {regno:<16} {name:<22} {sem:<10} {regno:<16} {default_pw}")
        except Exception as e:
            errors.append((regno, str(e)))

    print("\n" + "=" * 90)
    print(f"✅  Imported : {success}/{total}")
    if errors:
        print(f"❌  Errors   : {len(errors)}")
        for r, e in errors:
            print(f"     {r}: {e}")

    print("\n📌  Username  = Registration Number  (e.g. BCA-2081-001)")
    print("📌  Default Password = RegNo + DDMMYYYY of DOB")
    print("📌  Students MUST change their password on first login.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Import BCA students from Excel into MySQL")
    ap.add_argument("--file", default="BCA_Semester_1_to_8_Student_Table_csv.xlsx",
                    help="Path to the Excel file")
    args = ap.parse_args()
    import_file(args.file)
