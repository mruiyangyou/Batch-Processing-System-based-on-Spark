from sqlalchemy import create_engine, text
import os

def postgres_connection(db: str):
    # connection_string = f'postgresql+psycopg2://{os.getenv("username")}:{os.getenv("password")}@18.171.239.205:5432/{db}'
    connection_string = f'postgresql+psycopg2://{os.getenv("username")}:{os.getenv("password")}@10.0.9.168:5432/{db}'
    engine = create_engine(connection_string)
    return engine

def remove_table(table: str, engine):
    with engine.connect() as conn:
        # Begin a transaction
        with conn.begin():
            drop_statement = text(f"drop table {table};")
            conn.execute(drop_statement)

    print(f"{table} has been dropped!")