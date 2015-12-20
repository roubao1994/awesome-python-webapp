#!/usr/bin/env_python
# -*- coding: utf-8 -*-

import types, os, re, cgi, sys, time, datetime, functools, mimetypes, threading, logging, traceback, urllib
from db import Dict

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


ctx = threading.local()

#正则表达式判断是否是正确的status code字符串
_RE_RESPONSE_STATUS = re.compile(r'^\d\d\d(\ [\w\ ]+)?$')
_HEADER_X_POWERED_BY = ('x-powered-by','transwarp/1.0')
# response status
_RESPONSE_STATUSES = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',

    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',

    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended',
}

_RESPONSE_HEADERS = (
    'Accept-Ranges',
    'Age',
    'Allow',
    'Cache-Control',
    'Connection',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Disposition',
    'Content-Range',
    'Content-Type',
    'Date',
    'ETag',
    'Expires',
    'Last-Modified',
    'Link',
    'Location',
    'P3P',
    'Pragma',
    'Proxy-Authenticate',
    'Refresh',
    'Retry-After',
    'Server',
    'Set-Cookie',
    'Strict-Transport-Security',
    'Trailer',
    'Transfer-Encoding',
    'Vary',
    'Via',
    'Warning',
    'WWW-Authenticate',
    'X-Frame-Options',
    'X-XSS-Protection',
    'X-Content-Type-Options',
    'X-Forwarded-Proto',
    'X-Powered-By',
    'X-UA-Compatible',
)

class _HttpError(Exception):
	"""
	异常处理
	e = _HttpError(400)
	e.status
	'404 not found'
	"""
	def __init__(self, code):
		super(_HttpError, self).__init__()
		self.status = ('%d %s' %(code, _RESPONSE_STATUSES[code]))
		self._headers = None

	def headers(self, name, value):
		if not self._headers:
			self._headers = []
		self._headers.append((name,value))
		
	@property
	def headers(self):
		if hasattr(self,'_headers'):
			return self._headers
		return []

	def __str__(self):
		return self.status

	__repr__ = __str__

class _RedirectError(_HttpError):
    """
    RedirectError that defines http redirect code.
    >>> e = _RedirectError(302, 'http://www.apple.com/')
    >>> e.status
    '302 Found'
    >>> e.location
    'http://www.apple.com/'
    """
    def __init__(self, code, location):
        """
        Init an HttpError with response code.
        """
        super(_RedirectError, self).__init__(code)
        self.location = location

    def __str__(self):
        return '%s, %s' % (self.status, self.location)

    __repr__ = __str__



class HttpError(object):
	"""http错误类"""
	
	@staticmethod
	def badrequest():
		return _HttpError(400)

	@staticmethod
	def unauthorized():
		return _HttpError(401)

	@staticmethod
	def forbidden():
		return _HttpError(403)

	@staticmethod
	def notfound():
		return _HttpError(404)

	@staticmethod
	def conflict():
		return _HttpError(409)
	@staticmethod
	def redirect(location):
		return _RedirectError(location)
"""
   map（lambda x : x.upper(), _RESPONSE_HEADERS) 是指将_RESPONSE_HEADERS中的每个值都变为大写
   这个dict返回的就是  大写--非大写之间的对应
"""
_RESPONSE_HEADER_DICT = dict(zip(map(lambda x : x.upper(), _RESPONSE_HEADERS),_RESPONSE_HEADERS))
		
