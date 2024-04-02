getfile:
	echo "getfile"

fetchstations:
	echo "fetchstations"

createdb:
	echo "createdb"
	pipenv run python createdb.py

creategastypes:
	echo "creategastypes"
	pipenv run python creategastypes.py

deploy:
	pipenv run streamlit run home.py
