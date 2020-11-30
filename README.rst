=====
Django signals cloudevents
=====

This apps allow you to produce `Clouevents <https://cloudevents.io/>`_ starting from your models signals sending them to a configurable url (sink).

This app is mainly intended to transform a Django instance into a Knative source, through a `SinkBinding <https://knative.dev/docs/eventing/sources/sinkbinding/>`_ or a `ContainerSource <https://knative.dev/docs/eventing/sources/containersource/>`_.

For more information visit the `Knative eventing documentation <https://knative.dev/docs/eventing/>`_

Quick start
-----------

1. Add "django_signals_cloudevents" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'django_signals_cloudevents',
    ]

2. Register your models like this::

    from django_signals_cloudevents import send_cloudevent

    post_save.connect(send_cloudevent, sender=YourModel)

3. [Optional] Override customevents handling:

    As said previously, by default this app is configured to be used with a SinkBinding and get sink url from the environment variable K_SINK, that indicates to which url events will be dispatched, and the source name from K_SOURCE.
    It is possible to override the chosen env variable in your project settings, here is the default configuration::

    CLOUDEVENTS_ENV = {
        "SINK_VAR": "K_SINK",
        "SOURCE_VAR": "K_SOURCE"
    }

    However could be necessary to deploy Django application outside the cluster and send events to it through an external message broker, like Google Pub/Sub.
    It is possible to define a different handler for cloudevents dispatching.
    It could be both a callable, which expect event as unique argument, or its import string:

    # callable defined in settings
    def my_func(event):
        # ...

    CLOUDEVENTS_HANDLER = my_func

    # callable defined in a module

    CLOUDEVENTS_HANDLER = "my_module.my_func"
