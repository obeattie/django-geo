# -*- coding: utf-8 -*-
"""Assets for use in this module's unit tests."""

from django.db import models
from fields import PickledObjectField, DictionaryField

class PickleTestingModel(models.Model):
	pickle_field = PickledObjectField()

class DictTestingModel(models.Model):
	dictionary_field = DictionaryField()

class TestCustomDataType(str):
	pass

class DummyLocation(object):
	def __init__(self, location, *args, **kwargs):
		self.name = location
		return super(DummyLocation, self).__init__(*args, **kwargs)
