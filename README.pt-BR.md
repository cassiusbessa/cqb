# CQB

[English](README.md)

O CQB é um **portão de qualidade local** para código Go. Ele nasceu para o
fluxo **agentico no Cursor**: numa sessão você pede a revisão, o agente
roda o portão, lê o relatório e te diz o que corrigir.

O terminal (`cqb run`) e o hook de git existem. A forma mais simples — e
para a qual o kit foi feito — é o chat do Cursor.

Precisa de Go 1.22+, `python3`, `git` e `gofmt`/`go`.

---

## Uso rápido: sessão no Cursor

No chat do Cursor, uma linha que começa com `/` dispara um fluxo do
agente. O CQB traz dois.

### Primeira vez no repositório: `/cqb-setup`

Abra o chat **na raiz do git** e escreva `/cqb-setup`. O agente instala o
CLI se faltar, roda `cqb init` e **pergunta** se alguma pasta sugerida
deve entrar na **lista de rigor** (a próxima seção). Sem o seu “sim”, a
lista fica vazia: o portão continua avisando (amarelo) e **não** trava o
`git push` por teste unitário fraco.

O agente **não conhece** o seu produto e **não escolhe sozinho** o que
deve bloquear o git.

### Em cada revisão: `/cqb`

Escreva `/cqb`. O agente compara a sua branch com a base (`main` ou
`master`, em geral), **roda o portão**, espera o relatório
(`.quality/last.json`) e escreve em português o que corrigir.

Você não precisa rodar `cqb run` antes. Não cole o JSON no chat.

Se o git tiver `main` **e** `master` e a branch não tiver *upstream*, o
agente **para e pergunta** com qual ref comparar — não adivinha.

Skills do kit só são copiadas se o arquivo **ainda não existir** no seu
`.cursor/`. As rules de domínio que você já tem continuam valendo.

---

## Cores, saída 1, e o que isso faz

O portão olha só o que mudou no git. Cada verificação ganha uma cor no
relatório. O `/cqb` lê essas cores. O `cqb run` também vira código de
saída do processo:

| Cor | `cqb run` | Significado |
|---|---|---|
| verde | sai 0 | Rodou e passou. |
| amarelo | sai 0 | Aviso para a revisão. **Nunca** faz o processo sair 1. |
| vermelho | **sai 1** | Bloqueio. |
| skip | sai 0 | Não se aplica a este diff. Não é “passou”. |
| unavailable | sai 0 | Faltou ferramenta (Docker, gremlins). Não é “passou”. |

**Sair 1** faz duas coisas, sem salto mental:

1. o `/cqb` trata o item como bloqueio (“corrija isso agora”);
2. se você empurrou com o hook ligado (`CQB=1 git push`), o **push para**.

Amarelo aparece no `/cqb` como aviso; o git segue. Docker ausente com
suíte de jornada que *deveria* ter rodado fica `unavailable` e **não**
vira vermelho sozinho. Jornada que rodou e falhou o assert continua
vermelha.

Na primeira instalação a **lista de rigor** (abaixo) está vazia: falta de
teste unitário **não** sai 1. `gofmt` / `go vet` / `go build` quebrados
**saem 1** mesmo com a lista vazia.

---

## Lista de rigor (`strict_paths` no `cqb.yaml`)

A lista de rigor **não** é lista do que o CQB ignora. Paths fora dela
ainda são checados; o aviso só não sai 1.

Você **nomeia as pastas em que um teste unitário fraco ou cobertura baixa
sai 1** — e portanto alerta o `/cqb` e, com `CQB=1`, trava o push. Não é
o conjunto de tudo que você quer testar.

```yaml
# em cqb.yaml
strict_paths: []                 # padrão: aviso de teste/cobertura não sai 1

strict_paths:
  - "internal/billing/**"        # nesta pasta, teste fraco / cobertura baixa SAI 1
```

Um **glob** é um padrão de path. `internal/billing/**` = tudo debaixo
dessa pasta (arquivos **novos** inclusive). `*invoice*` = path que
contém `invoice`. Você **não** lista arquivo por arquivo. Comece vazio;
acrescente só o recorte que o time quer tratar como bloqueio.

Não cole `internal/` “por garantia”: aí **qualquer** helper novo em
`internal/` passa a sair 1.

Ainda saem 1 **com lista vazia**: higiene (`gofmt`/`vet`/`build`) e teste
de jornada que **rodou** e quebrou.

Colocar um glob aqui **não** dispara teste de jornada. Isso é outro
arquivo, mais abaixo, só se você tiver suíte e2e.

---

## Prefixo (`prefix` no `cqb.yaml`)

Se o git mostra `services/billing/internal/foo.go` mas o módulo Go (e os
testes) falam `internal/foo.go`, a raiz do git **não** é o módulo. Aí
você preenche o prefixo **no `cqb.yaml`**:

```yaml
prefix: "services/billing"
```

Sem isso, o padrão `internal/` da lista de rigor e dos testes rápidos
não enxerga `services/billing/internal/...`.

Vários módulos: o path mais específico primeiro, na chave `prefixes`.

Confira com:

