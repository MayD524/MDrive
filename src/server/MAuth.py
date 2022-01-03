from pprint import pprint
import hashlib
import sqlite3
import os

class MAuth:
    def __init__(self, db_file:str, firstBoot:bool=False) -> None:
        self.db_file     = db_file
        self.conn        = sqlite3.connect(self.db_file)
        self.cur         = self.conn.cursor()
        self.total_users = 0
        
        self.userData    = {}
        
        if firstBoot:
            self.MAuthFirstBoot()
            self.total_users += 1
        else:
            self.setUserData()
        
        pprint(self.userData)
    
    def setUserData(self) -> None:
        users = self.cur.execute("SELECT * FROM users").fetchall()
        self.total_users = len(users)
        for user in users:
            self.userData[user[1]] = self.readConfig(user[3])
            print(self.userData[user[1]])
    
    def readConfig(self, config_path:str) -> dict:
        with open(config_path, 'r') as f:
            return {line.split(':')[0]:line.split(':')[1].strip() for line in f.readlines()}
        
    def MAuthFirstBoot(self) -> None:
        self.cur.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, password TEXT ,userFile TEXT)""")
        #self.cur.execute("DELETE FROM users WHERE name = 'admin'")
        if not self.userExists('admin'):
            self.makeUser('admin', 'SuperAdminPasssword6742344234!!')
        self.conn.commit()
    
    def makeUser(self, name:str, password:str) -> bool:
        ## don't allow duplicate users
        if self.userExists(name):
            return False
        password = self.hashPassword(name, password)
        userFile = f'users/{name}.udata'
        userFolder = f'users/{name}.mfs'
        self.cur.execute(f"""INSERT INTO users (name, password, userFile) VALUES (?, ?, ?)""", (name, password, userFile))
        self.conn.commit()
        with open(userFile, 'w+') as f:
            f.write(f'activeToken:{name}_user_{self.total_users}\ndataFile:{userFile}\nauthLevel:1\nhome:{userFolder}\n')
        self.userData[name] = self.readConfig(userFile)
        
        self.total_users += 1
        return True ## new user was created
    
    def getUserHome(self, username:str) -> str:
        return self.userData[username]['home']
    
    def getUserAuthToken(self, name:str) -> str:
        return self.userData[name]['activeToken']
    
    def checkAuthToken(self, name:str, authToken:str) -> bool:
        return True if self.userData[name]['activeToken'] == authToken else False
    
    def userExists(self, name:str) -> bool:
        return False if not name or self.cur.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone() is None else True
    
    def getAuthLevel(self, name:str) -> int:
        return int(self.userData[name]['authLevel'])   
    
    def checkPassword(self, name:str, password:str) -> bool:
        ## get the hashed password from the database
        hashedPassword = self.cur.execute("SELECT password FROM users WHERE name = ?", (name,)).fetchone()[0]
        return True if hashedPassword == self.hashPassword(name, password) else False
    
    def getUserFile(self, name:str) -> str:
        return self.cur.execute("SELECT userFile FROM users WHERE name = ?", (name,)).fetchone()[0]
    
    @staticmethod
    def hashPassword(userName:str, password:str) -> str:
        rounds = len(userName)
        for i in range(rounds):
            password = hashlib.sha256(password.encode()).hexdigest()
            password += userName[i]
        ## TODO: do this yes
        #password = hashlib.sha256(password.encode()).hexdigest()
        return password
        