class Request(object):
	"""request对象,获取所有的http请求信息"""

	def __init__(self, environ):
		"""
		该environ包含了用户发出的所有信息
		"""
		self._environ = environ

	def _parse_input(self):
		"""
		将environ中的参数解析成一个字典对象
		 将通过wsgi 传入过来的参数，解析成一个字典对象 返回
        比如： Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
            这里解析的就是 wsgi.input 对象里面的字节流
		"""
		def _convert(item):
			if isinstance(item, list):
				return [utils.to_unicode(i.value) for i in item]
			if item.filename:
				return MultiPartFile(item)
			return utils.to_unicode(item)
		fs = cgi.FieldStorage(fp = self._environ['wsgi.input'], environ = self._environ, keep_blank_values = True)
		inputs = dict()
		for key in fs:
			inputs[key] = _convert(fs[key])
		return inputs

	def _get_raw_input(self):
		"""
		将解析出的字典对象添加为属性
		并返回该字典
		"""
		if not hasattr(self, '_raw_input'):
			self._raw_input = self._parse_input()
		return self._raw_input

	def __getitem__(self, key):
		"""
		class中的特殊方法，可以通过request[key]得到值
		通过Key值访问request中的数据
		如果该key有多个值，返回第一个
		如果不存在该key，则raise nokeyerror
		"""
		r = self._get_raw_input()[key]
		if isinstance(r, list):
			return r[0]
		return r

	#根据key返回value
	def get(self, key , default = None):
		"""
		与__getitem__类似
		但是如果不存在该key，则返回默认值
		"""
		r = self._get_raw_input().get(key, default)
		if isinstance(r, list):
			return r[0]
		return r

	def getList(self, key):
		"""
		根据key 返回一个List
		"""
		r = self._get_raw_input()[key]
		if isinstance(r,list):
			return r[:]
		return [r]

		

	def input(self, **kw):
		"""
		返回一个Dict对象， 该Dict对象由  传入的数据和environ中提取出的数据组成


        Get input as dict from request, fill dict using provided default value if key not exist.
        i = ctx.request.input(role='guest')
        i.role ==> 'guest'
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> i = r.input(x=2008)
        >>> i.a
        u'1'
        >>> i.b
        u'M M'
        >>> i.c
        u'ABC'
        >>> i.x
        2008
        >>> i.get('d', u'100')
        u'100'
        >>> i.x
        2008

		"""
		copy = Dict(**kw)
		raw = self._get_raw_input()
		for k,v in raw.iteritems():
			copy[k] = v[0] if isinstance(v,list) else v
		return copy

	def get_body(self):
		"""从POST中取出body的值，返回一个str"""
		fp = self._environ['wsgi.input']
		return fp.read()

	@property
	def environ(self):
		return self._environ

	@property
	def remote_addr(self):
		return self._environ.get('REMOTE_ADDR','0.0.0.0')

	@property
	def document_root(self):
		return self._environ.get('DOCUMENT_ROOT','')

	@property
	def query_string(self):
		return self._environ.get('QUERY_STRING','')

	@property
	#返回request的path信息
	def path_info(self):
		return urllib.unquote(self._environ.get('PATH_INFO',''))

	@property
	def request_method(self):
		return self._environ['REQUEST_METHOD']

	@property
	def host(self):
		return self._environ.get('HTTP_HOST','')

	@property
	#返回request的Header
	def headers(self):
		"""
		获取headers中的所有值
		"""
		return dict(**self._get_headers())

	@property
	def cookies(self):
		return dict(**self._get_cookies())

	def header(self, header, default = None):
		"""
		获取某个特定的header值
		"""
		return sefl._get_headers().get(header.upper(), default)


	def cookie(self, name, default = None):
		"""获取某个特定的cookie值"""
		return self._get_cookies().get(name, default)


	def _get_headers(self):
		if not hasattr(self, '_headers'):
			hdrs = {}
			for k,v in self._environ.iteritems():
				if k.startswith('HTTP_'):
					#convert 'HTTP_ACCEPT_ENCODING"' to "ACCEPT-ENCODING"
					hdrs[k[5:].replace('_','-').upper()] = v.decode('utf-8')
				self._headers = hdrs
		return self._headers

	def _get_cookies(self):
		"""从environ中获取cookies字符串，并解析成dict"""
		if not hasattr(self, '_cookies'):
			cookies = {}
			cookie_str = self._environ.get('HTTP_COOKIE')
			if cookie_str:
				for c in cookie_str.split(';'):
					pos = c.find('=')
					if pos > 0:
						cookies[c[:pos].strip()] = utils.unquote[c[pos+1:]]
			self._cookies = cookies
		return self._cookies
	


