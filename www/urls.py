#! usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Lei'

import logging

from transwarp.web import view,get
from models import Blog,User,Comment

@view('test_users.html')
@get('/')
def test_users():
	users = User.find_all()
	print users
	return dict(users = users)
