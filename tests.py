from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.test import TestCase
from unittest.mock import patch

from .sources import get_cloudevent_from_signal
import os

from django_fake_model import models as f
from django.db import models


class FakeSourceModel(f.FakeModel):

    name = models.CharField(max_length=100)
    enabled = models.BooleanField()


class SourceTestCase(TestCase):
    def setUp(self):
        pass
        # post_save.connect(self.assert_cloudevent_post_save, sender=FakeSourceModel)
        # post_delete.connect(self.assert_cloudevent_post_delete, sender=FakeSourceModel)

    @staticmethod
    @receiver(post_save, sender=FakeSourceModel)
    def assert_cloudevent_post_save(sender, **kwargs):
        event = get_cloudevent_from_signal(sender, **kwargs)
        extensions = event.Extensions()
        assert extensions.get("djangoapp") == FakeSourceModel._meta.app_label
        assert extensions.get("djangomodel") == FakeSourceModel._meta.model_name
        assert event.EventType() == "django.orm.post.save"

    @staticmethod
    @receiver(post_delete, sender=FakeSourceModel)
    def assert_cloudevent_post_delete(sender, **kwargs):
        event = get_cloudevent_from_signal(sender, **kwargs)
        extensions = event.Extensions()
        assert extensions.get("djangoapp") == FakeSourceModel._meta.app_label
        assert extensions.get("djangomodel") == FakeSourceModel._meta.model_name
        assert event.EventType() == "django.orm.post.delete"

    @FakeSourceModel.fake_me
    def test_send_event(self):
        fake_source = FakeSourceModel.objects.create(name="fake_source", enabled=True)
        fake_source.enabled = False
        fake_source.save()
        fake_source.delete()
