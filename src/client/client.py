import PIL.Image as Image
import requests
import os

url = 'http://admin:SuperAdminPasssword6742344234!!@localhost:8080/'#'http://admin:SuperAdminPasssword6742344234!!@a18e-2601-182-ce00-c860-3c42-c8b2-be91-176.ngrok.io/'


#resp = requests.post(url, data={'newUser': True, 'username': 'new_user', 'password': 'test_pass'})
## makefile : filename
## writefile : filename, data : str
## deletefile : filename
## readfile : filename (gotten from GET request)
## makefolder : foldername
## deletefolder : foldername
## listfolder : foldername
## changedir : foldername
## renamefile : filename, newname : str
## renamefolder : foldername, newname : str
##

requests.put(url, data={'deletefile': "4.png"})
img = Image.open('shitpost.png')
requests.post(url, data={'makefile': "4.png"})
resp = requests.put(url, data={"writefile": "4.png", "authToken": "new_user_user_1", "username": "new_user", "data": img.tobytes()})

resp = requests.get(url + "4.png")

image = Image.frombytes('RGBA', img.size, resp.content)
img.save('4.png', format='PNG')