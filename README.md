## Blackscreen Cutter

可以帮助剪辑某些游戏的视频的工具.  
本工具根据视频中的黑屏部分进行分段, 并生成带分段编号的字幕. 保存的字幕文件可以导入剪辑软件用于参考.  
用法: `cut.py [视频文件]`  
生成的字幕文件会生成在视频的位置, 并加上`.srt`扩展名.  

需要依赖:`opencv`,`pymediainfo`,`numpy`  


A tool to help cutting videos of some video games.  
This tool generates sections from black screens in a video, then saves the sections to a subtitle file. The saved subtitle file can be imported to a video editor as reference.  
Usage: `cut.py [VIDEO FILE]`  
The subtitle will be generated in where the video is at, with a `.srt` extension.  

Requirements:`opencv`,`pymediainfo`,`numpy`  