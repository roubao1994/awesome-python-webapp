#!/usr/bin/env_python
# -*- coding: utf-8 -*-
import threading
import logging
import functools 
from contextlib import contextmanager

engine = None

def create_engine(user,password,database,host=127.0.0.1,port=3306, **kw):
	import mysql.connector
	global engine
	if engine is not None:
		raise DBError('engine has already initialized')
	params = dict(user = user, password = password, database = database, host = host, port = port)
	defaults = dict(use_unicode = True, charset = 'utf8', collation = 'utf8_general_ci', autocommit = False)
	for k,v in defaults.iteritems():
		params[k] = kw.pop()
	
	params.update(kw)
	engine = _Engine(lambda:mysql.connector.connect(**params))

def with_connection(func):
	functools.wraps(func)
	def wrapper(*args, **kw):
		with _ConnectionCtx():
			return func(*args, **kw)
	return wrapper

@with_connection	
def _select(sql, first, args):
	global _dbCtx
	cursor = None

	sql = sql.replace('?','%s')
	logging.info('SQL: %s, ARGS: %s' % (sql, args)) 
	try:
		cursor = _dbCtx.connection.cursor()
		cursor.execute(sql, args)
		if cursor.description:
			names = (x[0] for x in cursor.description)
		if first:
			values = cursor.fetchone()
			if not values:
				return None
			return Dict(names, values)
		return [Dict(names, x) for x in cursor.fetchall()]
	finally:
		if cursor:
			cursor.close()


class Dict(dict):
	def __init__(self, name = (), values = (), **kw):
		super(Dict, self).__init__(**kw)
		for k,v in zip(name, values):
			self[k] = v

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError, e:
			raise e("no key %s" %key)

	def __setattr__(self, key, value):
		self[key] = value


class _Engine(object):
	"""docstring for _Engine"""
	def __init__(self, connect):
		self.connect = connect

	def connect(self):
		return self.connect

class _LazyConnection(object):
	"""惰性连接对象"""
	def __init__(self):
		self.connection = None

	def cursor(self):
		if self.connection is None:
			_connection = engine.connect()
			self.connection = _connection
		return connection.cursor()

	def commit(self):
		self.connection.commit()

	def rollback(self):
		self.connection.rollback()

	def cleanup(self):
		if self.connection is not None:
			_connection = self.connection
			self.connection = None
			_connection.close()

class _DbCtx(threading.local):
	"""数据库上下文对象，创建与释放连接"""
	def __init__(self):
		self.connection = None
		self.transaction = 0

	def init(self):
		if self.connection is None:
			self.connection = _LazyConnection()
			self.transaction = 0

	def is_init(self):
		return self.connection is not None
	
	def cursor(self):
		return self.connection.cursor()

	def cleanup(self):
		self.connection.close()
		self.connection = None

_dbCtx = _DbCtx()

class _ConnectionCtx(object):
	"""连接上下文，用于自动创建与释放连接"""
	def __enter__(self):
		global _dbCtx
		self.should_cleanup = False
		if not _dbCtx.is_init():
			_dbCtx.init()
			self.should_cleanup = True
		return self


	def __exit__(self, exc_type, exc_value, exc_backtrace):
		global _dbCtx
		if self.should_cleanup:
			_dbCtx.cleanup()
		

		


		
		



