#! /bin/python3

import math
import os,sys,subprocess,time,datetime,re

MAX_LENGTH=2000 #每段最大长度,单位ms. 设置0禁用

END_OFFSET=-400 #每段末位置偏移,单位ms

os.chdir(sys.path[0])

class Section:
    def __init__(self,start:int,end:int) -> None:
        self.start:int=start
        self.end:int=end
    def __repr__(self) -> str:
        return self.__str__()
    def __str__(self) -> str:
        return f"{self.start}ms -> {self.end}ms"

def parse_srt_time(line:str)->int:
    try:
        split1=line.strip().split(',')
        hour=0
        minutes=0
        seconds=0
        milliseconds=0

        if(split1.__len__()>=2):
            milliseconds=int(split1[1])
            line=split1[0]

        split=line.strip().split(':')
        if(split.__len__()>=3):
            hour=int(split[0])
            minutes=int(split[1])
            seconds=int(split[2])
        elif(split.__len__()>=2):
            minutes=int(split[0])
            seconds=int(split[1])
        return hour*3600000+minutes*60000+seconds*1000+milliseconds
    except:
        return -1

def parse_srt(lines:list[str])->list[Section]:
    sections:list[Section]=[]
    lastID=0

    for line in lines:
        try:
            lastID=int(line.strip())
        except:
            pass

        if '-->' in line:
            split=line.split('-->')
            if(split.__len__()>=2):
                start=parse_srt_time(split[0].strip())
                end=parse_srt_time(split[1].strip())
                sections.append(Section(start=start,end=end))
    return sections

def to_hhmmssms_time(total_time_ms:int)->str:
    minutes='{:02d}'.format(math.floor(total_time_ms/60000))
    seconds='{:02d}'.format(math.floor(total_time_ms/1000)%60)
    milliseconds='{:03d}'.format(total_time_ms%1000)
    return f"{minutes}:{seconds}.{milliseconds}"

def to_hhmmssframe_time(total_time_ms:int,fps:int)->str:
    minutes='{:02d}'.format(math.floor(total_time_ms/60000))
    seconds='{:02d}'.format(math.floor(total_time_ms/1000)%60)
    frames='{:02d}'.format(math.floor(fps/(total_time_ms%1000)))
    return f"{minutes}:{seconds}.{frames}"

def cut_video(input:str,output:str,section:Section):
    command=f"ffmpeg -ss {to_hhmmssms_time(section.start)} -t {to_hhmmssms_time(section.end-section.start)} -i {input} -c:v hevc -c:a aac {output}"
    subprocess.run(command,shell=True)

def dump_section(section:Section,replacement:str)->str:
    return replacement.replace('{starttime}',to_hhmmssms_time(section.start)).replace('{endtime}',to_hhmmssms_time(section.end)).replace('{length}',to_hhmmssms_time(section.end-section.start))

flag_dumponly=False
filepath=""
dump_template=None
try:
    for arg in (sys.argv):
        if(arg.startswith('-')):
            if(arg.startswith('--length=')):
                MAX_LENGTH=int(arg.split('=')[1])
            if(arg.startswith('--end_offset=')):
                END_OFFSET=int(arg.split('=')[1])
            if(arg.startswith('--dump=')):
                flag_dumponly=True
                with open(arg.split('=')[1],'r') as dumpTemplate:
                    dump_template=dumpTemplate.read()
        else:
            filepath=arg
    if(filepath==""):
        print("Usage/用法: make_slices.py [--dump=DUMP_TEMPLATE_FILE] [--length=MAX_LENGTH] [--end_offset=END_OFFSET] VIDEO_FILE")
        exit()

    srtpath=filepath+".srt"
    folder=os.path.dirname(filepath)
    filename=os.path.basename(filepath)
    outFolder=os.path.join(folder,f"{filename}_split")

    with open(srtpath,"r") as srtFile:
        sections=parse_srt(srtFile.readlines())
        if(sections.__len__()>0):
            os.makedirs(outFolder,exist_ok=True)
        digits=math.ceil(math.log(sections.__len__(),10))
        formatStr='{:0'+str(digits)+'d}'

        for i in range(sections.__len__()):
            section=sections[i]
            section.end=section.end+END_OFFSET
            if(MAX_LENGTH>0):
                section.start=max(section.start,section.end-MAX_LENGTH)
            if(section.start<section.end):
                if(not flag_dumponly):
                    cut_video(filepath,os.path.join(outFolder,f"{formatStr.format(i)}.mkv"),section=section)
                elif dump_template:
                    print(dump_section(section,dump_template))
                else:
                    print(dump_section(section,"{starttime} {endtime}"))
            
finally:
    pass