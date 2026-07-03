from dataclasses import dataclass, asdict

@dataclass
class ExportResult:
    arquivo: str
    formato: str
    banco: str
    consulta: str
    linhas: int
    abas: int
    chunksize: int | None
    tempo_execucao: float
    tamanho_arquivo: str | None = None
    def to_dict(self):
        return asdict(self)