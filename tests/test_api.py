from datetime import date, timedelta
from fastapi.testclient import TestClient

# Corpo de cadastro válido, reaproveitado com {**USUARIO_VALIDO, "campo": ...}.
# É o mesmo papel das fábricas nova_tarefa e novo_usuario do Dia 1: um
# ponto único a alterar quando o contrato de entrada mudar.
USUARIO_VALIDO = {
    "nome": "Bruno Lima",
    "email": "bruno@exemplo.com",
    "senha": "senha123",
}


# =============================================================================
# Dia 7 — TestClient: os endpoints públicos
# =============================================================================


def test_raiz_responde(cliente: TestClient):
    # Smoke test: se este falha, não vale investigar os outros.
    assert cliente.get("/").status_code == 200


def test_cadastrar_usuario_devolve_201_com_sessao_aberta(cliente: TestClient):
    # Verifica código 201, corpo com token e formato em camelCase (criadoEm).
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["accessToken"]
    assert corpo["tokenType"] == "bearer"
    assert corpo["usuario"]["nome"] == "Bruno Lima"
    assert "criadoEm" in corpo["usuario"], "o contrato usa camelCase"


def test_cadastro_nao_expoe_a_senha(cliente: TestClient):
    # Verifica em resposta.text (antes de parsear JSON) que nem senha nem hash vazam.
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    inteiro = resposta.text
    assert "senha123" not in inteiro
    assert "senhaHash" not in inteiro and "senha_hash" not in inteiro


def test_cadastrar_com_email_repetido_devolve_409(cliente: TestClient):
    cliente.post("/usuarios", json=USUARIO_VALIDO)
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "E-mail já cadastrado."


def test_email_duplicado_ignora_maiusculas_e_espacos(cliente: TestClient):
    cliente.post("/usuarios", json=USUARIO_VALIDO)
    resposta = cliente.post(
        "/usuarios",
        json={**USUARIO_VALIDO, "email": "BRUNO@Exemplo.com"},
    )
    assert resposta.status_code == 409


def test_email_malformado_devolve_422(cliente: TestClient):
    resposta = cliente.post(
        "/usuarios",
        json={**USUARIO_VALIDO, "email": "bruno@"},
    )
    assert resposta.status_code == 422


def test_senha_curta_devolve_422(cliente: TestClient):
    resposta = cliente.post(
        "/usuarios",
        json={**USUARIO_VALIDO, "senha": "123"},
    )
    assert resposta.status_code == 422


def test_login_correto_devolve_200_com_token(cliente: TestClient, usuario: dict):
    resposta = cliente.post(
        "/usuarios/login",
        json={"email": "ana@exemplo.com", "senha": "senha123"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["usuario"]["id"] == usuario["id"]
    assert corpo["accessToken"]


def test_login_com_senha_errada_devolve_401(cliente: TestClient, usuario: dict):
    resposta = cliente.post(
        "/usuarios/login",
        json={"email": "ana@exemplo.com", "senha": "errada"},
    )
    assert resposta.status_code == 401


def test_login_com_email_inexistente_devolve_401_com_a_mesma_mensagem(
    cliente: TestClient, usuario: dict
):
    # Mensagem idêntica evita enumeração de e-mails válidos.
    inexistente = cliente.post(
        "/usuarios/login",
        json={"email": "ninguem@exemplo.com", "senha": "senha123"},
    )
    senha_errada = cliente.post(
        "/usuarios/login",
        json={"email": "ana@exemplo.com", "senha": "errada"},
    )
    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json()["detail"] == senha_errada.json()["detail"]


def test_nao_existe_mais_busca_de_usuario_por_id(cliente: TestClient):
    assert cliente.get("/usuarios/1").status_code == 404
    assert cliente.get("/usuarios/9999").status_code == 404


def test_consultar_a_propria_conta_exige_token(cliente: TestClient):
    assert cliente.get("/usuarios/eu").status_code == 401


def test_openapi_expoe_os_sete_endpoints(cliente: TestClient):
    caminhos = cliente.get("/openapi.json").json()["paths"]
    operacoes = sum(len(metodos) for metodos in caminhos.values())
    assert operacoes == 8, "7 endpoints da API + a rota raiz"


# =============================================================================
# Dia 8 — cliente_logado: as tarefas, com a sessão aberta
# =============================================================================


def test_consultar_a_propria_conta_devolve_o_usuario_do_token(
    cliente_logado: TestClient, usuario: dict
):
    resposta = cliente_logado.get("/usuarios/eu")
    assert resposta.status_code == 200
    assert resposta.json() == usuario


def test_criar_tarefa_nasce_pendente(cliente_logado: TestClient, usuario: dict):
    resposta = cliente_logado.post(
        "/tasks",
        json={
            "titulo": "Entregar o relatório",
            "prioridade": "alta",
            "prazo": str(date.today() + timedelta(days=30)),
        },
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "pendente"
    assert corpo["concluidoEm"] is None
    assert corpo["usuarioId"] == usuario["id"], "o dono vem do token"


def test_criar_tarefa_sem_token_devolve_401(cliente: TestClient):
    assert cliente.post("/tasks", json={"titulo": "X"}).status_code == 401


def test_criar_tarefa_com_prioridade_invalida_devolve_422(
    cliente_logado: TestClient,
):
    resposta = cliente_logado.post(
        "/tasks",
        json={"titulo": "X", "prioridade": "altissima"},
    )
    assert resposta.status_code == 422


def test_listar_tarefas_de_usuario_sem_tarefas_devolve_lista_vazia(
    cliente_logado: TestClient,
):
    resposta = cliente_logado.get("/tasks")
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_listar_filtra_por_status(cliente_logado: TestClient):
    for titulo in ("A", "B"):
        cliente_logado.post("/tasks", json={"titulo": titulo})
    primeira = cliente_logado.get("/tasks").json()[0]
    cliente_logado.patch(f"/tasks/{primeira['id']}", json={"status": "concluida"})
    pendentes = cliente_logado.get("/tasks?status=pendente").json()
    assert len(pendentes) == 1
    assert pendentes[0]["status"] == "pendente"


def test_listar_ordena_por_prioridade_da_mais_urgente_para_a_menos(
    cliente_logado: TestClient,
):
    for prioridade in ("baixa", "urgente", "media"):
        cliente_logado.post(
            "/tasks",
            json={"titulo": prioridade, "prioridade": prioridade},
        )
    resposta = cliente_logado.get("/tasks?ordenarPor=prioridade&ordem=asc")
    assert [t["prioridade"] for t in resposta.json()] == [
        "urgente",
        "media",
        "baixa",
    ]


def test_campo_de_ordenacao_invalido_devolve_422(cliente_logado: TestClient):
    resposta = cliente_logado.get("/tasks?ordenarPor=inventado")
    assert resposta.status_code == 422


def test_filtrar_por_prazo_ate(cliente_logado: TestClient):
    hoje = date.today()
    cliente_logado.post(
        "/tasks",
        json={"titulo": "Vence logo", "prazo": str(hoje + timedelta(days=1))},
    )
    cliente_logado.post(
        "/tasks",
        json={"titulo": "Vence tarde", "prazo": str(hoje + timedelta(days=30))},
    )
    resposta = cliente_logado.get(f"/tasks?prazoAte={hoje + timedelta(days=7)}")
    assert [t["titulo"] for t in resposta.json()] == ["Vence logo"]

from datetime import date, timedelta
from fastapi.testclient import TestClient


def test_concluir_tarefa_preenche_a_data(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Concluir"}).json()
    resposta = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "concluida"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["concluidoEm"] is not None


def test_reabrir_tarefa_limpa_a_data(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Reabrir"}).json()
    cliente_logado.patch(f"/tasks/{criada['id']}", json={"status": "concluida"})
    resposta = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "pendente"}
    )
    assert resposta.json()["concluidoEm"] is None


def test_editar_titulo_de_tarefa_concluida_preserva_a_data(
    cliente_logado: TestClient,
):
    """A RN-03 verificada de ponta a ponta, atravessando todas as camadas.
    É a mesma regra do Dia 2, vista pelo outro lado. Se ela quebrar,
    compare as duas mensagens de falha: a do domínio aponta o método;
    esta diz apenas que duas datas vindas de duas respostas HTTP não são iguais.
    """
    criada = cliente_logado.post("/tasks", json={"titulo": "Original"}).json()
    concluida = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "concluida"}
    ).json()
    editada = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"titulo": "Título novo"}
    ).json()

    assert editada["titulo"] == "Título novo"
    assert editada["concluidoEm"] == concluida["concluidoEm"]


