.PHONY: help generate-requirements dump-stations create-db create-gastypes deploy test test-offline

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

dump-stations:  ## Fetch stations from api and dump them in db
	echo "fetchstations"
	uv run python utils.py --action dump_stations

create-gastypes:  ## Create gas types in db
	echo "creategastypes"
	uv run python utils.py --action creategastypes

create-db:  ## Create the sqlite db locally
	echo "create-db"
	uv run python session.py

restore-db:  ## Restore the sqlite db locally from S3 saved values
	echo "restore-db"
	uv run python session.py --action restore

deploy:  ## Deploy the app locally
	uv run streamlit run home.py

test:  ## Launch tests
	uv run pytest -v

test-offline:  ## Launch tests offline fashion
	uv run pytest -v -m 'not online'

# Example: make version=0.0.1 edit-version
version?=0.0.1
edit-version:  ## Modify VERSION in src/utils.py and version pyproject.toml.
	sed -i '' "s/^version = \".*\"/version = \"$(version)\"/" pyproject.toml
	sed -i '' "s/^VERSION = \".*\"/VERSION = \"$(version)\"/" utils.py
	sed -i '' "s/^__version__ = \".*\"/__version__ = \"$(version)\"/" src/carburoam/__init__.py
	git add pyproject.toml src/carburoam/__init__.py utils.py
	uvx towncrier build
	git add CHANGELOG.md
	git feat "Release $(version)" -S
	git tag -a v$(version) -m "Release $(version)"
	git push origin main
	git push origin v$(version)
