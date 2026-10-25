from medinfer.backends.base import Backend
from medinfer.config import Settings


def create_backend(settings: Settings) -> Backend:
    if settings.backend == "mlx":
        from medinfer.backends.mlx import MLXBackend

        return MLXBackend(settings)
    if settings.backend == "mock":
        from medinfer.backends.mock import MockBackend

        return MockBackend(settings)
    from medinfer.backends.http import HTTPBackend

    return HTTPBackend(settings)
