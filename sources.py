import json
import uuid
from datetime import datetime

import pytz
import requests
from django.db.models.signals import *
from cloudevents.sdk import converters
from cloudevents.sdk import marshaller
from cloudevents.sdk.converters import binary
from cloudevents.sdk.event import v1
import os
from django.conf import settings


def _get_event_type_from_signal(signal):
    if signal == pre_init:
        return "django.orm.pre.init"
    elif signal == post_init:
        return "django.orm.post.init"
    elif signal == pre_save:
        return "django.orm.pre.save"
    elif signal == post_save:
        return "django.orm.post.save"
    elif signal == m2m_changed:
        return "django.orm.m2m.change"
    elif signal == pre_delete:
        return "django.orm.pre.delete"
    elif signal == post_delete:
        return "django.orm.post.delete"
    elif signal == pre_migrate:
        return "django.orm.pre.migrate"
    elif signal == post_migrate:
        return "django.orm.post.migrate"


def send_cloudevent(sender, **kwargs):
    if os.environ.get("K_SINK") is not None:
        event = get_cloudevent_from_signal(sender, **kwargs)

        m = marshaller.NewHTTPMarshaller([binary.NewBinaryHTTPCloudEventConverter()])
        headers, body = m.ToRequest(event, converters.TypeBinary, json.dumps)

        response = requests.post(os.environ.get('K_SINK'),
                                 headers=headers,
                                 data=body)

        response.raise_for_status()


def get_cloudevent_from_signal(sender, **kwargs):
    event_type = _get_event_type_from_signal(kwargs.pop("signal"))
    instance = kwargs.pop("instance")
    obj_meta = sender._meta
    payload = {
        "signal_kwargs": {
            **kwargs
        },
        "data": {}
    }
    for field in obj_meta.fields:
        field_name = field.name
        payload["data"][field_name] = str(getattr(instance, field_name))
    payload["db_table"] = obj_meta.db_table
    app = obj_meta.app_label
    model = obj_meta.model_name
    extensions = {
        "djangoapp": app,
        "djangomodel": model,
    }
    event_id = str(uuid.uuid4())
    event = v1.Event()
    event.SetContentType('application/json')
    event.SetEventID(event_id)
    event.SetSource(os.environ.get("CLOUDEVENT_SOURCE", "django-orm"))
    event.SetSubject("DCE:%s.%s/%s" % (app, model, instance.id))
    event.SetEventTime(datetime.utcnow().replace(tzinfo=pytz.UTC).isoformat())
    event.SetEventType(event_type)
    # set extended properties
    event.SetExtensions(extensions)
    event.Set('Originid', event_id)
    event.SetData(payload)
    return event


def register(model, signals=(post_save, post_delete)):
    for sig in signals:
        sig.connect(send_cloudevent, sender=model)


def discovery(app, signals):
    # get all models -> for model in models: register(model, s)
    pass
