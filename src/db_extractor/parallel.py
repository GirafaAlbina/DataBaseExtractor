import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .output import exportar_parquet
from .query import preparar_sql_e_binds
from .session import SessaoExtracao


def exportar_lotes_paralelo(
    banco: str,
    consulta_sql: str,
    lotes: list[dict[str, Any]],
    diretorio_saida: str,
    prefixo_arquivo: str = "lote",
    max_workers: int = 4,
    chunksize: int = 100_000,
    arraysize: int = 50_000,
    compression: str = "zstd",
    downcast: bool = True,
    nome_lote_fn: Callable[[int, dict], str] | None = None,
    arquivo_config: str | None = None,
    usuario: str | None = None,
) -> list[str]:

    os.makedirs(diretorio_saida, exist_ok=True)
    arquivos_gerados: list[str] = []

    def _processar_lote(indice: int, params_lote: dict[str, Any]) -> str:
        nome_base = (
            nome_lote_fn(indice, params_lote)
            if nome_lote_fn
            else f"{prefixo_arquivo}_{indice:04d}"
        )
        caminho_parquet = os.path.join(diretorio_saida, f"{nome_base}.parquet")

        sql_final, binds = preparar_sql_e_binds(sql_base, params_lote)
        conn_prep = sessao.adquirir_conexao()
        cursor = conn_prep.executar(sql_final, binds)
        colunas = [desc[0] for desc in cursor.description]

        def _gerador_chunks():
            while True:
                linhas = cursor.fetchmany(chunksize)
                if not linhas:
                    break
                yield linhas  # Envia tuplas puras direto para Polars/Arrow (zero Pandas)

        try:
            exportar_parquet(
                _gerador_chunks(),
                arquivo_saida=caminho_parquet,
                compression=compression,
                downcast=downcast,
                colunas=colunas,
            )
            return caminho_parquet
        except Exception:
            if os.path.exists(caminho_parquet):
                try:
                    os.remove(caminho_parquet)
                except OSError:
                    pass
            raise

    with SessaoExtracao(
        banco=banco,
        min_workers=max_workers,
        max_workers=max_workers,
        arraysize=arraysize,
        arquivo_config=arquivo_config,
        usuario=usuario,
    ) as sessao:
        sql_base = sessao.resolver_sql(consulta_sql)
        executor = ThreadPoolExecutor(max_workers=max_workers)
        futuros = {
            executor.submit(_processar_lote, idx, lote): idx
            for idx, lote in enumerate(lotes, start=1)
        }

        try:
            for futuro in as_completed(futuros):
                caminho = futuro.result()
                arquivos_gerados.append(caminho)
        except Exception as erro:
            executor.shutdown(wait=False, cancel_futures=True)
            raise RuntimeError(
                f"Execução paralela abortada (Fail-Fast). Lotes pendentes cancelados. Motivo: {erro}"
            ) from erro
        else:
            executor.shutdown(wait=True)

    return sorted(arquivos_gerados)