import pytest

from app.application.qr_format import normalizar_codigo_qr


CODIGO = "NLD-17-AbcdefGhijkLmnoPqrs12345"


@pytest.mark.parametrize(
    "contenido",
    [
        CODIGO,
        f"https://medalloclub.example/pase/{CODIGO}",
        f"https://medalloclub.example/scan?code={CODIGO}",
        f'{{"qr_code":"{CODIGO}"}}',
        f'{{"data":{{"codigo":"{CODIGO}"}}}}',
    ],
)
def test_normaliza_formatos_de_qr(contenido: str) -> None:
    assert normalizar_codigo_qr(contenido) == CODIGO


def test_rechaza_qr_desconocido_y_contenido_excesivo() -> None:
    with pytest.raises(ValueError):
        normalizar_codigo_qr("https://example.com/no-es-un-pase")
    with pytest.raises(ValueError):
        normalizar_codigo_qr("x" * 2049)
