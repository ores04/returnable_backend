"""This file contains decorators used to inject mock services into tests."""


def test_with_mock_service(mock_service_class):
    """
    Decorator to inject a mock service into a test function.

    Args:
        mock_service_class: The class of the mock service to inject.
    """

    def decorator(test_func):
        def wrapper(*args, **kwargs):
            # Create an instance of the mock service
            mock_service = mock_service_class()
            # Inject the mock service into the test function
            return test_func(mock_service, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    from mock_service import ExampleMockService

    # Example usage of the decorator
    @test_with_mock_service(ExampleMockService)
    def example_test(mock_service):
        print("Running test with mock service:", mock_service)

    # Run the example test
    example_test()