class Response(object):
	"""请求对象"""
	def __init__(self):
		self._status = '200 OK'
		self._headers = {'CONTENT-TYPE': 'text/html; charset =utf-8' }

	def set_header(self, name, value):
		"""给指定的header赋值"""
		key = name.upper()
		if key not in _RESPONSE_HEADER_DICT:
			key = name
		self._headers[key] = utils.to_str(value)


	def unset_header(self, name):
		"""删除指定的header"""
		key = name.upper()
		if key not in _RESPONSE_HEADER_DICT:
			key = name
		if key in self._headers:
			del self._headers[key]

	def header(self, name):
		"""非大小写敏感地获取某个header值"""
		key = name.upper() 
		if key not in _RESPONSE_HEADER_DICT:
			key = name
		return self._headers.get(key)

	@property
	def headers(self):
		"""
		setter构造的属性
		获取所有header的值
		包括cookie的值
		""" 
		L = [(_RESPONSE_HEADER_DICT.get(k,k),v) for k, v in self._headers.iteritems()]
		if hasattr(self, '_cookies'):
			for v in self._cookies.itervalues():
				L.append(('Set-Cookie', v))
		L.append(_HEADER_X_POWERED_BY)
		return L

	# content_type
	@property
	def content_type(self):
		return self.header('CONTENT-TYPE')

	@content_type.setter
	def content_type(self, value):
		if value:
			self.set_header('CONTENT-TYPE', value)
		else:
			self.unset_header('CONTENT-TYPE')


	#content_length
	@property
	def content_length(self):
		return self.header('COTENT-LENGTH')

	@content_length.setter
	def cotent_length(self, value):
		if value:
			self.set_header('COTENT-LENGTH', str(value))
		else :
			self.unset_header('CONTENT-LENGTH')

	#cookie
	def delete_cookie(self, name):
		self.set_cookie(name,'__deleted__',expires = 0)

	def set_cookie(self, name, value, max_age=None, expires=None, path="/",domain=None,secure=False,http_only=True):
		"""
		set a cookie
		max_age: seconds of cookie's max age
		expires: 表示一个绝对的过期时间
		path: the cookie path, default to '/'
		http_only: for better safety, set to True, client-side script cannot access cookies with httpOnly flag
		"""
		if not hasattr(self, '_cookies'):
			self._cookies = {}
		L = ['%s = %s' %(utils.quote(name),util.quote(value))]
		if expires is not None:
			if isinstance(expires, (int, float, long)):
				L.append('Expires=%s' %datetime.datetime.fromtimestamp(expires,UTC_0).strftime('%a, %d-%b-%Y %H:%M:%S GMT'))
			if isinstance(expires, (datetime.date, datetime.datetime)):
				L.append('Expires=%s' %expires.astimezone(UTC_0).strftime('%a, %d-%b-%Y %H:%M:%S GMT'))
		elif isinstance(max_age, (int, long)):
			L.append('Max-Age=%d' %max_age)
		L.append('Path=%s' %path)
		if domain:
			L.append('Domain=%s' %domain)
		if secure:
			L.append('Secure')
		if http_only:
			L.append('HttpOnly')
		self._cookies[name] = ';'.join(L)

	def unset_cookie(self, name):
		if hasattr(self, '_cookies'):
			if name in self._cookies:
				del self._cookies[name]

	#status
	@property
	def status(self):
		return self._status


	@status.setter
	def status(self, value):
		if isinstance(value, (int, long)):
			if 100 <= value <= 999:
				st = _RESPONSE_STATUSES.get(value,'')
				if st:
					self._status = "%d %s" %(value,st)
				else:
					self._status = str(value)
			else:
				raise ValueError('Bad Response Code:%d' %value)
		elif isinstance(value, basestring):
			value = value.encode('utf-8')
			if _RE_RESPONSE_STATUS.match(value):
				self._status = value
			else:
				raise ValueError('Bad Response Code %d' %value)
		else:
			raise TypeError('Bad type of Response Code.')

	#status-code
	@property 
	def status_code(self):
		"""
		 r = Response()
		 r.status_code
		 200

		 r.status = "500 Internal Error"
		 r.status_code
		 500
		"""
		return int(self._status[:3])


#######################
#实现url路由功能
#将URL 映射到函数

#捕获变量的re
_re_route = re.compile(r'(:[a-zA-Z_]\w*)')

