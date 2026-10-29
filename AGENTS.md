# Guia do projeto para agentes

## Objetivo

myBotWinthor consulta produtos no Oracle/WinThor por meio de um bot Telegram. O painel web administra configuração, usuários, modelos de permissões, mensagens e fórmulas. A interface e as respostas são em português do Brasil. O ambiente principal de execução é Windows.

Leia primeiro [README.md](README.md). Para entender SQL e campos, consulte [docs/consultas.md](docs/consultas.md); para instalação, execução pelo terminal e backup, [docs/operacao.md](docs/operacao.md). Confira o código antes de alterar uma regra descrita aqui.

## Execução e verificação

- `configurar.bat`: configuração interativa.
- `iniciar.bat`: inicia API/painel e bot, com opção de abrir o navegador.
- `monitor.bat`: acompanha um arquivo de log existente; na execução direta, os logs aparecem no terminal do bot.
- Execução direta, na raiz: `.\.venv\Scripts\python.exe bot.py`.
- Testes sem Oracle ou Telegram reais: `.\.venv\Scripts\python.exe -m unittest discover -s tests`.
- Dependências: `requirements.txt`. Use o ambiente virtual do projeto.

O iniciador executa `bot.py` diretamente pelo Python da `.venv`; não instala nem inicia serviço Windows. A instalação de serviço foi retirada da interface. Os módulos antigos permanecem para compatibilidade com instalações anteriores; não os use no fluxo normal. Antes de migrar uma máquina antiga, pare e desative seu serviço para evitar instâncias duplicadas. Iniciar a aplicação pode ativar o polling Telegram real. Evite instâncias concorrentes usando o mesmo token.

## Mapa do código

Os arquivos Python da raiz são pontos de entrada; a implementação fica em `modulos/`.

| Arquivo | Responsabilidade |
|---|---|
| `modulos/bot.py` | Inicialização, comandos e handlers Telegram, consultas e montagem das respostas. |
| `modulos/database.py` | Conexão Oracle, consultas por código/nome, custos, catálogos e prévias reais. |
| `modulos/consulta_produto.py` | Exemplo de consulta manual pelo executor protegido; sem conexão no import. |
| `modulos/leitor_barras.py` | Leitura de códigos em imagens. |
| `modulos/permissoes.py` | Persistência JSON, configuração, usuários, modelos de perfil e autenticação do painel. |
| `modulos/escopo.py` | Restrições de filiais e regiões/tabelas de preço. |
| `modulos/painel_admin.py` | FastAPI, rotas autenticadas e HTML/CSS/JavaScript embutidos em `PAGINA`. |
| `modulos/painel_formulas.py` | Interface e rotas administrativas de fórmulas, incorporadas ao painel. |
| `modulos/mensagens.py` | Modelos de texto, variáveis permitidas, validação, prévia e renderização. |
| `modulos/campos_mensagem.py` | Reconhecimento e validação de colunas digitadas nas mensagens. |
| `modulos/campos_produto.py` | Configuração dos campos adicionais, formatação e permissão de visualização. |
| `modulos/calculos.py`, `modulos/formulas.py` | Cálculos padrão e explicação das fórmulas nas respostas. |
| `modulos/regras_margem.py` | Regras personalizadas, ajustes guiados e compilação de filtros em SQL com binds. |
| `modulos/margem_departamento.py` | Consulta e agregação do lucro por departamento. |
| `modulos/configurar.py`, `modulos/iniciar.py`, `modulos/rede.py` | Configuração por terminal, inicialização e endereços de acesso. |
| `modulos/servico_windows.py`, `modulos/bot_service.py`, `modulos/service_helper.py` | Instalação e administração do serviço Windows. |
| `modulos/monitor.py` | Monitoramento dos logs. |

## Dados de cada instalação

Na execução pelo código, a pasta persistente padrão é `<nome-do-projeto>-dados`, ao lado do projeto. `BOT_DATA_DIR` substitui esse caminho; se relativo, é resolvido a partir da raiz do projeto. `modulos/permissoes.py` define `DIRETORIO_DADOS` e `ARQUIVO_DADOS`.

- `dados_bot.json`: usuários, permissões, modelos de perfil e autenticação do painel.
- `config_bot.json`: configuração Telegram e opções do painel.
- `config_oracle.json`: conexão Oracle.
- `mensagens.json`: textos personalizados.
- `campos_produto.json`: registro interno dos campos adicionais usados nas mensagens e suas permissões.
- `formulas_margem.json`: regras personalizadas de cálculo.

Os arquivos opcionais são criados ao salvar. A configuração persistida pelo painel/BAT prevalece sobre os valores iniciais do ambiente. O cliente pode configurar pelo painel sem criar `.env`. Preserve os dados existentes e use os helpers de persistência com lock e gravação atômica; testes devem usar pastas temporárias.

