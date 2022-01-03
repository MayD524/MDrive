from pprint import pprint
import tracemalloc
import sqlite3
import sys
import os

HEADER_START:list[int] = [0xAA, 0xFF]
HEADER_END:list[int]   = [0xAA, 0xFF]
FILE_START:list[int]   = [0xAF, 0x0D]
FILE_END:list[int]     = [0x0D, 0xAF]

class mfilesys:
    
    def __init__(self, db_file:str='filesys.db', firstBoot:bool=False, root_path:str='') -> None:
        self.db_file = db_file
        self.root    = root_path
        
        self.con:sqlite3.Connection = sqlite3.connect(self.db_file)
        self.cur:sqlite3.Cursor     = self.con.cursor()
        if firstBoot:
            self.init_dataBase()
            
        self.active_containers:dict[str, list[bytes]] = {}
        self.getContainers()
            
    def init_dataBase(self) -> None:
        ## delete everything in the database
        self.cur.execute("""DROP TABLE IF EXISTS containers""")
        self.cur.execute("""DROP TABLE IF EXISTS filesys""")
        
        self.cur.execute("""CREATE TABLE IF NOT EXISTS filesys (id INTEGER PRIMARY KEY, filename TEXT, filepointer INTEGER, owner TEXT)""")
        self.cur.execute("""CREATE TABLE IF NOT EXISTS containers (id INTERGER PRIMARY KEY, user TEXT, container TEXT)""")
        self.con.commit()
    
    def getContainers(self) -> None:
        ## get all users in the database
        containers = self.cur.execute("""SELECT user FROM containers""").fetchall()
        for container in containers:
            self.getContainer(container[0])
    
    def containerExists(self, filename:str) -> bool:
        self.cur.execute("""SELECT * FROM containers WHERE container = ?""", (filename,))
        if self.cur.fetchone():
            return True
        return False
    
    def fileExists(self, fname:str, owner:str) -> bool:
        self.cur.execute("""SELECT * FROM filesys WHERE filename = ? AND owner = ?""", (fname, owner))
        if self.cur.fetchone():
            return True
        return False

    def makeContainer(self, owner:str) -> None:
        filename = self.makeContainerName(owner)
        if self.containerExists(filename):
            raise FileExistsError(f"Error in creating container. {filename} already exists.")
        
        nameBuffer:bytearray   = [0x00, 0x01] + list(bytearray(filename, 'utf-8'))
        ownerBuffer:bytearray  = [0x00, 0x10] + list(bytearray(owner, 'utf-8'))
        totalFiles:bytearray   = [0x00, 0x02, 0x00]
        
        self.active_containers[owner] = HEADER_START + nameBuffer + ownerBuffer + totalFiles + HEADER_END
            
        self.cur.execute("""INSERT INTO containers (user, container) VALUES (?, ?)""", (owner, filename))
        self.con.commit()
    
    def getContainer(self, owner:str) -> None:
        fname = self.makeContainerName(owner)
            
        with open(fname, 'rb') as f:
            self.active_containers[owner] = f.read()
    
    def containerCommit(self, owner:str) -> None:
        fname = self.makeContainerName(owner)
        
        with open(fname, 'wb') as f:
            f.write(bytes(self.active_containers[owner]))
    
    
    def file_get(self, owner:str, fname:str) -> tuple[str, int]:
        if not self.fileExists(fname, owner):
            raise FileNotFoundError(f"Error in getting file. {fname} does not exist.")
        
        fp:int = self.generate_FilePointer(fname)
        data:list[bytes] = self.active_containers[owner]
        dt_start = data.index(fp) + 1
        
        retBytes:list[bytes] = data[dt_start:]
        
        ## loop over every byte pair in the list
        for i in range(0, len(retBytes)):
            if retBytes[i] == 0x0D and retBytes[i+1] == 0xAF:
                return (self.intArrayToString(retBytes[:i]), i+1)
        
        raise Exception("Error in getting file. End of file not found.")
    
    def getUserFiles(self, owner:str) -> list[str]:
        self.cur.execute("""SELECT filename FROM filesys WHERE owner = ?""", (owner,))
        return [x[1] for x in self.cur.fetchall()]
    
    def deleteFile(self, owner:str, fname:str) -> None:
        
        if not self.fileExists(fname, owner):
            raise FileNotFoundError(f"Error in deleting file. {fname} does not exist (Looks like it did this for us?).")
        
        fp:int = self.generate_FilePointer(fname)
        data:list[bytes] = self.active_containers[owner]
        dt_start = data.index(fp) - 2
        dt_end = self.file_get(owner, fname)[1] + 4
        
        self.active_containers[owner] = data[:dt_start] + data[dt_start + dt_end:]
        self.containerCommit(owner)
        
        ## delete the file from the database
        self.cur.execute("""DELETE FROM filesys WHERE filename = ? AND owner = ?""", (fname, owner))
        self.con.commit()
        
    
    def writeFile(self, owner:str, fname:str, writeData:str) -> None:
        if not self.fileExists(fname, owner):
            raise FileExistsError(f"Error in writing file. {fname} does not exist.")
        
        fp:int = self.generate_FilePointer(fname)
        data:list[bytes] = self.active_containers[owner]
        dt_start = data.index(fp)
        
        writeData:bytes = bytes(bytearray(writeData, 'utf-8'))
        if isinstance(data[:dt_start + 1], list):
            data = data[:dt_start + 1] +  list(writeData) + FILE_END
        else:
            data = data[:dt_start + 1] + writeData + bytes(FILE_END)
        self.active_containers[owner] = data
        
        self.containerCommit(owner)
    
    def makeFile(self, owner:str, filename:str) -> None:
        if self.fileExists(filename, owner):
            raise FileExistsError(f"Error in creating file. {filename} already exists.")
        
        fp:int = self.generate_FilePointer(filename)
        
        self.active_containers[owner] += bytes(FILE_START + [fp] + FILE_END)
        self.containerCommit(owner)
        
        self.cur.execute("""INSERT INTO filesys (filename, filepointer, owner) VALUES (?, ?, ?)""", (filename, fp, owner))
        self.con.commit()
        
    
    def makeContainerName(self, owner:str) -> str:
        return f"{self.root}{owner}_container.mfs"
    
    @staticmethod
    def intArrayToString(intArray:list[bytes]) -> str:
        return ''.join(chr(i) for i in intArray)
    
    @staticmethod
    def generate_FilePointer(filename:str) -> int:
        fp = 0
        
        for char in filename:
            fp += ord(char) // 2
        
        if fp % 100 == 0:
            fp += 50
        
        return fp % 100 


def display_top(snapshot, key_type='lineno', limit=3):
    import linecache
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        print("#%s: %s:%s: %.1f KiB"
              % (index, filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))

if __name__ == "__main__":
    tracemalloc.start()
    fs = mfilesys(firstBoot=False)
    #fs.makeContainer('test')
    #fs.makeFile("test", "hello.txt")
    fs.deleteFile("test", "test.txt")
    
    snapshot = tracemalloc.take_snapshot()
    display_top(snapshot)
    