#方法的装饰器，用于捕获url
def get(path):
	"""
    A @get decorator.
    @get('/:id')
    def index(id):
        pass
    >>> @get('/test/:id')
    ... def test():
    ...     return 'ok'
    ...
    >>> test.__web_route__
    '/test/:id'
    >>> test.__web_method__
    'GET'
    >>> test()
    'ok'
    """
	def _decorator(func):
		func.__web_route__ = path
		func.__web_method__ = 'GET'
		return func
	return _decorator

def post(path):
	def _decorator(func):
		func.__web_route__ = path
		func.__web_method__ = 'POST'
		return func
	return _decorator

def _build_regex(path):
	"""用于将路径转换成正则表达式，并获取其中的参数"""
	re_list = ['^']
	var_list = []
	is_var = False
	for v in _re_route.split(path):
		if is_var:
			var_name = v[1:]
			var_list.append(var_name)
			re_list.append(r'(?P<%s>[^\/]+)' %var_name)
		else:
			s = ''
			for ch in v:
				if '0' <= ch <= '9':
					s += ch
				elif 'A' <= ch <= 'Z':
					s += ch
				elif 'a' <= ch <= 'z':
					s += ch
				else:
					s = s + '\\' + ch
			re_list.append(s)
		is_var = not is_var
	re_list.append('$')
	return ''.join(re_list)

def _static_file_generator(fpath, block_size = 8192):
	"""
	To master yield, 
	you must understand that when you call the function, 
	the code you have written in the function body does not run.
	The function only returns the generator object, this is a bit tricky :-)
	读取静态文件的一个generator
	"""

	with open(fpath,'rb') as f:
		block =  f.read(block_size)
		while block:
			yield block
			block = f.read(block_size) 

class Route(object):
	"""
	动态路由对象， 处理 装饰器捕获的url和函数
	比如：
	@get('/:id')
	def index(id):
		pass

	在构造器中，path,method,is_staic,route和url相关
	func指向装饰器中的func（比如上面的index函数)
	"""
	def __init__(self, func):
		"""
		path : 通过装饰器捕获的path
		method: 通过装饰器捕获的method
		is_static: 路径是否含变量
		route:动态url(含变量）则捕获其变量的re
		func: 方法装饰器里定义的函数
		"""
		self.path = func.__web_route__
		self.method = func.__web_method__
		self.is_static = _re_route.search(self.path) is None
		if not self.is_static:
			self.route = re.compile(_build_regex(self.path))
		self.func = func

	def match(self, url):
		"""传入url，返回捕获的变量"""
		m = self.route.match(url)
		if m:
			return m.groups()
		return None

	def __call__(self, *args):
		"""
		实例对象直接调用时，执行传入的func
		"""
		return self.func(*args)
	
	def __str__(self):
		if self.is_static:
			return 'Route(static, %s, path=%s' %(self.method, self.path)
		return 'Route(dynamic, %s, path = %s' %(self.method,self.path)


	__repr__ = __str__

class StaticFileRoute(object):
	"""静态文件路有对象"""
	def __init__(self):
		self.method = 'GET'
		self.is_static = False
		self.route = re.compile('^/static/(.+)$')

	def match(self, url):
		if url.startswith('/static/'):
			return (url[1:],)
		return None

	def __call__(self, *args):
		fpath = os.path.join(ctx.application.document_root,args[0])
		if not os.path.isfile(fpath):
			raise HttpError.notfound()
		fext = os.path.splittext(fpath)[1]
		ctx.response.content_type = mimetypes.types_map.get(fext.lower(),'application/octet-stream')
		return _static_file_generator(fpath)

class MultiPartFile(object):
	"""docstring for MultiPartFile"""
	def __init__(self, storage):
		self.filename = utils.to_unicode(storage.filename)
		self.file = storage.file
		
		

#定义拦截器
def interceptor(pattern):
	pass

###############
#实现视图功能
#################
class Template(object):
	"""docstring for Template"""
	def __init__(self, template_name, **kw):
		self.template_name = template_name
		self.model = dict(**kw)

