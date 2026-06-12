# In-process data acquisition (ADR 0004): extract from the published image,
# never build Concord from source. The image tag is the in-process *data*
# version; the matching *code* pin lives in pyproject.toml. Bump together.
CONCORD_IMAGE ?= ghcr.io/kbennett2000/concord:v1.2.0

.PHONY: get-db

get-db:  ## Extract bible.db + semantic artifacts into data/concord/ (needs Docker once)
	-docker rm -f concord-mcp-extract 2>/dev/null
	docker create --name concord-mcp-extract $(CONCORD_IMAGE)
	mkdir -p data/concord/semantic
	docker cp concord-mcp-extract:/app/bible.db data/concord/bible.db
	docker cp concord-mcp-extract:/app/model data/concord/semantic/model
	docker cp concord-mcp-extract:/app/embeddings.db data/concord/semantic/embeddings.db
	docker rm concord-mcp-extract
	@echo "Done: data/concord/ holds bible.db, semantic/model/, semantic/embeddings.db"
