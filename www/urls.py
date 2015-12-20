#! usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Lei'

import logging

from transwarp.web import view,get
from models import Blog,User,Comment

@view('blogs.html')
@get('/')
def index():
	blogs = Blog.find_all()
	user = User.find_first("where email = ?","test@163.com")
	return dict(blogs = blogs, user = user)
