<div align="center">

# OpenCode Fix

**Ferramenta de manutenção para o OpenCode Desktop no Windows.**

Destrava workspaces presos em retentativa, limpa erros do banco SQLite,
filtra apenas os modelos gratuitos do Zen e gerencia um conjunto de chaves
com troca automática quando alguma delas entra em limite de requisição.

[![Python](https://img.shields.io/badge/Python-3.10%2B-339933?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://learn.microsoft.com/windows/)
[![Dependências](https://img.shields.io/badge/Dependências-nenhuma-6B7280?style=for-the-badge&logo=python&logoColor=white)](#requisitos)

</div>

---

## O que é

O OpenCode Desktop armazena estado em um banco SQLite local. Quando uma
requisição falha, o app grava um contador de retentativa e uma mensagem de
erro. O workspace fica preso exibindo *"tentando novamente em Xs"* e não
se recupera até a limpeza manual do banco. O mesmo banco acumula imagens de
contexto além do limite de 50 por requisição, o que derruba chamadas novas.

O OpenCode Fix fecha esses caminhos em um executável de um clique. Ele
encerra processos travados, zera os contadores, remove as mensagens de
erro, arquiva imagens excedentes, instala gatilhos (triggers) de
autoproteção no SQLite e reabre o aplicativo.

Além do reparo, ele resolve o problema de cota do OpenCode Zen. O Zen
aplica limite de requisições por IP, não por chave. Quando o IP estoura,
todas as chaves retornam `429 Rate Limit` ao mesmo tempo. A ferramenta
mantém uma lista local de chaves, testa cada uma e ativa a que ainda tem
cota.

## Requisitos

| Requisito | Versão | Observação |
|---|---|---|
| Windows | 10 ou 11 | O script resolve os caminhos via `%APPDATA%` e `%USERPROFILE%` |
| Python | 3.10 ou superior | Marcado no PATH durante a instalação |
| OpenCode Desktop | qualquer | Deve estar instalado e ter rodado ao menos uma vez |
| Dependências Python | nenhuma | Usa apenas a biblioteca padrão |

O Cloudflare WARP é **opcional**. Ajuda quando o limite por IP é o
causador do erro, mas a ferramenta funciona sem ele.

## Instalação

```bash
git clone https://github.com/OTheMandaloriano/opencode-fix.git
cd opencode-fix
```

Depois, dê dois cliques em `OpenCode-Fix.bat`.

O `.bat` verifica se o Python está no PATH. Se não estiver, avisa e
indica o site de download antes de fechar.

## Como usar

Execute `OpenCode-Fix.bat` e escolha a opção no menu. A opção `[1]` é o
padrão: basta pressionar `ENTER`.

| Opção | O que faz |
|---|---|
| `[1]` Destravamento completo | Fecha processos travados, zera retentativas, limpa o SQLite, arquiva imagens excedentes, instala triggers, aplica o filtro de modelos gratuitos e reabre o OpenCode |
| `[2]` Gerenciador de chaves | Testa, ativa, cadastra, remove, importa e exporta chaves |
| `[3]` Rotação automática | Verifica o WARP, testa todas as chaves e ativa a que tiver cota livre |
| `[4]` Filtrar modelos Zen free | Deixa visíveis apenas os modelos com sufixo `-free` |
| `[5]` Reparar só o SQLite | Remove mensagens de erro e instala triggers, sem reiniciar o app |
| `[6]` Mudar para o XRouter | Ativa os modelos locais do XRouter quando a cota do Zen acaba |
| `[7]` Verificar Cloudflare WARP | Mostra o estado do serviço e o IP público atual |
| `[8]` Testar conexões | Testa WARP, XRouter local e a API oficial do Zen |

## Cadastrando chaves

O gerenciador aceita chaves por três caminhos. Escolha o que preferir.

**Pelo terminal.** Opção `[2]`, sub-opção `[4]`. O script pergunta o rótulo e
a chave e grava no `zen_keys.json`.

**Pelo arquivo `CHAVES.txt`.** Abra o arquivo em qualquer editor, adicione
uma linha por chave no formato `rotulo = sk-chave`, salve e volte ao
gerenciador, sub-opção `[6]`.

```
meuemail@exemplo.com = sk-ABC123_EXEMPLO_NAO_USAR
```

Linhas iniciadas com `#` e linhas em branco são ignoradas.

**Pela interface.** Use a sub-opção `[7]` para exportar o que já está
cadastrado de volta para o `CHAVES.txt`.

O `zen_keys.json` guarda o formato. Um exemplo rastreável está em
`zen_keys.example.json`.

> [!WARNING]
> O `zen_keys.json` e o `CHAVES.txt` ficam fora do controle de versão, no
> `.gitignore`. Suas chaves são suas. Se você já versionou esses arquivos em
> algum commit antigo, o histórico ainda contém as chaves e é preciso
> reescrevê-lo.

## Rotação automática

A ordem dentro do gerenciador importa. Testar antes de rotacionar mostra
qual chave está presa, e rotacionar sem testar pode trocar uma chave boa
por outra igualmente esgotada.

1. Verifique o WARP pela opção `[7]`. O Zen conta requisição por IP, então
   uma chave que falhou por `429` pode funcionar com o IP da Cloudflare.
2. Teste todas as chaves pela sub-opção `[1]`.
3. Ative a chave com cota livre pela sub-opção `[3]`.

O script também oferece a rotação em um clique pela opção `[3]` do menu
principal, que executa os três passos em sequência.

## Variável `XROUTER_TOKEN`

A opção `[8]` testa o XRouter local na porta `20127`. Esse teste é
autenticado por padrão, e o token **não** fica no código.

Defina a variável antes de executar:

```bat
set XROUTER_TOKEN=seu_token_aqui
OpenCode-Fix.bat
```

Sem a variável, o teste envia a requisição sem cabeçalho `Authorization`.
Um XRouter local sem autenticação responde normalmente; um configurado com
autenticação retorna `401`, e aí a variável é necessária.

## Limitações conhecidas

| Limitação | Motivo |
|---|---|
| Exclusivo para Windows | Os caminhos são resolvidos via `%APPDATA%` e `%USERPROFILE%`, que não existem em Linux e macOS |
| Não há dependências externas, mas também não há testes automatizados | O reparo atua sobre um banco SQLite vivo; um teste de integração exigiria uma instalação real do OpenCode, com o risco de alterar o estado da máquina de quem roda |
| O filtro de modelos depende da lista em `ZEN_FREE_MODELS` | O Zen renomeia e adiciona modelos. Se algum modelo gratuito novo não aparecer, acrescente o identificador na lista em `fix_opencode.py` |
| A rotação não contorna limite por IP por conta própria | Ela escolhe a chave com cota. Se todas retornarem `429`, o problema é o IP e a solução é o WARP |
| O XRouter local precisa estar rodando na porta `20127` | A ferramenta testa o serviço, mas não o instala |

## Arquivos

| Arquivo | Função |
|---|---|
| `OpenCode-Fix.bat` | Executável de um clique. Verifica o Python e chama o script |
| `fix_opencode.py` | Toda a lógica: reparo, filtros, chaves, WARP, testes |
| `CHAVES.txt` | Lista de chaves para importar. Não versionado |
| `zen_keys.json` | Banco de chaves do gerenciador. Não versionado |
| `zen_keys.example.json` | Exemplo do formato do `zen_keys.json` |
| `LEIA-ME.txt` | Manual em texto simples, para leitura sem Markdown |

## Contribuindo

Issues e pull requests são bem-vindos. Antes de abrir:

1. Não cole chaves, tokens ou `zen_keys.json` no issue. Descreva o
   comportamento, não o segredo.
2. Se o problema envolve reparo no SQLite, informe a versão do OpenCode
   Desktop e a do Python.
3. Rode a ferramenta em uma instalação de teste antes de sugeri-la como
   correção para outros. Ela altera banco de dados.

## Licença

MIT. Veja [LICENSE](LICENSE).
