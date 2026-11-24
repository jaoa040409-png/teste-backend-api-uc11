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

from datetime import date, timedelta

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
    
# Dia 9 — o contrato das tarefas 
# ============================================================================= 

def criar_tarefa(cliente: TestClient, **campos) -> dict: 
    """Cria uma tarefa pela API e devolve o JSON da resposta. 

    Não recebe o dono: ele vem do token do cliente informado. 
    """ 
    corpo = {"titulo": "Tarefa"} 
    corpo.update(campos) 
    resposta = cliente.post("/tasks", json=corpo) 
    assert resposta.status_code == 201, resposta.text 
    return resposta.json() 

# ---------------------------------------------------- campos — `@typedef Task` 

def test_tarefa_tem_exatamente_os_campos_do_typedef(cliente_logado: TestClient): 
    """Nem a mais nem a menos: um campo faltando quebra a tela, e um campo 
    extra indica que o domínio vazou para a borda.""" 
    tarefa = criar_tarefa(cliente_logado) 
    assert set(tarefa) == { 
        "id", 
        "usuarioId", 
        "titulo", 
        "status", 
        "prioridade", 
        "prazo", 
        "criadoEm", 
        "atualizadoEm", 
        "concluidoEm", 
    } 

# --------------------------------------------- datas — `new Date(...)` no front 

def test_datas_saem_em_utc_declarado(cliente_logado: TestClient, usuario: dict): 
    """Toda data e hora termina em `Z`. 

    Sem o sufixo, `new Date(...)` lê o horário como **local do navegador**, e 
    um servidor em UTC e um navegador em Brasília discordariam em três horas. 
    """ 
    tarefa = criar_tarefa(cliente_logado) 
    concluida = cliente_logado.patch( 
        f"/tasks/{tarefa['id']}", json={"status": "concluida"} 
    ).json() 

    assert tarefa["criadoEm"].endswith("Z") 
    assert tarefa["atualizadoEm"].endswith("Z") 
    assert concluida["concluidoEm"].endswith("Z") 
    assert usuario["criadoEm"].endswith("Z") 

def test_prazo_continua_sendo_so_a_data(cliente_logado: TestClient): 
    """`prazo` é `YYYY-MM-DD`, sem hora e sem fuso.""" 
    tarefa = criar_tarefa(cliente_logado, prazo="2026-03-15") 
    assert tarefa["prazo"] == "2026-03-15"
    
# ------------------------------- vocabulário dos filtros — TaskFilters.jsx 

def test_ordenar_por_recente_e_aceito(cliente_logado: TestClient): 
    """`useTasks.js` chama de `recente` o que a API chama de `criadoEm`.""" 
    criar_tarefa(cliente_logado, titulo="Primeira") 
    criar_tarefa(cliente_logado, titulo="Segunda") 

    resposta = cliente_logado.get("/tasks", params={"ordenarPor": "recente"}) 
    assert resposta.status_code == 200 
    assert [t["titulo"] for t in resposta.json()] == ["Segunda", "Primeira"] 

def test_sentinela_todas_vale_como_sem_filtro(cliente_logado: TestClient): 
    """Os seletores do front começam em `todas` e mandam esse valor.""" 
    criar_tarefa(cliente_logado, titulo="Pendente") 
    concluida = criar_tarefa(cliente_logado, titulo="Concluida") 
    cliente_logado.patch(f"/tasks/{concluida['id']}", json={"status": "concluida"}) 

    resposta = cliente_logado.get( 
        "/tasks", params={"status": "todas", "prioridade": "todas"} 
    ) 
    assert resposta.status_code == 200 
    assert len(resposta.json()) == 2 

def test_filtro_enviado_vazio_vale_como_sem_filtro(cliente_logado: TestClient): 
    """`?status=` é o que um formulário HTML produz com o campo em branco.""" 
    criar_tarefa(cliente_logado) 
    resposta = cliente_logado.get("/tasks?status=&prioridade=") 
    assert resposta.status_code == 200 
    assert len(resposta.json()) == 1 

