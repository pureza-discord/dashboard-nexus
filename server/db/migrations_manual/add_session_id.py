import os
import sqlite3
import sys

def main():
    # Database path relative to project root (same as dev.db in settings.py)
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "dev.db")
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(ai_messages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "session_id" not in columns:
            cursor.execute("ALTER TABLE ai_messages ADD COLUMN session_id VARCHAR(36)")
            conn.commit()
            print("Successfully added session_id to ai_messages table.")
        else:
            print("Column session_id already exists in ai_messages table.")
            
        # Add index for session_id if it doesn't exist
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_ai_messages_session_id ON ai_messages (session_id)")
        conn.commit()
        print("Successfully ensured index on session_id.")
        
    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
