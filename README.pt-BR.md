# CQB

[English](README.md)

O CQB é um **portão de qualidade local** para código Go. Ele olha só o que
você mudou no git, escreve um **relatório** em `.quality/last.json` e,
se você quiser, um comando no chat do Cursor (`/cqb`) lê esse relatório
na revisão.

Na primeira instalação ele **não impede o push** por teste fraco ou
cobertura. Isso só acontece depois que você aponta pastas específicas
(a *allowlist* — explicada mais abaixo).

Precisa só de Go 1.22+, `python3`, `git` e `gofmt`/`go`.

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
  `/cqb`) ler, não para travar o git.
- Sai **1** de cara só se `gofmt`, `go vet` ou `go build` falharam, ou se
  uma suíte e2e que *deveria* rodar quebrou. Falta de teste unitário **não**
  derruba o git nesta fase.

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
  cqb.yaml              regras *suas* (prefixo, allowlist, tetos…). o init
                        só cria se o arquivo ainda não existir
  .cqb/
    engine/             cópia do motor (Python) usada pelo `cqb run`
    templates/          modelos de skills e do hook
    hooks/pre-push      script de hook; **não** está ligado ao git ainda
    scan.json           inventário automático (quantos testes, pastas e2e)
    work/               arquivos temporários (cover); ignorado pelo git
  .quality/             relatórios (`last.json`); ignorado pelo git
  .gitignore            o init acrescenta um bloco `# cqb begin` … `# cqb end`
