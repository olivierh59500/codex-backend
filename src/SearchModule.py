# Copyright (C) 2016 Deloitte Argentina.
# This file is part of CodexGigas - https://github.com/codexgigassys/
# See the file 'LICENSE' for copying permission.
import urllib
import ssdeep
import operator
import hashlib
import time

from PackageControl.PackageController import *
import tree_menu
from virusTotalApi import download_from_virus_total
from Sample import *
from Launcher import *
from Utils.Functions import clean_hash,process_file
from Utils.ProcessDate import parse_date_range
from db_pool import *

def add_file_from_vt(hash_id):
    downloaded_file=download_from_virus_total(hash_id)
    if(downloaded_file==None):
        print "add_file_from_vt(): "+str(hash_id)+" not found in VT."
        return None

    print "add_file_from_vt(): downloaded_file is not None."+str(hash_id)
    data_bin=downloaded_file
    file_id=hashlib.sha1(data_bin).hexdigest()
    #print "file_id="+str(file_id)
    pc=PackageController()
    res=pc.searchFile(file_id)
    if(res==None): # File not found. Add it to the package.
        pc.append(file_id,data_bin,True)
        print str(hash_id)+" added to DB from VT."
        #print("Added: %s" % (file_id,))
    else:
        print "add_file_from_vt(): "+str(hash_id)+" was found in the DB and asked in VT: BUG. Going to process right now."
        process_file(file_id)
    return file_id

def fuzz_search_fast(id,p,fuzz):
    #print("searching fuzz")
    block=int(fuzz.split(':')[0])
    lap=500
    coll_meta=db[env["db_metadata_collection"]]

    f1=coll_meta.find({},{"file_id":1,p:1})
    l=[]
    for f in f1:
        l.append(f)
    #print("comparing")
    dic={}
    for a in l:
        res=-1
        try:
            f_comp=a[p]
            block_comp=int(f_comp.split(':')[0])
            if(block_comp <=block+lap and block_comp>=block-lap):
                res=ssdeep.compare(f_comp,fuzz)
                if(res>0):
                    dic[a["file_id"]]=res
        except Exception, e:
            print str(e)
            #print(str(res)+"------"+str(a[p])+"-----"+str(a["file_id"]))
            continue

    #print("sorting")
    order=sorted(dic.items(),key=operator.itemgetter(1))
    ret=[]
    count=0
    for o in order[::-1]:
        ret.append(o[0])
        count+=1
        if count>=100: break
    #print("finishing")
    return ret



def searchFull(search,limit=0,retrieve={},collection="meta_container"):
    coll_meta=db[collection]
    #count=coll_meta.find(search).count()
    #print(count)
    if limit==0:
        f1=coll_meta.find(search,retrieve)
    else:
        f1=coll_meta.find(search,retrieve).limit(limit)

    l=[]
    for f in f1:
        l.append(f)

    ret=[]
    for a in l:
        #print(a)
        dic={}
        for key in retrieve.keys():
            steps=key.split('.')
            partial_res=a
            for step in steps:
                partial_res=partial_res.get(step)
                if partial_res==None: break
                if type(partial_res)==type([]):
                    partial_res=None
                    break

            legend_to_show=key.split('.')[-1]
            if (legend_to_show=="file_id"):legend_to_show="sha1"

            if (legend_to_show=="TimeDateStamp" and partial_res!=None):partial_res=time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(int(eval(partial_res),16)))
            if (legend_to_show=="timeDateStamp" and partial_res!=None):partial_res=time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(partial_res))

            dic[legend_to_show]=partial_res

        ret.append(dic)
    return ret


def translate_id(id,str_value):
    str_value=str_value.replace("+"," ")
    if(id==1):
        str_value=clean_hash(str_value)
        largo=len(str_value)
        if(largo==32):
            id=1
        elif(largo==40):
            id=2
        elif(largo==64):
            id=3
        else:
            id=1

    if(id==12):
        str_value=clean_hash(str_value)
        largo=len(str_value)
        if(largo==32):
            id=12
        elif(largo==40):
            id=13
        elif(largo==64):
            id=14
        else:
            id=12

    dic=tree_menu.ids[id]
    path=str(dic["path"])
    type_format=dic["type"]
    do=dic.get("do")
    if do is "clean_hash":
        str_value=clean_hash(str_value)
    if type_format=="string":
        value=str(urllib.unquote(str_value).decode('utf8'))
        if(id==1 or id==2 or id==3):
            value=str(urllib.unquote(str_value).decode('utf8')).lower()
        else:
            value=str(urllib.unquote(str_value).decode('utf8'))
        #print(value)
    elif type_format == "int":
        value=int(str_value)
    elif type_format == "float":
        value=float(str_value)
    elif type_format == "check":
        if str_value=="true":
            value=True
        else:
            value=False
    elif type_format == "s_string":
        aux=str(urllib.unquote(str_value).decode('utf8')).lower()
        value="'%s'"%(aux,)
    elif type_format == "s_string_no_lower":
        aux=str(urllib.unquote(str_value).decode('utf8'))
        value="'%s'"%(aux,)
    elif type_format == "s_string_nl":
        aux=str(urllib.unquote(str_value).decode('utf8'))
        value="'%s'"%(aux,)
    elif type_format == "date_range":
        aux=value=str(urllib.unquote(str_value).decode('utf8'))
        value=parse_date_range(aux)
    else:
        value = None
    return path,value

