from config import load_config


_CONFIG = load_config()


def debug_print(*args, **kwargs):
    if not getattr(_CONFIG, "debug_mode", False):
        return
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)
