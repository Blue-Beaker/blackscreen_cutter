#! /bin/python3 

#Usage: cut.py [VIDEO FILE]
#用法: cut.py [视频文件]

import datetime
import math
import os,sys,cv2,pymediainfo
import traceback
import time
import numpy as np
from threading import Thread

from PyQt5 import QtWidgets,QtGui,QtCore,uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication,QPushButton,QLineEdit,QLabel,QListWidget,QProgressBar,QSpinBox,QListWidgetItem,QStatusBar,QVBoxLayout,QWidget,QGridLayout

# os.chdir(sys.path[0])
class CutterConfig:
    THREADS=3 #线程数量 不是越多越好 建议自己用不同的值测试 选择预计剩余时间最短者

    SHOW=False #是否要在处理时显示帧. 会变慢!
    #Whether to show image when processing. Slows down!

    COLOR_THRESOLD=10 #颜色判定阈值. 0~255,0=黑,255=白
    #Thresold to determine black color. 0~255, black = 0, white = 255

    PERCENTAGE_1=99 #黑色占所选区域百分比大于此值判定开始黑屏
    PERCENTAGE_2=98 #黑色占所选区域百分比小于此值判定结束黑屏
    
    def update(self):
        self.thr1=255-(self.PERCENTAGE_1*255/100)
        self.thr2=255-(self.PERCENTAGE_2*255/100)

    # 在此设置需要判定黑屏的范围
    x1=0
    x2=1600
    y1=0
    y2=900

    def crop(self,frame:np.ndarray):
        return frame[self.y1:self.y2,self.x1:self.x2]
        # return frame # 或无需裁剪



def get_timestamp(time:float):
    return f"{'{:02d}'.format(math.floor(time/3600))}:{'{:02d}'.format(math.floor(time/60)%60)}:{'{:02d}'.format(math.floor(time)%60)},{'{:03d}'.format(math.floor(time*1000)%1000)}"
    
class VideoWorkerThreaded(Thread):
    
    def __init__(self,videoFile:str,startFrame:int,endFrame:int,threadID:int,fps:float,config:CutterConfig):
        Thread.__init__(self)
        self.cap = cv2.VideoCapture(videoFile)
        self.startFrame=startFrame
        self.endFrame=endFrame
        self.curFrame=startFrame
        self.last_frame_black=False
        self.startFrames:list[int]=[]
        self.endFrames:list[int]=[]
        self.cap.set(cv2.CAP_PROP_POS_FRAMES,startFrame-1)
        self.lastMean=0
        self.threadID=threadID
        self.fps=fps
        self.finished=False
        self.config=config
        
    @property
    def progress(self):
        return (self.curFrame-self.startFrame)/(self.endFrame-self.startFrame)
    
    def run(self):
        self.process()
    def process(self):
        while ((not self.finished) and self.cap.isOpened()):
            # 由于已经二值化,此平均值反映的是非黑色部分占总画面的比例. 
            mean=self.process_frame()
            self.lastMean=mean
            if(self.last_frame_black):
                if mean>self.config.thr2: # 黑屏结束判定
                    self.last_frame_black=False
                    self.startFrames.append(self.curFrame)
                    print(f"<-{get_timestamp(self.curFrame/self.fps)}")
                    
            else:
                if mean<self.config.thr1: # 黑屏开始判定
                    self.last_frame_black=True
                    # 如果片段一开始就是黑屏, 不额外判定
                    if self.curFrame>self.startFrame:
                        self.endFrames.append(self.curFrame)
                        print(f"->{get_timestamp(self.curFrame/self.fps)}")

            self.curFrame=self.curFrame+1
            
            if(self.curFrame>=self.endFrame):
                self.finished=True
            
    def process_frame(self) -> float:
        # Loop until the end of the video
        # Capture frame-by-frame
        ret, frame = self.cap.read()

        if(not ret):
            self.finished=True
            return 255.0
        
        frame=self.config.crop(frame)
        
        frame = cv2.resize(frame, (320,180), fx = 0, fy = 0,
                            interpolation = cv2.INTER_LINEAR)

        if self.config.SHOW:
            cv2.imshow('Frame', frame)

        # # conversion of BGR to grayscale is necessary to apply this operation
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        Thresh:np.ndarray
        ret2,Thresh = cv2.threshold(gray,self.config.COLOR_THRESOLD ,255, cv2.THRESH_BINARY)
        
        mean=Thresh.mean()

        if self.config.SHOW:
            cv2.imshow('Thresh', Thresh)
        return mean
