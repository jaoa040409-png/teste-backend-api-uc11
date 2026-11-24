"""Testes da autenticação: do token emitido ao isolamento entre contas.
O arquivo cresce em três etapas, cada uma com uma seção nova no final:
1. a mecânica do token, sem HTTP — chamando `TokenDeAcesso` diretamente;
2. o cabeçalho `Authorization`, pela API;
3. o isolamento entre contas — uma conta não alcança os dados da outra.
"""

from datetime import timedelta
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.exceptions import NaoAutenticado, SessaoExpirada
from app.models import Usuario
from app.tokens import ALGORITMO, TokenDeAcesso

#: Segredo próprio deste arquivo, com mais de 32 bytes.
SEGREDO = "segredo-de-teste-com-mais-de-trinta-e-dois-bytes"


@pytest.fixture
def tokens() -> TokenDeAcesso:
    """Fixture **local**: só este arquivo precisa de um emissor de tokens.
    Compare com a `hasher`, que mora no `conftest.py` porque dois arquivos a
    usam. O lugar de uma fixture é decidido pelo **alcance** de quem precisa
    dela.
    """
    return TokenDeAcesso(segredo=SEGREDO, validade=timedelta(hours=1))


# =============================================================================
# Dia 4 — a mecânica do token, sem HTTP
# =============================================================================
def test_token_emitido_devolve_o_mesmo_usuario(tokens: TokenDeAcesso):
    """O caminho normal, em uma linha: o que entra é o que sai."""
    assert tokens.ler(tokens.emitir(42)) == 42


def test_token_nao_e_o_id_em_texto_puro(tokens: TokenDeAcesso):
    """O token é assinado: não dá para fabricar um escrevendo o id."""
    assert tokens.emitir(42) != "42"
    assert len(tokens.emitir(42)) > 40


def test_token_assinado_com_outro_segredo_e_recusado(tokens: TokenDeAcesso):
    """O caso que a assinatura existe para impedir."""
    intruso = TokenDeAcesso(
        segredo="outro-segredo-tambem-com-trinta-e-dois-bytes",
        validade=timedelta(hours=1),
    )
    with pytest.raises(NaoAutenticado):
        tokens.ler(intruso.emitir(42))


def test_token_alterado_e_recusado(tokens: TokenDeAcesso):
    """Trocar um caractere invalida a assinatura."""
    token = tokens.emitir(42)
    adulterado = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
    with pytest.raises(NaoAutenticado):
        tokens.ler(adulterado)


@pytest.mark.parametrize(
    "texto_invalido", ["", "   ", "nao-e-um-token", "a.b.c", "Bearer abc"]
)


def test_texto_que_nao_e_token_e_recusado(tokens: TokenDeAcesso, texto_invalido: str):
    """Cinco representantes de "isto não é um token" — o `parametrize` do Dia 3."""
    with pytest.raises(NaoAutenticado):
        tokens.ler(texto_invalido)


def test_token_expirado_e_recusado_com_excecao_propria(tokens: TokenDeAcesso):
    """A validade negativa é o truque que torna o teste instantâneo: o token
    nasce vencido há dez segundos."""
    vencido = TokenDeAcesso(segredo=SEGREDO, validade=timedelta(seconds=-10))
    with pytest.raises(SessaoExpirada):
        tokens.ler(vencido.emitir(42))


def test_sessao_expirada_tambem_e_nao_autenticado():
    """A herança é o que faz as duas responderem 401 com um só tratador."""
    assert issubclass(SessaoExpirada, NaoAutenticado)


def test_token_sem_sub_utilizavel_e_recusado(tokens: TokenDeAcesso):
    """Token assinado por nós, mas com conteúdo inesperado."""
    sem_sub = jwt.encode({"outro": "campo"}, SEGREDO, algorithm=ALGORITMO)
    with pytest.raises(NaoAutenticado):
        tokens.ler(sem_sub)


def test_token_nao_guarda_dados_pessoais(tokens: TokenDeAcesso):
    """O conteúdo de um JWT é legível por qualquer um que tenha o token."""
    conteudo = jwt.decode(tokens.emitir(42), SEGREDO, algorithms=[ALGORITMO])
    assert set(conteudo) == {"sub", "iat", "exp"}
    