def test_valor_de_filtro_invalido_continua_sendo_recusado( 
    cliente_logado: TestClient, 
): 
    """Aceitar a sentinela não é aceitar qualquer coisa: `inventado` não passa.""" 
    resposta = cliente_logado.get("/tasks", params={"status": "inventado"}) 
    assert resposta.status_code == 422 

# ---------------------------- sentido natural da ordenação — `ordenar()` no front 

def test_ordem_natural_de_prazo_e_crescente(cliente_logado: TestClient): 
    """Sem `ordem`, prazo ordena do mais próximo para o mais distante.""" 
    hoje = date.today() 
    criar_tarefa( 
        cliente_logado, titulo="Distante", prazo=str(hoje + timedelta(days=30)) 
    ) 
    criar_tarefa( 
        cliente_logado, titulo="Proxima", prazo=str(hoje + timedelta(days=1)) 
    ) 

    resposta = cliente_logado.get("/tasks", params={"ordenarPor": "prazo"}) 
    assert [t["titulo"] for t in resposta.json()] == ["Proxima", "Distante"]
    
def test_tarefa_sem_prazo_vai_para_o_fim_nos_dois_sentidos( 
    cliente_logado: TestClient, 
): 
    """O SQLite trata `NULL` como o menor valor; o PostgreSQL, não. 

    Sem `NULLS LAST` explícito, este teste passaria em desenvolvimento e 
    falharia em produção. Por isso o laço roda os **dois** sentidos. 
    """ 
    hoje = date.today() 
    criar_tarefa(cliente_logado, titulo="Com prazo", prazo=str(hoje)) 
    criar_tarefa(cliente_logado, titulo="Sem prazo", prazo=None) 

    for sentido in ("asc", "desc"): 
        resposta = cliente_logado.get( 
            "/tasks", params={"ordenarPor": "prazo", "ordem": sentido} 
        ) 
        titulos = [t["titulo"] for t in resposta.json()] 
        assert titulos[-1] == "Sem prazo", f"ordem={sentido} devolveu {titulos}" 

def test_ordem_natural_de_prioridade_comeca_na_urgente(cliente_logado: TestClient): 
    """Sem `ordem`, prioridade vai da mais urgente para a menos.""" 
    for prioridade in ("baixa", "urgente", "media"): 
        criar_tarefa(cliente_logado, titulo=prioridade, prioridade=prioridade) 

    resposta = cliente_logado.get("/tasks", params={"ordenarPor": "prioridade"}) 
    assert [t["prioridade"] for t in resposta.json()] == ["urgente", "media", "baixa"] 

def test_ordem_natural_de_criado_em_comeca_na_mais_recente( 
    cliente_logado: TestClient, 
): 
    """Cada campo de ordenação tem um sentido natural **diferente** — é a 
    tabela `_ORDENS_NATURAIS` do `app/enums.py` que registra isso.""" 
    criar_tarefa(cliente_logado, titulo="Antiga") 
    criar_tarefa(cliente_logado, titulo="Nova") 

    resposta = cliente_logado.get("/tasks") 
    assert [t["titulo"] for t in resposta.json()] == ["Nova", "Antiga"] 
    
# ------------------------------------------------------------ busca por título 

def test_busca_filtra_pelo_titulo_ignorando_maiusculas(cliente_logado: TestClient): 
    """O front busca com `titulo.toLowerCase().includes(termo)`.""" 
    criar_tarefa(cliente_logado, titulo="Revisar proposta do cliente") 
    criar_tarefa(cliente_logado, titulo="Organizar planilha") 

    resposta = cliente_logado.get("/tasks", params={"busca": "PROPOSTA"}) 
    assert [t["titulo"] for t in resposta.json()] == ["Revisar proposta do cliente"] 

def test_busca_trata_curingas_do_sql_como_texto(cliente_logado: TestClient): 
    """Procurar por `100%` não pode devolver tudo. 

    `%` é o curinga do `LIKE`. É o mesmo raciocínio da injeção de SQL, numa 
    versão sem malícia: um caractere digitado como texto sendo interpretado 
    como comando. 
    """ 
    criar_tarefa(cliente_logado, titulo="Pagar 100% da fatura") 
    criar_tarefa(cliente_logado, titulo="Revisar proposta") 

    resposta = cliente_logado.get("/tasks", params={"busca": "100%"}) 
    assert [t["titulo"] for t in resposta.json()] == ["Pagar 100% da fatura"] 

    resposta = cliente_logado.get("/tasks", params={"busca": "%"}) 
    assert [t["titulo"] for t in resposta.json()] == ["Pagar 100% da fatura"] 