class VideoCutter:
    def process(self):
        self.config.update()
        frames_per_thread=self.totalFrames//self.config.THREADS
        #为每个线程分配处理区段
        for i in range(self.config.THREADS):
            thread=VideoWorkerThreaded(self.videoFile,i*frames_per_thread-(i>0),min((i+1)*frames_per_thread,self.totalFrames),i,self.fps,self.config)
            self.threads.append(thread)
            
        lastTimes={}
        lastFrames={}
        #启动线程
        for thread in self.threads:
            thread.start()
            self.uncompletedThreads.append(thread)
            lastTimes[thread.threadID]=time.time()
            lastFrames[thread.threadID]=thread.curFrame
            
        self.halted=False
        #监视线程
        try:
            while self.uncompletedThreads:
                print("")
                for thread in self.threads:
                    if thread.progress>=1 and thread in self.uncompletedThreads:
                        self.uncompletedThreads.remove(thread)
                        
                    lastTime=lastTimes[thread.threadID]
                    lastFrame=lastFrames[thread.threadID]
                    newTime=time.time()
                    
                    frames_per_second=(thread.curFrame-lastFrame)/(newTime-lastTime) if newTime>lastTime else 0
                    
                    estimated = f"{(thread.endFrame-thread.curFrame)/frames_per_second:.1f}s" if frames_per_second>0 else "INFINITE!"
                    
                    lastTimes[thread.threadID]=newTime
                    lastFrames[thread.threadID]=thread.curFrame
                    
                    print(f"Thread {thread.threadID}: frames={thread.curFrame}/{thread.endFrame}\t{thread.progress*100:.2f}%\tmean={thread.lastMean:.1f}\tfps={frames_per_second:.1f}\testimated={estimated}")
                time.sleep(1)
        except:
            self.halt()
        
        for thread in self.threads:
            self.startFrames.extend(thread.startFrames)
            self.endFrames.extend(thread.endFrames)
        print(self.startFrames,self.endFrames)
        if not self.halted:
            self.write_to_subtitle()
    def halt(self):
        self.halted=True
        print("Halted! exiting threads")
        traceback.print_exc()
        for thread in self.threads:
            thread.finished=True
        
    def write_to_subtitle(self):
        id=0
        with open(self.videoFile+".srt","w") as subtitleFile:
            if not self.startFrames or not self.endFrames:
                return
            
            if(self.startFrames[0]>self.endFrames[0]):
                self.startFrames.insert(0,0)
                
            while id<len(self.startFrames) and id<len(self.endFrames):
                
                while (self.startFrames[id]>self.endFrames[id]):
                    self.endFrames.pop(id)
                    
                start=self.startFrames[id]
                end=self.endFrames[id]
                for line in self.gen_subtitle_line(id+1,start,end):
                    subtitleFile.write(line+"\n")
                id=id+1

    def get_timestamp_by_frame(self,frame:int):
        return get_timestamp(frame/self.fps)

    def gen_subtitle_line(self,id:int,start_frame:int,end_frame:int):
        return [
            str(id),
            f"{self.get_timestamp_by_frame(start_frame)} --> {self.get_timestamp_by_frame(end_frame)}",
            f"#{id}",
            ""
        ]

    def __init__(self,videoname,config:CutterConfig|None=None):
        self.subtitleLines=[]
        self.threads:list[VideoWorkerThreaded]=[]
        self.videoFile=videoname
        self.startFrames=[]
        self.endFrames=[]
        self.finished=False
        self.uncompletedThreads=[]
        self.halted=False
        
        if not config:
            config=CutterConfig()
        self.config=config

        info=pymediainfo.MediaInfo.parse(videoname).video_tracks[0] # type: ignore
        data=info.to_data()
        # print(data)
        if(data['frame_rate_mode']!='CFR'):
            print("Variable frame rate is not supported! Please convert it to Constant frame rate at first! \n不支持可变帧速率的视频,请先转码成固定帧速率")
            return
        self.fps=float(data['frame_rate'])
        self.totalFrames=int(data['frame_count'])

        self.frameIndex=0
        self.last_frame_black=False

    def close(self):
        # self.subtitle_file.close()
        # release the video capture object
        # self.cap.release()
        # Closes all the windows currently opened.
        cv2.destroyAllWindows()