# ============================================================================= 
# Dia 8 — o cabeçalho `Authorization`, pela API 
# ============================================================================= 

def test_sem_cabecalho_responde_401(cliente: TestClient): 
    """401 é "não sei quem você é"; 403 seria "sei e você não pode". 

    O cliente trata 401 limpando o token e mandando entrar de novo, e 403 
    mostrando "sem permissão". Trocar os dois faz o aplicativo pedir login a 
    quem já está logado, ou o contrário. 
    """ 
    assert cliente.get("/tasks").status_code == 401 

@pytest.mark.parametrize( 
    "cabecalho", 
    [ 
        "token-sem-esquema", 
        "Basic YWxhZGRpbjpvcGVuc2VzYW1l", 
        "Bearer", 
        "Bearer   ", 
    ], 
) 
def test_cabecalho_mal_formado_responde_401(cliente: TestClient, cabecalho: str): 
    """Quatro formas de errar o cabeçalho, todas com a mesma resposta. 

    Esqueceu o esquema; usou o esquema errado; mandou o esquema sem token; 
    mandou o esquema com espaços. Nenhuma pode virar 500. 
    """ 
    resposta = cliente.get("/tasks", headers={"Authorization": cabecalho}) 
    assert resposta.status_code == 401 

# ============================================================================= 
# Dia 8 — o cabeçalho `Authorization`, pela API 
# ============================================================================= 
    
def test_sem_cabecalho_responde_401(cliente: TestClient):
    """401 é "não sei quem você é"; 403 seria "sei e você não pode"."""
    assert cliente.get("/tasks").status_code == 401


@pytest.mark.parametrize(
    "cabecalho",
    [
        "token-sem-esquema",
        "Basic YWxhZGRpbjpvcGVuc2VzYW1l",
        "Bearer",
        "Bearer   ",
    ],
)
def test_cabecalho_mal_formado_responde_401(cliente: TestClient, cabecalho: str):
    resposta = cliente.get("/tasks", headers={"Authorization": cabecalho})
    assert resposta.status_code == 401
    
def test_token_valido_de_conta_apagada_responde_401( 
    cliente: TestClient, sessao_aberta: dict, sessao: Session 
): 
    """A conta sumiu, o token continua assinado — e a sessão não vale mais. 

    É por isso que o usuário é buscado no banco a cada requisição, em vez de 
    reconstruído a partir do token. 

    É o único teste da suíte que usa ao mesmo tempo o `cliente` (Dia 7) e a 
    `sessao` de banco (Dia 5): é preciso apagar pelo banco o que a API não 
    oferece endpoint para apagar. 
    """ 
    autorizacao = {"Authorization": f"Bearer {sessao_aberta['accessToken']}"} 
    assert cliente.get("/usuarios/eu", headers=autorizacao).status_code == 200 

    apagado = sessao.get(Usuario, sessao_aberta["usuario"]["id"]) 
    sessao.delete(apagado) 
    sessao.commit() 

    assert cliente.get("/usuarios/eu", headers=autorizacao).status_code == 401 

def test_openapi_declara_o_esquema_bearer(cliente: TestClient): 
    """É o que faz aparecer o botão **Authorize** no `/docs`.""" 
    esquema = cliente.get("/openapi.json").json() 
    esquemas = esquema["components"].get("securitySchemes", {}) 
    assert any( 
        definicao.get("scheme") == "bearer" for definicao in esquemas.values() 
    ) 
    
# ============================================================================= 
# Dia 9 — isolamento entre contas: duas sessões ao mesmo tempo 
# ============================================================================= 

def tarefa_de(cliente: TestClient, sessao: dict, titulo: str) -> dict: 
    """Cria uma tarefa em nome do dono da sessão informada. 

    É uma fábrica, como as do Dia 1, e existe por um motivo específico: estes 
    testes precisam agir como **duas** pessoas diferentes, o que o 
    `cliente_logado` — que tem um token fixo — não permite. 
    """ 
    resposta = cliente.post( 
        "/tasks", 
        json={"titulo": titulo}, 
        headers={"Authorization": f"Bearer {sessao['accessToken']}"}, 
    ) 
    assert resposta.status_code == 201, resposta.text 
    return resposta.json() 

