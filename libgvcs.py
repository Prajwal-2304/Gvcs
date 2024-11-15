import argparse
import collections
import configparser
from datetime import datetime
#import grp,pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os 
import re 
import sys 
import zlib

argparser=argparse.ArgumentParser()
argsubparsers=argparser.add_subparsers(title="Commands",dest="command")
argsubparsers.required=True

def main(argv=sys.argv[1:]):
    args=argparser.parse_args(argv)
    match args.command:
        case "add": cmd_add(args)
        case "cat-file": cmd_add(args)
        case "check-ignore": cmd_add(args)
        case "checkout" : cmd_checkout(args)
        case "commit": cmd_commit(args)
        case "hash-object": cmd_hash(args)
        case "init": cmd_init(args)
        case "log": cmd_log(args)
        case "ls-files" :cmd_ls_files(args)
        case "ls-tree": cmd_ls_tree(args)
        case "rev-parse":cmd_rev_parse(args)
        case "rm": cmd_rm(args)
        case "show-ref":cmd_show_ref(args)
        case "status":cmd_stats(args)
        case "tag":cmd_tag(args)
        case _:print("Invalid command")


class GitRepo(object):
    worktree=None
    gitdir=None
    conf=None

    def __init__(self,path,force=False):
        self.worktree=path
        self.gitdir=os.path.join(path,".git")
        if not(force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git repo %s" %path)
        
        self.conf=configparser.ConfigParser()
        cf=repo_file(self,"config")

        if(cf and os.path.exists(cf)):
            self.conf.read([cf])
        elif not force:
            raise Exception("Config file missing")
        
        if not force:
            vers=int(self.conf.get("core","repositoryformatversion"))
            if vers!=0:
                raise Exception("Unsupported format version %s" %vers)
            

#returns path to gitdir
def repo_path(repo,*path):
        return os.path.join(repo.gitdir,*path)
    

#returns the path to a file 
def repo_file(repo,*path,mkdir=False):
    if repo_dir(repo,*path[:-1],mkdir=mkdir):
        return repo_path(repo,*path)
    
#returns the path to a file with missing directories created     
def repo_dir(repo,*path,mkdir=False):
    path=repo_path(repo,*path)
    if os.path.exists(path):
        if(os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a directory %s" %path)
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

#creates a git repo 
def repo_create(path):

    repo=GitRepo(path,True)
    if(os.path.exists(repo.worktree)):
        if not(os.path.isdir(repo.worktree)):
            raise Exception("%s is not a directory "%path)
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception("%s is not empty "%path)
    else:
        os.makedirs(repo.worktree)
    
    assert repo_dir(repo,"branches",mkdir=True)
    assert repo_dir(repo,"objects",mkdir=True)
    assert repo_dir(repo,"refs","tags",mkdir=True)
    assert repo_dir(repo,"refs","heads",mkdir=True)

    with open(repo_file(repo,"description"),"w") as f:
        f.write("Unnamed repo! Edit this file 'description' to name the repo \n")

    with open(repo_file(repo,"HEAD"),"w") as f:
        f.write("ref: refs/heads/master \n")

    with open(repo_file(repo,"config"),"w") as f:
        config=repo_default_config()
        config.write(f)

    return repo

#sets the default config for the repo
def repo_default_config():
    ret=configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core","repositoryformatversion","0")
    ret.set("core","filemode","false")
    ret.set("core","bare","false")
    return ret


argsp=argsubparsers.add_parser("init",help="Initialize a new repo")
argsp.add_argument("path",metavar="directory",nargs="?",default=".",help="Where to create the repo?")

def cmd_init(args):
    repo_create(args.path)



#finds the root of the function
def repo_find(path=".",required=True):
    path=os.path.realpath(path)
    
    if os.path.isdir(os.path.join(path,"/git")):
        return GitRepo(path)
    
    parent=os.path.realpath(os.path.join(path,".."))
    if parent==path:
        if required:
            raise Exception("No git directory")
        else:
            return None 
    return repo_find(parent,required)



#defines the gitobject generic class
class GitObject(object):
    def __init__(self,data=None):
        if data!=None:
            deserialize(data)
        else:
            self.init()
    def serialize(self,repo):
        
        raise Exception("Unimplemented")
    
    def deserialize(self,data):

        raise Exception("Unimplemented")

    def init():
        pass


def read_object(repo,sha):
    path=repo_file(repo,"objects",sha[0:2],sha[2:])
    if not os.path.isfile(path):
        return None

    with open(path,"rb") as f:
        raw=zlib.decompress(f.read())
        x=raw.find(b' ')
        format=raw[0:x]
        y=raw.find(b'\x00',x)
        size=int(raw[x:y].decode("ascii"))
        if(size != len(raw)-y-1):
            raise Exception("Malformed object {0}: bad length".format(sha))
        
        match format:
            case b'commit':c=GitCommit
            case b'tree':c=GitTree
            case b'tag':c=GitTag
            case b'blob':c=GitBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(format.decode("ascii"),sha))

        return c(raw[y+1:])
    
def write_object(obj,repo=None):
    data=obj.serialize()
    result=obj.format +b' '+str(len(data)).encode()+b'\x00'+data
    sha=hashlib.sha1(result).hexdigest()

    if repo:
        path=repo_file(repo,"objects",sha[0:2],sha[2:],mkdir=True)

        if not os.path.exists(path):
            with open(path,wb) as f:
                f.write(zlib.compress(result))
    return sha


class GitBlob(GitObject):
    format=b'blob'
    def serialize(self, repo):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata=data



argsp=argsubparsers.add_parser("cat-file",help="Provide content of git objects")

argsp.add_argument("type",metavar="type",choices=["blob","commit","tree","tag"],help="Specify the type")

argsp.add_argument("object",metavar="object",help="Object to display ")

def cmd_cat_file(args):
    repo=repo.find()
    cat_file(repo,args.object,format=args.type.encode())

def cat_file(repo,obj,format=None):
    obj=read_object(repo,object_find(repo,obj,format=format))
    sys.stdout.buffer.write(obj.serialize())

def object_find(repo,name,format=None,follow=True):
    return name


argsp=argsubparsers.add_parser("hash-object",help="Compute the hash for a file")

argsp.add_argument("-t",metavar="type",dest="type",choices=["blob","commit","type","tree"],default="blob",help="Specify the type")
argsp.add_argument("-w",dest="write",action="store_true",help="Actually write the object into database")
argsp.add_argument("path",help="Read object from <file>")

def cmd_hash_object(args):
    if args.write:
        repo=repo_find()
    else:
        repo=None
    with open(args.path,"rb") as fd:
        sha=object_hash(fd,args.type.encode(),repo)
        print(sha)

def object_hash(fd,format,repo=None):
    data=fd.read()
    match format:
        case b'commit':obj=GitCommit(data)
        case b'tree':obj=GitTree(data)
        case b'tag':obj=GitTag(data)
        case b'blob':obj=GitBlob(data)
        case _:
            raise Exception("Unknown type %s "%format)
    return write_object(obj,repo)


def object_find(repo,name,format=None,follow=True):
    return name


argsp=argsubparsers.add_parser("hash-object",help="Create an object ID")
argsp.add_argument("-t",metavar="type",dest="type",choices=["blob","commit","tag","tree"],default="blob",help="Specify the type")
argsp.add_argument("-w",dest="action",action="store_true",help="Write the object into db")
argsp.add_argument("path",help="Read obj from file")

def cmd_hash_object(args):
    if args.write:
        repo=repo_find()
    else:
        repo=None
    with open(args.path,"rb") as fd:
        sha=obj_hash(fd,args.type.encode(),repo)
        print(sha)

def obj_hash(fd,format,repo=None):
    data=fd.read()
    match format:
        case b'commit':obj=GitCommit(data)
        case b'blob':obj=GitBlob(data)
        case b'tree':obj=GitTree(data)
        case b'tag':obj=GitTag(data)
        case _:raise Exception("Invalid type")
    return write_object(obj,repo)

    