#定义模板引擎
class TemplateEngine(object):
	"""模板引擎基类"""
	def __call__(self, path, model):
		return '<!-- override this method to render template--!>'

#定义默认引擎jingjia
class Jinjia2TemplateEngine(TemplateEngine):
	"""默认的引擎"""
	def __init__(self, templ_dir, **kw):
		from jinja2 import Environment,FileSystemLoader
		if 'autoescape' not in kw:
			kw['autoescape'] = True
		self._env = Environment(loader = FileSystemLoader(templ_dir), **kw)

	def add_filter(self, name, fn_filter):
		self._env.filters[name] = fn_filter

	def __call__(self, path, model):
		return self._env.get_template(path).render(**model).encode('utf-8')


def _debug():
	pass


def _defatult_error_handler(e, start_response, is_debug):
	"""
	用于处理异常，主要是响应一个异常页面
	"""
	if isinstance(e, HttpError):
		logging.info('HttpError: %s' %e.status)
		headers = e.headers[:]
		headers.append(('Content-Type','text/html'))
		start_response(e.status, headers)
		return ('<html><body><h1>%s</h1></body></html>' %e.status)

		loggin.exception('Exception:')
		start_response('500 Internal Server Error',[('Content-Type','text/html'),_HEADER_X_POWERED_BY])
		if is_debug:
			return _debug()
		return ('<html><body><h1>500 Internal Server Error</h1><h3>%s</h3></body></html>' %str(e))


def view(path):
	"""
	装饰器
	被装饰的func返回一个字典对象，用于渲染
	装饰器通过Template类  将path和dict关联到Template对象上
	"""
	def _decorator(func):
		@functools.wraps(func)
		def _wrapper(*args, **kw):
			r = func(*args, **kw)
			if isinstance(r, dict):
				logging.info('return Template')
				return Template(path, **r)
			else:
				raise ValueError('expect return a dict')
		return _wrapper
	return _decorator

##################
#实现URL拦截
#主要是interceptor的实现
_RE_INTERCEPTOR_STARTS_WITH = re.compile(r'^([^\*\?]+)\*?$')
_RE_INTERCEPTOR_ENDS_WITH = re.compile(r'^\*([^\*\?]+)$')

def _build_pattern_fn(pattern):
	"""传入需要匹配的字符串
	返回一个函数
	该函数接受一个字符串，检测该字符串是否符合pattern
	"""
	m = _RE_INTERCEPTOR_STARTS_WITH(pattern)
	if m:
		return lambda p : p.startswith(m.group(1))
	m = _RE_INTERCEPTOR_ENDS_WITH(pattern)
	if m:
		return lambda p : p.endswith(m.group(1))
	raise ValueError('Invalid pattern definition in interceptor.')


def interceptor(pattern = '/'):
	"""
	an @interceptor decorator
	"""
	def _decorator(func):
		func.__interceptor__ = _build_pattern_fn(pattern)
		return func
	return _decorator

def _build_interceptor_fn(func, next):
	"""拦截器接受一个next函数， 这样一个拦截器可以决定调用next继续处理请求还是直接返回"""
	def _wrapper():
		if func.__interceptor__(ctx.request.path_info):
			return func(next)
		else:
			return next()
	return _wrapper

def _build_interceptor_chain(last_fn, *interceptors):
	"""???build interceptor chain"""
	L = list(interceptors)
	L.reverse()
	fn = last_fn
	for f in L:
		fn = _build_interceptor_fn(f, fn)
	return fn

def _load_module(module_name):
	"""load module from name as str"""
	last_dot = module_name.rfind('.')
	if last_dot == (-1):
		return __import__(module_name, globals(), locals())
	from_module = module_name[:last_dot]
	import_module = module_name[last_dot+1:]
	m = __import__(from_module,globals(), locals(),[import_module])
	return getattr(m, import_module)


