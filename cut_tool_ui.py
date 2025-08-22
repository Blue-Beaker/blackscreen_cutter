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
from PyQt5.QtWidgets import QApplication,QPushButton,QLineEdit,QLabel,QListWidget,QProgressBar,QSpinBox,QListWidgetItem,QStatusBar,QVBoxLayout,QWidget,QGridLayout,QBoxLayout,QToolButton,QWidgetItem,QTextEdit,QDoubleSpinBox,QTabWidget,QCheckBox

from differential_check import DifferentialChecker
from utils import CutterConfig, parse_srt
from blackscreen_checker import VideoCutter

def dump(object:QObject):
    out=[]
    for key,value in object.__dict__.items():
        if(isinstance(value,QObject)):
            out.append(f"self.{key}: {type(value).__name__}")
    out.sort()
    print("\n".join(out))


class InputFileItem(QWidget):
    def __init__(self,filePath:str,config:CutterConfig=CutterConfig()):
        super(QWidget,self).__init__()
        self.filePath=filePath
        self.completed=False
        self.config=config
        self.grid:QGridLayout
        
        layout=QGridLayout()
        self.grid=layout
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

class InputFileItemDualInputs(InputFileItem):
    def __init__(self,filePath:str,file2Path:str,config:CutterConfig=CutterConfig()):
        super().__init__(filePath,config)
        self.file2Path=file2Path
        
        self.label2=QLabel(os.path.basename(file2Path))
        self.label2.setToolTip(self.file2Path)
        self.grid.addWidget(self.label2,1,0,1,4)

def getLayoutWidgets(layout:QBoxLayout):
    widgets=[]
    for i in range(layout.count()):
        item=layout.itemAt(i)
        if item:
            widgets.append(item.widget())
    return widgets

class Worker(QObject):
    
    finished=pyqtSignal()
    log=pyqtSignal(str)
    fileChanged=pyqtSignal(str)
    #Progress, estimated fps, estimated time
    update=pyqtSignal(float,float,float)
    
    def __init__(self):
        super().__init__()
        self.halted=False
        
    def showLog(self,text:str,**kwargs):
        self.log.emit(text)
        print(text,**kwargs)
        
    @property
    def isStarted(self):
        return False
    @property
    def isFinished(self):
        return True
    @property
    def isHalted(self):
        return False
    def run(self):
        pass
    def halt(self):
        pass

class WorkerBlackscreenDetection(Worker):
    
    cutter:VideoCutter|None=None
    threads:int
    
    def __init__(self,queuedFiles:list[InputFileItem],threads:int):
        super().__init__()
        self.queuedFiles=queuedFiles.copy()
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
        
    @property
    def isStarted(self):
        return self.cutter != None
    @property
    def isFinished(self):
        return self.cutter!=None and self.cutter.finished
    @property
    def isHalted(self):
        return self.cutter!=None and self.cutter.halted
                
