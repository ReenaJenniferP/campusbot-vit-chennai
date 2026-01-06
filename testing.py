import requests

r = requests.get("https://chennai.vit.ac.in", verify=False)
print(r.status_code)
print(len(r.content))