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
    sink_url = os.environ.get(settings.CLOUDEVENTS_ENV["SINK_VAR"])
    if sink_url is not None:
        event = get_cloudevent_from_signal(sender, **kwargs)

        m = marshaller.NewHTTPMarshaller([binary.NewBinaryHTTPCloudEventConverter()])
        headers, body = m.ToRequest(event, converters.TypeBinary, json.dumps)

        response = requests.post(sink_url,
                                 headers=headers,
                                 data=body)

        response.raise_for_status()


def get_cloudevent_from_signal(sender, **kwargs):
    event_type = _get_event_type_from_signal(kwargs.pop("signal"))
    obj_meta = sender._meta

    app = obj_meta.app_label
    model = obj_meta.model_name

    payload = {}
    if "instance" in kwargs:
        instance = kwargs.pop("instance")
        payload["data"] = {}
        for field in obj_meta.fields:
            field_name = field.name
            payload["data"][field_name] = str(getattr(instance, field_name))
        subject = "DCE:%s.%s/%s" % (app, model, instance.id)
    else:
        subject = "DCE:%s.%s" % (app, model)
    payload["signal_kwargs"] = {
        **kwargs
    }
    payload["db_table"] = obj_meta.db_table

    extensions = {
        "djangoapp": app,
        "djangomodel": model,
    }

    event_id = str(uuid.uuid4())
    event = v1.Event()
    event.SetContentType('application/json')
    event.SetEventID(event_id)
    event.SetSource(os.environ.get(settings.CLOUDEVENTS_ENV["SOURCE_VAR"], "django-orm"))
    event.SetSubject(subject)
    event.SetEventTime(datetime.utcnow().replace(tzinfo=pytz.UTC).isoformat())
    event.SetEventType(event_type)
    event.SetExtensions(extensions)
    event.Set('Originid', event_id)
    event.SetData(payload)
    return event


def inject_app_defaults(application):
    """Inject an application's default settings"""
    try:
        __import__('%s.settings' % application)
        import sys

        # Import our defaults, project defaults, and project settings
        _app_settings = sys.modules['%s.settings' % application]
        _def_settings = sys.modules['django.conf.global_settings']
        _settings = sys.modules['django.conf'].settings

        # Add the values from the application.settings module
        for _k in dir(_app_settings):
            if _k.isupper():
                # Add the value to the default settings module
                setattr(_def_settings, _k, getattr(_app_settings, _k))

                # Add the value to the settings, if not already present
                if not hasattr(_settings, _k):
                    setattr(_settings, _k, getattr(_app_settings, _k))
    except ImportError:
        # Silently skip failing settings modules
        pass


inject_app_defaults(__name__)
