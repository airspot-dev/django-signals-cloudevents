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

3. [Optional] Override cloudevents handling:

    As said previously, by default this app is configured to be used with a SinkBinding and get sink url from the environment variable K_SINK, that indicates to which url events will be dispatched, and the source name from K_SOURCE.
    It is possible to override the chosen env variable in your project settings, here is the default configuration::

    CLOUDEVENTS_ENV = {
        "SINK_VAR": "K_SINK",
        "SOURCE_VAR": "K_SOURCE"
    }

    Let's see how it works.

    Taking up the `Django tutorial <https://docs.djangoproject.com/en/3.1/intro/tutorial02/>`_ we suppose we have defined the following models:

    class Question(models.Model):
        question_text = models.CharField(max_length=200)
        pub_date = models.DateTimeField('date published')


    class Choice(models.Model):
        question = models.ForeignKey(Question, on_delete=models.CASCADE)
        choice_text = models.CharField(max_length=200)
        votes = models.IntegerField(default=0)

    After that we define a service to deploy a Django app in the cluster.

    apiVersion: serving.knative.dev/v1alpha1
    kind: Service
    metadata:
      name: django-orm
      labels:
        app: django-orm
    spec:
      template:
        metadata:
          annotations:
            autoscaling.knative.dev/minScale: "1"
          labels:
            app: django-orm
        spec:
          containers:
            - name: django-orm
              image: gcr.io/krules-dev-254113/django_orm
              imagePullPolicy: Always
              ports:
                - containerPort: 8080

    Then we sink the service with a broker using a SinkBinding

    apiVersion: sources.knative.dev/v1alpha2
    kind: SinkBinding
    metadata:
      name: django-orm-binding
    spec:
      subject:
        apiVersion: serving.knative.dev/v1alpha1
        kind: Service
        selector:
          matchLabels:
            app: django-orm
      sink:
        ref:
          apiVersion: eventing.knative.dev/v1
          kind: Broker
          name: default

    SinkBinding will set in env **K_SOURCE**, the service name, and **K_SINK**, the url of resource defined in sink.ref, in this example the Broker default.

    After saving a Question an event like this will be sent to the **default** broker:

    ☁️  cloudevents.Event
    Validation: valid
    Context Attributes,
      specversion: 1.0
      type: django.orm.post_save
      source: django-orm
      subject: DCE:polls.question/22
      id: a9b0a310-c7cd-4054-b112-93eb1b398686
      time: 2020-12-01T09:43:34.6461Z
      datacontenttype: application/json
    Extensions,
      datacontenttype: application/json
      djangoapp: polls
      djangomodel: question
      knativearrivaltime: 2020-12-01T09:43:34.793013561Z
      knativehistory: default-kne-trigger-kn-channel.crd-cm-deployment-demo.svc.cluster.local
      originid: a9b0a310-c7cd-4054-b112-93eb1b398686
    Data,
      {
        "data": {
          "id": "22",
          "question_text": "How are you?",
          "pub_date": "2020-12-01T09:43"
        },
        "signal_kwargs": {
          "created": true,
          "update_fields": null,
          "raw": false,
          "using": "default"
        },
        "db_table": "polls_question"
      }

    However could be necessary to override the default handler.
    Suppose you need to deploy Django application outside the cluster and send events to it through an external message broker, like Google Pub/Sub.
    It is possible to define a different handler for cloudevents dispatching.
    It could be both a callable, which expect event as unique argument, or its import string:


    from google.cloud import pubsub_v1
    import os
    import json
    import logging

    logger = logging.getLogger(__name__)
     # ...


    def pubsub_handler(event):

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(os.environ.get("PROJECT_ID"), os.environ.get("TOPIC_ID"))
        data = json.dumps(event.Data()).encode("utf-8")
        event_info = event.Properties()
        event_info.update(event_info.pop("extensions"))
        attrs = {
            "ce-extensions": json.dumps(event.Extensions()).encode('utf-8'),
            "ce-source": event.Source(),
            "ce-id": event.EventId(),
            "ce-time": event.EventTime(),
            "ce-type": event.EventType()
        }
        future = publisher.publish(topic_path, data=data, **attrs)
        logger.info(future.result())

    # callable defined in settings

    CLOUDEVENTS_HANDLER = pubsub_handler

    # callable defined in a module

    CLOUDEVENTS_HANDLER = "my_module.pubsub_handler"
