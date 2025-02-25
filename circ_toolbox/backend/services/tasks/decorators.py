# services/tasks/decorators.py
def step_retry_policy(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TransientError as e:
            countdown = 2 ** (kwargs.get('retries', 0) + 1)
            raise func.retry(exc=e, countdown=countdown, max_retries=5)
    return wrapper