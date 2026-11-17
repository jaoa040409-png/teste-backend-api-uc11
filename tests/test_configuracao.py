
import pytest

from app.config import normalizar_url

# ===================================================================
# Dia 3 - "parametrize" numa função pura: a normalização da URL
# ===================================================================

@pytest.mark.parametrize(
    "url_recebida",
    [
        "postgres://usuario:senha@host:5432/banco",
        "postgresql://usuario:senha@host:5432/banco",
    ],
)
def test_url_de_postgres_recebe_o_driver_do_projeto(url_recebida):
    """A URL entregue pela hospedagem deve funcionar colada como veio."""
    normalizada = normalizar_url(url_recebida)

    assert normalizada.startswith("postgresql+psycopg://")
    assert normalizada.endswith("usuario:senha@host:5432/banco")


def test_driver_declarado_explicitamente_e_respeitado():
    """Quem escreveu o driver na URL sabe o que quer - não sobrescrever."""
    url = "postgresql+psycopg2://usuario:senha@host:5432/banco"
    assert normalizar_url(url) == url


def test_url_de_sqlite_nao_e_alterada():
    assert normalizar_url("sqlite:///./todo_list.db") == "sqlite:///./todo_list.db"


def test_parametros_da_url_sao_preservados():
    """Banco gerenciado costuma exigir SSL, que vem como parâmetro na URL."""
    url = "postgres://u:s@host:5432/banco?sslmode=require"
    assert normalizar_url(url).endswith("?sslmode=require")
