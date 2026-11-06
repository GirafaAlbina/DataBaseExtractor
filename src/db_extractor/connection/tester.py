from typing import Tuple

def testar_conexao(tipo_banco: str, cfg: dict) -> Tuple[bool, bool, str]:
    """
    Testa a autenticação com o banco.
    
    Retorna uma tupla:
      (sucesso: bool, erro_de_credencial: bool, mensagem_erro: str)
    """
    usuario = cfg.get("user")
    senha = cfg.get("password")
    host = cfg.get("host")
    port = cfg.get("port")

    tipo = tipo_banco.strip().upper()

    # 1. Teste para Oracle
    if "ORACLE" in tipo:
        import oracledb
        service = cfg.get("service")
        dsn = f"{host}:{port}/{service}"
        
        try:
            # Timeout curto de 10s para não prender a execução
            with oracledb.connect(
                user=usuario,
                password=senha,
                dsn=dsn,
                tcp_connect_timeout=10,
                expire_time=2
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
            return True, False, ""
        except oracledb.DatabaseError as e:
            err_obj, = e.args
            msg = str(err_obj.message)
            # ORA-01017: invalid username/password; logon denied
            # ORA-28001: the password has expired
            is_auth_error = err_obj.code in (1017, 28001) or "ORA-01017" in msg
            return False, is_auth_error, msg
        except Exception as e:
            return False, False, str(e)

    # 2. Teste para Denodo (via PostgreSQL protocol / psycopg2)
    elif "DENODO" in tipo:
        import psycopg2
        database = cfg.get("database")
        
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=database,
                user=usuario,
                password=senha,
                connect_timeout=10
            )
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.close()
            return True, False, ""
        except psycopg2.OperationalError as e:
            msg = str(e)
            # Erros comuns de autenticação PostgreSQL/Denodo
            is_auth_error = any(term in msg.lower() for term in ["password authentication failed", "authentication failed", "fatal:"])
            return False, is_auth_error, msg
        except Exception as e:
            return False, False, str(e)

    else:
        # Se não for identificado, não bloqueia
        return True, False, ""