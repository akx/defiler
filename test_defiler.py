# coding=utf-8
from defiler import defile
import requests, time


def sub():
	raise Exception("exception!")


@defile("http")
def get_something():
	try:
		sub()
	except Exception:
		pass
	time.sleep(0.05)
	resp = requests.get("https://api.github.com/users/akx")
	print len(resp.content)


get_something()