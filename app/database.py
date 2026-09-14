from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# URL de conexão (usando SQLite local para testes iniciais)
SQLALCHEMY_DATABASE_URL = "sqlite:///./tecnotextil.db"

# Para PostgreSQL, no futuro você usará:
# SQLALCHEMY_DATABASE_URL = "postgresql://usuario:senha@localhost:5432/tecnotextil_db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Apenas necessário para SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency para obter a sessão do banco nas rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()