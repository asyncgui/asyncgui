test:
	python -m pytest ./tests

style:
	ruff check ./tests ./src ./examples

html:
	sphinx-build -b html ./sphinx ./docs
