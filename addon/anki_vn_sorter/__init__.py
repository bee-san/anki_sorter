try:
    from .addon import register_addon
except ModuleNotFoundError as error:
    if error.name != "aqt":
        raise
else:
    register_addon()
