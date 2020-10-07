import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django-signals-cloudevents",
    version="0.1.0",
    author="Airspot S.r.l.",
    author_email="info@airspot.tech",
    description="Package to convert Django mmodel to source",
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/airspot-dev/krules-py-cli.git",
    packages=setuptools.find_packages(),
    package_data={},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Framework :: Django",
    ],
    install_requires=[
    ],
    tests_require=[
        'django-fake-model==0.1.4',
    ],
    python_requires='>=3.6',
    keywords='cloudevents knative eventing krules'
)