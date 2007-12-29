# -*- coding: utf-8 -*-
"""Unit testing for this module's fields."""

from geopy import geocoders as geopy_geocoders, distance as geopy_distance
from django.test import TestCase
from django.db import models
from django.conf import settings
from fields import PickledObjectField
from test_assets import *
import models as geo_models

class PickledObjectFieldTests(TestCase):
	def setUp(self):
		self.testing_data = (
			{1:1, 2:4, 3:6, 4:8, 5:10},
			'Hello World',
			(1, 2, 3, 4, 5),
			[1, 2, 3, 4, 5],
			TestCustomDataType('Hello World'),
		)
		return super(PickledObjectFieldTests, self).setUp()
	
	def testDataIntegriry(self):
		"""Tests that data remains the same when saved to and fetched from the database."""
		print 'wee'
		for value in self.testing_data:
			model_test = TestingModel(pickle_field=value)
			model_test.save()
			model_test = TestingModel.objects.get(id__exact=model_test.id)
			self.assertEquals(value, model_test.pickle_field)
			model_test.delete()
	
	def testLookups(self):
		"""Tests that lookups can be performed on data once stored in the database."""
		for value in self.testing_data:
			model_test = TestingModel(pickle_field=value)
			model_test.save()
			self.assertEquals(value, TestingModel.objects.get(pickle_field__exact=value).pickle_field)

class GeocodingTest(TestCase):
	def setUp(self, query='London, UK'):
		self.query = query
		self.location_object = geo_models.Location.objects.create(query=self.query)
	
	def testModelFunctions(self):
		"""Tests that the various functions of the Location model perform as expected."""
		# Test the co-ordinate dictionary
		self.assertEquals({
			'latitude': self.location_object.latitude,
			'longitude': self.location_object.longitude,
		}, self.location_object.coords)
		# Test the co-ordinate two-tuple
		self.assertEquals((self.location_object.latitude, self.location_object.longitude), self.location_object.coords_tuple)
		# Test the name convenience function - we haven't set a friendly name so this should be equal
		# to the query
		self.assertEquals(self.query, self.location_object.query)
	
	def testGeocoding(self):
		print 'Hello World.'
		returned_query, correct_coords = getattr(geopy_geocoders, settings.DEFAULT_GEOCODER)(settings.GEOCODING_KEYS[settings.DEFAULT_GEOCODER]).geocode(self.query)
		self.assertEquals(correct_coords, self.location_object.coords_tuple)
