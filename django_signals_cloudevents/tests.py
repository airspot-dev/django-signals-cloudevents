import io
import json

from django.db.models.signals import *
from django.test import TestCase, override_settings

from django_signals_cloudevents import send_cloudevent
import os

from django_fake_model import models as f
from django.db import models

from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
from threading import Thread
import requests
from cloudevents.sdk import marshaller
from cloudevents.sdk.converters import binary
from cloudevents.sdk.event import v1

ALLOWED_EVENT_TYPES = (
    "django.orm.pre_init",
    "django.orm.post_init",
    "django.orm.pre_save",
    "django.orm.post_save",
    "django.orm.m2m_change",
    "django.orm.pre_delete",
    "django.orm.post_delete",
    "django.orm.pre_migrate",
    "django.orm.post_migrate",
)


class FakeSourceModel(f.FakeModel):
    name = models.CharField(max_length=100)
    enabled = models.BooleanField()


class MockServerRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Process an HTTP GET request and return a response with an HTTP 200 status.
        self.send_response(requests.codes.ok)
        self.end_headers()
        return

    def do_POST(self):
        # Process an HTTP POST request and return a response with an HTTP 200 status.
        content_len = int(self.headers.get('Content-Length'))
        request_body = self.rfile.read(content_len)
        m = marshaller.NewHTTPMarshaller([binary.NewBinaryHTTPCloudEventConverter()])
        event = m.FromRequest(v1.Event(), self.headers, io.BytesIO(request_body), lambda x: json.load(x))

        event_type = event.EventType()
        assert event_type in ALLOWED_EVENT_TYPES

        extensions = event.Extensions()
        extensions["djangoapp"] = FakeSourceModel._meta.app_label
        extensions["djangomodel"] = FakeSourceModel._meta.model_name

        event_data = event.Data()

        if event_type in ("django.orm.post.init", "django.orm.pre.save", "django.orm.post.save",
                          "django.orm.pre.delete", "django.orm.post.delete", "django.orm.m2m.change"):
            assert "data" in event_data
            instance_data = event_data["data"]
            assert "id" in instance_data and "name" in instance_data and "enabled" in instance_data

        assert event_data["db_table"] == FakeSourceModel._meta.db_table

        check_expected_kwargs(event_type, event_data["signal_kwargs"])
        self.send_response(requests.codes.ok)
        self.end_headers()
        return


def check_expected_kwargs(event_type, kwargs):
    if event_type == "django.orm.pre_init":
        assert len(kwargs) == 2 and all(k in kwargs for k in ("args", "kwargs"))
    elif event_type == "django.orm.post_init":
        assert len(kwargs) == 0
    elif event_type == "django.orm.pre_save":
        assert len(kwargs) == 3 and all(k in kwargs for k in ("update_fields", "raw", "using"))
    elif event_type == "django.orm.post_save":
        assert len(kwargs) == 4 and all(k in kwargs for k in ("created", "update_fields", "raw", "using"))
    elif event_type in ("django.orm.pre_delete", "django.orm.post_delete"):
        assert len(kwargs) == 1 and "using" in kwargs
    elif event_type == "django.orm.m2m_change":
        assert len(kwargs) == 5 and all(k in kwargs for k in ("action", "reverse", "model", "pk_set", "using"))
    elif event_type in ("django.orm.pre_migrate", "django.orm.post_migrate"):
        assert len(kwargs) == 6 and all(k in kwargs for k in ("app_config", "verbosity", "interactive", "using",
                                                              "apps", "plan"))



def get_free_port():
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    address, port = s.getsockname()
    s.close()
    return port


@override_settings(
    CLOUDEVENTS_ENV={
        "SINK_VAR": "MOCK_SINK",
        "SOURCE_VAR": "TEST_SOURCE"
    }
)
class SourceTestCase(TestCase):
    def setUp(self):
        self.mock_server_port = get_free_port()
        self.mock_server = HTTPServer(('localhost', self.mock_server_port), MockServerRequestHandler)
        self.mock_server_thread = Thread(target=self.mock_server.serve_forever)
        self.mock_server_thread.setDaemon(True)
        self.mock_server_thread.start()
        os.environ["MOCK_SINK"] = "http://localhost:%s" % self.mock_server_port
        os.environ["TEST_SOURCE"] = "test-orm-source"
        pre_init.connect(send_cloudevent, sender=FakeSourceModel)
        post_init.connect(send_cloudevent, sender=FakeSourceModel)
        pre_save.connect(send_cloudevent, sender=FakeSourceModel)
        post_save.connect(send_cloudevent, sender=FakeSourceModel)
        pre_delete.connect(send_cloudevent, sender=FakeSourceModel)
        post_delete.connect(send_cloudevent, sender=FakeSourceModel)

    @FakeSourceModel.fake_me
    def test_send_event(self):
        fake_source = FakeSourceModel.objects.create(name="fake_source", enabled=True)
        fake_source.enabled = False
        fake_source.save()
        fake_source.delete()
