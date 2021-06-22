import os
from setuptools import setup

DESCRIPTION = 'Bump semver for git repos with a single command.'

# Import the README and use it as the long-description.
# This requires 'README.md' to be present in MANIFEST.in.
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

setup(
    name='bumpsemver',
    version='1.0.2',
    url='https://github.com/zhaow-de/bumpsemver',
    author='Zhao Wang',
    author_email='zhaow.km@gmail.com',
    packages=['bumpsemver'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    entry_points={
        'console_scripts': [
            'bumpsemver = bumpsemver.cli:main'
        ]
    },
    python_requires='>=3.8',
    install_requires=[
        'jsonpath-ng',
        'ruamel.yaml',
        'yamlpath',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
)