def test_a_listagem_so_traz_as_tarefas_do_dono_do_token( 
    cliente: TestClient, sessao_aberta: dict, outro_usuario: dict 
): 
    """Não existe parâmetro para pedir "as tarefas de alguém". 

    O `X-Total-Count` é conferido junto porque um total que contasse as 
    tarefas de todos vazaria informação mesmo com a lista correta. 
    """ 
    tarefa_de(cliente, sessao_aberta, "Minha") 
    tarefa_de(cliente, outro_usuario, "Dele") 

    minhas = cliente.get( 
        "/tasks", 
        headers={"Authorization": f"Bearer {sessao_aberta['accessToken']}"}, 
    ) 
    assert [t["titulo"] for t in minhas.json()] == ["Minha"] 
    assert minhas.headers["X-Total-Count"] == "1"
    
def test_nao_se_altera_a_tarefa_de_outra_conta( 
    cliente: TestClient, sessao_aberta: dict, outro_usuario: dict 
): 
    """Os ids são sequenciais: quem tem uma conta qualquer sabe que existe a 
    tarefa 1, a 2, a 3. Saber o id não pode bastar para editar. 

    A mensagem é conferida porque ela precisa dizer o que aconteceu sem 
    revelar nada sobre a tarefa alheia. 
    """ 
    alheia = tarefa_de(cliente, outro_usuario, "Tarefa do Bruno") 

    resposta = cliente.patch( 
        f"/tasks/{alheia['id']}", 
        json={"titulo": "Invadida"}, 
        headers={"Authorization": f"Bearer {sessao_aberta['accessToken']}"}, 
    ) 
    assert resposta.status_code == 403 
    assert resposta.json()["detail"] == "Esta tarefa pertence a outro usuário."
    
def test_nao_se_apaga_a_tarefa_de_outra_conta( 
    cliente: TestClient, sessao_aberta: dict, outro_usuario: dict 
): 
    """A mesma verificação no `DELETE`, e ela precisa ser testada à parte. 
  
    `PATCH` e `DELETE` são dois caminhos no código. Um deles podia ter a 
    verificação e o outro não. 
    """ 
    alheia = tarefa_de(cliente, outro_usuario, "Tarefa do Bruno") 
  
    resposta = cliente.delete( 
        f"/tasks/{alheia['id']}", 
        headers={"Authorization": f"Bearer {sessao_aberta['accessToken']}"}, 
    ) 
    assert resposta.status_code == 403 
  
  
def test_a_tarefa_recusada_continua_intacta( 
    cliente: TestClient, sessao_aberta: dict, outro_usuario: dict 
): 
    """Recusar não é o bastante: é preciso que nada tenha mudado. 
  
    Um 403 devolvido *depois* de gravar a alteração seria **pior do que não 
    ter verificação nenhuma**, porque pareceria seguro. A resposta é uma 
    evidência do que aconteceu, não a prova. A prova é olhar o estado depois. 
    """ 
    dele = {"Authorization": f"Bearer {outro_usuario['accessToken']}"} 
    alheia = tarefa_de(cliente, outro_usuario, "Original") 
  
    cliente.patch( 
        f"/tasks/{alheia['id']}", 
        json={"titulo": "Invadida"}, 
        headers={"Authorization": f"Bearer {sessao_aberta['accessToken']}"}, 
    ) 
  
    depois = cliente.get("/tasks", headers=dele).json() 
    assert [t["titulo"] for t in depois] == ["Original"] 
  
  
def test_tarefa_inexistente_responde_404_e_nao_403( 
    cliente_logado: TestClient, 
): 
    """404 é "não existe"; 403 é "existe e não é sua". 
  
    Responder 403 confirma que a tarefa **existe**, o que é um vazamento 
    pequeno mas real. Este projeto escolheu a clareza para quem integra, e a 
    decisão está registrada no manual técnico. 
    """ 
    assert cliente_logado.delete("/tasks/9999").status_code == 404