Nunca versione `.env`, dados de clientes, tokens, senhas, logs, backups, `.venv` ou Oracle Client. O `.env.example` deve conter apenas exemplos fictícios. Ao publicar, confira o índice do Git, não apenas os arquivos alterados.

## Regras que devem ser preservadas

- Oracle é somente leitura. Tabelas são referenciadas sem prefixo de esquema; o usuário Oracle precisa de permissões ou sinônimos.
- Produtos excluídos (`PCPRODUT.DTEXCLUSAO` preenchido) não entram nas consultas nem nos totais de departamentos.
- Valores de entrada usam binds. Colunas e operações dinâmicas precisam de validação; nunca executar SQL, Python ou expressões arbitrárias enviados pelo usuário.
- `PCTABPR.PVENDA` é o preço de venda; `PCTABPR.PTABELA` é o preço programado. `NUMREGIAO` identifica a tabela/região; filial e região são dimensões distintas.
- **Preço programado só aparece com `ver_preco_programado`.** Consultar preços, ver custos ou ser administrador não substitui essa permissão. Mensagens personalizadas também devem respeitá-la.
- Custos, margem de produto e margem de departamento têm permissões independentes. Uma consulta individual não inclui o lucro do departamento.
- O administrador Telegram é cadastrado inicialmente com permissões completas, mas suas permissões do bot podem ser personalizadas. O login administrativo do painel é separado.
- Habilitar uma permissão habilita o acesso ao bot; desabilitar o acesso limpa as demais. Alterar um modelo propaga as permissões aos usuários vinculados, preservando os bloqueios previstos no código.
- Fórmula padrão de ganho sobre custo: `(preço − custo de entrada) / custo de entrada × 100`. Não trocar a base para preço de venda sem solicitação explícita. Valores inválidos não devem produzir divisão por zero.

## Personalização atual

A aba Personalização tem subabas **Mensagens** e **Fórmulas**. Não recrie o cadastro manual de campos como etapa obrigatória.

Nos blocos de identificação do produto, o administrador digita `{embalagem}`, `{codauxiliar}` ou outra coluna válida de PCPRODUT. Maiúsculas são normalizadas. Novos campos são validados contra metadados Oracle; salvar a mensagem registra os campos automaticamente. Campos desconhecidos como públicos começam restritos à permissão de custos. Preserve classificações já salvas.

A prévia padrão usa exemplos fictícios. **Consultar produto** usa CODPROD e valores reais, inclusive para produtos sem preço; campos nulos aparecem como “Não informado”. Testar não persiste alterações. A prévia administrativa pode mostrar campos que estarão restritos no Telegram.

Fórmulas são mantidas exclusivamente no painel. Ajustes podem afetar preço, custo ou resultado; percentual relativo e pontos percentuais são operações distintas. **Confirmar fórmula** atualiza a expressão e recalcula a prévia quando há CODPROD; somente **Salvar fórmula** persiste. Regras ativas usam prioridade crescente e filtros/listas de produtos. O departamento agrega os resultados ponderados pelo custo ajustado. Preserve a aplicação dos mesmos cálculos nas consultas e explicações do bot.

## Como alterar

Mantenha os pontos de entrada pequenos. Ao editar JavaScript embutido, confira também a string efetivamente renderizada por Python e a sintaxe do script. Subabas precisam ter seletores próprios para não interferir na navegação principal.

Execute testes pertinentes em `tests/`; use mocks ou SQLite para validar regras e SQL sem acessar produção. Mudanças em permissões, cálculos ou persistência precisam de regressões relevantes. Atualize README e documentação de consultas/operação conforme a mudança. Não registre valores sensíveis nos logs nem em saídas de diagnóstico.

## Executáveis e organização de entrega

Leia `docs/desenvolvimento.md` antes de alterar o empacotamento. `desktop/` contém gerenciador, instalador e build; `requirements-build.txt` separa a ferramenta PyInstaller das dependências de execução. `gerar_distribuicao.bat` publica `distribuicao/cliente`, `distribuicao/portatil` e seus ZIPs completos; `.build/` guarda intermediários e a distribuição anterior. Não mescle runtimes de versões diferentes nem inclua dados, credenciais ou desktop.json nos pacotes. As duas pastas geradas são ignoradas pelo Git.

No modo EXE, dados novos ficam em `%LOCALAPPDATA%/myBotWinthor/dados`. No uso pelo código, continua valendo o padrão `<projeto>-dados` ou BOT_DATA_DIR. O instalador pode reutilizar diretamente uma pasta de dados antiga escolhida pelo usuário; não a mova nem limpe durante builds/atualizações. O controle gráfico supervisiona um processo, não instala serviço Windows.
