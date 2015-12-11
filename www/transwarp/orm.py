#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import db
import time


"""
orm模块设计的原因：
    1. 简化操作
        sql操作的数据是 关系型数据， 而python操作的是对象，为了简化编程 所以需要对他们进行映射
        映射关系为：
            表 ==>  类
            行 ==> 实例
设计orm接口：
    1. 设计原则：
        根据上层调用者设计简单易用的API接口
    2. 设计调用接口
        1. 表 <==> 类
            通过类的属性 来映射表的属性（表名，字段名， 字段属性）
                from transwarp.orm import Model, StringField, IntegerField
                class User(Model):
                    __table__ = 'users'
                    id = IntegerField(primary_key=True)
                    name = StringField()
            从中可以看出 __table__ 拥有映射表名， id/name 用于映射 字段对象（字段名 和 字段属性）
        2. 行 <==> 实例
            通过实例的属性 来映射 行的值
                # 创建实例:
                user = User(id=123, name='Michael')
                # 存入数据库:
                user.insert()
            最后 id/name 要变成 user实例的属性
"""
_triggers = frozenset(['pre_insert','pre_update','pre_delete'])

def _gentable(table_name,mappings):
    pk = None
    sql = ['-- generating sql for table %s:' % table_name,'create table %s (' %table_name ]
    for f in sorted(mappings.values(), lambda x,y: cmp(x._order, y._order)):
        if not hasattr(f, 'ddl'):
            raise StandardError('fidld %s has no ddl' %f)
        ddl = f.ddl
        nullable = f.nullable
        if f.primary_key:
            pk = f.name
        sql.append(' `%s` %s, ' % (f.name, ddl) if nullable else ' `%s` %s not null,' % (f.name, ddl))
        sql.append(' primary key (`%s`)' % pk)
        sql.append(');')
        return '\n'.join(sql)

class Field(object):
    """
    保存数据库中的表的  字段属性
    _count: 类属性，每实例化一次，该值就+1
    self._order: 实例属性， 实例化时从类属性处得到，用于记录 该实例是 该类的第几个实例，也就是表中的第几个字段
    self._default: 用于让orm自己填入缺省值，缺省值可以是 可调用对象，比如函数
                比如：passwd 字段 <StringField:passwd,varchar(255),default(<function <lambda> at 0x0000000002A13898>),UI>
                     这里passwd的默认值 就可以通过 返回的函数 调用取得
    其他的实例属性都是用来描述字段属性的"""

    _count = 0
    def __init__(self, **kw):
        #属性名
        self.name = kw.get('name', None)
        self._default = kw.get('default',None)
        #是否是主键
        self.primary_key = kw.get('primary_key', False)
        self.nullable = kw.get("nullable", False)
        self.updatable = kw.get('updatable', True)
        self.insertable = kw.get('insertable', True)
        self.ddl = kw.get('ddl','')
        self._order = Field._count
        Field._count += 1

    @property
    def default(self):
        d = self._default
        return d() if callable(d) else d

    def __str__(self):
        """返回实例对象的信息"""
        s = ['<%s,%s,%s,default(%s)' %(self.__class__.__name__,self.name,self.ddl,self._default)]
        if self.nullable:
            s.append('N')
        if self.updatable:
            s.append('U')
        if self.insertable:
            s.append("I")
        s.append('>')
        return ''.join(s)

class IntegerField(Field):
    """整数类型字段"""
    def __init__(self, **kw):
        if not 'default' in kw:
            kw['default'] = 0
        if 'ddl' not in kw:
            kw['ddl'] = 'bigint'
        super(IntegerField, self).__init__(**kw)

class StringField(Field):
    """字符串类型"""
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = ''
        if 'ddl' not in kw:
            kw['ddl'] = 'varchar(255)'
        super(StringField, self).__init__(**kw)

class FloatField(Field):
    """浮点数类型"""
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = 0.0
        if 'ddl' not in kw:
            kw['ddl'] = 'real'
        super(FloatField, self).__init__(**kw)

class BooleanField(Field):
    """bool类型"""
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = False
        if 'ddl' not in kw:
            kw['ddl'] = 'bool'
        super(BooleanField, self).__init__(**kw)

class TextField(Field):
    """text类型"""
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = ''
        if 'ddl' not in kw:
            kw['ddl'] = 'text'
        super(TextField, self).__init__(**kw)


class BlobField(Field):
    """blob类型 """
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = ''
        if 'ddl' not in kw:
            kw['ddl'] = 'blob'
        super(BlobField, self).__init__(**kw)        
        
class VersionField(Field):
    """
    保存Version类型字段的属性
    """
    def __init__(self, name=None):
        super(VersionField, self).__init__(name=name, default=0, ddl='bigint')

