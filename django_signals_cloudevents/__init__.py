import json
import uuid
from datetime import datetime

import pytz
import requests
from django.db.models import ManyToOneRel
from django.db.models.signals import *
from cloudevents.sdk import converters
from cloudevents.sdk import marshaller
from cloudevents.sdk.converters import binary
from cloudevents.sdk.event import v1
import os
from django.conf import settings


def _get_event_type_from_signal(signal):
    if signal == pre_init:
        return "django.orm.pre_init"
    elif signal == post_init:
        return "django.orm.post_init"
    elif signal == pre_save:
        return "django.orm.pre_save"
    elif signal == post_save:
        return "django.orm.post_save"
    elif signal == m2m_changed:
        return "django.orm.m2m_change"
    elif signal == pre_delete:
        return "django.orm.pre_delete"
    elif signal == post_delete:
        return "django.orm.post_delete"
    elif signal == pre_migrate:
        return "django.orm.pre_migrate"
    elif signal == post_migrate:
        return "django.orm.post_migrate"


def _get_instance_dict(instance):
    instance_dict = {}
    for field in instance._meta.get_fields():
        field_name = field.name
        if isinstance(field, ManyToOneRel):
            field_name = field.related_name or "%s_set" % field_name
            instance_dict[field_name] = []
            for rel in getattr(instance, field_name).all():
                instance_dict[field_name].append(_get_instance_dict(rel))
        else:
            instance_dict[field_name] = str(getattr(instance, field_name))
    return instance_dict


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
        if type(instance) != sender:  # m2m signal
            obj_meta = instance._meta
            model = instance._meta.model_name
            kwargs["model"] = kwargs["model"]._meta.model_name
            kwargs["updated_pks"] = list(kwargs.pop("pk_set"))
        payload["data"] = _get_instance_dict(instance)
        for m_field in obj_meta.many_to_many:
            field_name = m_field.name
            m2m_data = []
            for m2m_obj in getattr(instance, field_name).all():
                m2m_data.append(_get_instance_dict(m2m_obj))
            payload["data"][field_name] = m2m_data
        # TODO parse related_fields
        # for r_field in obj_meta.related_objects:
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
