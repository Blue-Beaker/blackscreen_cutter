    #用法: cut.py [视频文件]

import cv2,pymediainfo
import traceback
import time
import numpy as np
from threading import Thread

from utils import CutterConfig,get_timestamp

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
