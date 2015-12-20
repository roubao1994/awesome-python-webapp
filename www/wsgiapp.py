#!/usr/bin/env_python
# -*- coding: utf-8 -*-

import logging

import os

from transwarp import db
from transwarp.web import WSGIApplication
from transwarp.web import Jinjia2TemplateEngine
from config import configs

logging.basicConfig(level = logging.DEBUG)

db.create_engine(**configs.db)

#init wsgi app
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))


template_engine = Jinjia2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates'))

wsgi.template_engine = template_engine

import urls

wsgi.add_module(urls)

if __name__ == '__main__':
	wsgi.run(9000)
