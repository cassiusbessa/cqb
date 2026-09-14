# CQB

[English](README.md)

O CQB é um **portão de qualidade local** para código Go. Ele olha só o que
você mudou no git, grava um relatório em `.quality/last.json` e, na revisão
no Cursor, o comando `/cqb` **roda o portão e explica o relatório**.

Na primeira instalação ele **não impede o push** por teste unitário fraco
ou cobertura baixa. Isso só acontece depois que você aponta pastas na
**lista de rigor** (explicada mais abaixo).

Precisa de Go 1.22+, `python3`, `git` e `gofmt`/`go`.

---

## Uso rápido

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /caminho/do/seu/repositório     # a raiz do git
cqb init
cqb run
```

O `cqb run` compara o que está no disco com o último commit (incluindo
arquivos novos ainda não no git). Ele formata e compila o Go que mudou.
Se o que você alterou cruzar com uma suíte de testes de jornada (e2e),
pode rodar esses testes — em geral eles precisam de Docker.

- Sai **0** na maioria das vezes: o relatório existe para você (e para o
  `/cqb`) ler. Amarelo nunca muda esse código de saída.
- Sai **1** só se alguma verificação ficou **vermelha**: em geral `gofmt`,
  `go vet`, `go build`, ou e2e que rodou e falhou. Falta de teste unitário
  **não** derruba o git enquanto a lista de rigor estiver vazia.

Não aponte o dia a dia para `@latest`. Pin a tag; quando quiser atualizar:

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cqb upgrade
```

O `upgrade` troca o motor copiado em `.cqb/` pelo que está **neste**
binário.

---

## O que o `init` colocou no disco

```
seu-repo/
  cqb.yaml              *seu* arquivo de configuração (prefixo, lista de
                        rigor, tetos…). o init só cria se ainda não existir
  .cqb/
    engine/             cópia do motor (Python) usada pelo `cqb run`
    templates/          modelos de skills e do hook
    hooks/pre-push      script de hook (só trabalha com CQB=1)
    scan.json           inventário (quantos testes, pastas e2e)
    work/               temporários; ignorado pelo git
  .quality/             relatórios (`last.json`); ignorado pelo git
  .gitignore            bloco `# cqb begin` … `# cqb end`
