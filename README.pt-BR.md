# CQB

[English](README.md)

**Quality gate** local e ritual de **revisão de código** para módulos Go.

O CQB mede **código novo no diff do git**, não a árvore inteira. Grava um
bundle JSON (`.quality/last.json`) que um humano ou o slash do Cursor
(`/cqb`) lê. Amarelo nunca bloqueia o git. **Vermelho é uma allowlist que
você nomeia depois** (vazia na primeira instalação): caminhos **dentro**
dessa lista podem falhar o push; caminhos **fora** ficam amarelos. O
repositório consumidor continua dono das skills, rules por path e da
linguagem de domínio — este kit não as substitui.

```
cqb init          → vendor da engine, cqb.yaml, gitignore, arquivo de hook opt-in
/cqb-setup        → entrevista opcional; HALT antes de gravar a allowlist vermelha
cqb run           → gate no diff (exit 1 só no vermelho, mais um caso do hook)
/cqb              → revisão: gather → camadas → triage → apresentar
```

Ferramentas de host (instaladas pelo `cqb init` se faltarem): **golangci-lint v2.4.0**,
**gremlins v0.5.1**. O `cqb run` do dia a dia usa a cópia **vendored** em
`.cqb/engine`, nunca `@latest`.

---

## Instalação

Go 1.22+, `python3`, `git` e o toolchain `go`/`gofmt`. E2E que implica Docker
também precisa de `docker` no `PATH`.

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /caminho/da/raiz/git     # não necessariamente o módulo Go aninhado; ver prefix
cqb init
```

O `cqb init` **não** altera `core.hooksPath`. Ele:

- copia a engine para `.cqb/engine/` e os templates para `.cqb/templates/`
- grava `cqb.yaml` se ainda não existir (yaml existente não é sobrescrito)
- grava `.cqb/scan.json` (path do módulo, densidade de `*_test.go`, suítes e2e)
- faz upsert de um bloco gerenciado no `.gitignore` (`# cqb begin` … `# cqb end`):
  `.quality/`, `.cqb/scan.json`, `.cqb/work/`, `*.coverprofile`,
  `.cqb/**/__pycache__/` — **não** ignora `.cqb/engine`, hooks, templates nem `cqb.yaml`
- grava `.cqb/hooks/pre-push` (opt-in)
- dá `go install` no linter/mutador pinados se estiverem ausentes

