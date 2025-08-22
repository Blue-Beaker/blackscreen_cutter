
import sys
import cv2,pymediainfo
import traceback
import time
import numpy as np
import numpy.typing as npt
from threading import Thread

from utils import CutterConfig,get_timestamp,Section, parse_srt, to_hhmmssms_time

class DifferentialChecker:
    def update(self):
        pass
    def halt(self):
        self.halted=True
        print("Halted!")
        traceback.print_exc()
        
    def printExt(self,text):
        pass
    def print(self,text,**kwargs):
        self.printExt(text)
        print(text,**kwargs)
        
    def __init__(self,videoFile:str,sections:list[Section],config:CutterConfig):
        self.videoFile=videoFile
        self.cap = cv2.VideoCapture(videoFile)
        self.lastFrameImage:npt.NDArray
        self.finished=False
        self.halted=False
        self.config=config
        self.sections=sections
        self.startIndex:int=0
        self.endIndex:int=sections.__len__()-1
        
        self.offset:float=0
        
        self.currentIndex:int=0
        self.lastTime:float=0.0
        self.lastIndex:int=0
        self.estimatedFps:float=0.0
        self.estimatedTime:float=float("inf")
        self.thresold=0.2
        
        self.differed_frames:list[int]=[]
        
        info=pymediainfo.MediaInfo.parse(self.videoFile).video_tracks[0] # type: ignore
        data=info.to_data()
        # print(data)
        if(data['frame_rate_mode']!='CFR'):
            print("Variable frame rate is not supported! Please convert it to Constant frame rate at first! \n不支持可变帧速率的视频,请先转码成固定帧速率")
            return
        self.fps=float(data['frame_rate'])
        self.totalFrames=int(data['frame_count'])

        
    def process(self):
        while (not self.finished and not self.halted and self.currentIndex<self.sections.__len__() and self.cap.isOpened()):
            sectionStartTime=(self.sections[self.currentIndex].start/1000)+self.offset
            sectionStartFrameIndex=round(sectionStartTime*self.fps)
            
            # print(f"{self.fps},time={sectionStartTime},frames={sectionStartFrameIndex}")
            self.seekToFrame(sectionStartFrameIndex)
            ret, frame = self.cap.read()
            if(not ret):
                self.finished=True
                self.estimate()
                self.update()
                continue
            frame=self.config.crop(frame)
            frame=cv2.resize(frame, (320,180), fx = 0, fy = 0,
                            interpolation = cv2.INTER_LINEAR)
            
            if(self.currentIndex==0):
                self.lastFrameImage=frame
            else:
                difference=self.compareFrames(frame1=frame,frame2=self.lastFrameImage)
                # print(f"difference={difference}")
                if(difference>self.thresold):
                    self.lastFrameImage=frame
                    self.differed_frames.append(sectionStartFrameIndex)
                    self.print(f"Differ {self.differed_frames.__len__()} found at {to_hhmmssms_time(round(sectionStartFrameIndex*1000/self.fps))}, frameIndex={sectionStartFrameIndex}")
                    
            self.estimate()
            self.update()
            self.currentIndex=self.currentIndex+1
            # print(self.currentIndex)
            
    def compareFrames(self,frame1:npt.NDArray,frame2:npt.NDArray):
        gray_image1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray_image2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        thresold1=150
        thresold2=200
        
        edges1 = cv2.Canny(gray_image1,thresold1,thresold2)
        edges2 = cv2.Canny(gray_image2,thresold1,thresold2)
        
        difference = cv2.absdiff(edges1, edges2)
        
        # ret2,difference = cv2.threshold(difference,100 ,255, cv2.THRESH_BINARY)
        if(self.config.SHOW):
            cv2.imshow('Edges1',edges1)
            cv2.imshow('Edges2',edges2)
            cv2.imshow('Frame1',frame1)
            cv2.imshow('Frame2',frame2)
            cv2.imshow('Difference',difference)
            cv2.waitKey(1)
        
        similarity_score = difference.mean()/255

        return similarity_score
                
        
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
    
if __name__ == "__main__":
    with open(sys.argv[1]+".srt") as f:
        sections=parse_srt(f.readlines())
    config=CutterConfig()
    config.SHOW=True
    checker=DifferentialChecker(sys.argv[1],sections,config)
    checker.process()