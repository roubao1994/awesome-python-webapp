#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
JSON API DEFINITION
"""

import functools
import json,logging,re

from transwarp.web import ctx

def dumps(obj):
	return json.dumps(obj)

class APIError(StandardError):
	"""the base APIError which contains error(required),data(optional),message(optional)"""
	def __init__(self, error, data='', message=''):
		super(APIError, self).__init__(message)
		self.error = error
		self.data = data
		self.message = message

class APIValueError(APIError):
	"""the input value has error
	data specifies the error field of input form
	"""
	def __init__(self, filed, message=''):
		super(APIValueError, self).__init__('value: invalid',field, message)

class APIResourceNotFoundError(APIError):
	"""cannot find resource 
	data specifies the resource name"""
	def __init__(self, field, message=''):
		super(APIResourceNotFoundError, self).__init__('value: notfound', field, message)

class APIPermissionError(APIError):
			"""api has no permission"""
			def __init__(self, message=''):
				super(APIPermissionError, self).__init__('permission:forbidden', 'forbidden',message)

						
def api(func):
	"""a decorator that makes a function to json api,
	makes return value json
	"""
	@functools.wraps(func)
	def _wrapper(*args, **kw):
		try:
			r = dumps(func(*args, **kw))
		except APIError, e:
			r = dumps(dict(error = e.error,data = e.data, message = e.message))
		except Exception, e:
			logging.exception(e)
			r = dumps(dict(error = 'internalError',data = e.__class__.__name__,message = e.message))
		ctx.response.content_type = 'application/json'
		return r
	return _wrapper