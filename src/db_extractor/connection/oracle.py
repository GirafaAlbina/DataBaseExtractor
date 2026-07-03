# dependency
from sqlalchemy import create_engine

def criar_conexao(cfg):
    connection_url = (
        f"oracle+oracledb://"
        f"{cfg['user']}:{cfg['password']}@"
        f"{cfg['host']}:{cfg['port']}"
        f"/?service_name={cfg['service']}"
    )
    return create_engine(connection_url)