"""Re-export entry infer — không import nặng lúc boot."""


def run():
    from modules.makeRobot import run as _run

    _run()