class InputFileItem(QWidget):
    
    def __init__(self,filePath:str):
        super(QWidget,self).__init__()
        self.filePath=filePath
        layout=QGridLayout()
        self.setLayout(layout)
        layout.addWidget(QLabel(os.path.basename(filePath)),0,0,1,5)
        self.progress=QProgressBar()
        layout.addWidget(self.progress,1,0,1,5)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)

class App(QtWidgets.QMainWindow):
    
    cutter:VideoCutter|None=None
    def __init__(self):
        super(App, self).__init__()
        uic.loadUi(os.path.join(sys.path[0],"cut_tool.ui"), self)
        self.label:QLabel
        self.inputThreads:QSpinBox
        self.buttonAddFile:QPushButton
        self.buttonStart:QPushButton
        self.buttonStop:QPushButton
        self.listThreads:QListWidget
        self.progress:QProgressBar
        self.convertInfo:QLabel
        self.statusbar:QStatusBar
        self.boxInputFiles:QVBoxLayout
        # for name,item in self.__dict__.items():
        #     print(f"{name}:{type(item).__name__}")
        self.setAcceptDrops(True)
        self.buttonStop.setDisabled(True)
        
        self.buttonStart.clicked.connect(self.startConvert)
        self.buttonStop.clicked.connect(self.haltConvert)
        
        self.boxInputFiles.setAlignment(Qt.AlignmentFlag.AlignTop)
    
    def dragEnterEvent(self, a0: QtGui.QDragEnterEvent) -> None:
        data=a0.mimeData()
        if not data:
            return
        text=data.text()
        
        if text.startswith("file://"):
            a0.accept()
    def dropEvent(self, a0:  QtGui.QDropEvent) -> None:
        data=a0.mimeData()
        if not data:
            return
        text=data.text()
        
        for line in text.split("\n"):
            if line.startswith("file://"):
                self.addFile(line[7:])
    
    def addFile(self,filePath:str):
        print(filePath)
        inputFileItem=InputFileItem(filePath=filePath)
        # self.listInputFiles.addItem(inputFileItem)
        self.boxInputFiles.addWidget(inputFileItem)
    
    def startConvert(self):
        self.buttonStart.setDisabled(True)
        self.buttonStop.setDisabled(False)
        if self.cutter and not self.cutter.finished and not self.cutter.halted:
            self.createPopupMenu()
        
    def haltConvert(self):
        self.buttonStart.setDisabled(False)
        self.buttonStop.setDisabled(True)
        if self.cutter:
            self.cutter.halt()
            
    def onFinished(self):
        self.buttonStart.setDisabled(False)
        self.buttonStop.setDisabled(True)
        
        
app = QApplication(sys.argv)
window = App()
try:
    window.show()
    app.exec()
finally:
    pass

# if(sys.argv.__len__()<2):
#     print("Usage: cut.py [VIDEO FILE]\n用法: cut.py [视频文件]")
#     exit()
# try:
#     print(f"Thresold: {thr1,thr2}")
#     cutter = VideoCutter(sys.argv[1])
#     cutter.process()
# finally:
#     cutter.close()

