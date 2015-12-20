﻿#!/usr/bin/env_python
# -*- coding: utf-8 -*-

import logging

import os
import time
from datetime import datetime
from transwarp import db
from transwarp.web import WSGIApplication
from transwarp.web import Jinjia2TemplateEngine
from config import configs

logging.basicConfig(level = logging.DEBUG)

db.create_engine(**configs.db)

#init wsgi app
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))

def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta // 60)
	if delta < 86400:
		return u'%s小时前' % (delta // 3600)
	if delta < 604800:
		return u'%s天前' % (delta // 86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


template_engine = Jinjia2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates'))
template_engine.add_filter('datetime',datetime_filter)

wsgi.template_engine = template_engine

import urls

wsgi.add_module(urls)


if __name__ == '__main__':
	wsgi.run(9000)
