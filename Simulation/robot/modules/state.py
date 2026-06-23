import sys
import os
from node import Node

'''
Đặc tả State (dùng cho cả simulation và robot thật):
[State này dùng cho cả inference và training]
'''
class State:
    def __init__(self,):
        self.value = encode_state()

    def encode_state(self):