class ModelMetaClass(type):
    """对类对象动态完成以下操作
    属性与字段的mapping：
       1.从类的属性dict中提取出 类属性和字段类 的 mapping  attr----field
       2.？？？提取完成后移除这些属性，避免和实例属性冲突
       3.新增"__mappings__"属性，保存提取出来的mapping
    类与表之间的mapping：
       1.提取类名，保存为表名  class_name ----- table_name
       2.将表名保存为"__table__"属性
    """
    def __new__(cls, name, bases, attrs):
        #name 类名  bases
        #如果是基类Model
        if name == "Model":
            return type.__new__(cls, name, bases, attrs)

        #store all subclasses info
        if not hasattr(cls, 'subclasses'):
            cls.subclasses={}
        if not name in cls.subclasses:
            cls.subclasses[name] = name
        else :
            logging.warning('redefine class: %s' %name)

        logging.info('scan orm mapping %s ......' % name)
        mappings = dict()
        primary_key = None
        for k,v in attrs.iteritems():
            if isinstance(v,Field):
                if not v.name:
                    v.name = k
                logging.info("[MAPPING] Found Mapping: %s => %s" %(k,v))

                #set primary key
                if v.primary_key:
                    #checkout dulplicate primary key
                    if primary_key:
                        raise TypeError("cannot define more than 1 priamry key in class: %s" %name)
                    #primary key cannot be updatable
                    if v.updatable:
                        logging.warning("Note: change primary key %s to non_updatable" %v.name)
                        v.updatable = False
                    #primary key cannot be nullable
                    if v.nullable:
                        logging.warning("Note: change priamry key %s to non_nullable" %v.name)
                        v.nullable = False
                    primary_key = v
                mappings[k] = v
        #check if it has a primary key
        if not primary_key:
            raise TypeError("there should be a primary key in class : %s " % name)

        #pop attrs
        for k in mappings.iterkeys():
            attrs.pop(k)

        #set table name by class name
        if not '__table__' in attrs:
            attrs['__table__'] = name.lower()
        attrs['__mappings__'] = mappings
        attrs['__primary_key__'] =primary_key
        #attrs['__sql__'] = lambda self : _gentable(attrs['__table__'], mappings)
        attrs['__sql__'] = _gentable(attrs['__table__'], mappings)
        for trigger in _triggers:
            if not trigger in attrs:
                attrs[trigger] = None
        return type.__new__(cls, name, bases, attrs)
        
class Model(dict):
    """这是一个基类
    用户在子类中定义映射关系
    需要动态扫描子类属性，从中取出类属性，完成 类->表的映射
    利用ModelMetaClass
    """
    __metaclass__ = ModelMetaClass

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        """get时生效"""
        try:
            return self[key]
        except KeyError:
            raise AttributeError('Dict Object has no attribute %s' %key)

    def __setattr__(self, key, value):
        """set时生效"""
        self[key] = value

    @classmethod
    def get(cls, pk):
        """get by primary_key"""
        d = db.selectone('select * from %s where %s = ?' %(cls.__table__, cls.__primary_key__.name), pk)
        return cls(**d) if d else None

    @classmethod
    def find_first(cls, where, *args):
        """通过where语句查询，返回一个查询结果。如果有多个结果，则返回一个第一个"""
        d = db.selectone('select * from %s %s' %(cls.__table__, where),*args)
        return cls(**d) if d else None

    @classmethod
    def find_all(cls, *args):
        """将结果以一个列表返回"""
        L = db.select('select * from %s' % cls.__table__)
        return [cls(**d) for d in L]

    @classmethod
    def find_by(cls, where, *args):
        """将符合where条件的结果以一个列表返回"""
        L = db.select('select * from %s %s' %(cls.__table__, where),*args)
        return [cls(**d) for d in L]

    @classmethod
    def count_all(cls):
        """
        执行 select count(pk) from table 
        """
        return db.select_int('select count(`%s`) from %s' %(cls.__primary_key__.name,cls.__table__))

    @classmethod
    def count_by(cls, where, *args):
        return db.select_int('select count(`%s`) from %s %s' %(cls.__primary_key__.name,cls.__table__,where), *args)

    def update(self):
        """
        如果该行字段updatable，表示该字段可更新
        继承Model的类是一个 Dict对象，该Dict的键值对会变成实例的属性
        可以通过属性来判断，该对象是否有这个字段
        如果有属性，就是用用户传入的值
        否则是用字段的default值
        """
        if self.pre_update:
            self.pre_update()

        L = []
        args = []
        for k,v in self.__mappings__.iteritems():
            if v.updatable:
                if hasattr(self,k):
                     arg = getattr(self,k)
                else:
                    arg = v.default
                    setattr(self,k,arg)
                L.append("`%s` = ?" %k)
                args.append(arg)
        pk = self.__primary_key__.name
        args.append(getattr((self,pk)))
        db.update('update `%s` set %s where %s = ?' %(self.__table__,','.join(L),pk),*args)
        return self

    def delete(self):
        """通过update接口执行sql
        sql: delete from 'user' where `id` = %s, args:(1090,)
        """
        self.pre_delete and self.pre_delete()
        pk = self.__primary_key__.name
        args = (getattr(self,pk),)
        db.update('delete from `%s` where `%s`= ?' %(self.__table__,pk), *args)
        return self

    def insert(self):
        """通过db的insert接口执行sql
        sql: insert into `user` (`password`,`last_modified`,`id`,`name`) values (%s,%s,%s,%s)
        args:('','','','')
        """
        self.pre_insert and self.pre_insert()
        params = {}
        for k,v in self.__mappings__.iteritems():
            if v.insertable:
                if not hasattr(self,k):
                    setattr(self,k,v.default)
                params[v.name] = self[k]
        db.insert(self.__table__,**params)
        return self

       
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    db.create_engine('root', '', 'test')
    db.update('drop table if exists user')
    db.update('create table user (id int primary key, name text, email text, password text, admin bool, image text)')

