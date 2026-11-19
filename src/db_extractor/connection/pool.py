import hashlib
import threading
import oracledb
from . import configurar_buffer_cursor


class ConexaoPreparada:
    """Encapsula uma conexão física do pool e seu cache privado de cursores preparados."""

    def __init__(self, conn, motor: str, arraysize: int):
        self.conn = conn
        self.motor = motor
        self.arraysize = arraysize
        self._cursores: dict[str, object] = {}

    def executar(self, sql: str, binds: dict | None = None):
        chave_sql = hashlib.blake2b(sql.encode("utf-8"), digest_size=16).hexdigest()

        if self.motor == "ORACLE":
            cur = self._cursores.get(chave_sql)
            if cur is None:
                cur = self.conn.cursor()
                configurar_buffer_cursor(cur, self.motor, self.arraysize)
                cur.prepare(sql)
                self._cursores[chave_sql] = cur

            cur.execute(None, binds or {})
            return cur

        # Denodo / psycopg2
        cur = self.conn.cursor()
        configurar_buffer_cursor(cur, self.motor, self.arraysize)
        cur.execute(sql, binds or {})
        return cur

    def fechar_cursores(self) -> None:
        for cur in self._cursores.values():
            try:
                cur.close()
            except Exception:
                pass
        self._cursores.clear()


class PoolSessao:
    """Gerencia o ciclo de vida do pool de conexões e a alocação isolada por thread."""

    def __init__(
        self,
        banco: str,
        min_workers: int = 1,
        max_workers: int = 4,
        arraysize: int = 50_000,
        arquivo_config: str | None = None,
    ):
        self.banco = banco
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.arraysize = arraysize
        self.arquivo_config = arquivo_config
        self._pool = None
        self._motor = "ORACLE"
        self._local = threading.local()
        self._conexoes_ativas: list[ConexaoPreparada] = []
        self._lock = threading.Lock()

    def iniciar(self) -> None:
        from .._config import obter_config_banco
        
        cfg = obter_config_banco(self.banco, arquivo_config=self.arquivo_config)
        porta = int(cfg.get("port", 1521))
        self._motor = "DENODO" if porta == 9996 else "ORACLE"

        if self._motor == "ORACLE":
            dsn = f"{cfg['host']}:{porta}/{cfg['service']}"
            self._pool = oracledb.create_pool(
                user=cfg["user"],
                password=cfg["password"],
                dsn=dsn,
                min=self.min_workers,
                max=self.max_workers,
                increment=1,
            )
        else:
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(
                minconn=self.min_workers,
                maxconn=self.max_workers,
                host=cfg["host"],
                port=porta,
                dbname=cfg["database"],
                user=cfg["user"],
                password=cfg["password"],
            )

    def adquirir_conexao(self) -> ConexaoPreparada:
        """Garante 1 conexão persistente e 1 cache de cursores por thread."""
        if not hasattr(self._local, "wrapper") or self._local.wrapper is None:
            raw_conn = self._pool.acquire() if self._motor == "ORACLE" else self._pool.getconn()
            wrapper = ConexaoPreparada(raw_conn, self._motor, self.arraysize)
            self._local.wrapper = wrapper
            with self._lock:
                self._conexoes_ativas.append(wrapper)
        return self._local.wrapper

    def encerrar(self) -> None:
        for wrapper in self._conexoes_ativas:
            wrapper.fechar_cursores()
            try:
                if self._motor == "ORACLE":
                    self._pool.release(wrapper.conn)
                else:
                    self._pool.putconn(wrapper.conn)
            except Exception:
                pass
        self._conexoes_ativas.clear()

        if self._pool:
            try:
                if self._motor == "ORACLE":
                    self._pool.close(force=True)
                else:
                    self._pool.closeall()
            except Exception:
                pass