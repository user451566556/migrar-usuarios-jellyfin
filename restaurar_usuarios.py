#!/usr/bin/env python3
"""
restaurar_usuarios.py - Versión limpia
Propósito: Restaurar usuarios e historial de reproducción entre bases de datos Jellyfin.
Se ha eliminado la modificación de configuración del servidor para evitar errores.
"""

import argparse
import csv
import datetime
import logging
import os
import shutil
import sqlite3
import sys
import uuid

logger = logging.getLogger("restaurar_usuarios")

##############################################
# LOGGING
##############################################

def setup_logging(debug: bool, logfile: str = "restaurar_usuarios.log"):
    handlers = [logging.StreamHandler(sys.stdout),
                logging.FileHandler(logfile, mode="w", encoding="utf-8")]
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s", handlers=handlers)


##############################################
# BACKUP
##############################################

def backup_file(path: str):
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = f"{path}.backup.{ts}"
    shutil.copy2(path, backup)
    logger.info(f"Backup creado: {backup}")
    return backup


##############################################
# UTILIDADES SQL
##############################################

def get_columns(conn, table: str):
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    return [r[1] for r in cur.fetchall()]


##############################################
# COPIA DE USUARIOS
##############################################

def copy_users(source_db: str, dest_db: str, dry_run: bool):
    logger.info("Copiando tabla Users...")
    with sqlite3.connect(source_db) as src, sqlite3.connect(dest_db) as dst:
        src.row_factory = sqlite3.Row
        src_cols = get_columns(src, "Users")
        dst_cols = get_columns(dst, "Users")
        common = [c for c in src_cols if c in dst_cols]
        
        if not common:
            logger.error("No se encontraron columnas comunes en la tabla Users.")
            return

        col_list = ", ".join([f'"{c}"' for c in common])
        placeholders = ", ".join(["?"] * len(common))
        query = f"INSERT OR REPLACE INTO Users ({col_list}) VALUES ({placeholders})"
        
        rows = src.execute(f"SELECT {col_list} FROM Users").fetchall()
        
        if dry_run:
            logger.info(f"Dry-run activo: Se habrían copiado {len(rows)} usuarios.")
            return
            
        dst.execute("BEGIN;")
        for r in rows:
            dst.execute(query, [r[c] for c in common])
        dst.execute("COMMIT;")
    logger.info("Usuarios restaurados correctamente.")


##############################################
# MIGRACIÓN DE USERITEMDATAS
##############################################

def migrate_useritems(dest_db: str, csv_path: str, dry_run: bool):
    logger.info("Migrando historial (UserItemDatas)...")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)
        
    with sqlite3.connect(dest_db) as conn:
        # Asegurar que la tabla existe con la estructura correcta
        conn.execute("""
            CREATE TABLE IF NOT EXISTS UserItemDatas (
                Id TEXT PRIMARY KEY,
                UserId TEXT NOT NULL,
                ItemId TEXT,
                LastPlayedDate TEXT,
                PlayCount INTEGER NOT NULL,
                IsFavorite INTEGER NOT NULL,
                PlaybackPositionTicks INTEGER NOT NULL,
                Played INTEGER NOT NULL,
                Rating REAL,
                RowVersion INTEGER NOT NULL,
                AudioStreamIndex INTEGER,
                SubtitleStreamIndex INTEGER
            );
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uid ON UserItemDatas (UserId, ItemId);")

        rows_to_insert = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                logger.warning("El archivo CSV está vacío.")
                return

            idx = {name: i for i, name in enumerate(header)}

            for row in reader:
                try:
                    user_id = row[idx.get("UserId", 1)]
                    item_id = row[idx.get("ItemId", 0)]
                    last_play = row[idx.get("LastPlayedDate", 7)] or None
                    playcount = int(row[idx.get("PlayCount", 4)] or 0)
                    isfav = int(row[idx.get("IsFavorite", 5)] or 0)
                    ticks = int(row[idx.get("PlaybackPositionTicks", 6)] or 0)
                    played = int(row[idx.get("Played", 3)] or 0)

                    audio = row[idx.get("AudioStreamIndex", 8)] or None
                    subs = row[idx.get("SubtitleStreamIndex", 9)] or None
                    audio = int(audio) if audio and audio.isdigit() else None
                    subs = int(subs) if subs and subs.isdigit() else None

                    rows_to_insert.append(
                        (str(uuid.uuid4()), user_id, item_id, last_play,
                         playcount, isfav, ticks, played, 1, audio, subs)
                    )
                except Exception as e:
                    continue

        if dry_run:
            logger.info(f"Dry-run: {len(rows_to_insert)} registros de historial procesados.")
            return

        conn.execute("BEGIN;")
        conn.executemany("""
            INSERT INTO UserItemDatas
            (Id, UserId, ItemId, LastPlayedDate, PlayCount, IsFavorite,
             PlaybackPositionTicks, Played, RowVersion, AudioStreamIndex, SubtitleStreamIndex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(UserId, ItemId) DO UPDATE SET
                LastPlayedDate=excluded.LastPlayedDate,
                PlayCount=excluded.PlayCount,
                IsFavorite=excluded.IsFavorite,
                PlaybackPositionTicks=excluded.PlaybackPositionTicks,
                Played=excluded.Played,
                RowVersion=excluded.RowVersion,
                AudioStreamIndex=excluded.AudioStreamIndex,
                SubtitleStreamIndex=excluded.SubtitleStreamIndex;
        """, rows_to_insert)
        conn.execute("COMMIT;")

    logger.info("UserItemDatas (historial) migrado correctamente.")


##############################################
# ARGPARSE
##############################################

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Ruta a la DB origen (jellyfin.db vieja)")
    p.add_argument("--dest", required=True, help="Ruta a la DB destino (jellyfin.db nueva)")
    p.add_argument("--userdatas", help="Ruta al CSV de UserDatas")
    p.add_argument("--migrate-userdatas", action="store_true", help="Activar migración de historial")
    p.add_argument("--dry-run", action="store_true", help="Simulacro (no guarda cambios)")
    p.add_argument("--backup", action="store_true", help="Crear backup antes de escribir")
    p.add_argument("--debug", action="store_true", help="Ver logs detallados")
    return p.parse_args()


##############################################
# MAIN
##############################################

def main():
    args = parse_args()
    setup_logging(args.debug)

    if args.backup:
        backup_file(args.dest)

    logger.info("Iniciando proceso de restauración...")
    
    # 1. Copiar Usuarios
    copy_users(args.source, args.dest, args.dry_run)

    # 2. Migrar Historial (si se solicita)
    if args.migrate_userdatas:
        if args.userdatas:
            migrate_useritems(args.dest, args.userdatas, args.dry_run)
        else:
            logger.warning("Se solicitó --migrate-userdatas pero no se especificó archivo CSV (--userdatas).")

    logger.info("Proceso terminado exitosamente.")


if __name__ == "__main__":
    main()
