"""
Microservicio 2 - INVENTARIO
Base de datos propia: SQLite (inventario.db)
"""
import os
import sqlite3
from contextlib import closing

from fastapi import FastAPI, HTTPException, Query

DB_PATH = os.getenv("DB_PATH", "inventario.db")

app = FastAPI(title="Servicio de Inventario (micro 2)")

# Datos iniciales para que la base no arranque vacía
TARJETAS_INICIALES = [
    ("NVIDIA", "RTX 4060", 1_350_000, 12),
    ("NVIDIA", "RTX 4070", 2_600_000, 5),
    ("NVIDIA", "RTX 4080 Super", 4_900_000, 2),
    ("NVIDIA", "RTX 4090", 8_200_000, 0),
    ("AMD", "RX 7600", 1_150_000, 8),
    ("AMD", "RX 7800 XT", 2_300_000, 4),
    ("AMD", "RX 7900 XTX", 4_400_000, 0),
    ("Intel", "Arc A770", 1_250_000, 6),
]


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_bd():
    with closing(conectar()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tarjetas (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                marca   TEXT    NOT NULL,
                modelo  TEXT    NOT NULL UNIQUE,
                precio  INTEGER NOT NULL,
                stock   INTEGER NOT NULL
            )
            """
        )
        if conn.execute("SELECT COUNT(*) FROM tarjetas").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO tarjetas (marca, modelo, precio, stock) VALUES (?, ?, ?, ?)",
                TARJETAS_INICIALES,
            )


@app.on_event("startup")
def al_iniciar():
    inicializar_bd()


@app.get("/salud")
def salud():
    return {"servicio": "inventario", "estado": "ok"}


@app.get("/inventario")
def listar_inventario():
    """Lista todas las tarjetas del inventario."""
    with closing(conectar()) as conn:
        filas = conn.execute("SELECT * FROM tarjetas ORDER BY marca, precio").fetchall()
    return [dict(f) for f in filas]


@app.get("/inventario/buscar")
def buscar_tarjeta(modelo: str = Query(..., min_length=2, description="Ej: 4070, RX 7600")):
    """
    Busca una tarjeta por modelo (búsqueda parcial, sin importar mayúsculas).
    Si hay varias coincidencias, prioriza la que tenga stock.
    """
    with closing(conectar()) as conn:
        fila = conn.execute(
            """
            SELECT * FROM tarjetas
            WHERE LOWER(modelo) LIKE LOWER(?)
            ORDER BY (stock > 0) DESC, precio ASC
            LIMIT 1
            """,
            (f"%{modelo.strip()}%",),
        ).fetchone()

    if fila is None:
        raise HTTPException(status_code=404, detail=f"No existe ninguna tarjeta que coincida con '{modelo}'")

    t = dict(fila)
    return {
        "marca": t["marca"],
        "modelo": t["modelo"],
        "precio": t["precio"],
        "stock": t["stock"],
        "disponible": t["stock"] > 0,
    }
