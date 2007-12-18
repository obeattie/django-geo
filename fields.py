from django.db import models

try:
	import cPickle as pickle
except ImportError:
	import pickle

class PickledObject(str):
	"""A subclass of string so it can be told whether a string is
	   a pickled object or not (if the object is an instance of this class
	   then it must [well, should] be a pickled one)."""
	pass

class PickledObjectField(models.TextField):
	__metaclass__ = models.SubfieldBase
	
	def to_python(self, value):
		if not isinstance(value, PickledObject):
			return value
		return pickle.loads(str(value))
	
	def get_db_prep_save(self, value):
		if value is not None and not isinstance(value, PickledObject):
			value = PickledObject(pickle.dumps(value))
		return value
	
	def get_internal_type(self): 
		return 'TextField'
	
	def get_db_prep_lookup(self, lookup_type, value):
		if lookup_type == 'exact':
			value = self.get_db_prep_save(value)
			return super(PickledObjectField, self).get_db_prep_lookup(lookup_type, value)
		elif lookup_type == 'in':
			value = [self.get_db_prep_save(v) for v in value]
			return super(PickledObjectField, self).get_db_prep_lookup(lookup_type, value)
		else:
			raise TypeError('Lookup type %s is not supported.' % lookup_type)
