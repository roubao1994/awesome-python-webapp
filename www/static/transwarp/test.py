import logging
def test():
	description = [(u'id', 3, None, None, None, None, 0, 16899), (u'name', 253, None, None, None, None, 0, 4097), (u'password', 253, None, None, None, None, 0, 4097)]
	names = [x[0] for x in description]
	values = (2, u'test', u'12345')
	diction = {}
	for k,v in zip(names, values):
		diction[k] = v
	print diction

logging.basicConfig(level = logging.DEBUG)
test()
