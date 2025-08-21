#! /bin/python3 

#Usage: cut.py [VIDEO FILE]
#用法: cut.py [视频文件]

import datetime
from functools import partial
import math
import os,sys,cv2,pymediainfo
import traceback
import time
import numpy as np
import json
from threading import Thread

from PyQt5 import QtWidgets,QtGui,QtCore,uic
from PyQt5.QtCore import Qt,QThread,QObject,pyqtSignal
from PyQt5.QtWidgets import QApplication,QPushButton,QLineEdit,QLabel,QListWidget,QProgressBar,QSpinBox,QListWidgetItem,QStatusBar,QVBoxLayout,QWidget,QGridLayout,QBoxLayout,QToolButton,QWidgetItem,QTextEdit,QDoubleSpinBox

CONFIG_FILE_PATH='cut_tool_config.json'


def dump(object:QObject):
    out=[]
    for key,value in object.__dict__.items():
        if(isinstance(value,QObject)):
            out.append(f"self.{key}: {type(value).__name__}")
    out.sort()
    print("\n".join(out))

# os.chdir(sys.path[0])
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
        
    def save(self):
        with open(CONFIG_FILE_PATH,"w") as f:
            dict2=self.__dict__.copy()
            dict2.pop('thr1',None)
            dict2.pop('thr2',None)
            json.dump(dict2,f,skipkeys=True,indent=2)
        
    def load(self):
        if(not os.path.isfile(CONFIG_FILE_PATH)):
            return
        with open(CONFIG_FILE_PATH,"r") as f:
            dict2=json.load(f)
        for key,value in dict2.items():
            self.__dict__[key]=value


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
        
        self.lastTime:float=0.0
        self.lastFrame:int=0
        self.estimatedFps:float=0.0
        self.estimatedTime:float=float("inf")
        
    def estimate(self):
        newTime=time.time()
        
        frames_per_second=(self.curFrame-self.lastFrame)/(newTime-self.lastTime) if newTime>self.lastTime else 0
        self.estimatedFps=frames_per_second
        
        self.estimatedTime = (self.endFrame-self.curFrame)/frames_per_second if frames_per_second>0 else float("inf")
        
        self.lastTime=newTime
        self.lastFrame=self.curFrame
        
    @property
    def progress(self):
        return (self.curFrame-self.startFrame)/(self.endFrame-self.startFrame)
    
    def run(self):
        self.process()
    def printExt(self,text):
        pass
        
    def print(self,text,**kwargs):
        self.printExt(text)
        print(text,**kwargs)
        
    def process(self):
        while ((not self.finished) and self.cap.isOpened()):
            # 由于已经二值化,此平均值反映的是非黑色部分占总画面的比例. 
            mean=self.process_frame()
            self.lastMean=mean
            if(self.last_frame_black):
                if mean>self.config.thr2: # 黑屏结束判定
                    self.last_frame_black=False
                    self.startFrames.append(self.curFrame)
                    self.print(f"<-{get_timestamp(self.curFrame/self.fps)}")
                    
            else:
                if mean<self.config.thr1: # 黑屏开始判定
                    self.last_frame_black=True
                    # 如果片段一开始就是黑屏, 不额外判定
                    if self.curFrame>self.startFrame:
                        self.endFrames.append(self.curFrame)
                        self.print(f"->{get_timestamp(self.curFrame/self.fps)}")

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
    
    def print(self,text,**kwargs):
        print(text,**kwargs)
    
    def update(self):
        pass
        
    def process(self):
        self.config.update()
        frames_per_thread=self.totalFrames//self.THREADS
        #为每个线程分配处理区段
        for i in range(self.THREADS):
            thread=VideoWorkerThreaded(self.videoFile,i*frames_per_thread-(i>0),min((i+1)*frames_per_thread,self.totalFrames),i,self.fps,self.config)
            thread.printExt=self.print
            self.threads.append(thread)
            
        #启动线程
        for thread in self.threads:
            thread.start()
            self.uncompletedThreads.append(thread)
            
            thread.lastTime=time.time()
            thread.lastFrame=thread.curFrame
            
        self.halted=False
        #监视线程
        try:
            while self.uncompletedThreads:
                print("")
                for thread in self.threads:
                    if thread.progress>=1 and thread in self.uncompletedThreads:
                        self.uncompletedThreads.remove(thread)
                        
                    thread.estimate()
                    
                    print(f"Thread {thread.threadID}: frames={thread.curFrame}/{thread.endFrame}\t{thread.progress*100:.2f}%\tmean={thread.lastMean:.1f}\tfps={thread.estimatedFps:.1f}\testimated={thread.estimatedTime:.1f}s")
                    
                self.update()
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
        self.uncompletedThreads.clear()
        
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

    def __init__(self,videoname,threads:int=3,config:CutterConfig|None=None):
        self.subtitleLines=[]
        self.threads:list[VideoWorkerThreaded]=[]
        self.videoFile=videoname
        self.startFrames=[]
        self.endFrames=[]
        self.finished=False
        self.uncompletedThreads=[]
        self.halted=False
        self.THREADS=threads
        
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
    def __init__(self,filePath:str,config:CutterConfig=CutterConfig()):
        super(QWidget,self).__init__()
        self.filePath=filePath
        self.completed=False
        self.config=config
        
        layout=QGridLayout()
        self.setLayout(layout)
        
        self.label=QLabel(os.path.basename(filePath))
        self.label.setToolTip(self.filePath)
        layout.addWidget(self.label,0,0,1,4)
        
        self.removeButton=QToolButton()
        self.removeButton.setText("-")
        self.removeButton.clicked.connect(self.remove)
        layout.addWidget(self.removeButton,0,4,1,1)
        
        line=QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(line,2,0,1,5)
        
    def setDisabled(self,disabled:bool):
        self.removeButton.setDisabled(disabled)
        
    def remove(self):
        parent=self.parent()
        if isinstance(parent,QWidget):
            layout=parent.layout()
            if isinstance(layout,QBoxLayout):
                layout.removeWidget(self)

