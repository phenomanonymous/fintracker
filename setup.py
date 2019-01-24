import os
from setuptools import setup

try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()

readme = os.path.join(os.path.dirname(__file__), 'README.md')
setup(
    name='fintracker',
    description='automated headless mint screen-scraper, storing data in google sheets',
    long_description=read_md(readme) if os.path.exists(readme) else '',
    version='1.0',
    packages=['fintracker'],
    license='The MIT License',
    author='Frank McCormick',
    author_email='frankie.mccormick@gmail.com',
    url='https://github.com/phenomanonymous/fintracker',
    install_requires=['httplib2', 'google-api-python-client', 'oauth2client', 'selenium', 'selenium-requests'],
    entry_points=dict(
        console_scripts=[
            'mintapi = fintracker.fintracker:main',
        ],
    ),
)
