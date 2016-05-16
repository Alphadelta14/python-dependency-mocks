
class MockedDependency(StopIteration):
    @classmethod
    def stop(cls):
        raise cls('Stopping execution of code using Mocks')
