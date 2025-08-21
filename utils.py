
import json
import math
import os

import numpy as np
from PyQt5 import QtWidgets,QtGui,QtCore,uic
from PyQt5.QtCore import Qt,QThread,QObject,pyqtSignal
from PyQt5.QtWidgets import QApplication,QPushButton,QLineEdit,QLabel,QListWidget,QProgressBar,QSpinBox,QListWidgetItem,QStatusBar,QVBoxLayout,QWidget,QGridLayout,QBoxLayout,QToolButton,QWidgetItem,QTextEdit,QDoubleSpinBox,QTabWidget
# os.chdir(sys.path[0])
CONFIG_FILE_PATH='cut_tool_config.json'

class CutterConfig:
    #Whether to show image when processing. Slows down!
    def __init__(self):
        self.SHOW:bool=False #是否要在处理时显示帧. 会变慢!
            
        self.COLOR_THRESOLD:int=10 #颜色判定阈值. 0~255,0=黑,255=白
        #Thresold to determine black color. 0~255, black = 0, white = 255

        self.PERCENTAGE_1:float=99 #黑色占所选区域百分比大于此值判定开始黑屏
        self.PERCENTAGE_2:float=98 #黑色占所选区域百分比小于此值判定结束黑屏
        
        # 在此设置需要判定黑屏的范围
        self.x1:int=0
        self.x2:int=1600
        self.y1:int=0
        self.y2:int=900
    
    def setColorThresold(self,num:int):
        self.COLOR_THRESOLD=num
    def setPercentage1(self,num:float):
        self.PERCENTAGE_1=num
        self.update()
    def setPercentage2(self,num:float):
        self.PERCENTAGE_2=num
        self.update()
        
    def setX1(self,num:int):
        self.x1=num
    def setX2(self,num:int):
        self.x2=num
    def setY1(self,num:int):
        self.y1=num
    def setY2(self,num:int):
        self.y2=num
    
    def update(self):
        self.thr1=255-(self.PERCENTAGE_1*255/100)
        self.thr2=255-(self.PERCENTAGE_2*255/100)


    def crop(self,frame:np.ndarray):
        return frame[self.y1:self.y2,self.x1:self.x2]
        # return frame # 或无需裁剪
        
    def save(self,config_path=CONFIG_FILE_PATH):
        with open(config_path,"w") as f:
            dict2=self.__dict__.copy()
            dict2.pop('thr1',None)
            dict2.pop('thr2',None)
            json.dump(dict2,f,skipkeys=True,indent=2)
        
    def load(self,config_path=CONFIG_FILE_PATH):
        if(not os.path.isfile(config_path)):
            return
        with open(config_path,"r") as f:
            dict2=json.load(f)
        for key,value in dict2.items():
            self.__dict__[key]=value

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

def get_timestamp(time:float):
    return f"{'{:02d}'.format(math.floor(time/3600))}:{'{:02d}'.format(math.floor(time/60)%60)}:{'{:02d}'.format(math.floor(time)%60)},{'{:03d}'.format(math.floor(time*1000)%1000)}"


class Worker(QObject):
    
    finished=pyqtSignal()
    log=pyqtSignal(str)
    fileChanged=pyqtSignal(str)
    update=pyqtSignal(float,float,float)
    
    def __init__(self):
        super().__init__()
        self.halted=False
    def run(self):
        pass