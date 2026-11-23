"""O contrato com o front-end, verificado como teste.
Os outros arquivos verificam se a API faz o que promete. Este verifica outra
coisa: se ela fala **exatamente** o que o front-end em React sabe consumir — o
formato do JSON, o vocabulário dos parâmetros, o texto das mensagens de erro.
Esse contrato não está no código de nenhum dos dois lados. Um `rename`
bem-intencionado de `criadoEm` para `criado_em` passaria por toda a suíte sem
falhar e quebraria a integração só na hora de ligar as duas pontas.
**O front-end ainda não consome esta API** — continua mockado no
`localStorage`. Estes testes travam a parte do contrato que já está pronta, e
cada um aponta para o arquivo do front-end que depende dele.
"""
from fastapi.testclient import TestClient
# =============================================================================
# Dia 7 — o contrato dos endpoints públicos
# =============================================================================
# ---------------------------------------------- campos — `@typedef Usuario`
def test_usuario_tem_exatamente_os_campos_publicos(usuario: dict):
    """O `@typedef Usuario` menos a senha.
    Este teste verifica a RN-05 por um caminho diferente do
    `test_cadastro_nao_expoe_a_senha`: ele não procura a palavra `senhaHash`,
    ele exige que o conjunto de campos seja *exatamente* este. Duas formas de
    verificar a mesma propriedade — e é bom que existam as duas.
    """
    assert set(usuario) == {"id", "nome", "email", "criadoEm"}
def test_sessao_tem_os_campos_que_o_authcontext_vai_consumir(sessao_aberta: dict):
    """O que `AuthContext.login` e `AuthContext.cadastrar` vão receber."""
    assert set(sessao_aberta) == {"accessToken", "tokenType", "usuario"}
    assert sessao_aberta["tokenType"] == "bearer"
def test_cadastro_e_login_continuam_publicos(cliente: TestClient):
    """Os dois únicos endpoints que não podem exigir token.
    Não há como pedir credencial de quem está criando a conta ou tentando
    entrar nela — é o `CadastroForm.jsx` e o `LoginForm.jsx` chamando a API
    antes de existir qualquer sessão.
    """
    cadastro = cliente.post(
        "/usuarios",
        json={"nome": "Carla", "email": "carla@exemplo.com", "senha": "senha123"},
    )
    assert cadastro.status_code == 201
    login = cliente.post(
        "/usuarios/login",
        json={"email": "carla@exemplo.com", "senha": "senha123"},
    )
    assert login.status_code == 200

# ------------------------------- formato do erro — `setErro(e.message)` no front
def test_erro_de_validacao_tem_detail_em_texto(cliente: TestClient):
    """`detail` é sempre uma frase, nunca uma lista de objetos.
    Com o formato padrão do FastAPI — `detail` como lista —, a tela exibiria
    `[object Object]`. O `isinstance` trava o **tipo** do campo.
    """
    resposta = cliente.post(
        "/usuarios", json={"nome": "A", "email": "nao-e-email", "senha": "123"}
    )
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert isinstance(corpo["detail"], str)
    assert corpo["detail"].strip()
def test_erro_de_validacao_preserva_os_detalhes_em_erros(cliente: TestClient):
    """A lista original continua disponível, só não ocupa mais o `detail`."""
    resposta = cliente.post("/usuarios", json={"email": "nao-e-email"})
    corpo = resposta.json()
    assert isinstance(corpo["erros"], list)
    assert corpo["erros"]
    assert all("loc" in erro for erro in corpo["erros"])
def test_erro_de_negocio_tem_detail_em_texto(cliente: TestClient, usuario: dict):
    """Erro de domínio e erro de validação têm a mesma forma de `detail`."""
    resposta = cliente.post(
        "/usuarios",
        json={"nome": "Outra", "email": usuario["email"], "senha": "senha123"},
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "E-mail já cadastrado."

def test_credencial_invalida_responde_401(cliente: TestClient, usuario: dict):
    """O front traduz este 401 no `null` que o `verificarCredenciais` devolve."""
    resposta = cliente.post(
        "/usuarios/login", json={"email": usuario["email"], "senha": "errada"}
    )
    assert resposta.status_code == 401
# ------------------------------------- mensagens em pt-BR, prontas para a tela
def test_campo_obrigatorio_em_portugues(cliente: TestClient):
    resposta = cliente.post("/usuarios", json={})
    assert resposta.status_code == 422
    assert "campo obrigatório" in resposta.json()["detail"]
def test_tamanho_minimo_cita_o_numero(cliente: TestClient):
    """A mensagem diz quantos caracteres faltam, e dos **dois** campos."""
    resposta = cliente.post(
        "/usuarios", json={"nome": "A", "email": "ana@exemplo.com", "senha": "123"}
    )
    detalhe = resposta.json()["detail"]
    assert "nome: deve ter no mínimo 2 caracteres." in detalhe
    assert "senha: deve ter no mínimo 6 caracteres." in detalhe
def test_email_invalido_em_portugues(cliente: TestClient):
    resposta = cliente.post(
        "/usuarios", json={"nome": "Ana", "email": "nao-e-email", "senha": "senha123"}
    )
    assert "e-mail inválido" in resposta.json()["detail"]

# =============================================================================
# Dia 8 — o contrato da autenticação
# =============================================================================
def test_todos_os_endpoints_de_tarefa_exigem_token(cliente: TestClient):
 """Sem `Authorization`, nenhuma operação de tarefa passa.
 O teste verifica os cinco endpoints de uma vez, comparando a **lista** de
 códigos. Um endpoint novo que esquecesse a autenticação não apareceria
 aqui — apareceria no `test_openapi_expoe_os_sete_endpoints`, do Dia 7, que
 conta as rotas. Os dois juntos fecham o cerco.
 """
 chamadas = [
 cliente.get("/tasks"),
 cliente.post("/tasks", json={"titulo": "X"}),
 cliente.patch("/tasks/1", json={"titulo": "X"}),
 cliente.delete("/tasks/1"),
 cliente.get("/usuarios/eu"),
 ]
 assert [c.status_code for c in chamadas] == [401, 401, 401, 401, 401]
def test_erro_de_autenticacao_tem_detail_em_texto(cliente: TestClient):
 """O 401 também precisa caber em `setErro(e.message)`."""
 resposta = cliente.get("/tasks")
 assert resposta.status_code == 401
 assert isinstance(resposta.json()["detail"], str)
 assert resposta.json()["detail"].strip()
def test_cors_libera_o_cabecalho_authorization(cliente: TestClient):
 """O `preflight` precisa autorizar o cabeçalho que o cliente vai enviar.
 `cliente.options(...)` é a requisição que o navegador faz por conta
 própria, antes da requisição de verdade.
 """
 resposta = cliente.options(
 "/tasks",
 headers={
 "Origin": "http://localhost:5173",
 "Access-Control-Request-Method": "GET",
 "Access-Control-Request-Headers": "authorization,content-type",
 },
 )
 assert resposta.status_code == 200
 permitidos = resposta.headers.get("access-control-allow-headers", "").lower()
 assert "authorization" in permitidos
def test_total_e_exposto_ao_navegador(cliente: TestClient):
 """Sem `expose_headers`, o `fetch` do navegador não lê o `X-Total-Count`.
 O servidor responde certo, o cliente não consegue ler, e os logs do
 servidor não registram nada de anormal. É a categoria de defeito que só um
 teste de contrato encontra.
 """
 resposta = cliente.get("/", headers={"Origin": "http://localhost:5173"})
 expostos = resposta.headers.get("access-control-expose-headers", "")
 assert "X-Total-Count" in expostos