def test_busca_vazia_nao_filtra(cliente_logado: TestClient): 
    criar_tarefa(cliente_logado) 
    resposta = cliente_logado.get("/tasks", params={"busca": "   "}) 
    assert len(resposta.json()) == 1 

# ------------------------------------- total de registros — DashboardPage.jsx 

def test_total_vem_no_cabecalho_e_ignora_o_limite(cliente_logado: TestClient): 
    """`X-Total-Count` diz quantas existem, não quantas vieram.""" 
    for n in range(3): 
        criar_tarefa(cliente_logado, titulo=f"Tarefa {n}") 

    resposta = cliente_logado.get("/tasks", params={"limit": 2}) 
    assert len(resposta.json()) == 2 
    assert resposta.headers["X-Total-Count"] == "3" 

def test_total_respeita_os_filtros(cliente_logado: TestClient): 
    """Um total correto sobre o conjunto errado é tão ruim quanto um errado.""" 
    criar_tarefa(cliente_logado, titulo="Urgente", prioridade="urgente") 
    criar_tarefa(cliente_logado, titulo="Baixa", prioridade="baixa") 

    resposta = cliente_logado.get("/tasks", params={"prioridade": "urgente"}) 
    assert resposta.headers["X-Total-Count"] == "1"
    
# --------------------------------------------- mensagens de erro das tarefas 

def test_valor_de_enum_invalido_lista_os_aceitos(cliente_logado: TestClient): 
    """Quem recebeu o erro precisa saber o que mandar em vez disso.""" 
    resposta = cliente_logado.post( 
        "/tasks", json={"titulo": "X", "prioridade": "altissima"} 
    ) 
    assert resposta.json()["detail"] == ( 
        "prioridade: valor inválido. Aceitos: baixa, media, alta ou urgente." 
    ) 

def test_data_malformada_informa_o_formato(cliente_logado: TestClient): 
    """O erro mais comum de integração: data em formato brasileiro.""" 
    resposta = cliente_logado.post( 
        "/tasks", json={"titulo": "X", "prazo": "15/03/2026"} 
    ) 
    assert resposta.json()["detail"] == ( 
        "prazo: deve ser uma data no formato AAAA-MM-DD." 
    ) 

def test_mensagem_usa_o_nome_publico_do_campo(cliente_logado: TestClient): 
    """O cliente envia `prazoAte`; a mensagem não pode falar de `prazo_ate`.""" 
    resposta = cliente_logado.get("/tasks?prazoAte=15/03/2026") 
    detalhe = resposta.json()["detail"] 
    assert detalhe.startswith("prazoAte:"), detalhe 
    assert "prazo_ate" not in detalhe 
# ------------------------------------------- o fluxo que o AuthContext executa 

def test_fluxo_completo_que_o_front_vai_executar(cliente: TestClient): 
    """Cadastrar, usar o token, reabrir o app e recuperar a sessão. 

    O único teste da suíte que percorre um **cenário de uso** de ponta a 
    ponta. Vale um por suíte: é caro e, quando falha, não diz onde — mas é o 
    único que prova que as peças se encaixam na ordem em que alguém vai usá-las. 
    """ 
    sessao = cliente.post( 
        "/usuarios", 
        json={"nome": "Davi", "email": "davi@exemplo.com", "senha": "senha123"}, 
    ).json() 
    autorizacao = {"Authorization": f"Bearer {sessao['accessToken']}"} 

    criada = cliente.post( 
        "/tasks", json={"titulo": "Primeira tarefa"}, headers=autorizacao 
    ) 
    assert criada.status_code == 201 

    conta = cliente.get("/usuarios/eu", headers=autorizacao) 
    assert conta.status_code == 200 
    assert conta.json() == sessao["usuario"] 

    minhas = cliente.get("/tasks", headers=autorizacao) 
    assert [t["titulo"] for t in minhas.json()] == ["Primeira tarefa"]