Num yaml **novo**, se o scan achar um único catálogo e2e (por exemplo
`services/billing/internal/e2e`), `e2e.catalog_root` aponta para esse path.
**`prefix` e `red_allowlist` continuam vazios** — você (ou o `/cqb-setup`
depois do seu sim) preenche. Ver [Configuração manual](#configuração-manual).

### Entrevista opcional na primeira vez

No Cursor, `/cqb-setup` instala o CLI se faltar, roda `cqb init` e **propõe
candidatos** de allowlist a partir de `.cqb/scan.json` (diretórios de suíte
e2e, não “todo pacote que tem teste”). Dá **HALT** e pergunta sim/não por
candidato. Sem confirmação → `red_allowlist` fica `[]`. O agente **não**
sabe com segurança qual pasta é o recorte duro do produto; só chuta a
partir do scan. Pular o setup ainda deixa um gate funcionando e
não-bloqueante.

### Rodar

```bash
cqb run                                 # working tree (inclui untracked)
cqb run --mode staged
cqb run --mode file-list --files internal/billing/normalize.go
cqb run --mode push                     # o que o hook chama
cqb run --output .quality/last.json     # padrão
```

### Upgrade

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0   # ou uma tag mais nova
cqb upgrade     # atualiza .cqb/ a partir *deste* binário; bump de kit_version
```

Não aponte o dia a dia para `@latest`. Pin uma tag; faça upgrade de propósito.

---

## Allowlist vermelha (não é lista de ignore)

`red_allowlist` é o conjunto de globs **onde** hunters, teste rápido e cover
**podem ficar vermelhos** (exit 1). **Não** é lista do que o gate ignora.

| Arquivo no diff | `red_allowlist` | Esses checks | `cqb run` por causa deles |
|---|---|---|---|
| qualquer | `[]` (padrão após o init) | amarelo ou cover `skip` | **0** (não falha o git) |
| casa um glob, ex. `internal/billing/**` | não vazia | **vermelho** se dispararem | **1** |
| não casa nenhum glob | não vazia | amarelo | **0** |

```yaml
# Primeira instalação — hunters/cover não falham o git:
red_allowlist: []

# Humano nomeou um recorte — só esses paths podem falhar o push por
# falta de TestFoo+Foo(, t.Fatal("x") cego, invocação no cover, etc.:
red_allowlist:
  - "internal/billing/**"
  - "internal/application/services/*invoice*"
```

O que **não** passa pela allowlist (ainda pode ser vermelho com lista vazia):

- **lint** — `gofmt` / `go vet` / `go build` no diff
- **e2e** — suíte implicada falhou, ou o catálogo `globs.txt` está quebrado

Lista vazia ≠ “ignorar o repo”. Lista vazia = “ainda não tratar path nenhum
como recorte duro.” Inferir `internal/` sozinho faria o oposto: o primeiro
`cqb run` num módulo grande ficaria vermelho em todo lado. Por isso o setup
dá **HALT**.

---

## Configuração manual

O `cqb init` não faz perguntas. Depois dele, **você** edita o `cqb.yaml`
(ou confirma candidatos no `/cqb-setup`). Nada abaixo é preenchido a partir
do seu domínio.

Trabalhe na **raiz do git** (onde rodou o `cqb init`). Paths no bundle são
relativos ao git. Globs podem ser escritos **relativos ao `prefix`**.

### 1. `prefix` / `prefixes` — obrigatório em monorepo

Se o módulo Go não é a raiz do git — o git mostra
`services/billing/internal/foo.go` mas testes e `globs.txt` dizem
`internal/foo.go` — defina o diretório do módulo:

```yaml
prefix: "services/billing"
```

Vários módulos: o mais específico primeiro.

```yaml
prefixes:
  - "services/billing/cmd/worker"
  - "services/billing"
```

Deixe `prefix: ""` só quando a raiz do git **é** o módulo (`internal/` no
disco é `internal/` no `git diff`).

Sem isso, `testable: [internal/]` não vê `services/billing/internal/...`, e
linhas do `globs.txt` como `internal/db/queries/faturas_queries.sql` parecem
“faltando” na raiz do repo.

Confira: `cqb run --mode file-list --files services/billing/internal/billing/normalize.go`
**não** deve imprimir `diff outside configured prefix` se esse arquivo é o
trabalho que importa.

### 2. `red_allowlist` — vazia até você querer dizer isso

Não cole `internal/` “por garantia”. Isso faz **todo** helper novo sob
`internal/` poder falhar o git.

Como escolher um glob:

1. Abra `.cqb/scan.json` → `e2e_suites` (diretórios que já têm `globs.txt`).
   Isso é **candidato**, não decisão.
2. Abra o `globs.txt` da suíte. As linhas *implicam e2e*; não viram vermelho
   automaticamente.
3. Escolha o conjunto **menor** de paths pelos quais você topa bloquear um
   push (o pacote que está endurecendo agora). Exemplo:
   `internal/application/services/*invoice*`.
4. Coloque essas strings em `red_allowlist`. Com `prefix` definido, pode
   omitir `services/billing/`.
5. Rode `cqb run` num diff sabidamente ruim (função nova, sem `Foo(`).
   Confirme **vermelho** só naquele path e **amarelo** num irmão fora do glob.

O `/cqb-setup` sugere candidatos a partir do scan (em geral dirs de e2e /
paths no formato `internal/billing/`). **Tem de perguntar sim/não.** **Não**
pode gravar a lista porque “esse pacote tem testes”. Se a sugestão for
errada, responda não; o yaml permanece `[]`.

Para **desligar** um recorte depois: `red_allowlist: []` de novo. Cover vira
`skip`; hunters voltam a amarelo.

### 3. `testable.include` / `exclude` — quem leva hunter de teste rápido

Padrão: include `internal/`, exclude `internal/interface/` (adaptadores HTTP
muitas vezes não têm `TestHandleFoo` que chame `HandleFoo(`).

Esses globs decidem **se** o hunter de teste rápido roda (amarelo ou
vermelho). **Não** falham o git sozinhos. Vermelho ainda exige a allowlist.

Ajuste se o domínio não mora em `internal/`, ou se quiser incluir handlers.
A forma de diretório `internal/` é aquele diretório e tudo abaixo (depois de
tirar o `prefix`).

### 4. `e2e.catalog_root` e `globs.txt`

O init já pode ter posto `catalog_root` em `services/billing/internal/e2e`
quando essa árvore é única. Se as suítes moram noutro lugar, defina você
(path relativo ao git).

Cada suíte é um diretório com `globs.txt`:

```
services/billing/internal/e2e/invoices/globs.txt
```

```
# comentários e linhas em branco ok
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

- Linhas com `*` / `?` são fnmatch contra o diff (path git **ou** sem prefixo).
- Linhas **sem** curinga precisam existir como arquivo: primeiro
  `{raiz git}/{prefix}/{linha}`, depois `{raiz git}/{linha}`. SQL ausente
  marca o **catálogo vermelho** (quebrado), não “suíte skip”.
- Se o diff casar alguma linha, o CQB roda
  `go test -tags e2e -count=1 -timeout 8m ./<dir-da-suíte>` na **raiz do git**.
- Suíte implicada + sem `docker` no `PATH` → e2e `unavailable`. Aí
  `CQB=1 git push` sai 1.

Você cria o `globs.txt`; o init não inventa suítes.

### 5. `cover.baseline_path` e `io_floor`

Cover **não roda** enquanto `red_allowlist` estiver vazia (`skip`).

Quando a lista tem itens e o diff toca `.go` de produção que casam, o CQB
grava `.cqb/work/cover.out` (gitignored) e compara:

- I/O (o arquivo importa `database/sql`, `net/http` ou `os` por omissão):
  percentual abaixo de `io_floor` (80) → vermelho
- Helper puro: sem `Foo(` nos testes → vermelho
- Arquivo no JSON de baseline cujo percentual **cai** → vermelho

Arquivo padrão: `.cqb/cover-baseline.json`. Se você já mantém baseline
noutro path, aponte `cover.baseline_path` (relativo ao git). O hook
**nunca** reescreve esse arquivo. Subir o percentual gravado é um comando
separado e intencional **no seu** repo (`cqb run` não reescreve baseline).

Estenda `io_imports` se o I/O for `pgx` / pacote da casa, não `database/sql`.

### 6. Tetos de `complexity`

Padrão = defaults da **ferramenta** golangci-lint: 30 / 30 / 5, delta 5.
São **só amarelo**, nunca vermelho.

Handlers HTTP com cadeia de `if err != nil { return }` passam de 30
ciclomáticos e continuam legíveis. O `/cqb-setup` pode **sugerir** subir
`cyclomatic` (ex.: 35). Não baixa para “10” de blog, e não muda o yaml sem
você concordar.

Você edita:

```yaml
complexity:
  cognitive: 30
  cyclomatic: 35
  nested_if: 5
  delta: 5
```

### 7. Opcional: hunters extras, idioma, hook

```yaml
extra_hunters: ["placebo_validator"]   # desligado se não listar
operator_language: "pt-BR"             # prosa do /cqb; ids dos hunters em inglês
```

Hook (init/setup nunca ligam, salvo você pedir):

```bash
git config core.hooksPath .cqb/hooks
CQB=1 git push
```

Não exporte `CQB=1` no bashrc.

### 8. O que você **não** configura

Estas chaves, se existirem, são ignoradas: `yellow_blocks`, `whole_module`,
`always_on_hook`, `legacy_absolute_red`. Aparecem no bundle como
`ignored_keys`. Yaml não consegue fazer amarelo falhar git.

---

## Constituição (não é YAML)

| Regra | Significado |
|---|---|
| Só o diff | Nunca varrer o módulo inteiro “por garantia”. |
| Complexidade nova vs legado | Função **nova**: cognitivo / ciclomático / nested-if absolutos. **Legado**: só delta, e só amarelo. |
| Amarelo nunca falha git | Teto estourado, hunter fora da allowlist, mutante vivo → exit **0**. |
| Allowlist vermelha vazia | Até um humano nomear o escopo (HALT do `/cqb-setup`). Cover e hunters de conteúdo não ficam vermelhos. |
| Agente ≠ exit do git | O `/cqb` lê o bundle; não decide o `git push`. |
| Hook é opt-in | `git config core.hooksPath .cqb/hooks` e depois `CQB=1 git push`. O init nunca anexa. |

---

## Cores e código de saída

Cada **slot** é um de: `green`, `yellow`, `red`, `skip`, `unavailable`.

| Cor | Git | Significado |
|---|---|---|
| green | 0 | Rodou e passou. |
| yellow | 0 | Sinal para revisão, não falha de push. |
| red | **1** | Allowlist (ou higiene / e2e falhou). |
| skip | 0 | Fora de escopo. **Não é pass.** |
| unavailable | 0 no dia a dia | Ferramenta ausente (Docker, gremlins). **Não é pass.** Push com flag é mais rígido. |

`cqb run` sai **1** quando `has_red` é true.

**Também sai 1:** `--mode push` quando e2e está `unavailable` **e** há suíte
implicada (em geral Docker faltando). O `cqb run` do dia a dia mantém
`unavailable` e sai 0.

---

## Slots

O bundle é `.quality/last.json` (`schema_version: 1`).

### `lint`

`gofmt -l`, `go vet`, `go build` nos pacotes dos `.go` do recorte. Qualquer
falha é **vermelha** (não passa pela allowlist). golangci-lint é instalado
para o humano/`/cqb`; não é slot vermelho no v0.1.

### `complexity`

- função nova: cognitivo **30**, ciclomático **30**, nested-if **5** → amarelo se passar
- legado: delta cognitivo **5** → amarelo se passar; nunca vermelho

### `test` / hunter de teste rápido

Símbolos **novos** em `testable.include` (menos `exclude`): `TestFoo` **e**
`Foo(` nos testes do pacote. Handlers HTTP (`http.ResponseWriter`) estão
isentos.

- fora da allowlist → **amarelo**
- na allowlist → **vermelho**

### `hunters` (conteúdo)

Em `*_test.go` do diff (vermelho só se o arquivo casar a allowlist):

| Hunter | O que marca |
|---|---|
| `blind_assert` | `t.Fatal("short")` / `t.Error("…")` sem verbo `%` |
| `compound_assert` | dois asserts na mesma linha, ou `&&` dentro do assert |
| `non_deterministic` | `time.Now` ou `math/rand` no teste |
| `order_dependent` | estado de pacote mutado em teste sem `t.Cleanup` |
| `duplicate_observable` | o mesmo literal de fatal/error em duas linhas |
| `missing_boundary` | comparação **nova na produção** com literal numérico / `len` que não aparece nos testes do pacote. Índice, status HTTP, `time.Duration` isentos. Nome de teste sem `Empty`/`Zero` **não** basta. |
| `placebo_validator` | opt-in: `validator.Struct` sem assertar o erro |

Findings únicos em `(hunter, arquivo, linha, mensagem)`.

### `e2e`

Ver [configuração manual §4](#4-e2ecatalog_root-e-globstxt). Passou → green.
Teste falhou → red. Nenhum glob → skip. Docker ausente com suíte implicada →
unavailable.

### `cover`

Ver [configuração manual §5](#5-coverbaseline_path-e-io_floor). Allowlist
vazia → skip. O hook nunca reescreve a baseline.

### `mutation`

Gremlins quando um símbolo **novo** tem `TestFoo` e `Foo(`. Binário ausente →
unavailable. Sobreviventes são **amarelos**. Sem teste que invoca → skip.

---

## `cqb.yaml` (esqueleto)

```yaml
kit_version: "0.1.0"
prefix: ""                    # no monorepo, ex. services/billing
operator_language: "pt-BR"
complexity:
  cognitive: 30
  cyclomatic: 30
  nested_if: 5
  delta: 5
red_allowlist: []             # vazia = hunters/cover não podem ser vermelhos
testable:
  include: ["internal/"]
  exclude: ["internal/interface/"]
io_imports: ["database/sql", "net/http", "os"]
extra_hunters: []
e2e:
  catalog_root: "internal/e2e"
cover:
  io_floor: 80
  baseline_path: ".cqb/cover-baseline.json"
```

**Ajustável:** tudo nesse arquivo, menos a constituição.
**Não ajustável:** amarelo-nunca-falha-git, allowlist-vazia-até-humano, hook opt-in.

---

## Revisão `/cqb`

Idioma do operador padrão: **pt-BR**. Não cole o JSON cru no chat.

1. **Gather** — diff unificado. Se tocar `prefix`, sobe `cqb run` em
   background em `.quality/last.json`.
2. **Camadas** (paralelo) — ramos mortos / erros ignorados; bordas; espera
   bundle com `has_red`; overlay das rules do consumidor (ganham em estilo,
   não podem pintar slot vermelho de verde).
3. **Triage** — `patch` / `defer` / `decision_needed` / `rejected`.
4. **Apresentar** — prosa das cores primeiro, depois a lista da revisão.

Diff só de documento usa lentes editoriais no mesmo slash.

---

## Arquitetura

```
cqb (Go) ──embed──► engine/*.py + templates/
                │
                ├─ cqb init     copia para .cqb/ do consumidor
                ├─ cqb run      python3 .cqb/engine/orchestrator.py
                └─ cqb upgrade  troca a engine vendored a partir deste binário
```

| Peça | Onde | Papel |
|---|---|---|
| CLI | `cmd/cqb`, `internal/cli` | init / run / upgrade / setup-copy / render-reader |
| Engine | `engine/orchestrator.py`, `engine/cqb/*.py` | diff, slots, hunters |
| Templates | `templates/` | yaml padrão, hook, skills do Cursor |
| Host | `PATH` | gofmt, go, python3, docker (e2e), golangci-lint, gremlins |

`cqb setup-copy` só grava skill do kit se o destino **ainda não existir**.

---

## Este repositório

Público de propósito. Sem fonte de empregador, path de produto, ticket ou
credencial. Testes usam fixtures inventados `internal/billing` e
`services/billing` (`github.com/example/billingapp`). Ver
[CONTRIBUTING.md](CONTRIBUTING.md).

```bash
go test ./...
python3 -m unittest discover -s engine/tests
```
