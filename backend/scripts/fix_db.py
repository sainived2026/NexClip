import sqlite3
import os

def main():
    db_path = os.path.join(os.path.dirname(__file__), "nexclip.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE clips ADD COLUMN captioned_video_url_landscape VARCHAR(1000) DEFAULT '';")
        conn.commit()
        print("Column captioned_video_url_landscape added successfully to clips table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column already exists.")
        else:
            print(f"OperationalError: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
