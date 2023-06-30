#!/usr/bin/env python
from setuptools import setup

setup(
    name="target-web_endpoint",
    version="0.1.0",
    description="Singer.io target for sending data to a web endpoint via GET or POST",
    author="Stitch",
    url="http://singer.io",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["target_web_endpoint"],
    install_requires=[
        "singer-python>=5.0.12",
    ],
    entry_points="""
    [console_scripts]
    target-web_endpoint=target_web_endpoint:main
    """,
    packages=["target_web_endpoint"],
    package_data = {},
    include_package_data=True,
)
