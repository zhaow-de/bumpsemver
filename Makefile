test:
	docker build --tag test-bumpsemver .
	docker run --rm --name test-bumpsemver test-bumpsemver

clean:
	rm -rf dist build *.egg-info

dist:	clean
	python setup.py sdist bdist_wheel

upload:
	twine upload dist/*

.PHONY: dist upload test
