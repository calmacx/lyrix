import setuptools
import os
import sys

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()
    
setuptools.setup(
    name="lyrix", 
    author="Calum Macdonald",
    version="0.0.1",
    author_email="calmacx@gmail.com",
    description="Python CLI for searching and analysing lyrics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/calmacx/lyrix",
    entry_points = {
        'console_scripts':[
            'lyrix=lyrix.cli.cli:lyrix'
        ],
    },
    packages=setuptools.find_packages(),
    install_requires=required,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
