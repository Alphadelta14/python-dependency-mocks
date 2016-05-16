
import fnmatch
import inspect


def itermembers(obj):
    if not hasattr(obj, '__dict__') and not hasattr(obj, '__dir__'):
        for attr in dir(obj):
            yield attr, getattr(attr)
    for attr in dir(obj):
        try:
            try:
                yield attr, obj.__dict__[attr]
            except KeyError:
                yield attr, getattr(obj, attr)
        except AttributeError:
            pass


class AbstractObject(object):
    """Builds a list of attributes by inspect.getmembers(obj)
    """
    priority = 0
    excludes = []

    def __init__(self, name, obj, **options):
        self.name = name
        self.attributes = []
        self.read(obj)

    def is_blacklisted(self, name):
        for pattern in self.excludes:
            # HACK: fnmatch makes patterns easier, but is meant for files
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def read(self, obj):
        for name, attr in itermembers(obj):
            if self.is_blacklisted(name):
                continue
            self.handle_attribute(name, attr)

    def handle_attribute(self, name, attr):
        if inspect.isfunction(attr) or inspect.ismethod(attr):
            self.attributes.append(Callable(name, attr))
        elif inspect.ismodule(attr):
            self.attributes.append(ModuleImport(name, attr))
        elif inspect.isclass(attr):
            self.attributes.append(ComplexClass(name, attr))
        else:
            self.attributes.append(SimpleType(name, attr))

    def to_string(self):
        # FIXME: needs a topological sort for dependencies
        return '\n'.join(value.to_string() for value in
                         sorted(self.attributes, key=lambda x: x.priority))


class Callable(AbstractObject):
    excludes = ['__*__', 'im_*', 'func_*']

    def __init__(self, name, obj):
        self.args = ''
        self.rtype = None
        self.doc = ''
        AbstractObject.__init__(self, name, obj)

    def read(self, obj):
        self.doc = inspect.getdoc(obj) or 'No documentation'
        argspec = inspect.getargspec(obj)
        args = argspec.args[:]
        for index, default in enumerate(argspec.defaults or [], 1):
            args[-index] = SimpleType(
                args[-index], default, space=0).to_string()
        self.args = ', '.join(args)
        AbstractObject.read(self, obj)

    def to_string(self):
        definition = """
def {name}({args}):
    '''{doc}
    '''
    MockedDependency.stop()
    return {rtype}
        """.format(**self.__dict__)
        for value in self.attributes:
            definition += '{}.{} = None'.format(self.name, value.name)
        return definition


class SimpleType(AbstractObject):
    def __init__(self, name, obj, **options):
        self.value = None
        self.spacestr = ' '*options.get('space', 1)
        AbstractObject.__init__(self, name, obj)

    def read(self, obj):
        for safe_type in (int, float):
            if isinstance(obj, safe_type):
                self.value = obj
                return
        if isinstance(obj, basestring):
            self.value = '\'{}\''.format(obj.encode('string_escape'))
            return
        for careful_type in (list, dict, tuple):
            if isinstance(obj, careful_type):
                self.value = careful_type()
                return
        try:
            self.value = '{}()'.format(obj.__class__.__name__)
        except AttributeError:
            self.value = None

    def to_string(self):
        return '{name}{spacestr}={spacestr}{value}'.format(**self.__dict__)


class ComplexClass(AbstractObject):
    excludes = ['__*__']
    priority = -5

    def __init__(self, name, obj):
        self.bases = 'object'
        AbstractObject.__init__(self, name, obj)

    def read(self, obj):
        bases = []
        for base in obj.__bases__:
            if inspect.getmodule(base):
                bases.append(base.__name__)
        self.bases = ', '.join(bases or ['object'])

    def to_string(self):
        definition = """
class {name}({bases}):
    def __init__(self, *args, **kwargs):
        MockedDependency.stop()
        \n""".format(**self.__dict__)
        for line in AbstractObject.to_string(self).splitlines():
            definition += '    {}\n'.format(line)
        return definition


class ModuleImport(AbstractObject):
    priority = -10

    def __init__(self, name, obj):
        self.value = None
        AbstractObject.__init__(self, name, obj)

    def read(self, obj):
        self.value = inspect.getmodule(obj)

    def to_string(self):
        if self.value.__name__ == self.name:
            return 'import {}'.format(self.value.__name__)
        return 'import {} as {}'.format(self.value.__name__, self.name)


class Module(AbstractObject):
    excludes = ['__*__']

    def to_string(self):
        return 'from dependency_mocks.runtime import MockedDependency\n'+\
            AbstractObject.to_string(self)


class Package(AbstractObject):
    pass


class Compiler(object):
    def __init__(self, name):
        self.name = name
        self.packages = []

    def add_package(self, name, obj, **options):
        pass