class WorkerDifferentialDetection(Worker):
    cutter:DifferentialChecker|None=None
    def __init__(self,queuedFiles:list[InputFileItemDualInputs]):
        super().__init__()
        self.queuedFiles=queuedFiles.copy()
    def run(self):
        for item in self.queuedFiles:
            if self.halted:
                return
            self.convertSingle(item)
    def onUpdate(self,cutter:DifferentialChecker):
        if(self.isFinished):
            self.finished.emit()
        # self.showLog(f"{cutter.differed_frames[-1]},{cutter.estimatedTime}")
        self.update.emit(cutter.progress,cutter.estimatedFps,cutter.estimatedTime)
        
    def convertSingle(self,item:InputFileItemDualInputs):
        videoFile=item.filePath
        subtitleFile=item.file2Path
        self.fileChanged.emit(videoFile)
        with open(subtitleFile,"r") as f:
            lines=f.readlines()
        self.cutter=DifferentialChecker(videoFile,parse_srt(lines),item.config)
        self.cutter.update=partial(self.onUpdate,self.cutter)
        self.cutter.printExt=self.showLog
        self.cutter.process()
        
    @property
    def isStarted(self):
        return self.cutter != None
    @property
    def isFinished(self):
        return self.cutter!=None and self.cutter.finished
    @property
    def isHalted(self):
        return self.cutter!=None and self.cutter.halted
    
    def halt(self):
        if self.cutter:
            self.cutter.halt()
        

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
        self.buttonAddFile_2: QPushButton
        self.buttonStart_2: QPushButton
        self.buttonStop_2: QPushButton
        self.listThreads:QListWidget
        self.statusbar:QStatusBar
        self.boxInputFiles:QVBoxLayout
        self.boxInputFiles_2: QVBoxLayout
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
        self.tabWidget: QTabWidget
        self.config_diff_cannyThresold1: QSpinBox
        self.config_diff_cannyThresold2: QSpinBox
        self.config_diff_diffThresold: QDoubleSpinBox
        self.config_diff_timeOffset: QDoubleSpinBox
        self.config_show_image: QCheckBox
        
        self.config:CutterConfig=CutterConfig()
        
        # for name,item in self.__dict__.items():
        #     print(f"{name}:{type(item).__name__}")
        self.setAcceptDrops(True)
        self.buttonStop.setDisabled(True)
        
        self.buttonStart.clicked.connect(self.startConvert)
        self.buttonStart_2.clicked.connect(self.startDifferentialCheck)
        self.buttonStop.clicked.connect(self.haltConvert)
        self.buttonStop_2.clicked.connect(self.haltConvert)
        
        self.boxInputFiles.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.boxInputFiles_2.setAlignment(Qt.AlignmentFlag.AlignTop)
    
        self.buttonAddFile.clicked.connect(self.pickFiles)
        self.tabWidget.setCurrentIndex(0)
        self.initConfig()
        self.loadConfig()
        # dump(self)
                
    def pickFiles(self,event):
        dialog=QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["Video(*.mkv *.mp4 *.flv)","All Files(*)"])
        if dialog.exec_():
            files=dialog.selectedFiles()
            for file in files:
                self.addFile(file)
    def pickSingleFile(self,format=""):
        dialog=QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters([format,"All Files(*)"])
        if dialog.exec_():
            selected = dialog.selectedFiles()
            return selected[0] if selected.__len__()>0 else None
        return None

    def dragEnterEvent(self, a0: QtGui.QDragEnterEvent) -> None:
        tabIndex=self.tabWidget.currentIndex()
        if(tabIndex==2):
            return
        data=a0.mimeData()
        if not data:
            return
        text=data.text().split("\n")
        if(text.__len__()==0):
            return
        if text[0].startswith("file://"):
            if tabIndex!=3:
                a0.accept()
            elif text.__len__()==1 and text[0].endswith(".json"):
                a0.accept()
    def dropEvent(self, a0:  QtGui.QDropEvent) -> None:
        data=a0.mimeData()
        if not data:
            return
        files=data.text().split("\n")
        tabIndex=self.tabWidget.currentIndex()
        if(tabIndex==0):
            for line in files:
                if line.startswith("file://"):
                    self.addFile(line[7:])
        elif(tabIndex==1):
            videoPath=None
            subtitlePath=None
            for line in files:
                if line.endswith(".srt"):
                    subtitlePath=line[7:]
                else:
                    videoPath=line[7:]
                        
            if(videoPath==None and subtitlePath!=None):
                if(os.path.exists(subtitlePath.removesuffix(".srt"))):
                    videoPath=subtitlePath.removesuffix(".srt")
                else:
                    videoPath=self.pickSingleFile("Video(*.mkv *.mp4 *.flv)")
                
            elif(subtitlePath==None and videoPath!=None):
                if(os.path.exists(videoPath+".srt")):
                    subtitlePath=videoPath+".srt"
                else:
                    subtitlePath=self.pickSingleFile("Subtitle(*.srt)")
            if videoPath==None or subtitlePath==None:
                return
                        
            inputFileItem=InputFileItemDualInputs(filePath=videoPath,file2Path=subtitlePath,config=self.config)
            # self.listInputFiles.addItem(inputFileItem)
            self.boxInputFiles_2.addWidget(inputFileItem)
        elif(tabIndex==3):
            self.config.load(files[0][7:])
            self.postConfigLoad()
        
    
    def addFile(self,filePath:str):
        print(filePath)
        inputFileItem=InputFileItem(filePath=filePath,config=self.config)
        # self.listInputFiles.addItem(inputFileItem)
        self.boxInputFiles.addWidget(inputFileItem)
            
    #Start blackscreen check
    def startConvert(self):
        self.queuedFiles.clear()
        
        for widget in getLayoutWidgets(self.boxInputFiles):
            if(isinstance(widget,InputFileItem)):
                widget.setDisabled(True)
                if not widget.completed:
                    self.queuedFiles.append(widget)
        self.buttonStart.setDisabled(True)
        self.buttonStop.setDisabled(False)
        self.buttonStart_2.setDisabled(True)
        self.buttonStop_2.setDisabled(False)
        
        self.inputThreads.setDisabled(True)
        
        if self.worker:
            worker=self.worker
            if worker.isStarted and not worker.isFinished and not worker.isHalted:
                self.createPopupMenu()
                return
        
        self.thread=QThread(parent=self)
        # print([file.filePath for file in self.queuedFiles])
        self.worker=WorkerBlackscreenDetection(self.queuedFiles,self.inputThreads.value())
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.update.connect(self.updateProgress)
        self.worker.finished.connect(self.onFinished)
        self.worker.fileChanged.connect(self.currentFileLabel.setText)
        self.worker.log.connect(self.showLog)
        
        self.thread.start()
        
    #Start differential check
    def startDifferentialCheck(self):
        self.queuedFiles.clear()
        
        for widget in getLayoutWidgets(self.boxInputFiles_2):
            if(isinstance(widget,InputFileItemDualInputs)):
                widget.setDisabled(True)
                if not widget.completed:
                    self.queuedFiles.append(widget)
                    
        self.buttonStart.setDisabled(True)
        self.buttonStop.setDisabled(False)
        self.buttonStart_2.setDisabled(True)
        self.buttonStop_2.setDisabled(False)
        
        self.inputThreads.setDisabled(True)
        
        if self.worker:
            worker=self.worker
            if worker.isStarted and not worker.isFinished and not worker.isHalted:
                self.createPopupMenu()
                return
        
        self.thread=QThread(parent=self)
        # print([file.filePath for file in self.queuedFiles])
        self.worker=WorkerDifferentialDetection(self.queuedFiles) # type: ignore
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
                self.statusbar.showMessage(f"Processing fps:{fps:.1f}, Estimated:{estimatedTime:.1f}s",2147483647)
        except:
            traceback.print_exc()
        
    def haltConvert(self):
        if self.worker:
            print("Halting worker...")
            self.worker.halt()
        if self.thread:
            print("Terminating thread...")
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
    
    config_fields:dict={
        "configArea_x1":"x1",
        "configArea_x2":"x2",
        "configArea_y1":"y1",
        "configArea_y2":"y2",
        "config_color_thresold":"COLOR_THRESOLD",
        "config_percentage1":"PERCENTAGE_1",
        "config_percentage2":"PERCENTAGE_2",
        "config_diff_timeOffset":"timeOffset",
        "config_diff_diffThresold":"diffThresold",
        "config_diff_cannyThresold1":"cannyThresold1",
        "config_diff_cannyThresold2":"cannyThresold2",
        "config_show_image":"SHOW",
    }
    
    def initConfig(self):
        for configWidget,configField in self.config_fields.items():
            widget=self.__dict__.get(configWidget)
            if(hasattr(widget,"valueChanged")):
                widget.valueChanged.connect(partial(self.config.setField,configField)) # type: ignore
            elif(hasattr(widget,"stateChanged")):
                widget.stateChanged.connect(partial(self.config.setField,configField)) # type: ignore
    
    def postConfigLoad(self):
        for configWidget,configField in self.config_fields.items():
            widget=self.__dict__.get(configWidget)
            if(hasattr(widget,"setValue")):
                widget.setValue(self.config.getField(configField)) # type: ignore
            elif(hasattr(widget,"setChecked")):
                widget.setChecked(self.config.getField(configField)) # type: ignore
    
    def loadConfig(self):
        self.config.load()
        self.postConfigLoad()
        
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

