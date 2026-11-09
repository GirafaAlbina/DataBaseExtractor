from typing import Tuple, NamedTuple, Optional
import sys

class TesteConexaoResult(NamedTuple):
    sucesso: bool
    erro_credencial: bool
    mensagem: str


def _testar_oracle(cfg: dict, timeout: int = 5) -> TesteConexaoResult:
    usuario = cfg.get("user")
    senha = cfg.get("password")
    host = cfg.get("host")
    port = cfg.get("port", 1521)
    service = cfg.get("service")

    if not all([usuario, host, service]):
        return TesteConexaoResult(
            False, False, "Campos obrigatórios ausentes no config para Oracle (user, host, service)."
        )

    try:
        import oracledb
    except ImportError:
        return TesteConexaoResult(False, False, "Biblioteca 'oracledb' não instalada.")

    dsn = f"{host}:{port}/{service}"

    try:
        with oracledb.connect(
            user=usuario,
            password=senha or "",
            dsn=dsn,
            tcp_connect_timeout=timeout,
            expire_time=2,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
        return TesteConexaoResult(True, False, "")

    except oracledb.DatabaseError as e:
        msg = str(e)
        code = None

        if e.args and hasattr(e.args[0], "code"):
            code = e.args[0].code
            msg = str(getattr(e.args[0], "message", msg))

        # 1017: invalid username/password
        # 28000: account is locked
        # 28001: password has expired
        # 1005:  null password given
        # 1045:  user lacks CREATE SESSION privilege
        codigos_credencial = {1017, 28000, 28001, 1005, 1045}
        is_auth_error = (code in codigos_credencial) or any(
            ora in msg for ora in ["ORA-01017", "ORA-28000", "ORA-28001", "ORA-01005", "ORA-01045"]
        )

        return TesteConexaoResult(False, is_auth_error, msg)

    except Exception as e:
        return TesteConexaoResult(False, False, f"Falha de rede/sistema ao conectar no Oracle: {e}")


def _testar_denodo(cfg: dict, timeout: int = 5) -> TesteConexaoResult:
    usuario = cfg.get("user")
    senha = cfg.get("password")
    host = cfg.get("host")
    port = cfg.get("port", 9996)
    database = cfg.get("database")

    if not all([usuario, host, database]):
        return TesteConexaoResult(
            False, False, "Campos obrigatórios ausentes no config para Denodo (user, host, database)."
        )

    try:
        import psycopg2
    except ImportError:
        return TesteConexaoResult(False, False, "Biblioteca 'psycopg2' não instalada.")

    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=usuario,
            password=senha or "",
            connect_timeout=timeout,
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        return TesteConexaoResult(True, False, "")

    except psycopg2.OperationalError as e:
        msg = str(e)
        pgcode = getattr(e, "pgcode", None)

        # 28P01: invalid_password Denodo VQL
        # 28000: invalid_authorization_specification
        is_auth_error = (pgcode in {"28P01", "28000"}) or any(
            termo in msg.lower()
            for termo in [
                "password authentication failed",
                "authentication failed",
                "invalid user/password",
                "check credentials",
            ]
        )

        return TesteConexaoResult(False, is_auth_error, msg)

    except Exception as e:
        return TesteConexaoResult(False, False, f"Falha ao conectar no Denodo: {e}")

    finally:
        if conn is not None and not conn.closed:
            conn.close()


def testar_conexao(tipo_banco: str, cfg: dict, timeout: int = 5) -> Tuple[bool, bool, str]:
    """
    Retorna uma NamedTuple compatível com Tuple[bool, bool, str]:
      (sucesso, erro_de_credencial, mensagem_erro)
    """
    tipo = (tipo_banco or "").strip().upper()

    if "ORACLE" in tipo:
        return _testar_oracle(cfg, timeout=timeout)
    elif "DENODO" in tipo:
        return _testar_denodo(cfg, timeout=timeout)
    else:
        return TesteConexaoResult(
            False, False, f"Tipo de banco '{tipo_banco}' não suportado para validação de conexão."
        )