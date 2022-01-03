from http.server import HTTPServer, SimpleHTTPRequestHandler
from mFileSystem.mfilesys import mfilesys, display_top
from http.cookies import SimpleCookie
from types import NoneType
from MAuth import MAuth
import urllib.parse
import tracemalloc
import logging
import base64
import os

MIN_USERNAME_LENGTH = 5

class mhttpServer(SimpleHTTPRequestHandler):            
    def _set_response(self, cookies:SimpleCookie=None, responsecode:int=200):
        self.send_response(responsecode)
        self.send_header('Content-Type', 'text/html')
        if cookies:
            for morsel in cookies.values():
                self.send_header('Set-Cookie', morsel.OutputString())
        self.end_headers()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"MServer\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
    def checkAuth(self) -> bool:
        ## no auth
        if self.headers.get('Authorization') == None:
            self.do_AUTHHEAD()
            self.wfile.write('<h1>401</h1><br>Success = False<br>No auth header received'.encode('utf-8'))
            return False
        
        uData = base64.b64decode(self.headers.get('Authorization')[6:]).decode('utf-8').split(':')
        print(uData)
        ## failed auth
        if not auth.userExists(uData[0]) or (auth.userExists(uData[0]) and not auth.checkPassword(uData[0], uData[1])):
            self._set_response()
            self.wfile.write('<h1>401</h1><br>Success = False<br>Failed authentication'.encode('utf-8'))
            return False
        
        return uData

    def handleCookieJar(self) -> (tuple[SimpleCookie, list[str]] | NoneType):
        ## Reads cookies and looks for authToken and username
        cookies = SimpleCookie(self.headers.get('Cookie'))
        uName = ''
        authT = ''
        for cookie in cookies.values():
            cookie = cookie.OutputString().split('=')
            match cookie[0]:
                case 'username':
                    uName = cookie[1]
               
                case 'authToken':
                    authT = cookie[1]
        
        if (uName != '' and authT != '') and not auth.checkAuthToken(uName, authT):
            self.do_AUTHHEAD()
            return None
                
        elif (authRet := self.checkAuth()) == False:
            self.do_AUTHHEAD()
            return None
        
        if uName != '' and authT != '':
            cookies['authToken'] = auth.getUserAuthToken(authRet[0])
            cookies['username'] = authRet[0]
            
        return (cookies, authRet)

    def do_GET(self):
        rVal = self.handleCookieJar()
        if rVal == None:
            return
        cookies = rVal[0]
        authRet = rVal[1]
        
        ## success auth
        logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        self._set_response(cookies)    

        if fs.fileExists(self.path.replace("/", ''), authRet[0]):
            try:
                self.wfile.write(fs.file_get(authRet[0], self.path.replace("/", ''))[0].encode('utf-8'))
            except Exception as e:
                self.wfile.write(f'<h1>500</h1><br>{e}'.encode('utf-8'))
        else:
            self.wfile.write(f'<h1>404</h1><br>File not found'.encode('utf-8'))
    
    ## handling user FILE DATA (upload)
    def do_PUT(self):
        """
            Handles the following requests:
                - writefile
                - deletefile
        """
        
        CookieJar = self.handleCookieJar()
        
        if CookieJar == None:
            return
        
        cookies:SimpleCookie = CookieJar[0]
        authRet:list[str]    = CookieJar[1]
        responseCode:int     = 200
        
        content_length = int(self.headers['Content-Length'])
        put_data = self.rfile.read(content_length).decode('utf-8')
        logging.info("PUT request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
                     str(self.path), str(self.headers), put_data)
        
        put_data = self.requestParse(put_data)
        
        
        writeBuffer:list[str] = []      
        if 'writefile' in put_data:
            fname = urllib.parse.unquote_plus(put_data['writefile'])
            data = urllib.parse.unquote_plus(put_data['data'])
            if fs.fileExists(fname, authRet[0]):
                fs.writeFile(authRet[0], fname, data)
                writeBuffer.append("<h1>200</h1><br>Successfully wrote to file")
            else:
                writeBuffer.append("<h1>404</h1><br>File not found or not authorized")
                responseCode = 404
                
        elif 'deletefile' in put_data:
            path = urllib.parse.unquote_plus(put_data['deletefile'])
            if fs.fileExists(path, authRet[0]):
                fs.deleteFile(authRet[0], path)
                writeBuffer.append("<h1>200</h1><br>Successfully deleted file")
            else:
                writeBuffer.append("<h1>404</h1><br>File not found or not authorized (ig it didn't like you)")
                responseCode = 404
                
                
        self._set_response(cookies, responseCode)
        self.wfile.write(bytes('<br>'.join(writeBuffer), 'utf-8'))
                
    ## handling user DATA
    def do_POST(self):
        """
            Handles the following requests:
                - newUser
                - makefile
                - listfolder
                - renamefile
        """
        
        CookieJar = self.handleCookieJar()
        
        if CookieJar == None:
            return
        
        cookies:SimpleCookie = CookieJar[0]
        authRet:list[str]    = CookieJar[1]
        responseCode:int     = 200
        
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length).decode('utf-8') # <--- Gets the data itself
        logging.info("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
                str(self.path), str(self.headers), post_data)
        post_data = self.requestParse(post_data)
        
        if 'newUser' in post_data and post_data['newUser'] == 'True':
            if len(post_data['username']) < MIN_USERNAME_LENGTH:
                self._set_response(cookies, 500)
                self.wfile.write(f'<h1>500</h1><br>Username must be at least {MIN_USERNAME_LENGTH} characters long not {len(post_data["username"])}'.encode('utf-8'))
                return
            if auth.makeUser(post_data['username'], post_data['password']):
                self._set_response(cookies)
                fs.makeContainer(post_data['username'])
                fs.containerCommit(post_data['username'])
                self.wfile.write('<h1>200</h1><br>Success = True<br>User created'.encode('utf-8'))
                return
            self.do_AUTHHEAD()
            
        ## auth user
        if self.checkAuth() == False:
            self.do_AUTHHEAD()
            return
        
        writeBuffer:list[str] = []
        if 'makefile' in post_data:
            fname = urllib.parse.unquote_plus(post_data['makefile'])
            if fs.fileExists(fname, authRet[0]):
                writeBuffer.append('<h1>409</h1><br>Success = False<br>File already exists')
                responseCode = 409
            
            else:
                fs.makeFile(authRet[0], fname)
                writeBuffer.append("<h1>200</h1><br>Success = True<br>File created")
                
        elif 'listfolder' in post_data:
            path = auth.getUserHome(authRet[0]) + urllib.parse.unquote_plus(post_data['listfolder'])
            print(path)
            if os.path.exists(path):
                files = os.listdir(path)
                writeBuffer.append(f'<h3>{path}</h3>' + '<br>'.join(files))
                
            else:
                writeBuffer.append('<h1>404</h1><br>Folder not found')
                responseCode = 404
                
        elif 'renamefile' in post_data:
            path = auth.getUserHome(authRet[0]) + urllib.parse.unquote_plus(post_data['renamefile'])
            print(path)
            if os.path.exists(path):
                ## rename file
                os.rename(path, auth.getUserHome(authRet[0]) + urllib.parse.unquote_plus(post_data['newname']))
                writeBuffer.append('<h1>200</h1><br>Success = True<br>File renamed')
            else:
                writeBuffer.append('<h1>404</h1><br>File not found')
                responseCode = 404     
                
        self._set_response(cookies, responseCode)
        self.wfile.write('<br>'.join(writeBuffer).encode('utf-8'))

    @staticmethod
    def requestParse(requst:str) -> dict:
        parts = requst.split('&')
        return {part.split('=')[0]:part.split('=')[1] for part in parts}
        
def run(server_class=HTTPServer, handler_class=mhttpServer, port=8080):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logging.info('Starting httpd...\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')
    logging.info('Server stopped')
    

if __name__ == '__main__':
    tracemalloc.start()
    first_boot = False
    auth = MAuth(firstBoot=first_boot, db_file='databases/users.db')
    fs   = mfilesys(firstBoot=first_boot, root_path='users/', db_file='databases/filesys.db') 
    if first_boot:
        fs.makeContainer('admin')
        fs.containerCommit('admin')
    run()
    snapshot = tracemalloc.take_snapshot()
    display_top(snapshot)