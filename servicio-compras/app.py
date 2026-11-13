"""
Microservicio 1 - COMPRAS (el que atiende al usuario)
Base de datos propia: SQLite (compras.db)
"""
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "compras.db")
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://localhost:5002")

app = FastAPI(title="Servicio de Compras (micro 1)")


class Consulta(BaseModel):
    modelo: str = Field(..., min_length=2, examples=["RTX 4070"])


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_bd():
    with closing(conectar()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS consultas (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                modelo_consultado  TEXT    NOT NULL,
                encontrado         INTEGER NOT NULL,
                marca              TEXT,
                modelo             TEXT,
                precio             INTEGER,
                stock              INTEGER,
                disponible         INTEGER,
                fecha              TEXT    NOT NULL
            )
            """
        )


def guardar_consulta(modelo_consultado: str, resp: dict | None) -> int:
    with closing(conectar()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO consultas
                (modelo_consultado, encontrado, marca, modelo, precio, stock, disponible, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                modelo_consultado,
                1 if resp else 0,
                resp["marca"] if resp else None,
                resp["modelo"] if resp else None,
                resp["precio"] if resp else None,
                resp["stock"] if resp else None,
                (1 if resp["disponible"] else 0) if resp else None,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return cur.lastrowid


def pesos(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")


@app.on_event("startup")
def al_iniciar():
    inicializar_bd()


@app.get("/", include_in_schema=False)
def pagina_principal():
    """Página web para el usuario."""
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/salud")
def salud():
    return {"servicio": "compras", "estado": "ok"}


@app.get("/catalogo")
def catalogo():
    """Lista de modelos (se la pide al inventario) para mostrar sugerencias en la página."""
    try:
        r = httpx.get(f"{INVENTARIO_URL}/inventario", timeout=5)
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="El servicio de inventario no está disponible")
    return [{"marca": t["marca"], "modelo": t["modelo"]} for t in r.json()]


@app.post("/consultas")
def consultar_tarjeta(consulta: Consulta):
    """El usuario pregunta por una tarjeta gráfica."""
    modelo = consulta.modelo.strip()

    # 2. Preguntarle al microservicio de inventario
    try:
        r = httpx.get(f"{INVENTARIO_URL}/inventario/buscar", params={"modelo": modelo}, timeout=5)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="El servicio de inventario no está disponible")

    if r.status_code == 404:
        resp_inventario = None
    elif r.status_code == 200:
        resp_inventario = r.json()
    else:
        raise HTTPException(status_code=502, detail=f"Respuesta inesperada del inventario ({r.status_code})")

    # 4. Guardar la respuesta en la base de datos de compras
    consulta_id = guardar_consulta(modelo, resp_inventario)

    # 5. Responder al usuario
    if resp_inventario is None:
        return {
            "consulta_id": consulta_id,
            "encontrado": False,
            "mensaje": f"No manejamos ninguna tarjeta que coincida con '{modelo}'.",
        }

    if resp_inventario["disponible"]:
        mensaje = (
            f"¡Sí la tenemos! {resp_inventario['marca']} {resp_inventario['modelo']} "
            f"a {pesos(resp_inventario['precio'])} ({resp_inventario['stock']} en stock)."
        )
    else:
        mensaje = (
            f"La {resp_inventario['marca']} {resp_inventario['modelo']} cuesta "
            f"{pesos(resp_inventario['precio'])}, pero está agotada."
        )

    return {"consulta_id": consulta_id, "encontrado": True, **resp_inventario, "mensaje": mensaje}


@app.get("/consultas")
def historial():
    """Historial de todo lo que se ha consultado (lo guardado en compras.db)."""
    with closing(conectar()) as conn:
        filas = conn.execute("SELECT * FROM consultas ORDER BY id DESC").fetchall()
    return [dict(f) for f in filas]