class WSGIApplication(object):
	"""docstring for WSGIApplication"""
	def __init__(self, document_root=None, **kw):
		"""
		init a wsgiapplication
		args: document_root:document_root path
		"""
		self._running = False
		self._document_root = document_root

		self._interceptors = []
		self._template_engine = None

		self._get_static = {}
		self._post_static = {}

		self._get_dynamic = []
		self._post_dynamic = []


	def _check_not_running(self):
		"""检查app对象是否运行"""
		if self._running:
			raise RuntimeError('cannot midify WSGIApplication when running')

	@property
	def template_engine(self):
		return self._template_engine

	@template_engine.setter
	def template_engine(self, engine):
		self._check_not_running()
		self._template_engine = engine


	def add_module(self, mod):
		self._check_not_running()
		m = mod if type(mod) == types.ModuleType else _load_module(mod)
		logging.info('add module: %s' %m.__name__)
		for name in dir(m):
			fn =getattr(m, name)
			if callable(fn) and hasattr(fn, '__web_route__') and hasattr(fn,'__web_method__'):
				self.add_url(fn)

	def add_url(self, func):
		self._check_not_running()
		route = Route(func)
		if route.is_static:
			if route.method == 'GET':
				self._get_static[route.path] = route
			if route.method == 'POST':
				self._post_static[route.path] = route
		else:
			if route.method == 'GET':
				self._get_dynamic.append(route)
			if route.method == 'POST':
				route._post_dynamic.append(route)

		logging.info('add route: %s' %str(route))


	def add_interceptor(self, func):
		self._check_not_running()
		self._interceptors.append(func)
		logging.info('add interceptor : %s' %str(func))


	def run(self, port = 9000, host = '127.0.0.1'):
		"""
		启动python自带的wsgiserver
		"""
		from wsgiref.simple_server import make_server
		logging.info('application (%s) will start at %s:%s...' %(self._document_root,host,port))
		server = make_server(host,port, self.get_wsgi_application(debug=True))
		server.serve_forever()

	def get_wsgi_application(self, debug=False):
		self._check_not_running()
		if debug:
			self._get_dynamic.append(StaticFileRoute())
		self._running = True

		_application = Dict(document_root= self._document_root)

		def fn_route():
			request_method = ctx.request.request_method
			path_info = ctx.request.path_info
			if request_method == 'GET':
				fn = self._get_static.get(path_info,None)
				if fn:
					return fn()
				for fn in self._get_dynamic:
					args = fn.match(path_info)
					if args:
						return fn(*args)
				raise HttpError.notfound()
			if request.method == 'POST':
				fn = self._post_static.get(path_info,None)
				if fn:
					return fn()
				for fn in self._post_dynamic:
					args = fn.match(path_info)
					if args:
						return fn(*args)
				raise HttpError.notfound()
			raise badrequest()

		fn_exec = _build_interceptor_chain(fn_route, *self._interceptors)

		def wsgi(env, start_response):
			ctx.application = _application
			ctx.request = Request(env)
			response = ctx.response = Response()
			try:
				r = fn_exec()
				print r
				if isinstance(r, Template):
					r = self._template_engine(r.template_name, r.model)
				if isinstance(r, unicode):
					r = r.encode('utf-8')
				if isinstance(r, Template):
					r = self._template_engine(r.template_name, r.model)
				if r is None:
					r = []
				start_response(response.status, response.headers)
				print response.headers
				return r
			except _RedirectError, e:
				response.set_header('Location', e.location)
				start_response(e.status, response.headers)
				return []
			except _HttpError, e:
				start_response(e.status, response.headers)
				return ['<html><body><h1>', e.status, '</h1></body></html>']
			except Exception, e:
				logging.exception(e)
				if not debug:
					start_response('500 Internal Server Error', [])
					return ['<html><body><h1>500 Internal Server Error</h1></body></html>']
				exc_type, exc_value, exc_traceback = sys.exc_info()
				fp = StringIO()
				traceback.print_exception(exc_type, exc_value, exc_traceback, file=fp)
				stacks = fp.getvalue()
				fp.close()
				start_response('500 Internal Server Error', [])
				return [
				    r'''<html><body><h1>500 Internal Server Error</h1><div style="font-family:Monaco, Menlo, Consolas, 'Courier New', monospace;"><pre>''',
				    stacks.replace('<', '&lt;').replace('>', '&gt;'),
				    '</pre></div></body></html>']
			finally:
				del ctx.application
				del ctx.request
				del ctx.response

		return wsgi