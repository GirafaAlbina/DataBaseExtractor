class DBExtractorError(Exception):
    pass

# KeyError
class BancoNaoEncontrado(DBExtractorError, KeyError):
    pass


# FileNotFoundError
class ConsultaNaoEncontrada(DBExtractorError, FileNotFoundError):
    pass
class ConfigNaoEncontrado(DBExtractorError, FileNotFoundError):
    pass


# ValueError
class ConexaoNaoIdentificado(DBExtractorError, ValueError):
    pass
class FormatoConsultaInvalido(DBExtractorError, ValueError):
    pass
class FormatoSaidaInvalido(DBExtractorError, ValueError):
    pass
class ChunksizeInvalido(DBExtractorError, ValueError):
    pass
class NomePlanilhaInvalido(DBExtractorError, ValueError):
    pass