import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django-signals-cloudevents",
    version="0.1.2",
    author="Airspot S.r.l.",
    author_email="info@airspot.tech",
    description="App to produce Cloudevents from Django model signals",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/airspot-dev/django-signals-cloudevents",
    packages=["django_signals_cloudevents"],
    package_data={},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Framework :: Django",
    ],
    install_requires=[
        'requests==2.24.0',
        'cloudevents==0.3.0'
    ],
    tests_require=[
        'django-fake-model==0.1.4',
    ],
    python_requires='>=3.6',
    keywords='cloudevents knative eventing krules'
)
