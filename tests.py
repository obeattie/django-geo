# -*- coding: utf-8 -*-
"""Unit testing for this module's fields and a subset of the model's functions.."""

from geopy import distance as geopy_distance
from django.test import TestCase
from django.db import models
from django.conf import settings
from fields import PickledObjectField
from test_assets import *
import models as geo_models
import geocoding

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
		for value in self.testing_data:
			model_test = PickleTestingModel(pickle_field=value)
			model_test.save()
			model_test = PickleTestingModel.objects.get(id__exact=model_test.id)
			self.assertEquals(value, model_test.pickle_field)
			model_test.delete()
	
	def testLookups(self):
		"""Tests that lookups can be performed on data once stored in the database."""
		for value in self.testing_data:
			model_test = PickleTestingModel(pickle_field=value)
			model_test.save()
			self.assertEquals(value, PickleTestingModel.objects.get(pickle_field__exact=value).pickle_field)

class DictionaryFieldTests(TestCase):
	def setUp(self):
		self.valid_testing_data = (
			{1:1, 2:4, 3:6, 4:8, 5:10},
			{u'Hello': u'Bonjour', u'こんにちは': u'你好'}
		)
		self.invalid_testing_data = (
			(1, 2, 3, 5, 5),
			[1, 2, 3, 4, 5],
			'Hello',
			1,
			1.001,
			TestCustomDataType('Hello World'),
		)
		return super(DictionaryFieldTests, self).setUp()
	
	def testDataTypes(self):
		"""Tests the field handles different data types appropriately."""
		# Test valid data types (ones that should perform fine)
		for value in self.valid_testing_data:
			model_test = DictTestingModel(dictionary_field=value)
			model_test.save()
			self.assertEquals(value, DictTestingModel.objects.get(dictionary_field__exact=value).dictionary_field)
			

class GeocodingTest(TestCase):
	def __init__(self, *args, **kwargs):
		self.query = 'London, UK'
		self.location_object = geo_models.Location.objects.get_or_create(query=self.query, geocoded=True)[0]
		return super(GeocodingTest, self).__init__(*args, **kwargs)
	
	def testGeocoding(self):
		correct_coords = tuple(geocoding.SHORT_NAME_MAPPINGS[settings.DEFAULT_GEOCODER](DummyLocation(self.query)).geocode().coords)
		self.assertEquals(correct_coords, self.location_object.coords_tuple)
	
	def testModelFunctions(self):
		"""Tests that the various functions of the Location model perform as expected."""
		# Test the co-ordinate two-tuple
		self.assertEquals((self.location_object.latitude, self.location_object.longitude, 0.0), self.location_object.coords_tuple)
		# Test the name convenience function - we haven't set a friendly name so this should be equal
		# to the query
		self.assertEquals(self.query, self.location_object.query)
		# Test that the object is indexable (latitude and longitude)
		self.assertEquals(self.location_object[0], self.location_object.latitude)
		self.assertEquals(self.location_object[1], self.location_object.longitude)
		# Test the within_bounds function, with two locations known to be northwest and southeast of London
		self.location_object_nw = geo_models.Location.objects.get_or_create(query='Birmingham, UK', geocoded=True)[0]
		self.location_object_se = geo_models.Location.objects.get_or_create(query='Brussels, Belgium', geocoded=True)[0]
		self.assertEquals(self.location_object.within_bounds(north_west=self.location_object_nw, south_east=self.location_object_se), True)
		# Also test it with objects in opposite parts of the world
		self.assertEquals(True, geo_models.Location.objects.get_or_create(query='Sydney, Australia', geocoded=True)[0].within_bounds(north_west=geo_models.Location.objects.get_or_create(query='Darwin, Australia', geocoded=True)[0], south_east=geo_models.Location.objects.get_or_create(query='Wellington, New Zealand', geocoded=True)[0]))
		# And finally test that it fails if given an area that is is not in
		self.assertEquals(False, self.location_object.within_bounds(north_west=geo_models.Location.objects.get_or_create(query='New York, NY, USA', geocoded=True)[0], south_east=self.location_object_nw))