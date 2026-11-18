import hashlib
import os
import threading
from time import perf_counter
import oracledb
import pandas as pd

from ._config import obter_config_banco
from ._constants import DEFAULT_SHEET_NAME, DEFAULT_CSV_SEPARATOR
from ._sql_parser import preparar_sql_e_binds
from .connection import configurar_buffer_cursor
from .models import ExportResult
from .output import exportar_csv, exportar_xlsx, exportar_parquet
from .query import carregar_consulta
from .utils import (
    normalizar_banco,
    normalizar_consulta,
    normalizar_saida,
    normalizar_nome_planilha,
    normalizar_chunksize,
    validar_consulta,
    validar_saida,
    validar_chunksize,
    validar_nome_planilha,
    resolver_saida,
    imprimir_exportacao,
    imprimir_dataframe,
)


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

    def fechar_cursores(self):
        for cur in self._cursores.values():
            try:
                cur.close()
            except Exception:
                pass
        self._cursores.clear()


class SessaoExtracao:
    """Gerenciador de contexto para Pool de Conexões Persistente."""

    def __init__(
        self,
        banco: str,
        min_workers: int = 1,
        max_workers: int = 4,
        arraysize: int = 50_000,
        arquivo_config: str | None = None,
    ):
        self.banco = normalizar_banco(banco)
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.arraysize = arraysize
        self.arquivo_config = arquivo_config
        self._pool = None
        self._motor = "ORACLE"
        self._local = threading.local()
        self._conexoes_ativas: list[ConexaoPreparada] = []
        self._lock = threading.Lock()

    def __enter__(self) -> "SessaoExtracao":
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
        return self

    def adquirir_conexao(self) -> ConexaoPreparada:
        """Garante 1 conexão persistente e 1 cache de cursores por thread."""
        if not hasattr(self._local, "wrapper") or self._local.wrapper is None:
            raw_conn = self._pool.acquire() if self._motor == "ORACLE" else self._pool.getconn()
            wrapper = ConexaoPreparada(raw_conn, self._motor, self.arraysize)
            self._local.wrapper = wrapper
            with self._lock:
                self._conexoes_ativas.append(wrapper)
        return self._local.wrapper

    def _resolver_sql(self, consulta: str) -> str:
        """Aceita tanto o caminho/nome de um arquivo .sql quanto uma string SQL direta."""
        if os.path.isfile(consulta) or consulta.strip().lower().endswith((".sql", ".vql")):
            arq = normalizar_consulta(consulta)
            validar_consulta(arq)
            return carregar_consulta(arq)
        return consulta

    def consultar_dataframe(
        self,
        consulta: str,
        parametros: dict | None = None,
        chunksize: int | None = None,
        dataframe: str = "pandas",
        monitorar: bool = False,
    ):
        """Executa consulta reaproveitando a conexão e o cursor preparado da sessão."""
        dataframe = dataframe.lower()
        if dataframe not in ("pandas", "polars"):
            raise ValueError("dataframe deve ser 'pandas' ou 'polars'")

        chunksize = normalizar_chunksize(chunksize)
        validar_chunksize(chunksize)

        inicio = perf_counter()
        sql_base = self._resolver_sql(consulta)
        sql_final, binds = preparar_sql_e_binds(sql_base, parametros)

        conn_prep = self.adquirir_conexao()
        cursor = conn_prep.executar(sql_final, binds)
        colunas = [desc[0] for desc in cursor.description]

        if chunksize is not None:
            def _generator():
                while True:
                    linhas = cursor.fetchmany(chunksize)
                    if not linhas:
                        break
                    df_pd = pd.DataFrame(linhas, columns=colunas)
                    if dataframe == "polars":
                        import polars as pl
                        yield pl.from_pandas(df_pd)
                    else:
                        yield df_pd
            return _generator()

        linhas = cursor.fetchall()
        df_pd = pd.DataFrame(linhas, columns=colunas)

        if dataframe == "polars":
            import polars as pl
            df_pl = pl.from_pandas(df_pd)
            if monitorar:
                imprimir_dataframe(df=df_pl, tempo_execucao=perf_counter() - inicio, dataframe="polars")
            return df_pl

        if monitorar:
            imprimir_dataframe(df=df_pd, tempo_execucao=perf_counter() - inicio, dataframe="pandas")
        return df_pd

    def __exit__(self, exc_type, exc_val, exc_tb):
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


def abrir_sessao(
    banco: str,
    min_workers: int = 1,
    max_workers: int = 4,
    arraysize: int = 50_000,
    arquivo_config: str | None = None,
) -> SessaoExtracao:
    """Abre um gerenciador de contexto com Pool de Conexões e Cache de Cursores Preparados."""
    return SessaoExtracao(
        banco=banco,
        min_workers=min_workers,
        max_workers=max_workers,
        arraysize=arraysize,
        arquivo_config=arquivo_config,
    )