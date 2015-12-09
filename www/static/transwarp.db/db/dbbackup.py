#!/usr/bin/env_python
# -*- coding: utf-8 -*-
import threading
import logging
import functools
 
engine = None

def create_engine(user,password,database,host='127.0.0.1', port = 3306, **kw):
	import mysql.connector
	global engine
	if engine is not None:
		raise DBError('engine has already initialized')
	params = dict(user = user, password = password, database = database, host = host, port = port)
	defaults = dict(use_unicode = True, charset = 'utf8', collation = 'utf8_general_ci', autocommit = False)
	for k,v in defaults.iteritems():
		params[k] = kw.pop(k, v)
	params.update(kw)
	engine = _Engine(lambda:mysql.connector.connect(**params))

class _Engine(object):
	"""数据库引擎对象
	保存 create_engine创建的连接

	"""
	def __init__(self, connect):
		self._connect = connect

	def connect(self):
		return self._connect()

def connection():
	"""
    db模块核心函数，用于获取一个数据库连接
    通过_ConnectionCtx对 _db_ctx封装，使得惰性连接可以自动获取和释放，
    也就是可以使用 with语法来处理数据库连接
    _ConnectionCtx    实现with语法
    ^
    |
    _db_ctx           _DbCtx实例
    ^
    |
    _DbCtx            获取和释放惰性连接
    ^
    |
    _LasyConnection   实现惰性连接
    """
	return _ConnectionCtx()

def with_connection(func):
	functools.wraps(func)
	def _wrapper(*args, **kw):
		with _ConnectionCtx():
			return func(*args, **kw)
	return _wrapper

def with_transaction(func):
	functools.wraps(func)
	def _wrapper(*args, **kw):
		with _TransactionCtx():
			return func(*args, **kw)
		return _wrapper

@with_connection
def _select(sql, first, *args):
    """
    执行SQL，返回一个结果 或者多个结果组成的列表
    """
    global _dbCtx
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _dbCtx.connection.cursor()
        cursor.execute(sql, args)
        if cursor.description:
            names = [x[0] for x in cursor.description]
        if first:
            values = cursor.fetchone()
            if not values:
                return None
            return Dict(names, values)
        return [Dict(names, x) for x in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()

@with_connection
def _update(sql, *args):
	"""
	执行update语句，返回update行数
	"""
	global _dbCtx
	cursor = None
	sql = sql.replace('?', '%s')
	logging.info('SQL: %s, ARGS: %s' %(sql, args))
	try:
		cursor = _dbCtx.connection.cursor()
		cursor.execute(sql, args)
		r = cursor.rowcount
		if _dbCtx.transactions == 0:
			#no transactions 可以提交
			logging.info('auto commit')
			_dbCtx.connection.commit()
		return r
	finally:
		if cursor:
			cursor.close()

def update(sql, *args):
	return _udpate(sql, *args)

@with_connection
def insert(table, **kw):
	"""
    执行insert语句
    >>> u1 = dict(id=2000, name='Bob', email='bob@test.org', passwd='bobobob', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 2000)
    >>> u2.name
    u'Bob'
    >>> insert('user', **u2)
    Traceback (most recent call last):
      ...
    IntegrityError: 1062 (23000): Duplicate entry '2000' for key 'PRIMARY'
    """
	col,args = zip(*kw.iteritems())
	sql = 'insert into `%s` (%s) values (%s)' % (table, ','.join(['`%s`' % col for col in cols]), ','.join(['?' for i in range(len(cols))]))
	return _update(sql,*args)

def select(sql, *args):
	return _select(sql,False, *args)

def selectOne(sql, *args):
	return _select(sql, True, *args)

def selectInt(sql, *args):
	"""返回int，如果超过一个值则raise  error"""
	d = _select(sql,True, *args)
	if len(d) != 1:
		raise MultiColumnError('expect only one column')
	return d.values()[0]

class Dict(dict):
	"""字典对象
	实现一个简单的可以通过属性访问的字典"""
	def __init__(self, names= (), values = (), **kw):
		super(Dict, self).__init__(**kw)
		for k,v in zip(names,values):
			self[k] = v

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Dict' object has no attribute %s" %key)

	def __setattr__(self,key,value):
		self[key] = value
		

class _LasyConnection(object):
	"""惰性连接对象"""
	def __init__(self):
		self.connection = None

	def cursor(self):
		if self.connection is None:
			_connection = engine.connect()
			logging.info("[CONNECTION][OPEN] connection <%s>" %hex(id(_connection)))
			self.connection = _connection
		return self.connection.cursor()

	def commit(self):
		self.connection.commit()

	def rollback(self):
		self.connection.rollback()

	def cleanup(self):
		if self.connection:
			_connection = self.connection
			self.connection = None
			logging.info('[CONNECTION][CLOSE] connection <%s>' %hex(id(_connection)))
			_connection.close()

class _DbCtx(threading.local):
	"""
	数据库连接上下文对象
	获取和释放连接
	取得的是一个LazyConnection
	"""
	def __init__(self):
		self.connection = None
		self.transactions = 0

	def is_init(self):
		return self.connection is not None

	def init(self):
		logging.info('open lazy connection')
		self.connection = _LasyConnection()
		self.transactions = 0

	def cleanup(self):
		self.connection.cleanup()
		self.connection = None

	def cursor(self):
		return self.connection.cursor()

#thread local db context
_dbCtx = _DbCtx()

class _ConnectionCtx(object):
	"""连接的自动获取和释放"""
	def __enter__(self):
		global _dbCtx
		self.should_cleanup = False
		if not _dbCtx.is_init():
			_dbCtx.init()
			self.should_cleanup = True
		return self

	def __exit__(self, exctype,excvalue, traceback):
		global _dbCtx
		if self.should_cleanup:
			_dbCtx.cleanup()

class _TransactionCtx(object):
	"""事务嵌套
	需要计数
	每遇到一层嵌套+1，离开一层-1，到0时提交事务"""

	def __enter__(self):
		global _dbCtx
		shelf.should_close_conn = False
		if not _dbCtx.is_init():
			_dbCtx.init()
			self.should_close_conn = True
		_dbCtx.transactions += 1
		logging.info('begin transaction ...' if _dbCtx.transactions == 1 else 'join current transaction...')
		return self

	def __exit__(self,exc_type, exc_value, exc_traceback):
		global _dbCtx
		_dbCtx -= 1
		try:
			if _dbCtx.transactions == 0:
				if exc_type is None:
					self.commit()
				else:
					self.rollback()
		finally:
			if should_close_conn:
				_dbCtx.cleanup()

	def commit(self):
		global _dbCtx
		logging.info('commit transaction...')
		try:
			_dbCtx.connection.commit()
			logging.info('commit OK')
		except :
			logging.warning('commit failed.try rollback...')
			_dbCtx.connection.rollback()
			raise

	def rollback(self):
		global _dbCtx
		logging.warning('rollback transaction...')
		_dbCtx.connection.rollback()
		logging.warning('rollback OK ......')

		
		

class DBError(Exception):
	pass

class MultiColumnError(DBError):
	pass
		

if __name__ == '__main__':
	logging.basicConfig(level = logging.DEBUG)
	create_engine('root','','test')
	print _select('select * from user','first')






		