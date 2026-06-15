# 演示项目

初始实现会直接抛出 Python 的 `ZeroDivisionError`。预期修复方式是先校验除数，
当除数为零时抛出含义明确的 `ValueError`。
