import aiosqlite
import json
import os
from typing import List, Dict, Any

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "researchmind.db"))

async def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    # Migrate old database from root folder if it exists there and new db doesn't exist yet
    old_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "researchmind.db")
    if os.path.exists(old_db_path) and not os.path.exists(DB_PATH):
        try:
            import shutil
            shutil.move(old_db_path, DB_PATH)
        except Exception:
            pass
            
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions_meta (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                is_pinned BOOLEAN DEFAULT 0,
                is_archived BOOLEAN DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Try to run migrations for old databases
        try:
            await db.execute("ALTER TABLE chat_history ADD COLUMN user_id TEXT NOT NULL DEFAULT 'anonymous'")
        except Exception:
            pass
            
        try:
            await db.execute("ALTER TABLE sessions_meta ADD COLUMN user_id TEXT NOT NULL DEFAULT 'anonymous'")
        except Exception:
            pass

        await db.commit()

async def append_message(user_id: str, session_id: str, role: str, content: str, metadata: dict = None):
    meta_str = json.dumps(metadata) if metadata else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (user_id, session_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, content, meta_str)
        )
        await db.commit()

async def get_chat_history(user_id: str, session_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content, metadata FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp ASC",
            (user_id, session_id)
        )
        rows = await cursor.fetchall()
        
        history = []
        for row in rows:
            history.append({
                "role": row["role"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None
            })
        return history

async def get_all_sessions(user_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Join with sessions_meta to get pinned and archived status
        cursor = await db.execute('''
            SELECT ch.session_id, MIN(ch.timestamp) as start_time, ch.content, ch.metadata, 
                   COALESCE(sm.is_pinned, 0) as is_pinned,
                   COALESCE(sm.is_archived, 0) as is_archived
            FROM chat_history ch
            LEFT JOIN sessions_meta sm ON ch.session_id = sm.session_id
            WHERE ch.user_id = ? AND ch.role = 'user'
            GROUP BY ch.session_id
            HAVING COALESCE(sm.is_archived, 0) = 0
            ORDER BY is_pinned DESC, start_time DESC
        ''', (user_id,))
        rows = await cursor.fetchall()
        
        sessions = []
        for row in rows:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            doc_heading = meta.get("doc_heading") if meta else None
            title = doc_heading if doc_heading else (row["content"][:40] + "..." if len(row["content"]) > 40 else row["content"])
            
            sessions.append({
                "session_id": row["session_id"],
                "title": title,
                "start_time": row["start_time"],
                "is_pinned": bool(row["is_pinned"])
            })
        return sessions

async def toggle_session_pin(user_id: str, session_id: str, is_pinned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO sessions_meta (session_id, user_id, is_pinned) 
            VALUES (?, ?, ?) 
            ON CONFLICT(session_id) DO UPDATE SET is_pinned=excluded.is_pinned
        ''', (session_id, user_id, int(is_pinned)))
        await db.commit()

async def toggle_session_archive(user_id: str, session_id: str, is_archived: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO sessions_meta (session_id, user_id, is_archived) 
            VALUES (?, ?, ?) 
            ON CONFLICT(session_id) DO UPDATE SET is_archived=excluded.is_archived
        ''', (session_id, user_id, int(is_archived)))
        await db.commit()

async def delete_session(user_id: str, session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM chat_history WHERE user_id = ? AND session_id = ?", (user_id, session_id))
        await db.execute("DELETE FROM sessions_meta WHERE user_id = ? AND session_id = ?", (user_id, session_id))
        await db.commit()

async def register_user(email: str, password_hash: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO users (email, password_hash, user_id) VALUES (?, ?, ?)", (email, password_hash, user_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False # Email already exists

async def get_user_by_email(email: str) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_user_password(email: str, new_password_hash: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (new_password_hash, email)
        )
        await db.commit()
        return cursor.rowcount > 0

async def merge_guest_data(guest_id: str, permanent_id: str):
    if guest_id == permanent_id or not guest_id.startswith('usr_'):
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE chat_history SET user_id = ? WHERE user_id = ?", (permanent_id, guest_id))
        await db.execute("UPDATE sessions_meta SET user_id = ? WHERE user_id = ?", (permanent_id, guest_id))
        await db.commit()
