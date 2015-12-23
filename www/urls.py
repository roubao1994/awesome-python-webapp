#! usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Lei'

import os,re,time,hashlib,base64

import logging

from transwarp.web import view,get,ctx,post,interceptor
from transwarp.web import HttpError
from models import Blog,User,Comment
from apis import api,APIValueError,APIPermissionError
from config import configs

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')


_COOKIE_NAME = 'awsession'
_COOKIE_KEY = configs.session.secret

def make_signed_cookie(id, password, max_age):
	# build cookie string by: id-expires-md5
	expires = str(int(time.time() + (max_age or 86400)))
	L =[id, expires, hashlib.md5('%s-%s-%s-%s' %(id,password,expires,_COOKIE_KEY)).hexdigest()]
	return '-'.join(L)

def parse_signed_cookie(cookie_str):
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		id, expires, md5 = L
		if int(expires) < time.time():
			return None
		user = User.get(id)
		if user is None:
			return None
		if md5 != hashlib.md5('%s-%s-%s-%s' %(id, user.password,expires, _COOKIE_KEY)).hexdigest():
			return None
		return user
	except:
		return None

def check_admin():
	user = ctx.request.user 
	if user and user.admin:
		return
	else:
		raise APIPermissionError('No permission')


@view('blogs.html')
@get('/')
def index():
	blogs = Blog.find_all()
	return dict(blogs = blogs, user = ctx.request.user)

@view('register.html')
@get('/register')
def register():
	return dict()

@view('login.html')
@get('/login')
def login():
	return dict()

@get('/logout')
def logout():
	ctx.response.delete_cookie(_COOKIE_NAME)
	raise HttpError.seeother('/')

@interceptor('/')
def user_interceptor(next):
    print 'enter interceptor'
    logging.info('try to bind user from session cookie...')
    user = None
    cookie = ctx.request.cookies.get(_COOKIE_NAME)
    if cookie:
        logging.info('parse session cookie...')
        user = parse_signed_cookie(cookie)
        logging.info(user)
        if user:
            logging.info('bind user <%s> to session...' % user.email)
    ctx.request.user = user
    return next()

@interceptor('/manage/')
def manage_interceptor(next):
	user = ctx.request.user
	if user and user.admin:
		return next()
	raise seeother('/login')

@api
@post('/api/authenticate')
def authenticate():
	i = ctx.request.input(remember='')
	email = i.email.strip().lower()
	password = i.password
	remember = i.remember

	user = User.find_first('where email = ?', email)
	if user is None:
		raise APIError('auth failed','email','invalid email')
	elif password != user.password:
		raise APIError('auth failed','password','invalid password')

	#set cookie
	max_age = 604800 if remember=='true' else None
	cookie = make_signed_cookie(user.id, user.password, max_age)
	ctx.response.set_cookie(_COOKIE_NAME, cookie, max_age = max_age)
	user.password = '******'
	return user

@api
@post('/api/users')
def register_user():
	i = ctx.request.input(name='',email='',password='')
	name = i.name.strip()
	email = i.email.strip().lower()
	password = i.password

	if not name:
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not password or not _RE_MD5.match(password):
		raise APIValueError('password')

	user = User.find_first('where email = ?',email)

	if user:
		raise APIError('register failed','email','the email has been used')
	user = User(name = name, email = email, password = password)
	user.insert()
	return user

@api
@get('/api/users')
def api_get_users():
	"""获取所有的user列表"""


@api
@post('/api/blogs')
def create_blog():
	"""创建日志"""
	i = ctx.request.input(name='',summary='',content='')
	name = i.name.strip()
	summary = i.summary.strip()
	content = i.content.strip()
	if name is None:
		raise APIValueError('name')
	if not summary:
		raise APIValueError('summary')
	if not content:
		raise APIValueError('content')

	user = ctx.request.user
	blog = Blog(use_id=user.id, user_name=user.name,name=name,summary=summary,content=content)
	blog.insert()
	return blog