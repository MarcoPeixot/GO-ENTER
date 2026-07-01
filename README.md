# MVP de comparação de documentos jurídicos

Detecta documentos **parecidos dentro de um mesmo `case_id`** e os classifica em:

| Classificação | Significado |
|---|---|
| `EXACT_FILE_DUPLICATE` | Arquivo byte-a-byte idêntico (mesmo SHA-256). |
| `EXACT_TEXT_DUPLICATE` | Texto normalizado idêntico, arquivo possivelmente diferente. |
| `NEAR_DUPLICATE` | Provável cópia ou versão modificada (alta sobreposição literal + estrutural). |
| `SEMANTICALLY_RELATED` | Assunto parecido, sem forte sobreposição literal. |
| `DIFFERENT` | Nenhum candidato relevante encontrado. |

## Arquitetura

```
POST /documents ──► backend-go ──► salva arquivo em /data/uploads (volume)
                          │        cria documento (status=PROCESSING)
                          └──────► publica job no RabbitMQ
                                         │
                                         ▼
                              worker-python (consumer)
                  extrai → normaliza → mascara → hashes → MinHash
                  → chunks → embeddings → busca candidatos (mesmo case_id)
                  → classifica (regras) → [LLM opcional] → grava matches
                                         │
                                         ▼
                          postgres + pgvector (documents, document_chunks, document_matches)
```

Serviços do `docker-compose`: `postgres` (pgvector), `rabbitmq`, `backend`, `worker`.

```
backend/   API Go (Gin) — upload, consulta de status e matches
worker/    pipeline Python — extração, embeddings, similaridade, LLM
db/migrations/  schema SQL versionado
examples/  documentos de exemplo para a demonstração
```

## Como subir o projeto

Pré-requisitos: Docker + Docker Compose.

```bash
cp .env.example .env        # ajuste se quiser (LLM, thresholds, credenciais)
docker compose up --build
```

> A **primeira** build do worker baixa o modelo de embeddings
> (`paraphrase-multilingual-MiniLM-L12-v2`, ~470 MB) para dentro da imagem,
> então pode demorar. Builds seguintes usam cache.

Serviços expostos:
- API: <http://localhost:8080>
- RabbitMQ management: <http://localhost:15672> (guest/guest)
- Postgres: `localhost:5432`

## Configuração (`.env`)

Principais variáveis (veja `.env.example` para a lista completa):

| Variável | Default | Descrição |
|---|---|---|
| `POSTGRES_USER/PASSWORD/DB` | postgres/postgres/juridicflow | credenciais do banco |
| `RABBITMQ_USER/PASSWORD` | guest/guest | credenciais da fila |
| `MAX_UPLOAD_BYTES` | 26214400 (25 MiB) | tamanho máximo de upload |
| `EMBEDDING_MODEL` | paraphrase-multilingual-MiniLM-L12-v2 | modelo de embeddings (dim 384) |
| `MINHASH_NEAR_DUP` | 0.80 | limiar de Jaccard (MinHash) para NEAR_DUPLICATE |
| `CHUNK_SIM_THRESHOLD` | 0.80 | similaridade de chunk considerada "forte" |
| `CHUNK_SIM_FRACTION` | 0.60 | fração mínima de chunks fortes para NEAR_DUPLICATE |
| `SEMANTIC_RELATED` | 0.78 | similaridade semântica média para SEMANTICALLY_RELATED |
| `MINHASH_SEMANTIC_MAX` | 0.60 | MinHash máximo para considerar SEMANTICALLY_RELATED |
| `LLM_API_KEY` | *(vazio)* | se vazio, roda **somente com regras** (sem LLM) |
| `LLM_BASE_URL` / `LLM_MODEL` | OpenAI / gpt-4o-mini | endpoint compatível com OpenAI |

## Migrations

As migrations em `db/migrations/` são aplicadas **automaticamente** na primeira
inicialização do Postgres (montadas em `/docker-entrypoint-initdb.d`). Habilitam
a extensão `vector` e criam `documents`, `document_chunks`, `document_matches`.

Para reaplicar do zero (apaga dados):

```bash
docker compose down -v && docker compose up --build
```

Para rodar manualmente em um banco já existente:

```bash
psql "$DATABASE_URL" -f db/migrations/0001_init.sql
```

## Demonstração (fluxo completo)

```bash
# 1. Subir tudo
docker compose up --build -d

# 2. Enviar documento A
curl -s -X POST http://localhost:8080/documents \
  -F "case_id=caso-001" \
  -F "file=@examples/contrato_a.txt"
# => {"document_id":"<UUID_A>","status":"PROCESSING"}

# 3. Enviar documento B (parecido: mesma estrutura, valores/datas/nomes trocados)
curl -s -X POST http://localhost:8080/documents \
  -F "case_id=caso-001" \
  -F "file=@examples/contrato_b.txt"
# => {"document_id":"<UUID_B>","status":"PROCESSING"}

# 4. Consultar status (aguarde alguns segundos para o worker processar)
curl -s http://localhost:8080/documents/<UUID_B>

# 5. Consultar matches do documento B
curl -s http://localhost:8080/documents/<UUID_B>/matches
```