def test_apagar_o_prazo_e_diferente_de_nao_informar(cliente_logado: TestClient):
    """No JSON, "não mencionei o prazo" e "quero o prazo vazio" são coisas
    diferentes: a primeira é a ausência da chave, a segunda é `null`.
    """
    prazo = str(date.today() + timedelta(days=10))
    criada = cliente_logado.post(
        "/tasks", json={"titulo": "Com prazo", "prazo": prazo}
    ).json()

    sem_mencionar = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"titulo": "Outro título"}
    ).json()
    assert sem_mencionar["prazo"] == prazo

    apagando = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"prazo": None}
    ).json()
    assert apagando["prazo"] is None


def test_atualizar_tarefa_inexistente_devolve_404(cliente_logado: TestClient):
    resposta = cliente_logado.patch("/tasks/9999", json={"status": "concluida"})
    assert resposta.status_code == 404


def test_titulo_vazio_no_patch_devolve_422(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Original"}).json()
    resposta = cliente_logado.patch(f"/tasks/{criada['id']}", json={"titulo": " "})
    assert resposta.status_code == 422

def test_remover_tarefa_devolve_204_sem_corpo(cliente_logado: TestClient):
    """204 No Content: o corpo precisa estar **vazio**, não só ausente."""
    criada = cliente_logado.post("/tasks", json={"titulo": "Remover"}).json()
    resposta = cliente_logado.delete(f"/tasks/{criada['id']}")
    assert resposta.status_code == 204
    assert resposta.content == b""
def test_remover_a_mesma_tarefa_duas_vezes_devolve_404(cliente_logado: TestClient):
    """A segunda remoção não é sucesso silencioso: a tarefa não existe mais."""
    criada = cliente_logado.post("/tasks", json={"titulo": "Remover"}).json()
    cliente_logado.delete(f"/tasks/{criada['id']}")
    assert cliente_logado.delete(f"/tasks/{criada['id']}").status_code == 404

# =============================================================================
# Dia 9 — duas contas
# =============================================================================
def test_usuario_id_no_corpo_e_ignorado(
 cliente_logado: TestClient, usuario: dict, outro_usuario: dict
):
 """Mandar `usuarioId` de outra pessoa não cria tarefa para ela.
 É um **teste de regressão**: não verifica uma regra nova, e sim que uma
 falha já corrigida — o dono vir do corpo da requisição — não volta.
 """
 resposta = cliente_logado.post(
 "/tasks",
 json={"titulo": "Tentativa", "usuarioId": outro_usuario["usuario"]["id"]},
 )
 assert resposta.status_code == 201
 assert resposta.json()["usuarioId"] == usuario["id"]