```

O git **deve** versionar `cqb.yaml`, `.cqb/engine`, `.cqb/hooks` e
`.cqb/templates`. O init **não** ignora esses paths. Ele ignora lixo de
execução: `.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` não é configuração. É um retrato na hora do init. O
`/cqb-setup` usa isso para *sugerir* pastas; você decide.

**Quando o init preenche `e2e.catalog_root`?** Ele procura pastas que já
tenham testes de jornada. Encontrou **exatamente uma** (ex.:
`services/billing/internal/e2e`) → anota esse caminho no `cqb.yaml`
**novo**, só para saber onde procurar suítes. Zero pastas, ou duas ou
mais → deixa o campo em paz; não escolhe por você. Isso **não** preenche
a lista de rigor nem o prefixo.

Se o init viu `core.hooksPath` vazio neste repositório, ele aponta o git
local para `.cqb/hooks`. Se você já tinha outro valor (husky, etc.), ele
não sobrescreve. Em qualquer caso o hook **só roda o CQB** quando você
exporta `CQB=1` naquele push.

---

## Cores no relatório

Cada parte (lint, testes, e2e, cobertura…) ganha uma cor:

| Cor | O git | Significado |
|---|---|---|
| verde | segue | Rodou e passou. |
| amarelo | segue | Aviso para a revisão. **Nunca** faz o `cqb run` sair 1. |
| vermelho | **para** (`cqb run` sai 1) | Problema que o CQB trata como bloqueio. |
| skip | segue | Não se aplica a este diff. Não é “passou”. |
| unavailable | segue | Faltou ferramenta (Docker, gremlins). Não é “passou”. |

O `cqb run` sai 1 quando **algum** item está vermelho — no terminal, no
`--mode push` e no hook com `CQB=1`. Docker ausente com suíte que
*deveria* ter rodado fica `unavailable` e **não** vira vermelho sozinho.
E2e que rodou e falhou o assert, ou `globs.txt` quebrado, continuam
vermelhos.

---

## O que o CQB verifica

Só entra o que está no **diff** (e, se você configurou `prefix` no
`cqb.yaml`, só dentro dessa pasta). Não varre o módulo inteiro.

**Higiene (lint)** — `gofmt`, `go vet`, `go build` nos pacotes dos `.go`
que mudaram. Falhou → vermelho, **mesmo com lista de rigor vazia**.

**Complexidade** — funções **novas** acima dos tetos (30 cognitivo, 30
ciclomático, 5 `if` aninhados) ficam **amarelas**. Função antiga: só o
*aumento* (delta 5) é amarelo. Nunca vermelho.

**Teste rápido** — para uma função **nova** `Foo` em pasta “testável”
(padrão: `internal/`, fora de `internal/interface/`): existe um
`TestFoo` **e** o corpo do teste **chama** `Foo(`? Se falta o teste ou a
chamada → aviso. Isso *não* é percentual de cobertura e *não* é o
`go test` da suíte e2e. Handlers HTTP (`http.ResponseWriter`) ficam de
fora. Lista de rigor vazia → **amarelo**; path na lista → **vermelho**.

**Checagens no `*_test.go` (hunters)** — padrões frágeis, por exemplo:

- `t.Fatal("falhou")` sem mostrar o valor obtido e o esperado
- dois asserts na mesma linha
- `time.Now` / `rand` no teste
- comparação nova na **produção** (`n > 10`, `len(x) == 0`) cujo número
  não aparece em nenhum teste do pacote

Lista vazia: amarelo. Path na lista: vermelho.

**E2e** — se o diff casa o `globs.txt` de uma suíte, o CQB roda
`go test -tags e2e` naquela pasta. Passou → verde. Assert falhou →
vermelho. Sem Docker e a suíte foi pedida → `unavailable`. Isso **não** é
a lista de rigor: implicar Docker não bloqueia push por falta de
`TestFoo`.

**Cobertura** — percentual de código exercitado pelos testes unitários,
nos pacotes dos `.go` de produção que estão no diff. **Roda mesmo com a
lista de rigor vazia** (aí o aviso fica amarelo). Só pode ficar vermelho
— e parar o git — nos paths da lista. Sem `.go` de produção no diff →
`skip`. O CQB **não** reescreve o arquivo de baseline no `cqb run`.

**Mutação** — opcional (gremlins), só se a função nova já tem teste que
a invoca. Mutante que sobrevive → amarelo, nunca vermelho no v0.1.

---

## Lista de rigor (`strict_paths`)

No `cqb.yaml` a chave é `strict_paths` (o nome antigo `red_allowlist`
ainda é lido). Não é “permissão” e **não** é lista do que o CQB ignora.

Você **nomeia as pastas em que um aviso pode parar o push**. Não é o
conjunto de tudo que você quer testar. Não é lista do que fica de fora:
o que não está na lista ainda é checado; só não fica vermelho.

```yaml
# em cqb.yaml
strict_paths: []                 # padrão: avisos de teste/cobertura não param o git

strict_paths:
  - "internal/billing/**"        # nesta pasta, teste fraco / cobertura baixa PODE sair 1
```

Um **glob** é um padrão de path. `internal/billing/**` = tudo debaixo
dessa pasta. `*invoice*` = path que contém `invoice`. Você **não** precisa
listar o módulo inteiro. Comece vazio; acrescente só o recorte que o time
quer tratar como bloqueio.

Não cole `internal/` “por garantia”: aí **qualquer** helper novo em
`internal/` passa a poder falhar o git.

Ainda podem ser vermelhos **com lista vazia**: higiene (`gofmt`/`vet`/`build`)
e e2e que rodou e quebrou (ou catálogo `globs.txt` inválido).

**Não confundir com `globs.txt` de e2e.** Esse arquivo responde “devo
**rodar** esta suíte de jornada?”. A lista de rigor responde “neste path,
aviso de teste unitário / cobertura pode **impedir o push**?”. Os textos
podem ser iguais; as perguntas não são.

---

## Os modos do `cqb run`

O CQB nunca olha o repo inteiro. O `--mode` diz **qual diff**.

| Comando | O que entra |
|---|---|
| `cqb run` | Alterado ou novo desde o `HEAD` (inclui untracked). Dia a dia no terminal. |
| `cqb run --mode staged` | Só o que está no `git add` (o próximo commit). |
| `cqb run --mode push` | Diff contra o upstream (`git push`). É o que o hook chama. |
| `cqb run --mode review` | Commits desde o merge-base da branch base **mais** o working tree. É o que o `/cqb` chama. |
| `cqb run --mode file-list --files a.go,b.go` | Só esses paths. Útil para debugar um arquivo. |

`--mode review` escolhe a base assim: branch de *upstream* se existir;
senão `main` **ou** `master` se só um dos dois existir. Se os dois
existirem (ou nenhum), o comando **para e pede** `--base <ref>` — não
adivinha. O `/cqb` faz a mesma pergunta a você.

`--output` (padrão `.quality/last.json`) é só o caminho do relatório.

---

## Comandos no Cursor

No chat do Cursor, uma linha que começa com `/` dispara um fluxo do
agente. O CQB traz dois.

**`/cqb`** — revisão de código. Escolhe o diff (`--mode review`, a menos
que você peça só o working tree), **roda `cqb run`**, espera o
`.quality/last.json` e escreve em português o que corrigir. Você não
precisa rodar o CLI antes. Não cole o JSON no chat.

**`/cqb-setup`** — primeira configuração guiada. Instala o CLI se faltar,
roda `cqb init`, lê o `scan.json` e **pergunta** se alguma pasta sugerida
(em geral as que já têm suíte e2e) deve entrar na lista de rigor. Sem o
seu “sim”, a lista permanece vazia: o gate continua avisando (amarelo),
sem bloquear push por teste unitário. O agente **não conhece** o seu
produto e **não escolhe sozinho** a pasta que deve bloquear o push.

Skills do kit só são copiadas se o arquivo **ainda não existir** no seu
`.cursor/`. As rules de domínio que você já tem continuam valendo.

---

## O arquivo `cqb.yaml`

Toda configuração mora **neste arquivo** na raiz do git (ou no path que
você passou ao `cqb run`). Não é variável de ambiente.

Se o git mostra `services/billing/internal/foo.go` mas os testes e o
`globs.txt` falam `internal/foo.go`, o módulo Go não é a raiz do git.
Aí você preenche o prefixo **no `cqb.yaml`**:

```yaml
prefix: "services/billing"
```

Sem isso, o padrão `internal/` não enxerga `services/billing/internal/...`.

Vários módulos: o path mais específico primeiro, na chave `prefixes`.

Confira com:

```bash
cqb run --mode file-list --files services/billing/internal/billing/normalize.go
```

Não deve dizer que o diff está fora do prefixo, se esse for o seu código.

---

## E2e (`globs.txt`) e tetos — quando você for usar

Cada suíte é uma pasta com um arquivo `globs.txt`. Esse arquivo lista o
que **deve disparar** a suíte se aparecer no diff — não o que deve ser
ignorado. Exemplo
`services/billing/internal/e2e/invoices/globs.txt`:

```
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

Linha com `*` casa o diff (path do git ou já sem o `prefix`). Linha
**sem** `*` tem que existir como arquivo (`prefix/linha` ou na raiz).
Arquivo SQL sumido → catálogo **vermelho**.

O init **não** inventa suítes. Você (ou o time) cria o `globs.txt`.

Cobertura: baseline padrão `.cqb/cover-baseline.json`. Se você já tem
outro JSON, aponte `cover.baseline_path` no `cqb.yaml`. Imports que
contam como I/O (piso 80% quando o path está na lista de rigor):
`database/sql`, `net/http`, `os` — dá para estender em `io_imports`.

Tetos de complexidade são **só amarelo**. Handlers com vários
`if err != nil` costumam querer `cyclomatic` 35; o `/cqb-setup` pode
*sugerir* isso e **não grava** no yaml sem o seu sim.

---

## Hook de git

Depois do `init`, se o repositório não tinha `core.hooksPath`, o git
local já aponta para `.cqb/hooks`. O script **não faz nada** até:

```bash
CQB=1 git push          # roda `cqb run --mode push`
git push                # sem CQB, o push segue
```

Não coloque `CQB=1` no bashrc: todo push do time passaria a esperar o
gate. Yaml **não** liga o hook sozinho.

---

## O que o yaml não desfaz

O `cqb.yaml` ajusta tetos, prefixo, lista de rigor, catálogo e2e. Ele
**não** consegue:

- varrer o módulo inteiro “por garantia”
- fazer amarelo falhar o git
- exigir `CQB=1` em todo push do time
- pintar de vermelho teste/cobertura fora da lista de rigor

Chaves como `yellow_blocks` são ignoradas (`ignored_keys` no relatório).
Isso é de propósito: o time não congela o git por um teto de
complexidade.

---

## Arquitetura

```
cqb (binário Go) ──embute──► engine Python + templates
        cqb init     copia isso para .cqb/ no seu repo
        cqb run      python3 .cqb/engine/orchestrator.py
        cqb upgrade  troca essa cópia pela do binário atual
```

`golangci-lint` e `gremlins` entram no `PATH` no init; no v0.1 o lint
vermelho do CQB é só gofmt/vet/build. O golangci fica para você ou para
o `/cqb`.

---

## Glossário

| Termo | Significado aqui |
|---|---|
| Relatório | JSON `.quality/last.json` com as cores de cada verificação. |
| Slot | Uma seção desse relatório (lint, teste, e2e, cover…). |
| Lista de rigor (`strict_paths`) | Globs onde aviso de teste/cobertura **pode** virar vermelho e parar o git. Não é ignore. O yaml antigo `red_allowlist` é o mesmo campo. |
| Glob | Padrão de path (`internal/billing/**`, `*invoice*`). |
| Prefixo (`prefix`) | Pasta do módulo Go, **no `cqb.yaml`**, quando ela não é a raiz do git. |
| Teste rápido | “Função nova `Foo` tem `TestFoo` que chama `Foo(`?”. Não é e2e nem %. |
| Hunter | Checagem automática num `*_test.go` ou numa linha nova de produção. |
| Cobertura | Percentual exercitado pelos testes unitários (`go test -cover`). |
| E2e | Teste de jornada (`go test -tags e2e`), em geral com Docker. |
| `globs.txt` | Lista do que **dispara** o e2e, não do que fica vermelho no unitário. |
| Scan (`scan.json`) | Inventário gerado no init; não é a lista de rigor. |
| Hook | Script de pre-push; só analisa se `CQB=1`. |
| Motor / engine | Python em `.cqb/engine` que monta o relatório. |
| `/cqb`, `/cqb-setup` | Comandos no **chat do Cursor**. `/cqb` roda o portão e interpreta. |
| Skip / unavailable | Não rodou / faltou ferramenta. Não interprete como verde. |

---

## Este repositório

Público de propósito. Exemplos inventados: `internal/billing`,
`services/billing` (`github.com/example/billingapp`). Ver
[CONTRIBUTING.md](CONTRIBUTING.md).

```bash
go test ./...
python3 -m unittest discover -s engine/tests
```