Resultado esperado: B classificado como `NEAR_DUPLICATE` em relação a A
(o mascaramento de nomes, CPF/CNPJ, valores, datas e número de processo deixa os
textos quase idênticos, elevando o MinHash). Envie `examples/peticao_diferente.txt`
no mesmo caso para ver um `DIFFERENT` / `SEMANTICALLY_RELATED`.

> Importante: a comparação só ocorre **dentro do mesmo `case_id`**. Documentos de
> casos diferentes nunca são comparados entre si.

## Endpoints

A documentação interativa fica disponível no backend:

```text
http://localhost:8080/swagger
```

A especificação OpenAPI fica em:

```text
http://localhost:8080/openapi.yaml
```

### `POST /documents`
`multipart/form-data` com `file` e `case_id`. Valida extensão (`.txt`, `.pdf`,
`.docx`) e tamanho. Responde **202 Accepted**:

```json
{ "document_id": "uuid", "status": "PROCESSING" }
```

### `GET /documents/{id}`
```json
{
  "document_id": "uuid", "case_id": "caso-001",
  "filename": "contrato_b.txt", "storage_path": "/data/uploads/...",
  "status": "PROCESSED", "file_hash": "…", "text_hash": "…",
  "created_at": "…", "updated_at": "…"
}
```

### `GET /documents/{id}/matches`
Retorna os resultados de comparação contra candidatos do mesmo `case_id`.
Apesar do nome do campo, `matches` também inclui `DIFFERENT` quando um
documento foi comparado e considerado diferente.

```json
{
  "document_id": "uuid",
  "status": "PROCESSED",
  "matches": [
    {
      "matched_document_id": "uuid",
      "relation_type": "NEAR_DUPLICATE",
      "near_duplicate_score": 0.91,
      "semantic_score": 0.84,
      "reason": "Alta sobreposição textual e estrutura semelhante.",
      "evidence": [
        { "source_chunk": "…", "matched_chunk": "…", "similarity": 0.93 }
      ]
    },
    {
      "matched_document_id": "uuid",
      "relation_type": "DIFFERENT",
      "near_duplicate_score": 0,
      "semantic_score": 0.51,
      "reason": "Sem candidato relevante (MinHash=0.00, semântica=0.51, trechos fortes=0%).",
      "evidence": [
        { "source_chunk": "…", "matched_chunk": "…", "similarity": 0.51 }
      ]
    }
  ]
}
```

## Como funciona a classificação

A decisão primária é **determinística** (sem multiplicar scores), nesta ordem:

1. **`file_hash` igual** (mesmo caso) → `EXACT_FILE_DUPLICATE`.
2. **`text_hash` igual** (texto normalizado) → `EXACT_TEXT_DUPLICATE`.
3. **MinHash ≥ `MINHASH_NEAR_DUP`** *e* **≥ `CHUNK_SIM_FRACTION` dos chunks com
   similaridade ≥ `CHUNK_SIM_THRESHOLD`** → `NEAR_DUPLICATE`.
4. **Similaridade semântica média ≥ `SEMANTIC_RELATED`** *e* **MinHash <
   `MINHASH_SEMANTIC_MAX`** → `SEMANTICALLY_RELATED`.
5. Caso contrário → `DIFFERENT` (gravado para deixar explícito que houve comparação).

Etapas do worker: leitura → extração (TXT/PDF/DOCX) → normalização → mascaramento
(datas, valores, nº de processo, CPF/CNPJ) → hashes → MinHash (shingles de 5
palavras, `datasketch`) → chunks (500–800 palavras, com sobreposição) →
embeddings (`sentence-transformers`, dim 384) → busca de candidatos do mesmo
`case_id` (hash → MinHash → vetorial no pgvector, top 5) → classificação.

**LLM (opcional):** chamado apenas para candidatos `NEAR_DUPLICATE` /
`SEMANTICALLY_RELATED`, recebendo só os chunks relevantes + scores, e devolvendo
um JSON com `reason` e `changed_elements`. Nunca decide a classificação. Sem
`LLM_API_KEY`, o sistema funciona 100% com as regras.

## Estados do documento

`PROCESSING` → `PROCESSED` | `FAILED` | `NEEDS_OCR`

- `NEEDS_OCR`: PDF sem camada de texto (provável digitalização). OCR fora de escopo.
- `FAILED`: falha definitiva (tipo não suportado, sem texto, ou erro após retries).

## Testes

Testes unitários do worker (normalização, mascaramento, chunking, regras de
classificação) — não exigem dependências pesadas:

```bash
cd worker
python -m venv .venv && . .venv/bin/activate
pip install pytest
python -m pytest -q
```

Build/lint do backend:

```bash
cd backend && go build ./... && go vet ./...
```

## Limitações conhecidas do MVP

- **Não há OCR** — PDFs escaneados são marcados `NEEDS_OCR`.
- **Não há autenticação** — qualquer cliente pode enviar/consultar.
- **MinHash é calculado de forma simples** (shingles de palavras, 128 permutações).
- **LLM é opcional** e nunca decide a classificação.
- **Thresholds ainda precisam de calibração** com dados reais.
- **Armazenamento é local** (volume Docker `uploads`); a interface `Storage`
  no backend permite trocar por S3 futuramente.
- Busca vetorial usa `ivfflat` com parâmetros padrão, adequada a volumes pequenos.
- Retries do worker são simples (backoff linear, sem dead-letter queue).
```
