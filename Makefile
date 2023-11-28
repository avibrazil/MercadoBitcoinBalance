pkg:
	-rm dist/*
	python -m build

pypi-test:
	python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

pypi:
	python -m twine upload --verbose dist/*

changelog:
	f1=`mktemp`; \
	f2=`mktemp`; \
	git tag --sort=-committerdate | tee "$$f1" | sed -e 1d > "$$f2"; \
	paste "$$f1" "$$f2" | sed -e 's|	|...|g' | while read range; do echo; echo "## $$range"; git log '--pretty=format:* %s' "$$range"; done; \
	rm "$$f1" "$$f2"

clean:
	-rm -rf *.egg-info dist .ipynb_checkpoints src/*.egg-info src/.ipynb_checkpoints build *dist-info *pyproject-* .pyproject* .package_note*


