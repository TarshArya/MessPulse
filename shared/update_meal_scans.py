from db import get_connection

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE meal_scans ADD COLUMN meal_type TEXT")
    print("meal_type column added successfully.")
except Exception as e:
    print("Skipped:", e)

conn.commit()
conn.close()