#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
import time
from transwarp.db import next_id
from transwarp.orm import Model,StringField,IntegerField,BooleanField,FloatField,TextField

class User(Model):
	"""
	user类
	   id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(updatable=False, ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(updatable=False, default=time.time
	"""
	__table__ = 'user'
	id = StringField(primary_key=True,default=next_id,ddl='varchar(50)')
	email = StringField(updatable=False, ddl ='varchar(50)')
	password = StringField(ddl = 'varchar(50)')	
	admin = BooleanField()
	name = StringField(ddl='varchar(50)')
	image = StringField(ddl='varchar(500)')
	created_at = FloatField(updatable=False, default=time.time)

class Blog(Model):
	"""
	blog类

	"""

	__table__ = 'blog'
	id = StringField(primary_key=True, default = next_id, ddl = 'varchar(50)')
	user_id = StringField(updatable=False, ddl='varchar(50)')
	user_name = StringField(ddl = 'varchar(50)')
	user_image = StringField(ddl = 'varchar(500)')
	title = StringField(ddl = 'varchar(50)')
	summary = StringField(ddl = 'varchar(500)')
	content = TextField()
	created_at = FloatField(updatable=False, default=time.time)

class Comment(Model):
	__table__ = 'comment'
	id = StringField(primary_key=True, default=next_id, ddl = 'varchar(50)')
	blog_id = StringField(updatable=False, ddl = 'varchar(50)')
	user_id = StringField(updatable=False, ddl = 'varchar(50)')
	user_name = StringField(ddl = 'varchar(50)')
	user_image = StringField(ddl = 'varchar(500)')
	content = TextField()
	created_at = FloatField(updatable=False, default=time.time)

		