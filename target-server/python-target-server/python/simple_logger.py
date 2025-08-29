from datetime import datetime


def log(level: str, message: str, extras: any = None):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {level:7} :: {message}{f' :: {extras}' if extras else ''}")
