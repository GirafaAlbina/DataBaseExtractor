import os
import sys


def resolver_saida(caminho):
    if os.path.isabs(caminho):
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

        return caminho

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    caminho = os.path.join(script_dir, caminho)
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    return caminho