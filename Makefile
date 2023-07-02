PYTHON = python
PYTEST = $(PYTHON) -m pytest
FLAKE8 = $(PYTHON) -m flake8

test:
	$(PYTEST) ./tests

style:
	$(FLAKE8) --count --select=E9,F63,F7,F82 --show-source --statistics ./tests ./src
	$(FLAKE8) --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics ./src

apidoc:
	sphinx-apidoc --separate --output-dir ./doc ./src

livehtml:
	sphinx-autobuild -b html ./doc ./doc/_build/html
