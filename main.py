#!/usr/bin/env python3
"""Mở UI Train / Infer — map đọc từ map/train/ và map/infer/."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "Simulation"))


def main():
    from Ui_app.rl_app_UI import run_app

    run_app()


if __name__ == "__main__":
    main()


'''
1. Huấn luyện và chạy trên map test cho sẵn -> tính đứa nhiều điểm nhất
2. Present đủ ý -> ý hay -> sáng tạo

3. imple trên map thật (nên bàn cho flow hợp lý) -> khó hơn như nào 
= Tính điểm dựa trên 3 mục trên.


========
nhanh nhất -> 
tối ưu ->

'''