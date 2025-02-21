#! /bin/python3 

#Usage: cut.py [VIDEO FILE]
#用法: cut.py [视频文件]

import math
import os,sys,cv2,pymediainfo
import numpy as np

os.chdir(sys.path[0])

SHOW=False #是否要在处理时显示帧. 会变慢!
#Whether to show image when processing. Slows down!

COLOR_THRESOLD=10 #颜色判定阈值. 0~255,0=黑,255=白
#Thresold to determine black color. 0~255, black = 0, white = 255

PERCENTAGE_1=99 #黑色占所选区域百分比大于此值判定开始黑屏
PERCENTAGE_2=98 #黑色占所选区域百分比小于此值判定结束黑屏

# 在此设置需要判定黑屏的范围
x1=0
x2=1600
y1=0
y2=900

def crop(frame:np.ndarray):
    return frame[y1:y2,x1:x2]
    # return frame # 或无需裁剪


thr1=255-(PERCENTAGE_1*255/100)
thr2=255-(PERCENTAGE_2*255/100)

class VideoCutter:
    def process(self):
        while ((not self.finished) and self.cap.isOpened()):
            # 由于已经二值化,此平均值反映的是非黑色部分占总画面的比例. 
            mean=self.process_frame()

            if(self.last_frame_black):
                if mean>thr2: # 黑屏结束判定
                    self.last_frame_black=False
                    self.start_subtitle()
            else:
                if mean<thr1: # 黑屏开始判定
                    self.last_frame_black=True
                    self.end_subtitle()

            self.frameIndex=self.frameIndex+1

            print("\r"+f"frames={self.frameIndex} mean={mean}",end="")

    def start_subtitle(self):
        self.last_subtitle_start_frame=self.frameIndex

    def get_timestamp_by_frame(self,frame:int):
        return self.get_timestamp(frame/self.fps)

    def get_timestamp(self,time:float):
        return f"{'{:02d}'.format(math.floor(time/3600))}:{'{:02d}'.format(math.floor(time/60)%60)}:{'{:02d}'.format(math.floor(time)%60)},{'{:03d}'.format(math.floor(time*1000)%1000)}"
    
    def end_subtitle(self):
        lines="\n".join([
            str(self.subtitle_line_id),
            f"{self.get_timestamp_by_frame(self.last_subtitle_start_frame)} --> {self.get_timestamp_by_frame(self.frameIndex)}",
            f"#{self.subtitle_line_id}",
            "\n"
        ])
        self.subtitle_file.write(lines)
        self.subtitle_file.flush()
        print(lines,end=None)
        self.subtitle_line_id=self.subtitle_line_id+1

    def process_frame(self) -> float:
        # Loop until the end of the video
        # Capture frame-by-frame
        ret, frame = self.cap.read()

        if(not ret):
            self.finished=True
            return 255.0
        
        frame=crop(frame)
        
        frame = cv2.resize(frame, (320,180), fx = 0, fy = 0,
                            interpolation = cv2.INTER_LINEAR)

        if SHOW:
            cv2.imshow('Frame', frame)

        # # conversion of BGR to grayscale is necessary to apply this operation
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        Thresh:np.ndarray
        ret2,Thresh = cv2.threshold(gray,COLOR_THRESOLD ,255, cv2.THRESH_BINARY)
        
        mean=Thresh.mean()

        if SHOW:
            cv2.imshow('Thresh', Thresh)
        return mean


    def __init__(self,videoname):

        self.subtitle_file=open(videoname+".srt","w")
        self.subtitle_line_id:int=1
        self.last_subtitle_start_frame:int=0
        self.finished=False

        info=pymediainfo.MediaInfo.parse(videoname).video_tracks[0] # type: ignore
        data=info.to_data()
        if(data['frame_rate_mode']!='CFR'):
            print("Variable frame rate is not supported!")
            return
        self.fps=float(data['frame_rate'])

        self.frameIndex=0
        self.cap = cv2.VideoCapture(videoname)
        self.last_frame_black=False

    def close(self):
        self.subtitle_file.close()
        # release the video capture object
        self.cap.release()
        # Closes all the windows currently opened.
        cv2.destroyAllWindows()

if(sys.argv.__len__()<2):
    print("Usage: cut.py [VIDEO FILE]")
    exit()
try:
    print(f"Thresold: {thr1,thr2}")
    cutter = VideoCutter(sys.argv[1])
    cutter.process()
finally:
    cutter.close()

# for file in os.listdir(INPUT):
    # file_path=os.path.join(INPUT,file)
    # read_video(file_path)