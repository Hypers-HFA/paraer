#!/usr/bin/python
import os
import sys
import shutil
from setuptools import setup
from paraer import __version__ as VERSION

if sys.argv[-1] == 'publish':
    if os.system("wheel version"):
        print("wheel not installed.\nUse `pip install wheel`.\nExiting.")
        sys.exit()
    if os.system("pip freeze | grep twine"):
        print("twine not installed.\nUse `pip install twine`.\nExiting.")
        sys.exit()
    os.system("python setup.py sdist bdist_wheel")
    os.system("twine upload -r pypi dist/*")
    print("You probably want to also tag the version now:")
    print("  git tag -a %s -m 'version %s'" % (VERSION, VERSION))
    print("  git push --tags")
    shutil.rmtree('dist')
    shutil.rmtree('build')
    shutil.rmtree('paraer.egg-info')
    sys.exit()

README = """
paraer checker and api doc generator
Installation
From pip:
pip install paraer
Project @ https://github.com/drinksober/paraer
"""

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='paraer',
    version=VERSION,
    install_requires=[
        'coreapi>=2.3.0',
        'openapi-codec>=1.3.1',
        'djangorestframework>=3.5.4',
        'simplejson',
        'django-rest-swagger',
        'six'
    ],
    packages=['paraer'],
    include_package_data=True,
    license='MIT',
    description='a para checker and doc generator',
    long_description=README,
    test_suite='tests',
    author='drinksober',
    author_email='drinksober@foxmail.com',
    url='https://github.com/Hypers-HFA/paraer',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    zip_safe=False
)
