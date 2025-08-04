
from abc import ABC, abstractmethod


class AbstractMockService(ABC):
    """
    Abstract base class for mock services uses to test E2E llm applications. These services will expose a 
    set of endpoints that can be used to simulate the behavior of a real service.

    """
    @abstractmethod
    def __init__(self):
        """
        Initialize the mock service.
        """
        pass


class ExampleMockService(AbstractMockService):
    """
    Example implementation of a mock service for testing purposes.
    """

    def __init__(self):
        super().__init__()
        self.data = "Mock data"

    def get_data(self):
        """
        Simulate fetching data from the mock service.
        """
        return self.data

    def set_data(self, new_data):
        """
        Simulate setting data in the mock service.
        """
        self.data = new_data
