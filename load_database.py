import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Add backend to path to import cfg_database
sys.path.append(os.getcwd())
from app.core.cfg_database import engine

sql_files = [
    "../Sql/00_DDL_drop_tables_banco_andino.sql",
    "../Sql/01_DDL_create_tables_banco_andino.sql",
    "../Sql/02_DML_catalogos_banco_andino.sql",
    "../Sql/03_DML_clientes_personal_banco_andino.sql",
    "../Sql/04_DML_creditos_2025_banco_andino.sql",
    "../Sql/05_DML_ahorros_2025_banco_andino.sql",
    "../Sql/06_DML_metas_kpis_banco_andino.sql",
    "../Sql/07_DDL_DML_mejoras_proyecto.sql",
    "../Sql/08_DML_crear_castor_perez.sql"
]

def run_sql_file(conn, file_path):
    print(f"Executing {file_path}...")
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False
    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()
    
    # Execute the SQL statements
    conn.execute(text(sql_content))
    return True

def main():
    print("Connecting to database...")
    with engine.begin() as conn:
        for sql_file in sql_files:
            success = run_sql_file(conn, sql_file)
            if not success:
                print("Failed at", sql_file)
                sys.exit(1)
    print("Database loaded successfully!")

if __name__ == "__main__":
    main()
