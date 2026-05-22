# services/

Non user facing runtime services in the Verolas platform. These are deployed independently and communicate over the API gateway, NATS, or gRPC.

This directory is intentionally empty today. Services are introduced as their workstreams come online. Expected residents include:

- `llm-gateway` multi provider LLM routing
- `embeddings` embeddings service
- `rag-ingest` knowledge base and RAG ingestion
- `geometry-kernel` geometry and mesh operations
- `cad-parse` CAD and BIM parsing pipeline
- `dwg-output` standard conformant drawing output

Each service lives in its own workspace once introduced.
