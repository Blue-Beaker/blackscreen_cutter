
import cv2,pymediainfo
import traceback
import time
import numpy as np
import numpy.typing as npt
from threading import Thread

from utils import CutterConfig,get_timestamp,Section

class DifferentialChecker:
    def update(self):
        pass
    def halt(self):
        self.halted=True
        print("Halted!")
        traceback.print_exc()
        
    def __init__(self,videoFile:str,sections:list[Section],config:CutterConfig):
        self.videoFile=videoFile
        self.cap = cv2.VideoCapture(videoFile)
        self.lastFrameImage:npt.NDArray|None=None
        self.finished=False
        self.halted=False
        self.config=config
        self.sections=sections
        self.startIndex:int=0
        self.endIndex:int=sections.__len__()-1
        
        self.offset:float=0.2
        
        self.currentIndex:int=0
        self.lastTime:float=0.0
        self.lastIndex:int=0
        self.estimatedFps:float=0.0
        self.estimatedTime:float=float("inf")
        
        info=pymediainfo.MediaInfo.parse(self.videoFile).video_tracks[0] # type: ignore
        data=info.to_data()
        # print(data)
        if(data['frame_rate_mode']!='CFR'):
            print("Variable frame rate is not supported! Please convert it to Constant frame rate at first! \n不支持可变帧速率的视频,请先转码成固定帧速率")
            return
        self.fps=float(data['frame_rate'])
        self.totalFrames=int(data['frame_count'])

        
    def process(self):
        print(self.sections)
        while ((not self.finished and not self.halted) and self.currentIndex<self.sections.__len__() and self.cap.isOpened()):
            sectionStartTime=(self.sections[self.currentIndex].start/1000)+self.offset
            sectionStartFrameIndex=round(sectionStartTime*self.fps)
            
            print(f"{self.fps},time={sectionStartTime},frames={sectionStartFrameIndex}")
            self.seekToFrame(sectionStartFrameIndex)
            ret, frame = self.cap.read()
            if(not ret):
                self.finished=True
                self.estimate()
                self.update()
                continue
            if(self.currentIndex==0):
                self.lastFrameImage=frame
            else:
                pass
            # cv2.imshow('Frame',frame)
            self.estimate()
            self.update()
            self.currentIndex=self.currentIndex+1
            print(self.currentIndex)
                
        
    def seekToFrame(self,frame:int):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
        
    def estimate(self):
        newTime=time.time()
        
        frames_per_second=(self.currentIndex-self.lastIndex)/(newTime-self.lastTime) if newTime>self.lastTime else 0
        self.estimatedFps=frames_per_second
        
        self.estimatedTime = (self.endIndex-self.currentIndex)/frames_per_second if frames_per_second>0 else float("inf")
        
        self.lastTime=newTime
        self.lastIndex=self.currentIndex
        
    @property
    def progress(self):
        return (self.currentIndex-self.startIndex)/(self.endIndex-self.startIndex)