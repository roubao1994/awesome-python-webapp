#! usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Lei'

import logging

from transwarp.web import view,get
from models import Blog,User,Comment
from apis import api

@view('blogs.html')
@get('/')
def index():
	blogs = Blog.find_all()
	user = User.find_first("where email = ?","test@163.com")
	return dict(blogs = blogs, user = user)

@api
@get('/api/users')
def api_get_users():
	users = User.find_all()
	return dict(users=users)

