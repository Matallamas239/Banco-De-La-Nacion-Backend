import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Add backend to path to import core config/database and security
sys.path.append(os.getcwd())
from app.core.cfg_database import engine
from app.core.cfg_security import hashear_password

def main():
    print("Connecting to database...")
    default_pwd_hash = hashear_password("demo1234")
    print(f"Generated default password hash for 'demo1234'.")

    with engine.begin() as conn:
        # Get all clients
        clients = conn.execute(text("SELECT pkcliente, codcliente FROM dcliente")).fetchall()
        print(f"Found {len(clients)} clients in dcliente.")

        # Insert each client into usuarios_homebanking if not exists
        inserted = 0
        for client in clients:
            pkcliente = client[0]
            codcliente = client[1].strip().lower()

            # Check if user already exists
            exists = conn.execute(
                text("SELECT 1 FROM usuarios_homebanking WHERE pkcliente = :pk"),
                {"pk": pkcliente}
            ).scalar()

            if not exists:
                conn.execute(
                    text("""
                        INSERT INTO usuarios_homebanking (pkcliente, username, password_hash, activo, bloqueado)
                        VALUES (:pk, :username, :pwd_hash, 'S', 'N')
                    """),
                    {
                        "pk": pkcliente,
                        "username": codcliente,
                        "pwd_hash": default_pwd_hash
                    }
                )
                inserted += 1
        
        # Also let's make sure we have an 'admin' user if needed.
        # But wait, admin is not in dcliente, or is it? The admin route uses a JWT with 'tipo' == 'admin'.
        # Since JWT can have tipo admin directly, we don't necessarily need an admin user in usuarios_homebanking
        # because usuarios_homebanking is for clients.

        print(f"Inserted {inserted} users into usuarios_homebanking.")

if __name__ == "__main__":
    main()
