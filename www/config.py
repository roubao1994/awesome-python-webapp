#!/usr/bin/env_python
# -*- coding: utf-8 -*-

from transwarp.db import Dict
import config_default
import logging

def merge(defaults, override):
	"""合并默认的和覆盖的参数"""
	r = {}
	for k,v in defaults.iteritems():
		if k in override:
			if isinstance(v, dict):
				r[k] = merge(v,override[k])
			else:
				r[k] = override[k]
		else:
			r[k] = v
	return r

def toDict(d):
	D = Dict()
	for k,v in d.iteritems():
		if isinstance(v, dict):
			D[k] = toDict(v)
		else:
			D[k] = v
	return D

configs = config_default.configs

try:
	import config_override
	configs = merge(configs, config_override.configs)
except ImportError:
	pass

configs = toDict(configs)