```

O git **deve** versionar `cqb.yaml`, `.cqb/engine`, `.cqb/hooks` e
`.cqb/templates`. O init **não** ignora esses paths. Ele ignora lixo de
execução: `.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` não é configuração. É um retrato do repo na hora do init
(módulo Go, densidade de `*_test.go`, pastas que já têm `globs.txt` de
e2e). O comando `/cqb-setup` usa isso para *sugerir* pastas; você decide.

Às vezes o scan encontra **uma** pasta que já tem testes de jornada
(e2e), por exemplo `services/billing/internal/e2e`. Aí o `cqb.yaml` novo
anota esse caminho em `e2e.catalog_root` — só para o CQB saber onde
procurar as suítes. Isso **não** escolhe pastas que bloqueiam o push.
Prefixo do monorepo e allowlist **continuam vazios** até você preencher
— ver [Quando o repo não é um módulo só](#quando-o-repo-não-é-um-módulo-só)
e [Allowlist](#allowlist-onde-o-amarelo-pode-virar-vermelho).

---

## Cores no relatório

Cada parte do relatório (lint, testes, e2e, cobertura…) ganha uma cor:

| Cor | O git | Significado |
|---|---|---|
| verde | segue | Rodou e passou. |
| amarelo | segue | Aviso para a revisão. **Nunca** faz o `cqb run` sair 1. |
| vermelho | **para** (`cqb run` sai 1) | Problema que o CQB trata como bloqueio. |
| skip | segue | Não se aplica a este diff. Não é “passou”. |
| unavailable | segue no dia a dia | Faltou ferramenta (Docker, gremlins). Não é “passou”. |

O `cqb run` sai 1 quando **algum** item está vermelho.

Exceção do hook (opcional, no fim deste guia): se você ligar o hook e
fizer `CQB=1 git push`, e2e `unavailable` com suíte que *deveria* ter
rodado também sai 1 — em geral Docker fora do `PATH`.

---

## O que o CQB verifica

Só entra o que está no **diff** (e, se você configurou, dentro do
`prefix`). Não varre o módulo inteiro.

**Higiene (lint)** — `gofmt`, `go vet`, `go build` nos pacotes dos `.go`
que mudaram. Falhou → vermelho, **mesmo com allowlist vazia**.

**Complexidade** — funções **novas** acima dos tetos (30 cognitivo, 30
ciclomático, 5 `if` aninhados) ficam **amarelas**. Função antiga: só o
*aumento* (delta 5) é amarelo. Nunca vermelho.

**Teste rápido** — para uma função **nova** `Foo` em pasta “testável”
(padrão: `internal/`, fora de `internal/interface/`): existe um
`TestFoo` **e** o corpo do teste **chama** `Foo(`? Se falta nome ou
falta a chamada → aviso. Isso *não* é “percentual de cobertura” e *não*
é o `go test` da suíte e2e. Handlers HTTP (`http.ResponseWriter`) ficam
de fora. Com allowlist vazia isso é **amarelo**; na allowlist vira
**vermelho**.

**Checagens de qualidade no `*_test.go` (hunters)** — padrões frágeis,
por exemplo:

- `t.Fatal("falhou")` sem dizer o valor obtido e o esperado (cego)
- dois asserts na mesma linha
- `time.Now` / `rand` no teste
- comparação nova na **produção** (`n > 10`, `len(x) == 0`) cujo número
  não aparece em nenhum teste do pacote

Com allowlist vazia: amarelo. Na allowlist: vermelho.

**E2e** — se o diff casa o `globs.txt` de uma suíte, o CQB roda
`go test -tags e2e` naquela pasta. Passou → verde. Assert falhou →
vermelho. Sem Docker e a suíte foi implicada → `unavailable`. Isso **não**
é a allowlist: implicar Docker não bloqueia push por falta de `TestFoo`.

**Cobertura (cover)** — percentual de linhas exercitadas pelos testes
unitários, **só** quando a allowlist tem itens **e** o diff toca `.go` de
produção que casam. Sem allowlist o item fica `skip` (nem roda). Helper
puro sem `Foo(` no teste → vermelho. Arquivo que fala com banco/HTTP
abaixo de 80% → vermelho. O CQB **não** reescreve o arquivo de baseline
no `cqb run`.

**Mutação** — opcional (gremlins), só se a função nova já tem teste que
a invoca. Mutante que sobrevive → amarelo, nunca vermelho no v0.1.

---

## Allowlist: onde o amarelo pode virar vermelho

A `red_allowlist` no `cqb.yaml` é uma lista de **padrões de path** (globs).
Ela **não** é lista do que o CQB ignora.

- Path **dentro** de um glob → teste rápido, hunters e cobertura **podem**
  ficar vermelhos e o `cqb run` **pode sair 1**.
- Path **fora**, ou lista `[]` → esses mesmos avisos ficam amarelos (ou
  cobertura `skip`) e **não** derrubam o git.

```yaml
red_allowlist: []          # padrão após o init: nada disso é vermelho

red_allowlist:
  - "internal/billing/**"  # daqui pra frente, teste fraco *nessa* pasta pode bloquear o push
```

Não cole `internal/` “por garantia”: aí **qualquer** helper novo em
`internal/` passa a poder falhar o git.

A allowlist **não** é “só percentual de cobertura”. Cobertura é um dos
avisos. Nesses paths também podem ficar vermelhos: função nova sem teste
que a chama; `t.Fatal` que não mostra o valor obtido e o esperado; os
outros hunters da seção acima.

Ainda podem ser vermelhos **com lista vazia**: higiene (`gofmt`/`vet`/`build`)
e e2e que rodou e quebrou (ou catálogo `globs.txt` inválido).

**Não confundir com `globs.txt` de e2e.** Esse arquivo só responde “devo
rodar a suíte de integração?”. A allowlist responde “neste path, aviso
de teste unitário pode impedir o push?”. Os textos podem ser iguais; as
perguntas não são.

---

## Os modos do `cqb run`

O CQB nunca olha o repo inteiro. O `--mode` diz **qual diff**.

| Comando | O que entra |
|---|---|
| `cqb run` | Alterado ou novo desde o `HEAD` (inclui untracked). Dia a dia. |
| `cqb run --mode staged` | Só o que está no `git add` (o próximo commit). |
| `cqb run --mode push` | Diff contra o upstream (`git push`). É o que o hook chama. |
| `cqb run --mode file-list --files a.go,b.go` | Só esses paths. Útil para debugar um arquivo. |

`--output` (padrão `.quality/last.json`) é só o caminho do relatório.

---

## Comandos no Cursor (opcional)

No chat do Cursor, uma linha que começa com `/` dispara um fluxo do
agente. O CQB traz dois. Nenhum substitui o `cqb run` no terminal.

**`/cqb-setup`** — primeira configuração guiada. Instala o CLI se faltar,
roda `cqb init`, lê o `scan.json` e **pergunta** se alguma pasta sugerida
(em geral as que já têm suíte e2e) deve entrar na allowlist. Sem o seu
“sim”, a lista permanece vazia: o gate continua só avisando (amarelo),
sem bloquear push por teste unitário. O agente **não conhece** o seu
produto e **não escolhe sozinho** a pasta que deve bloquear o push. Se a
sugestão for ruim, diga não.

**`/cqb`** — revisão de código. Junta o diff, se o diff tocar o `prefix`
sobe um `cqb run` em segundo plano, espera o `.quality/last.json` e
escreve o que corrigir. Não cole o JSON no chat. O idioma da prosa
padrão é pt-BR.

Skills do kit só são copiadas se o arquivo **ainda não existir** no seu
`.cursor/`. As rules de domínio que você já tem continuam valendo.

---

## Quando o repo não é um módulo só

Se o git mostra `services/billing/internal/foo.go` mas os testes e o
`globs.txt` falam `internal/foo.go`, diga ao CQB onde o módulo mora:

```yaml
prefix: "services/billing"
```

Sem isso, o padrão `internal/` não enxerga `services/billing/internal/...`.

Vários módulos: o path mais específico primeiro, em `prefixes`.

Confira:  
`cqb run --mode file-list --files services/billing/internal/billing/normalize.go`  
não deve dizer que o diff está fora do prefixo, se esse for o seu código.

---

## E2e (`globs.txt`) e cobertura — quando você for usar

Cada suíte é uma pasta com `globs.txt`, por exemplo
`services/billing/internal/e2e/invoices/globs.txt`:

```
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

Linha com `*` casa o diff (path do git ou já sem o `prefix`). Linha
**sem** `*` tem que existir como arquivo (`prefix/linha` ou na raiz).
Arquivo SQL sumido → catálogo **vermelho**.

O init **não** inventa suítes. Você (ou o time) cria o `globs.txt`.

Cobertura só roda com allowlist preenchida. Baseline padrão:
`.cqb/cover-baseline.json`. Se você já tem outro JSON, aponte
`cover.baseline_path`. Imports que contam como I/O (piso 80%):
`database/sql`, `net/http`, `os` — dá para estender em `io_imports`.

Tetos de complexidade são **só amarelo**. Handlers com vários
`if err != nil` costumam querer `cyclomatic` 35; o `/cqb-setup` pode
*sugerir* isso, não grava sozinho.

---

## Hook de git (opt-in)

O init **grava** `.cqb/hooks/pre-push` e **não** liga no git. Para ligar:

```bash
git config core.hooksPath .cqb/hooks
CQB=1 git push          # aí sim roda `cqb run --mode push`
git push                # sem CQB, o script não faz nada
```

Não coloque `CQB=1` no bashrc: todo push do time passaria a esperar o gate.

---

## Constituição (yaml não desfaz)

O `cqb.yaml` ajusta tetos, prefixo, allowlist, catálogo e2e. **Não** dá
para, via yaml, varrer o módulo inteiro, fazer amarelo falhar git, ou
ligar o hook sozinho. Chaves como `yellow_blocks` são ignoradas
(`ignored_keys` no relatório).

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
| Relatório / bundle | Arquivo JSON `.quality/last.json` com as cores de cada verificação. |
| Slot | Uma seção desse relatório (lint, teste, e2e, cover…). |
| Allowlist (`red_allowlist`) | Pastas/globs onde aviso de teste/cobertura **pode** virar vermelho e parar o git. Não é ignore. |
| Glob | Padrão de path (`internal/billing/**`, `*invoice*`). |
| Prefixo (`prefix`) | Pasta do módulo Go quando ela não é a raiz do git. |
| Teste rápido | “Função nova `Foo` tem `TestFoo` que chama `Foo(`?”. Não é e2e nem %. |
| Hunter | Checagem automática num `*_test.go` ou numa linha nova de produção. |
| Cover / cobertura | Percentual de código exercitado pelos testes unitários (`go test -cover`). |
| E2e | Teste de jornada (`go test -tags e2e`), em geral com Docker. |
| `globs.txt` | Lista que decide se o e2e **roda**, não se o unitário é vermelho. |
| Scan (`scan.json`) | Inventário gerado no init; não é a allowlist. |
| Hook opt-in | Script de pre-push que só roda o gate se `CQB=1`. |
| Motor / engine | Python em `.cqb/engine` que de fato monta o relatório. |
| `/cqb`, `/cqb-setup` | Comandos no **chat do Cursor**, não no terminal. |
| Consumidor | O repositório Go que instalou o CQB. |
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
