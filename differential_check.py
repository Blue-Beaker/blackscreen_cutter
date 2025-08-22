
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
        
        
        self.currentIndex:int=0
        self.lastTime:float=0.0
        self.lastIndex:int=0
        self.estimatedFps:float=0.0
        self.estimatedTime:float=float("inf")
        
        self.thresold=self.config.diffThresold
        self.offset:float=self.config.timeOffset
        
        self.outputSections:list[Section]=[]
        
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
            section=self.sections[self.currentIndex]
            sectionStartTime=(section.start/1000)+self.offset
            frameToCompareIndex=round(sectionStartTime*self.fps)
            
            # print(f"{self.fps},time={sectionStartTime},frames={sectionStartFrameIndex}")
            self.seekToFrame(frameToCompareIndex)
            
            frameFound=False
            
            frame:npt.NDArray
            # while not frameFound:
            ret, frame = self.cap.read()
            if(not ret):
                self.finished=True
                self.estimate()
                self.update()
                continue
        
            frame=self.config.crop(frame)
            frame=cv2.resize(frame, (320,180), fx = 0, fy = 0,
                            interpolation = cv2.INTER_LINEAR)
            #     if(self.checkDarkFrame(frame)>25):
            #         frameFound=True
            #         continue
            #     frameToCompareIndex=frameToCompareIndex+1
            
            if(self.currentIndex!=0):
                difference=self.compareFrames(frame1=frame,frame2=self.lastFrameImage)
                # print(f"difference={difference}")
                if(difference>self.thresold):
                    self.lastFrameImage=frame
                    lastSection=self.sections[self.currentIndex-1]
                    self.outputSections.append(Section(lastSection.start,lastSection.end,f"#{self.currentIndex-1},diff={difference:.4f}"))
                    
                    self.print(f"difference={difference}")
                    self.print(f"Differ {self.outputSections.__len__()} found at {to_hhmmssms_time(round(frameToCompareIndex*1000/self.fps))}, frameIndex={frameToCompareIndex}")
            
            self.lastFrameImage=frame
            self.estimate()
            self.update()
            self.currentIndex=self.currentIndex+1
            # print(self.currentIndex)
        if not self.halted:
            self.write_subtitle()
        self.finished=True
        self.update()
        
    def checkDarkFrame(self,frame:npt.NDArray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret2,Thresh = cv2.threshold(gray,self.config.COLOR_THRESOLD ,255, cv2.THRESH_BINARY)
        mean=Thresh.mean()
        return mean
    
    def compareFrames(self,frame1:npt.NDArray,frame2:npt.NDArray):
        gray_image1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray_image2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        
        difference_raw = cv2.absdiff(gray_image1, gray_image2)
        
        # color=cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        # color[:,:]=self.config.diffSubtract
        
        # difference = cv2.subtract(difference_raw,color)
        
        difference:np.ndarray
        ret2,difference = cv2.threshold(difference_raw,self.config.diffSubtract ,255, cv2.THRESH_BINARY)
        
        difference=cv2.multiply(difference,difference_raw,scale=1/256)
        
        if(self.config.SHOW):
            frames=np.vstack([frame1,frame2])
            shown_diff=cv2.cvtColor(np.vstack([difference_raw,difference]),cv2.COLOR_GRAY2BGR)
            
            cv2.imshow('Frames',np.hstack([frames,shown_diff]))
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
        
    def write_subtitle(self):
        subtitleId=0
        lines:list[str]=[]
        for section in self.outputSections:
            lines.extend(section.makeLines(subtitleId))
            subtitleId=subtitleId+1
        outputFile=self.videoFile+"_diff.srt"
        with open(outputFile,"w") as f:
            f.write("\n".join(lines))
        
        
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