def search_by_id(data,limit,columns=[],search_on_vt=False):
    #date - mime - packager are needed for stats
    if(len(columns)==0):
        retrieve={"file_id":1,"description":1,"size":1,
                "mime_type":1,"particular_header.packer_detection":1,"particular_header.headers.file_header.TimeDateStamp":1}
    else:
        retrieve={"file_id":1,"description":1,
                "mime_type":1,"particular_header.packer_detection":1,"particular_header.headers.file_header.TimeDateStamp":1}
        for col in columns:
            dic=tree_menu.ids[int(col)]
            path=str(dic["path"])
            retrieve[path]=1

    search_list=data.split('&')
    #print(len(search_list))
    query_list=[]
    av_collection_query_list=[]
    hash_search=False
    hash_for_search=""
    for search in search_list:
        #print(search)
        str_id,str_value=search.split('=')
        id=int(str_id.split('.')[0])
        if(id<=0):
            id=0
        if str_value=="":
            continue
        p,v=translate_id(id,str_value)
        if (id==10 or id==11 or id==21):
            res=fuzz_search_fast(id,p,v)
            return res
        if(id==1 or id==2 or id==3):
            hash_search=True
            hash_for_search=v
        if(id>=10000):   # for adding AVs searchs
            av_collection_query_list.append({p:{"$regex":v,"$options":'i'}})
            continue
        query_list.append({p:v})

    if(len(query_list)>0 and len(av_collection_query_list)==0):
        query={"$and":query_list}
        res=searchFull(query,limit,retrieve)
        if(hash_search and len(res)==0 and search_on_vt):# searching in VT.
            print "search_by_id() -> add_file_from_vt()"
            sha1=add_file_from_vt(hash_for_search)
            if sha1==None: return []
            process_file(sha1)
            query={"file_id":sha1}
            res=searchFull(query,1,retrieve)
        return res

    # if the user seachs only for AV_signature and date.
    # Because VT antivirus analysis are on a seperate collection, we used to 
    # search AV signature first, collection the hashes, and then search hash by hash
    # to see if the other restrictions in the query match the hash contents in meta_container.
    # (basically split the query in two). The problem with this began when the av_anaylsis collection
    # started to grow. Possible solutions are, query the av_analysis collection with a count(), then the
    # meta_container also with a count(), and search first the collection with the lower number.
    # This will improve performance a little. Other way was to search both queries and intersect the hashes.
    # Currently, VT antivirus analysis is in a seperate collection because mongo limits the number of indexes
    # to 64. If this limit is removed, then av_analysis and meta_container should merge.
    # Meanwhile, we can get a decent performance for a small query with only date and av_signature.
    if(len(query_list)==1 and len(av_collection_query_list) > 0 and query_list[0].get('date') is not None):
        query_list.extend(av_collection_query_list)
        query={"$and":query_list}
        retrieve['sha1']=1
        retrieve.pop('description',None)
        retrieve.pop('mime_type',None)
        retrieve.pop('file_id',None)
        retrieve.pop('particular_header.headers.file_header.TimeDateStamp',None)
        retrieve.pop('particular_header.packer_detection',None)
        return searchFull(query,limit,retrieve,"av_analysis")

    if(len(av_collection_query_list)>0):
        av_query={"$and":av_collection_query_list}

    #res= ["2fa9672b7507f0e983897cfd18b24d3810bb2160","hashfile2"]

    if(len(av_collection_query_list)==0):
        return []
    else:
        # do AV search
        db_collection = env["db_metadata_collection"]
        av_coll=db.av_analysis

        if limit==0:
            av_res=av_coll.find(av_query,{"sha1":1})
        else:
            av_res=av_coll.find(av_query,{"sha1":1}).limit(limit)
        lista_av=[]
        for f in av_res:
            lista_av.append(f)
        #print(lista_av)# results of AV searchs

        res=[]
        for l in lista_av:
            query_list_for_combinated=[]
            sha1=l.get("sha1")
            query_list_for_combinated.append({"hash.sha1":sha1})
            query_list_for_combinated=query_list_for_combinated+query_list
            query={"$and":query_list_for_combinated}
            search=searchFull(query,1,retrieve)
            res=res+search
        if(limit > 0):
            return res[0:limit]
        else:
            return res

def count_documents():
    coll_meta=db[env["db_metadata_collection"]]
    val=coll_meta.count()
    return val