```bash
cqb run --mode file-list --files services/billing/internal/billing/normalize.go
```

Não deve dizer que o diff está fora do prefixo, se esse for o seu código.

---

## O que o `init` colocou no disco

O `/cqb-setup` já rodou isso. No terminal: `cqb init` na raiz do git.

```
seu-repo/
  cqb.yaml              *seu* arquivo (prefixo, lista de rigor, tetos…).
                        o init só cria se ainda não existir
  .cqb/
    engine/             cópia do motor (Python) usada pelo `cqb run`
    templates/          modelos de skills e do hook
    hooks/pre-push      script de hook (só trabalha com CQB=1)
    scan.json           inventário na hora do init (não é configuração)
    work/               temporários; ignorado pelo git
  .quality/             relatórios (`last.json`); ignorado pelo git
  .gitignore            bloco `# cqb begin` … `# cqb end`
```

O git **deve** versionar `cqb.yaml`, `.cqb/engine`, `.cqb/hooks` e
`.cqb/templates`. O init **não** ignora esses paths. Ele ignora lixo de
execução: `.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` é um retrato. O `/cqb-setup` usa para *sugerir* pastas da
lista de rigor; você decide.

**Onde o init anota testes de jornada.** Ele procura pastas que já tenham
suítes e2e. Encontrou **exatamente uma** (ex.:
`services/billing/internal/e2e`) → anota esse caminho em
`e2e.catalog_root` num `cqb.yaml` **novo**, só para o motor saber **onde
procurar** as suítes. Zero pastas, ou duas ou mais → não escolhe por
você. Isso **não** preenche a lista de rigor nem o prefixo.

**Hook.** Se `core.hooksPath` estava vazio neste repositório, o init
aponta o git **local** para `.cqb/hooks`. Se você já tinha outro valor
(husky, etc.), ele não sobrescreve. Em qualquer caso o hook **só roda o
CQB** neste comando:

```bash
CQB=1 git push          # roda `cqb run --mode push`; sair 1 cancela o push
git push                # sem CQB, o push segue
```

Não coloque `CQB=1` no bashrc: todo push do time passaria a esperar o
portão. O yaml **não** liga o hook sozinho.

---

## O que o CQB verifica

Só entra o que está no **diff** (e, com `prefix`, só dentro dessa pasta).
Não varre o módulo inteiro.

**Higiene (lint)** — `gofmt`, `go vet`, `go build` nos pacotes dos `.go`
que mudaram. Falhou → vermelho, **mesmo com lista de rigor vazia**.

**Complexidade** — funções **novas** acima dos tetos (30 cognitivo, 30
ciclomático, 5 `if` aninhados) ficam **amarelas**. Função antiga: só o
*aumento* (delta 5) é amarelo. Nunca vermelho. Handlers HTTP com vários
`if err != nil` costumam querer `cyclomatic` 35; o `/cqb-setup` pode
*sugerir* isso e **não grava** no yaml sem o seu sim.

**Teste rápido** — para uma função **nova** `Foo` em pasta “testável”
(padrão: `internal/`, fora de `internal/interface/`): existe um
`TestFoo` **e** o corpo do teste **chama** `Foo(`? Se falta o teste ou a
chamada → aviso. Isso *não* é percentual de cobertura e *não* é o teste
de jornada. Handlers HTTP (`http.ResponseWriter`) ficam de fora. Lista
de rigor vazia → **amarelo**; path na lista → **vermelho** (sai 1).

**Checagens no `*_test.go` (hunters)** — padrões frágeis, por exemplo:

- `t.Fatal("falhou")` sem mostrar o valor obtido e o esperado
- dois asserts na mesma linha
- `time.Now` / `rand` no teste
- comparação nova na **produção** (`n > 10`, `len(x) == 0`) cujo número
  não aparece em nenhum teste do pacote

Lista vazia: amarelo. Path na lista: vermelho (sai 1).

**Teste de jornada (e2e)** — se o diff cruza o recorte de uma suíte, o
CQB roda `go test -tags e2e` naquela pasta (em geral precisa de Docker).
Passou → verde. Assert falhou → vermelho (sai 1). Sem Docker e a suíte
foi pedida → `unavailable` (não sai 1). Isso **não** é a lista de rigor:
falta de Docker **não** trava o git por falta de `TestFoo`. Como o
recorte da suíte é declarado: seção seguinte.

**Cobertura** — percentual exercitado pelos testes unitários, nos
pacotes dos `.go` de produção que estão no diff. **Roda mesmo com a
lista de rigor vazia** (aí o aviso fica amarelo). Só sai 1 nos paths da
lista. Sem `.go` de produção no diff → `skip`. O CQB **não** reescreve o
arquivo de baseline no `cqb run`.

**Mutação** — ferramenta extra (`gremlins`), **não** é o mesmo que teste
rápido. Só tenta mutar se a função nova **já tem** `TestFoo` que chama
`Foo(`. Sem essa chamada, mutação fica `skip`; quem avisa a falta do
teste é o slot de teste rápido (amarelo ou vermelho conforme a lista de
rigor). Sem `gremlins` no `PATH` → `unavailable`, nunca vermelho. Mutante
que sobrevive → **amarelo**, nunca vermelho no v0.1.

---

## Teste de jornada: um padrão por suíte, não um inventário

Você **não precisa** disso para o `/cqb` funcionar. Só entra se o time
já tem (ou vai ter) `go test -tags e2e`.

São **dois** lugares, com perguntas diferentes:

| Onde | Pergunta |
|---|---|
| `strict_paths` no `cqb.yaml` | Neste path, aviso de unitário/cobertura **sai 1**? |
| `globs.txt` dentro da pasta da suíte | Devo **rodar** esta jornada se o diff casar? |

Pôr um glob só no `cqb.yaml` **não** dispara e2e. Os textos podem ser
iguais; as perguntas não são.

Cada suíte é uma pasta sob `e2e.catalog_root` (anotado no init, ou você
preenche). Nessa pasta existe um `globs.txt`. Você escreve **um padrão de
pasta**, não cada arquivo novo:

```
# services/billing/internal/e2e/invoices/globs.txt
internal/billing/**
```

Arquivo `.go` novo, pasta nova debaixo de `internal/billing/` → já casa.
Você **não** volta no `globs.txt` a cada implementação. Só edita quando
nasce uma **suíte nova** ou o código de produção mora em **outra árvore**.

Linha **com** `*` ou `**` casa o diff (path do git ou já sem o prefixo).
Linha **sem** `*` pina um arquivo que tem que existir (`prefix/linha` ou
na raiz); sumiu → catálogo **vermelho**. Prefira o padrão de pasta.

O init **não** inventa suítes. Você (ou o time) cria a pasta e o
`globs.txt`.

---

## Cobertura: baseline e I/O

Baseline padrão: `.cqb/cover-baseline.json`. Se você já tem outro JSON,
aponte `cover.baseline_path` no `cqb.yaml`. Imports que contam como I/O
(piso 80% quando o path está na lista de rigor): `database/sql`,
`net/http`, `os` — dá para estender em `io_imports`.

---

## No terminal (além do Cursor)

O dia a dia pode ser só `/cqb`. Estes comandos servem para instalar à
mão, depurar, e para o hook.

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /caminho/do/seu/repositório     # a raiz do git
cqb init
cqb run
```

O `cqb run` compara o que está no disco com o último commit (incluindo
arquivos novos ainda não no git).

Não aponte o dia a dia para `@latest`. Pin a tag; quando quiser atualizar:

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cqb upgrade
```

O `upgrade` troca o motor copiado em `.cqb/` pelo que está **neste**
binário.

O `--mode` diz **qual diff** (nunca o repo inteiro):

| Comando | O que entra |
|---|---|
| `cqb run` | Alterado ou novo desde o `HEAD` (inclui untracked). Dia a dia no terminal. |
| `cqb run --mode staged` | Só o que está no `git add` (o próximo commit). |
| `cqb run --mode push` | Diff contra o upstream (`git push`). É o que o hook chama. |
| `cqb run --mode review` | Commits desde o merge-base da branch base **mais** o working tree. É o que o `/cqb` chama, a menos que você peça só o working tree. |
| `cqb run --mode file-list --files a.go,b.go` | Só esses paths. Útil para debugar um arquivo. |

`--mode review` escolhe a base assim: branch de *upstream* se existir;
senão `main` **ou** `master` se só um dos dois existir. Se os dois
existirem (ou nenhum), o comando **para e pede** `--base <ref>`. O
`/cqb` faz a mesma pergunta.

`--output` (padrão `.quality/last.json`) é só o caminho do relatório.

---

## O que o yaml não desfaz

O `cqb.yaml` ajusta tetos, prefixo, lista de rigor, catálogo e2e. Ele
**não** consegue:

- varrer o módulo inteiro “por garantia”
- fazer amarelo sair 1
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
o `/cqb`. Gremlins só entra no slot de mutação, e mesmo assim não sai 1.

---

## Glossário

| Termo | Significado aqui |
|---|---|
| Relatório | JSON `.quality/last.json` com as cores de cada verificação. |
| Slot | Uma seção desse relatório (lint, teste, e2e, cover…). |
| Lista de rigor (`strict_paths`) | Globs onde aviso de teste/cobertura **sai 1** (alerta o `/cqb` e, com `CQB=1`, para o push). Não é lista do que o CQB ignora. |
| Glob | Padrão de path (`internal/billing/**`, `*invoice*`). Cobre arquivo novo que case; não é inventário. |
| Prefixo (`prefix`) | Pasta do módulo Go, **no `cqb.yaml`**, quando ela não é a raiz do git. |
| Teste rápido | “Função nova `Foo` tem `TestFoo` que chama `Foo(`?”. Não é e2e nem %. |
| Hunter | Checagem automática num `*_test.go` ou numa linha nova de produção. |
| Cobertura | Percentual exercitado pelos testes unitários (`go test -cover`). |
| E2e | Teste de jornada (`go test -tags e2e`), em geral com Docker. |
| `globs.txt` | Padrão que **dispara** a jornada; não é a lista de rigor. |
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
