import pandas as pd
from sqlalchemy import create_engine

def cargar_datos_a_postgres():
    print("Iniciando lectura del archivo CSV...")
    
    df = pd.read_csv('data/spam.csv', encoding='latin-1')
    
    df = df[['v1', 'v2']]
    
    # Connection String para PostgreSQL en DigitalOcean
    db_url = "postgresql://doadmin:*************@db-postgresql-nyc3-02715-do-user-28207668-0.h.db.ondigitalocean.com:25060/defaultdb?sslmode=require"
    engine = create_engine(db_url)
    
    print("Conectando a la base de datos en DigitalOcean y subiendo información...")
    
    df.to_sql('spam_raw', engine, if_exists='replace', index=True, index_label='id')
    
    print(f"¡Éxito! Se han cargado {len(df)} registros en la tabla 'spam_raw'.")

if __name__ == "__main__":
    cargar_datos_a_postgres()