def getLayoutWidgets(layout:QBoxLayout):
    widgets=[]
    for i in range(layout.count()):
        item=layout.itemAt(i)
        if item:
            widgets.append(item.widget())
    return widgets

class Worker(QObject):
    
    finished=pyqtSignal()
    update=pyqtSignal(float,float,float)
    log=pyqtSignal(str)
    fileChanged=pyqtSignal(str)
    cutter:VideoCutter|None=None
    threads:int
    
    def __init__(self,queuedFiles:list[InputFileItem],threads:int):
        super(QObject,self).__init__()
        self.queuedFiles=queuedFiles.copy()
        self.halted=False
        self.threads=threads
        
    def onUpdate(self,cutter:VideoCutter):
        if cutter:
            fps=0.0
            progress=100.0
            estimatedTime=0.0
            for thr in cutter.threads:
                progress=min(progress,thr.progress)
                fps=fps+thr.estimatedFps
                estimatedTime=max(estimatedTime,thr.estimatedTime)
            self.update.emit(progress,fps,estimatedTime)
    
    def showLog(self,text:str,**kwargs):
        self.log.emit(text)
        print(text,**kwargs)
        
    def halt(self):
        self.halted=True
        if self.cutter:
            self.cutter.halt()
    def run(self):
        for item in self.queuedFiles:
            if self.halted:
                return
            try:
                self.log.emit(item.filePath)
                self.fileChanged.emit(item.filePath)
                cutter=VideoCutter(item.filePath,self.threads,item.config)
                self.cutter=cutter
                cutter.update=partial(self.onUpdate,cutter)
                cutter.print=self.showLog
                cutter.process()
                if not cutter.halted:
                    item.completed=True
                
                self.log.emit("File completed!")
            finally:
                cutter.close()
                
        self.fileChanged.emit("Idle")
        self.finished.emit()
        self.log.emit("All completed!")
        print("All completed!")
                

