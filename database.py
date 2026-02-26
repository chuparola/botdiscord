import aiosqlite

DB_PATH = "pedidos.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)
        await db.commit()
        print("✅ SQLite pronto")


async def criar_pedido(user_id, username, payment_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO pedidos (user_id, username, payment_id, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (user_id, username, payment_id)
        )
        await db.commit()


async def listar_pendentes():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, payment_id
            FROM pedidos
            WHERE status = 'pending'
            """
        )
        rows = await cursor.fetchall()
        return rows


async def atualizar_status(payment_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE pedidos
            SET status = ?
            WHERE payment_id = ?
            """,
            (status, payment_id)
        )
        await db.commit()