class App(QtWidgets.QMainWindow):
    
    thread:QThread|None=None
    def __init__(self):
        super(App, self).__init__()
        uic.loadUi(os.path.join(sys.path[0],"cut_tool.ui"), self)
        self.label:QLabel
        self.inputThreads:QSpinBox
        self.buttonAddFile:QPushButton
        self.buttonStart:QPushButton
        self.buttonStop:QPushButton
        self.listThreads:QListWidget
        self.statusbar:QStatusBar
        self.boxInputFiles:QVBoxLayout
        self.logOutput:QListWidget
        self.queuedFiles:list[InputFileItem]=[]
        self.progressBar:QProgressBar
        self.currentFileLabel:QLabel
        self.worker:Worker|None=None
        self.configArea_x1: QSpinBox
        self.configArea_x2: QSpinBox
        self.configArea_y1: QSpinBox
        self.configArea_y2: QSpinBox
        self.config_color_thresold: QSpinBox
        self.config_percentage1: QDoubleSpinBox
        self.config_percentage2: QDoubleSpinBox
        
        self.config:CutterConfig=CutterConfig()
        
        # for name,item in self.__dict__.items():
        #     print(f"{name}:{type(item).__name__}")
        self.setAcceptDrops(True)
        self.buttonStop.setDisabled(True)
        
        self.buttonStart.clicked.connect(self.startConvert)
        self.buttonStop.clicked.connect(self.haltConvert)
        
        self.boxInputFiles.setAlignment(Qt.AlignmentFlag.AlignTop)
    
        self.buttonAddFile.clicked.connect(self.pickFiles)
        self.initConfig()
        self.loadConfig()
        dump(self)
                
    def pickFiles(self,event):
        dialog=QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["Video(*.mkv *.mp4 *.flv)","All Files(*)"])
        if dialog.exec_():
            files=dialog.selectedFiles()
            for file in files:
                self.addFile(file)

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
        inputFileItem=InputFileItem(filePath=filePath,config=self.config)
        # self.listInputFiles.addItem(inputFileItem)
        self.boxInputFiles.addWidget(inputFileItem)
    
    def startConvert(self):
        self.queuedFiles.clear()
        
        for widget in getLayoutWidgets(self.boxInputFiles):
            if(isinstance(widget,InputFileItem)):
                widget.setDisabled(True)
                if not widget.completed:
                    self.queuedFiles.append(widget)
        self.buttonStart.setDisabled(True)
        self.buttonStop.setDisabled(False)
        self.inputThreads.setDisabled(True)
        
        if self.worker:
            worker=self.worker
            if worker.cutter and not worker.cutter.finished and not worker.cutter.halted:
                self.createPopupMenu()
                return
        
        self.thread=QThread(parent=self)
        # print([file.filePath for file in self.queuedFiles])
        self.worker=Worker(self.queuedFiles,self.inputThreads.value())
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.update.connect(self.updateProgress)
        self.worker.finished.connect(self.onFinished)
        self.worker.fileChanged.connect(self.currentFileLabel.setText)
        self.worker.log.connect(self.showLog)
        
        self.thread.start()
        
        
                
    def showLog(self,line:str):    
        self.logOutput.addItem(QListWidgetItem(line))
        
    def updateProgress(self,progress:float,fps:float,estimatedTime:float):
        try:
            self.progressBar.setValue(math.floor(progress*100))
            if self.worker:
                self.statusbar.showMessage(f"Processing fps:{fps:.1f}(avg.{fps/self.worker.threads:.1f}), Estimated:{estimatedTime:.1f}s",2147483647)
        except:
            traceback.print_exc()
        
    def haltConvert(self):
        if self.worker:
            self.worker.halt()
        if self.thread:
            self.thread.terminate()
        self.onFinished()
            
    def onFinished(self):
        try:
            self.buttonStart.setDisabled(False)
            self.buttonStop.setDisabled(True)
            self.inputThreads.setDisabled(False)
            
            for widget in getLayoutWidgets(self.boxInputFiles):
                if(isinstance(widget,InputFileItem)):
                    widget.setDisabled(False)
                    self.queuedFiles.clear()
        except:
            traceback.print_exc()
                
    def closeEvent(self,event:QtGui.QCloseEvent):
        try:
            self.saveConfig()
            if self.worker:
                self.worker.halt()
            if self.thread:
                self.thread.terminate()
                while self.thread.isRunning():
                    time.sleep(0.1)
            event.accept()
        except:
            traceback.print_exc()
    
    def initConfig(self):
        self.configArea_x1.valueChanged.connect(self.config.setX1)
        self.configArea_x2.valueChanged.connect(self.config.setX2)
        self.configArea_y1.valueChanged.connect(self.config.setY1)
        self.configArea_y2.valueChanged.connect(self.config.setY2)
        self.config_color_thresold.valueChanged.connect(self.config.setColorThresold)
        self.config_percentage1.valueChanged.connect(self.config.setPercentage1)
        self.config_percentage2.valueChanged.connect(self.config.setPercentage2)
    
    def loadConfig(self):
        self.config.load()
        self.configArea_x1.setValue(self.config.x1)
        self.configArea_x2.setValue(self.config.x2)
        self.configArea_y1.setValue(self.config.y1)
        self.configArea_y2.setValue(self.config.y2)
        self.config_color_thresold.setValue(self.config.COLOR_THRESOLD)
        self.config_percentage1.setValue(self.config.PERCENTAGE_1)
        self.config_percentage2.setValue(self.config.PERCENTAGE_2)
        self.config.save()
        
    def saveConfig(self):
        self.config.save()
    
        
        
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

